"""
Seed des données de référence au démarrage.
Idempotent : ON CONFLICT (code) DO NOTHING — aucun doublon même après plusieurs démarrages.
"""
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ── Données de référence ──────────────────────────────────────────────────────

_PRIORITES = [
    {"code": "CRITIQUE", "label": "Critique", "declenche_telegram": True},
    {"code": "HAUTE",    "label": "Haute",    "declenche_telegram": False},
    {"code": "NORMALE",  "label": "Normale",  "declenche_telegram": False},
]

# priorite_id référence l'ordre d'insertion ci-dessus :
#   CRITIQUE = 1, HAUTE = 2, NORMALE = 3
_INCIDENT_TYPES = [
    {"code": "feu",              "label": "Incendie",           "priorite_code": "CRITIQUE"},
    {"code": "refuge_suspect",   "label": "Refuge suspect",     "priorite_code": "CRITIQUE"},
    {"code": "terrorisme",       "label": "Terrorisme",         "priorite_code": "CRITIQUE"},
    {"code": "trafic",           "label": "Trafic",             "priorite_code": "CRITIQUE"},
    {"code": "contrebande",      "label": "Contrebande",        "priorite_code": "CRITIQUE"},
    {"code": "coupe_illegale",   "label": "Coupe illégale",     "priorite_code": "HAUTE"},
    {"code": "depot_dechets",    "label": "Dépôt de déchets",   "priorite_code": "NORMALE"},
    {"code": "maladie_vegetale", "label": "Maladie végétale",   "priorite_code": "NORMALE"},
]

_STATUTS = [
    {"code": "en_attente", "label": "En attente", "couleur": "#E53935"},
    {"code": "en_cours",   "label": "En cours",   "couleur": "#FB8C00"},
    {"code": "traite",     "label": "Traité",     "couleur": "#43A047"},
    {"code": "rejete",     "label": "Rejeté",     "couleur": "#757575"},
]


# ── Fonction principale ───────────────────────────────────────────────────────

def run_seed(db: Session) -> None:
    """
    Insère les données de référence si elles n'existent pas encore.
    Idempotent — safe à appeler à chaque démarrage.
    """
    _seed_priorites(db)
    _seed_incident_types(db)
    _seed_statuts(db)
    logger.info("Seed incident_db terminé.")


# ── Helpers privés ────────────────────────────────────────────────────────────

def _seed_priorites(db: Session) -> None:
    for p in _PRIORITES:
        db.execute(
            text("""
                INSERT INTO priorites (code, label, declenche_telegram)
                VALUES (:code, :label, :declenche_telegram)
                ON CONFLICT (code) DO NOTHING
            """),
            p,
        )
    db.commit()


def _seed_incident_types(db: Session) -> None:
    for t in _INCIDENT_TYPES:
        db.execute(
            text("""
                INSERT INTO incident_types (code, label, priorite_id)
                VALUES (
                    :code,
                    :label,
                    (SELECT id FROM priorites WHERE code = :priorite_code)
                )
                ON CONFLICT (code) DO NOTHING
            """),
            t,
        )
    db.commit()


def _seed_statuts(db: Session) -> None:
    for s in _STATUTS:
        db.execute(
            text("""
                INSERT INTO statuts (code, label, couleur)
                VALUES (:code, :label, :couleur)
                ON CONFLICT (code) DO NOTHING
            """),
            s,
        )
    db.commit()
