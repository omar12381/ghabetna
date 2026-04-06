# Import dans l'ordre des dépendances FK pour que Base.metadata soit complet
from .priorite import Priorite
from .incident_type import IncidentType
from .statut import Statut
from .incident import Incident
from .photo import IncidentPhoto
from .comment import IncidentComment
from .history import IncidentStatusHistory

__all__ = [
    "Priorite",
    "IncidentType",
    "Statut",
    "Incident",
    "IncidentPhoto",
    "IncidentComment",
    "IncidentStatusHistory",
]
