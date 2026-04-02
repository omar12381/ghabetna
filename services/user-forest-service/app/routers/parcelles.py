from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from shapely.geometry import shape

from app.db import get_db
from app import models, schemas
from app.geo_utils import geojson_to_geometry, geometry_to_geojson
from app.utils.jwt_guard import TokenPayload, get_current_user, require_roles


router = APIRouter()


@router.post("/", response_model=schemas.ParcelleRead, status_code=status.HTTP_201_CREATED)
def create_parcelle(parcelle_in: schemas.ParcelleCreate, db: Session = Depends(get_db), _: TokenPayload = Depends(require_roles("admin", "superviseur"))):
    try:
        # Load parent forest
        forest = db.query(models.Forest).get(parcelle_in.forest_id)
        if not forest:
            raise HTTPException(status_code=404, detail="Forêt parente non trouvée")

        # Convert parcelle geometry
        geom = geojson_to_geometry(parcelle_in.geometry)

        # Vérifier que la parcelle est TOTALEMENT à l'intérieur de la forêt parente
        is_within = db.query(models.Forest).filter(
            models.Forest.id == parcelle_in.forest_id,
            models.Forest.geom.ST_Contains(geom)
        ).first()

        if not is_within:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La parcelle doit être totalement à l'intérieur de la forêt parente"
            )

        # Vérifier que la parcelle ne touche pas ET ne chevauche pas les autres parcelles dans la même forêt
        # ST_Disjoint retourne True si les géométries ne se chevauchent pas et ne se touchent pas
        touching_parcelles = db.query(models.Parcelle).filter(
            models.Parcelle.forest_id == parcelle_in.forest_id,
            ~models.Parcelle.geom.ST_Disjoint(geom)  # NOT disjoint = touching or intersecting
        ).all()

        if touching_parcelles:
            touching_names = [p.name for p in touching_parcelles]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La parcelle chevauche ou touche les parcelles existantes : {', '.join(touching_names)}"
            )

        # Calculate surface in hectares
        surface_ha = None
        try:
            # Support both raw geometry and Feature wrapper for frontend compatibility.
            area_geojson = parcelle_in.geometry
            if isinstance(area_geojson, dict) and area_geojson.get("type") == "Feature":
                area_geojson = area_geojson.get("geometry", area_geojson)

            parcelle_shp = shape(area_geojson)
            area_deg = parcelle_shp.area
            surface_ha = area_deg * (111320 * 111320) / 10000
        except ValueError as e:
            print(f"Erreur calcul surface: {e}")
            surface_ha = None

        # Create parcelle
        db_parcelle = models.Parcelle(
            forest_id=parcelle_in.forest_id,
            name=parcelle_in.name,
            description=parcelle_in.description,
            geom=geom,
            surface_ha=surface_ha,
            created_by_id=parcelle_in.created_by_id,
        )
        db.add(db_parcelle)
        db.commit()
        db.refresh(db_parcelle)

        # Return response
        return schemas.ParcelleRead(
            id=db_parcelle.id,
            forest_id=db_parcelle.forest_id,
            name=db_parcelle.name,
            description=db_parcelle.description,
            geometry=geometry_to_geojson(db_parcelle.geom),
            surface_ha=db_parcelle.surface_ha,
            created_by_id=db_parcelle.created_by_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur: {str(e)}"
        ) from e


@router.get("/", response_model=List[schemas.ParcelleRead])
def list_parcelles(skip: int = 0, limit: int = 1000, db: Session = Depends(get_db), _: TokenPayload = Depends(get_current_user)):
    parcelles = db.query(models.Parcelle).offset(skip).limit(limit).all()
    return [
        schemas.ParcelleRead(
            id=p.id,
            forest_id=p.forest_id,
            name=p.name,
            description=p.description,
            geometry=geometry_to_geojson(p.geom),
            surface_ha=p.surface_ha,
            created_by_id=p.created_by_id,
        )
        for p in parcelles
    ]


