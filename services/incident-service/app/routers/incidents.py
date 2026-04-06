import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Incident, IncidentComment, IncidentPhoto, IncidentStatusHistory, IncidentType, Statut
from ..schemas import IncidentListItem, IncidentRead, IncidentStatusUpdate, StatutRead, TypeIncidentRead
from ..utils.forest_client import get_parcelle_at
from ..utils.jwt_guard import CurrentUser, get_current_user, require_roles
from ..utils.redis_client import publish_incident

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/incidents", tags=["Incidents"])

MEDIA_DIR = "/media/incidents"
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_incident_read(inc: Incident) -> IncidentRead:
    return IncidentRead(
        id=inc.id,
        agent_id=inc.agent_id,
        parcelle_id=inc.parcelle_id,
        forest_id=inc.forest_id,
        dir_secondaire_id=inc.dir_secondaire_id,
        latitude=inc.latitude,
        longitude=inc.longitude,
        gps_match_type=inc.gps_match_type,
        incident_type_id=inc.incident_type_id,
        statut_id=inc.statut_id,
        description=inc.description,
        note_superviseur=inc.note_superviseur,
        commentaire_superviseur=inc.commentaire_superviseur,
        updated_by=inc.updated_by,
        deleted_at=inc.deleted_at,
        created_at=inc.created_at,
        updated_at=inc.updated_at,
        type_label=inc.type.label,
        priorite_code=inc.type.priorite.code,
        statut_code=inc.statut.code,
        statut_couleur=inc.statut.couleur,
        photo_urls=[p.photo_url for p in inc.photos],
        comments=[c for c in inc.comments],
        history=[h for h in inc.history],
    )


def _build_list_item(inc: Incident) -> IncidentListItem:
    return IncidentListItem(
        id=inc.id,
        agent_id=inc.agent_id,
        parcelle_id=inc.parcelle_id,
        forest_id=inc.forest_id,
        dir_secondaire_id=inc.dir_secondaire_id,
        latitude=inc.latitude,
        longitude=inc.longitude,
        gps_match_type=inc.gps_match_type,
        description=inc.description,
        deleted_at=inc.deleted_at,
        created_at=inc.created_at,
        type_label=inc.type.label,
        priorite_code=inc.type.priorite.code,
        statut_code=inc.statut.code,
        statut_couleur=inc.statut.couleur,
        photo_urls=[p.photo_url for p in inc.photos],
    )


# ── Référence ─────────────────────────────────────────────────────────────────

