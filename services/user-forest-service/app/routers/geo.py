from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.utils.jwt_guard import TokenPayload, get_current_user

router = APIRouter()


@router.get("/parcelle-at")
def get_parcelle_at(
    lat: float,
    lng: float,
    db: Session = Depends(get_db),
    _: TokenPayload = Depends(get_current_user),
):
    result = db.execute(
        text(
            "SELECT p.id, p.name, p.forest_id "
            "FROM parcelles p "
            "WHERE ST_Contains(p.geom, ST_SetSRID(ST_Point(:lng, :lat), 4326)) "
            "LIMIT 1"
        ),
        {"lat": lat, "lng": lng},
    ).first()

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aucune parcelle à ces coordonnées")

    return {"parcelle_id": result.id, "parcelle_name": result.name, "forest_id": result.forest_id}
