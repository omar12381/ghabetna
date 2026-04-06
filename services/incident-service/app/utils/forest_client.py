"""
Client HTTP interne vers user-forest-service.
Utilisé par incident-service pour résoudre la parcelle à partir du GPS.
"""
import httpx
from fastapi import HTTPException

from ..config import settings


async def get_parcelle_at(lat: float, lng: float) -> dict:
    """
    Appelle GET /geo/parcelle-at sur user-forest-service.

    Retourne :
        { parcelle_id, forest_id, dir_secondaire_id, gps_match_type }

    Lève :
        HTTPException 422  — position hors zone surveillée (404 upstream)
        HTTPException 503  — service indisponible (timeout / connexion échouée)
    """
    url = f"{settings.FOREST_SERVICE_URL}/geo/parcelle-at"
    headers = {"X-Internal-Key": settings.INTERNAL_API_KEY}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, params={"lat": lat, "lng": lng}, headers=headers)
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Service de géolocalisation indisponible",
        ) from exc

    if response.status_code == 404:
        raise HTTPException(
            status_code=422,
            detail="Position hors zone surveillée",
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=503,
            detail=f"Erreur user-forest-service : {response.status_code}",
        )

    return response.json()
