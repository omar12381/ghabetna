from datetime import datetime

from pydantic import BaseModel


class AssignmentCreate(BaseModel):
    agent_id: int
    parcelle_id: int


class AssignmentRead(BaseModel):
    id: int
    agent_id: int
    parcelle_id: int
    forest_id: int
    dir_secondaire_id: int
    dir_regionale_id: int
    assigned_by: int
    assigned_at: datetime
    actif: bool
    # Données enrichies récupérées depuis user-forest-service
    agent_username: str
    parcelle_name: str
    forest_name: str

    model_config = {"from_attributes": True}


class AssignmentMinimal(BaseModel):
    parcelle_id: int | None = None
    parcelle_name: str | None = None
    forest_id: int | None = None
    forest_name: str | None = None


class AgentIdsResponse(BaseModel):
    agent_ids: list[int]
