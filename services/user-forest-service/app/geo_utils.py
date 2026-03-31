from typing import Any, Dict, Tuple

from fastapi import HTTPException, status
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import shape, mapping
from shapely.validation import explain_validity


def _coords_close(a: Tuple[float, float], b: Tuple[float, float], eps: float = 1e-12) -> bool:
    """Compares 2D coordinates with a tiny tolerance (floats from JSON)."""
    return abs(a[0] - b[0]) <= eps and abs(a[1] - b[1]) <= eps


def _parse_point_2d(coord: Any, ring_idx: int) -> Tuple[float, float]:
    if not isinstance(coord, (list, tuple)) or len(coord) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Coordonnées invalides (point) sur l'anneau {ring_idx}. Attendu: [lng, lat].",
        )

    try:
        lng = float(coord[0])
        lat = float(coord[1])
        return (lng, lat)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Coordonnées non numériques sur l'anneau {ring_idx}.",
        )


def _extract_and_validate_polygon_geojson(geojson: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accepts:
      - GeoJSON Geometry: {"type":"Polygon","coordinates":[...]}
      - GeoJSON Feature: {"type":"Feature","geometry":{...}}
    Enforces:
      - type Polygon only
      - coordinates ring structure
      - ring closure (first == last coordinate per ring)
    """
    if not isinstance(geojson, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GeoJSON doit être un objet JSON (dictionnaire).",
        )

    if geojson.get("type") == "Feature":
        if "geometry" not in geojson or not isinstance(geojson["geometry"], dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feature GeoJSON invalide: champ 'geometry' manquant ou incorrect.",
            )
        geom_geojson = geojson["geometry"]
    else:
        geom_geojson = geojson

    if geom_geojson.get("type") != "Polygon":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Type de géométrie non supporté: attendu 'Polygon' (reçu: {geom_geojson.get('type')}).",
        )

    coordinates = geom_geojson.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GeoJSON Polygon invalide: champ 'coordinates' manquant ou vide.",
        )

    # GeoJSON Polygon: coordinates = [ exteriorRing, hole1?, hole2? ... ]
    for ring_idx, ring in enumerate(coordinates):
        if not isinstance(ring, list) or len(ring) < 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Anneau {ring_idx} invalide: attendu au moins 4 points (avec fermeture).",
            )

        first = _parse_point_2d(ring[0], ring_idx)
        last = _parse_point_2d(ring[-1], ring_idx)
        if not _coords_close(first, last):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Anneau {ring_idx} non fermé: le premier point {[first[0], first[1]]} "
                    f"doit être identique au dernier point {[last[0], last[1]]}."
                ),
            )

        # Validate each point quickly (type/numeric).
        for point_idx, coord in enumerate(ring):
            _ = _parse_point_2d(coord, ring_idx)
            # Only minimal validation to avoid overhead.

    return geom_geojson


def geojson_to_geometry(geojson: Dict[str, Any], srid: int = 4326):
    """
    Converts GeoJSON Polygon (Geometry or Feature wrapper) to a GeoAlchemy2 Geometry.
    Raises HTTP 400 for invalid/unsupported geometry.
    """
    geom_geojson = _extract_and_validate_polygon_geojson(geojson)

    try:
        shp = shape(geom_geojson)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GeoJSON Polygon invalide: impossible de construire la géométrie.",
        )

    if shp.geom_type != "Polygon":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Géométrie invalide: attendu Polygon (reçu: {shp.geom_type}).",
        )

    if not shp.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Polygon invalide (auto-intersections ou anneau incorrect): {explain_validity(shp)}",
        )

    return from_shape(shp, srid=srid)





# Convertit un geometry en objet geoJSON flow  men postgis hattekchi flutter

def geometry_to_geojson(geom) -> Dict[str, Any]:
    """
    Convertit une colonne Geometry en GeoJSON geometry.
    """
    # Convertit l'objet Geometry(postgis) en objet Shape(python)
    shp = to_shape(geom)
    # Convertit l'objet Shape(python) en objet GeoJSON(flutter)
    return mapping(shp)