@router.get("/by_forest/{forest_id}", response_model=List[schemas.ParcelleRead])
def list_parcelles_by_forest(
    forest_id: int,
    skip: int = 0,
    limit: int = 1000,
    db: Session = Depends(get_db),
    _: TokenPayload = Depends(get_current_user),
):
    parcelles = (
        db.query(models.Parcelle)
        .filter(models.Parcelle.forest_id == forest_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        schemas.ParcelleRead(
            id=p.id,
            forest_id=p.forest_id,
            name=p.name,
            description=p.description,
            geometry=geometry_to_geojson(p.geom),
            surface_ha=p.surface_ha,
            created_by_id=p.created_by_id,
        )
        for p in parcelles
    ]


@router.get("/by_forest/{forest_id}/summary", response_model=List[schemas.ParcelleSummaryRead])
def list_parcelles_by_forest_summary(
    forest_id: int,
    skip: int = 0,
    limit: int = 1000,
    db: Session = Depends(get_db),
    _: TokenPayload = Depends(get_current_user),
):
    """Light payload for list views (no GeoJSON geometry)."""
    parcelles = (
        db.query(models.Parcelle)
        .filter(models.Parcelle.forest_id == forest_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        schemas.ParcelleSummaryRead(
            id=p.id,
            forest_id=p.forest_id,
            name=p.name,
            description=p.description,
            surface_ha=p.surface_ha,
            created_by_id=p.created_by_id,
        )
        for p in parcelles
    ]


@router.get("/{parcelle_id}", response_model=schemas.ParcelleRead)
def get_parcelle(parcelle_id: int, db: Session = Depends(get_db), _: TokenPayload = Depends(get_current_user)):
    parcelle = db.query(models.Parcelle).get(parcelle_id)
    if not parcelle:
        raise HTTPException(status_code=404, detail="Parcelle non trouvée")
    return schemas.ParcelleRead(
        id=parcelle.id,
        forest_id=parcelle.forest_id,
        name=parcelle.name,
        description=parcelle.description,
        geometry=geometry_to_geojson(parcelle.geom),
        surface_ha=parcelle.surface_ha,
        created_by_id=parcelle.created_by_id,
    )


@router.put("/{parcelle_id}", response_model=schemas.ParcelleRead)
def update_parcelle(parcelle_id: int, parcelle_in: schemas.ParcelleUpdate, db: Session = Depends(get_db), _: TokenPayload = Depends(require_roles("admin", "superviseur"))):
    parcelle = db.query(models.Parcelle).get(parcelle_id)
    if not parcelle:
        raise HTTPException(status_code=404, detail="Parcelle non trouvée")

    data = parcelle_in.dict(exclude_unset=True)

    if "geometry" in data:
        new_geojson = data.get("geometry")
        if new_geojson is None:
            raise HTTPException(
                status_code=400,
                detail="La géométrie de la parcelle ne peut pas être nulle",
            )

        # Convert geometry once (used for PostGIS checks + persistence).
        geom = geojson_to_geometry(new_geojson)

        # 1) Validate containment in parent forest (same semantic as create).
        is_within = db.query(models.Forest).filter(
            models.Forest.id == parcelle.forest_id,
            models.Forest.geom.ST_Contains(geom),
        ).first()

        if not is_within:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La géométrie de la parcelle doit être totalement à l'intérieur de la forêt parente",
            )

        # 2) Validate non-overlap/non-touch with other parcelles in the same forest.
        touching_parcelles = db.query(models.Parcelle).filter(
            models.Parcelle.forest_id == parcelle.forest_id,
            models.Parcelle.id != parcelle_id,
            ~models.Parcelle.geom.ST_Disjoint(geom),  # NOT disjoint = touching or intersecting
        ).all()

        if touching_parcelles:
            touching_names = [p.name for p in touching_parcelles]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La parcelle chevauche ou touche les parcelles existantes : {', '.join(touching_names)}",
            )

        # Recalculate surface (client-facing value).
        surface_ha = None
        try:
            # Support both GeoJSON geometry and Feature wrapper for safety.
            area_geojson = new_geojson
            if isinstance(area_geojson, dict) and area_geojson.get("type") == "Feature":
                area_geojson = area_geojson.get("geometry", area_geojson)

            parcelle_shp = shape(area_geojson)
            area_deg = parcelle_shp.area
            surface_ha = area_deg * (111320 * 111320) / 10000
        except ValueError:
            # Keep existing None if Shapely cannot compute an area.
            surface_ha = None

        parcelle.surface_ha = surface_ha
        parcelle.geom = geom
        data.pop("geometry", None)

    for field, value in data.items():
        setattr(parcelle, field, value)

    db.commit()
    db.refresh(parcelle)
    return schemas.ParcelleRead(
        id=parcelle.id,
        forest_id=parcelle.forest_id,
        name=parcelle.name,
        description=parcelle.description,
        geometry=geometry_to_geojson(parcelle.geom),
        surface_ha=parcelle.surface_ha,
        created_by_id=parcelle.created_by_id,
    )


@router.delete("/{parcelle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_parcelle(parcelle_id: int, db: Session = Depends(get_db), _: TokenPayload = Depends(require_roles("admin", "superviseur"))):
    parcelle = db.query(models.Parcelle).get(parcelle_id)
    if not parcelle:
        raise HTTPException(status_code=404, detail="Parcelle non trouvée")
    db.delete(parcelle)
    db.commit()
    return