@router.get("/types", response_model=list[TypeIncidentRead])
def list_types(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    rows = db.query(IncidentType).join(IncidentType.priorite).order_by(IncidentType.id).all()
    return [
        TypeIncidentRead(
            code=t.code,
            label=t.label,
            priorite_code=t.priorite.code,
            priorite_label=t.priorite.label,
            declenche_telegram=t.priorite.declenche_telegram,
        )
        for t in rows
    ]


@router.get("/statuts", response_model=list[StatutRead])
def list_statuts(
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
):
    return db.query(Statut).order_by(Statut.id).all()


# ── Création ──────────────────────────────────────────────────────────────────

@router.post("/", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
async def create_incident(
    incident_type_code: str      = Form(...),
    description:        str | None = Form(None),
    latitude:           float    = Form(...),
    longitude:          float    = Form(...),
    photo:              UploadFile = ...,
    db:                 Session  = Depends(get_db),
    current_user:       CurrentUser = Depends(require_roles("agent_forestier")),
):
    # ── 1. Valider type de fichier ──────────────────────────────────────────
    if photo.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail="Type de fichier non supporté. Acceptés : jpg, jpeg, png, webp",
        )

    # ── 2. Valider taille fichier ───────────────────────────────────────────
    contents = await photo.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=422, detail="Fichier trop grand (max 10 MB)")

    # ── 3. Valider incident_type_code ───────────────────────────────────────
    inc_type = (
        db.query(IncidentType)
        .join(IncidentType.priorite)
        .filter(IncidentType.code == incident_type_code)
        .first()
    )
    if inc_type is None:
        raise HTTPException(status_code=422, detail=f"Type d'incident inconnu : {incident_type_code}")

    # ── 4. Résoudre la parcelle via GPS ─────────────────────────────────────
    geo = await get_parcelle_at(latitude, longitude)

    # ── 5. Résoudre statut initial (en_attente) ──────────────────────────────
    statut = db.query(Statut).filter(Statut.code == "en_attente").first()
    if statut is None:
        raise HTTPException(status_code=500, detail="Statut 'en_attente' introuvable en DB")

    # ── 6. Sauvegarder la photo ─────────────────────────────────────────────
    ext = Path(photo.filename or "photo.jpg").suffix.lower() or ".jpg"
    filename = uuid4().hex + ext
    filepath = os.path.join(MEDIA_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(contents)
    photo_url = f"/media/incidents/{filename}"

    # ── 7. Transaction atomique ─────────────────────────────────────────────
    incident = Incident(
        agent_id=current_user.id,
        parcelle_id=geo["parcelle_id"],
        forest_id=geo["forest_id"],
        dir_secondaire_id=geo["dir_secondaire_id"],
        latitude=latitude,
        longitude=longitude,
        gps_match_type=geo["gps_match_type"],
        incident_type_id=inc_type.id,
        statut_id=statut.id,
        description=description,
    )
    db.add(incident)
    db.flush()  # obtenir incident.id sans commit

    db.add(IncidentPhoto(incident_id=incident.id, photo_url=photo_url))
    db.add(IncidentStatusHistory(
        incident_id=incident.id,
        old_statut_id=None,
        new_statut_id=statut.id,
        changed_by=current_user.id,
    ))

    db.commit()
    db.refresh(incident)

    # ── 8. PUBLISH Redis (non-bloquant) ──────────────────────────────────────
    publish_incident({
        "incident_id":        incident.id,
        "agent_id":           incident.agent_id,
        "forest_id":          incident.forest_id,
        "dir_secondaire_id":  incident.dir_secondaire_id,
        "priorite_code":      inc_type.priorite.code,
        "declenche_telegram": inc_type.priorite.declenche_telegram,
        "type_code":          inc_type.code,
        "type_label":         inc_type.label,
        "latitude":           latitude,
        "longitude":          longitude,
    })

    return _build_incident_read(incident)


# ── Liste avec RBAC ───────────────────────────────────────────────────────────

@router.get("/", response_model=list[IncidentListItem])
def list_incidents(
    forest_id:     Optional[int]      = Query(None),
    statut_code:   Optional[str]      = Query(None),
    type_code:     Optional[str]      = Query(None),
    priorite_code: Optional[str]      = Query(None),
    date_debut:    Optional[datetime] = Query(None),
    date_fin:      Optional[datetime] = Query(None),
    skip:          int                = Query(0,  ge=0),
    limit:         int                = Query(50, ge=1, le=200),
    db:            Session            = Depends(get_db),
    current_user:  CurrentUser        = Depends(get_current_user),
):
    from ..models import Priorite  # évite import circulaire au module level

    q = (
        db.query(Incident)
        .join(Incident.type)
        .join(IncidentType.priorite)
        .join(Incident.statut)
        .filter(Incident.deleted_at.is_(None))
    )

    # ── RBAC ──────────────────────────────────────────────────────────────────
    if current_user.role == "agent_forestier":
        q = q.filter(Incident.agent_id == current_user.id)
    elif current_user.role == "superviseur":
        if current_user.direction_secondaire_id is None:
            raise HTTPException(403, "Superviseur sans direction_secondaire_id dans le token")
        q = q.filter(Incident.dir_secondaire_id == current_user.direction_secondaire_id)
    # admin : aucun filtre forcé

    # ── Filtres optionnels ────────────────────────────────────────────────────
    if forest_id is not None:
        q = q.filter(Incident.forest_id == forest_id)
    if statut_code is not None:
        q = q.filter(Statut.code == statut_code)
    if type_code is not None:
        q = q.filter(IncidentType.code == type_code)
    if priorite_code is not None:
        q = q.filter(Incident.type.has(IncidentType.priorite.has(code=priorite_code)))
    if date_debut is not None:
        q = q.filter(Incident.created_at >= date_debut)
    if date_fin is not None:
        q = q.filter(Incident.created_at <= date_fin)

    rows = q.order_by(Incident.created_at.desc()).offset(skip).limit(limit).all()
    return [_build_list_item(inc) for inc in rows]
