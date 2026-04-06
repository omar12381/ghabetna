import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db

router = APIRouter()

_INTERNAL_KEY = os.getenv("INTERNAL_API_KEY", "")


def verify_internal_key(request: Request) -> None:
    key = request.headers.get("X-Internal-Key", "")
    if not _INTERNAL_KEY or key != _INTERNAL_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="X-Internal-Key absent ou invalide",
        )


@router.get("/parcelle-at")
def get_parcelle_at(
    lat: float,
    lng: float,
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_key),
):
    # Étape 1 — ST_Contains (exact match)
    row = db.execute(
        text("""
            SELECT p.id          AS parcelle_id,
                   p.forest_id,
                   f.direction_secondaire_id,
                   'exact'       AS gps_match_type
            FROM   parcelles p
            JOIN   forests   f ON f.id = p.forest_id
            WHERE  ST_Contains(p.geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326))
            LIMIT  1
        """),
        {"lat": lat, "lng": lng},
    ).first()

    if row is None:
        # Étape 2 — ST_Distance fallback (parcelle la plus proche)
        row = db.execute(
            text("""
                SELECT p.id          AS parcelle_id,
                       p.forest_id,
                       f.direction_secondaire_id,
                       'nearest'     AS gps_match_type
                FROM   parcelles p
                JOIN   forests   f ON f.id = p.forest_id
                ORDER  BY ST_Distance(p.geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326))
                LIMIT  1
            """),
            {"lat": lat, "lng": lng},
        ).first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune parcelle dans la base de données",
        )

    return {
        "parcelle_id":        row.parcelle_id,
        "forest_id":          row.forest_id,
        "dir_secondaire_id":  row.direction_secondaire_id,
        "gps_match_type":     row.gps_match_type,
    }
