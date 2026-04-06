from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ── Référence ─────────────────────────────────────────────────────────────────

class TypeIncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code:               str
    label:              str
    priorite_code:      str
    priorite_label:     str
    declenche_telegram: bool


class StatutRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code:    str
    label:   str
    couleur: str


# ── Création d'incident ───────────────────────────────────────────────────────

class IncidentCreate(BaseModel):
    """
    Champs JSON du multipart/form-data.
    lat / lng sont déclarés comme Form séparés dans le router (pas dans ce schéma).
    """
    incident_type_code: str
    description:        Optional[str] = None


# ── Lecture détaillée ─────────────────────────────────────────────────────────

class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:          int
    author_id:   int
    author_role: str
    content:     str
    created_at:  datetime


class HistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:            int
    old_statut_id: Optional[int]
    new_statut_id: int
    changed_by:    int
    changed_at:    datetime
    commentaire:   Optional[str]


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                      int
    agent_id:                int
    parcelle_id:             int
    forest_id:               int
    dir_secondaire_id:       int
    latitude:                float
    longitude:               float
    gps_match_type:          str
    incident_type_id:        int
    statut_id:               int
    description:             Optional[str]
    note_superviseur:        Optional[int]
    commentaire_superviseur: Optional[str]
    updated_by:              Optional[int]
    deleted_at:              Optional[datetime]
    created_at:              datetime
    updated_at:              datetime

    # Champs dénormalisés (peuplés manuellement dans le router)
    type_label:     str
    priorite_code:  str
    statut_code:    str
    statut_couleur: str
    photo_urls:     list[str]
    comments:       list[CommentRead]
    history:        list[HistoryRead]


# ── Liste allégée ─────────────────────────────────────────────────────────────

class IncidentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                int
    agent_id:          int
    parcelle_id:       int
    forest_id:         int
    dir_secondaire_id: int
    latitude:          float
    longitude:         float
    gps_match_type:    str
    description:       Optional[str]
    deleted_at:        Optional[datetime]
    created_at:        datetime

    # Champs dénormalisés
    type_label:     str
    priorite_code:  str
    statut_code:    str
    statut_couleur: str
    photo_urls:     list[str]


# ── Mise à jour de statut ─────────────────────────────────────────────────────

class IncidentStatusUpdate(BaseModel):
    statut_code:             str
    note_superviseur:        Optional[int] = None   # 1–5
    commentaire:             Optional[str] = None
