from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..utils.jwt_guard import TokenPayload, require_roles

router = APIRouter()

# ── Helper — JOIN enrichi commun ─────────────────────────────────────────────

_JOIN_SQL = """
    SELECT apa.id, apa.agent_id, apa.parcelle_id, apa.assigned_by,
           apa.assigned_at, apa.actif,
           u.username          AS agent_username,
           p.name              AS parcelle_name,
           f.id                AS forest_id,
           f.name              AS forest_name,
           f.direction_secondaire_id AS dir_secondaire_id,
           ds.region_id        AS dir_regionale_id
    FROM agent_parcelle_assignments apa
    JOIN users                u  ON u.id  = apa.agent_id
    JOIN parcelles            p  ON p.id  = apa.parcelle_id
    JOIN forests              f  ON f.id  = p.forest_id
    JOIN direction_secondaire ds ON ds.id = f.direction_secondaire_id
    WHERE {where}
    ORDER BY apa.assigned_at DESC
"""


def _query_one(db: Session, where: str, params: dict) -> Optional[dict]:
    row = db.execute(text(_JOIN_SQL.format(where=where)), params).mappings().first()
    return dict(row) if row else None


def _query_many(db: Session, where: str, params: dict) -> List[dict]:
    rows = db.execute(text(_JOIN_SQL.format(where=where)), params).mappings().all()
    return [dict(r) for r in rows]


# ── NT2.1 — POST /affectations/ ──────────────────────────────────────────────

@router.post("/", response_model=schemas.AssignmentRead, status_code=status.HTTP_201_CREATED)
def create_assignment(
    body: schemas.AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(require_roles("admin")),
):
    # 1. Charger agent
    agent = db.query(models.User).get(body.agent_id)
    if not agent:
        raise HTTPException(404, "Agent introuvable")
    if not agent.actif:
        raise HTTPException(403, "Agent inactif")
    if agent.role.name != "agent_forestier":
        raise HTTPException(403, "L'utilisateur n'est pas un agent forestier")

    # 2. Charger parcelle → forêt → direction_secondaire → region_id
    row = db.execute(text("""
        SELECT p.id, p.name, f.id AS forest_id, f.direction_secondaire_id AS dir_secondaire_id,
               ds.region_id AS dir_regionale_id
        FROM parcelles p
        JOIN forests f ON f.id = p.forest_id
        JOIN direction_secondaire ds ON ds.id = f.direction_secondaire_id
        WHERE p.id = :parcelle_id
    """), {"parcelle_id": body.parcelle_id}).mappings().first()

    if not row:
        raise HTTPException(404, "Parcelle introuvable ou sans direction secondaire associée")

    # 3. Validation géographique
    if agent.direction_regionale_id != row["dir_regionale_id"]:
        raise HTTPException(
            403,
            "Incohérence géographique : agent et parcelle dans des régions différentes",
        )

    # 4. Transaction atomique
    # a. Désactiver ancienne affectation active
    db.execute(text("""
        UPDATE agent_parcelle_assignments
        SET actif = FALSE
        WHERE agent_id = :agent_id AND actif = TRUE
    """), {"agent_id": body.agent_id})

    # b. Insérer nouvelle affectation
    db.execute(text("""
        INSERT INTO agent_parcelle_assignments (agent_id, parcelle_id, assigned_by, actif)
        VALUES (:agent_id, :parcelle_id, :assigned_by, TRUE)
    """), {
        "agent_id": body.agent_id,
        "parcelle_id": body.parcelle_id,
        "assigned_by": current_user.sub,
    })

    # c. Toujours synchroniser direction_secondaire_id de l'agent avec la DS de la parcelle
    db.execute(text("""
        UPDATE users SET direction_secondaire_id = :ds_id WHERE id = :agent_id
    """), {"ds_id": row["dir_secondaire_id"], "agent_id": body.agent_id})

    db.commit()

    # 5. Retourner AssignmentRead enrichi
    result = _query_one(db, "apa.agent_id = :agent_id AND apa.actif = TRUE", {"agent_id": body.agent_id})
    return schemas.AssignmentRead(**result)


# ── NT2.2 — DELETE /affectations/{agent_id} ──────────────────────────────────

@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(
    agent_id: int,
    db: Session = Depends(get_db),
    _: TokenPayload = Depends(require_roles("admin")),
):
    assignment = (
        db.query(models.AgentParcelleAssignment)
        .filter(
            models.AgentParcelleAssignment.agent_id == agent_id,
            models.AgentParcelleAssignment.actif == True,
        )
        .first()
    )
    if not assignment:
        raise HTTPException(404, "Agent non affecté")
    assignment.actif = False
    # Remettre direction_secondaire_id à NULL — agent redevient libre
    db.execute(text("""
        UPDATE users SET direction_secondaire_id = NULL WHERE id = :agent_id
    """), {"agent_id": agent_id})
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── NT2.3 — GET /affectations/ ───────────────────────────────────────────────

@router.get("/", response_model=List[schemas.AssignmentRead])
def list_assignments(
    dir_secondaire_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(require_roles("admin", "superviseur")),
):
    if current_user.role == "superviseur":
        # Superviseur : uniquement sa direction secondaire
        ds_id = current_user.direction_secondaire_id
        if ds_id is None:
            raise HTTPException(400, "Votre compte n'a pas de direction secondaire assignée")
        rows = _query_many(db, "apa.actif = TRUE AND f.direction_secondaire_id = :ds_id", {"ds_id": ds_id})
    elif dir_secondaire_id is not None:
        # Admin avec filtre optionnel
        rows = _query_many(db, "apa.actif = TRUE AND f.direction_secondaire_id = :ds_id", {"ds_id": dir_secondaire_id})
    else:
        # Admin sans filtre → toutes
        rows = _query_many(db, "apa.actif = TRUE", {})

    return [schemas.AssignmentRead(**r) for r in rows]


# ── NT2.4 — GET /affectations/agent/{agent_id} ───────────────────────────────

@router.get("/agent/{agent_id}", response_model=schemas.AssignmentMinimal)
def get_agent_assignment(
    agent_id: int,
    db: Session = Depends(get_db),
    _: TokenPayload = Depends(require_roles("admin", "superviseur")),
):
    row = _query_one(db, "apa.agent_id = :agent_id AND apa.actif = TRUE", {"agent_id": agent_id})
    if not row:
        return schemas.AssignmentMinimal()
    return schemas.AssignmentMinimal(
        parcelle_id=row["parcelle_id"],
        parcelle_name=row["parcelle_name"],
        forest_id=row["forest_id"],
        forest_name=row["forest_name"],
        dir_secondaire_id=row["dir_secondaire_id"],
    )


# ── NT2.5 — GET /affectations/parcelle/{parcelle_id} ─────────────────────────

@router.get("/parcelle/{parcelle_id}", response_model=List[dict[str, Any]])
def get_parcelle_agents(
    parcelle_id: int,
    db: Session = Depends(get_db),
    _: TokenPayload = Depends(require_roles("admin", "superviseur")),
):
    rows = db.execute(text("""
        SELECT u.id, u.username, u.email, u.telephone
        FROM agent_parcelle_assignments apa
        JOIN users u ON u.id = apa.agent_id
        WHERE apa.parcelle_id = :parcelle_id AND apa.actif = TRUE
    """), {"parcelle_id": parcelle_id}).mappings().all()
    return [dict(r) for r in rows]
