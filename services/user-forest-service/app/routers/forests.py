from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db import get_db
from app import models, schemas
from app.geo_utils import geojson_to_geometry, geometry_to_geojson
from app.utils.jwt_guard import TokenPayload, get_current_user, require_roles


router = APIRouter()

# Crée une forêt ; retourne ForestRead (201)
@router.post("/", response_model=schemas.ForestRead, status_code=status.HTTP_201_CREATED)
def create_forest(forest_in: schemas.ForestCreate, db: Session = Depends(get_db), _: TokenPayload = Depends(require_roles("admin", "superviseur"))):
    geom = geojson_to_geometry(forest_in.geometry)

    # Vérifier que la nouvelle forêt ne chevauche pas les forêts existantes
    overlapping_forests = db.query(models.Forest).filter(
        models.Forest.geom.ST_Intersects(geom)
    ).all()

    if overlapping_forests:
        overlapping_names = [f.name for f in overlapping_forests]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La forêt chevauche les forêts existantes : {', '.join(overlapping_names)}"
        )

    db_forest = models.Forest(
        name=forest_in.name,
        description=forest_in.description,
        geom=geom,
        created_by_id=forest_in.created_by_id,
        direction_secondaire_id=forest_in.direction_secondaire_id,
        direction_regionale_id=forest_in.direction_regionale_id,
        surface_ha=forest_in.surface_ha,
        type_foret=forest_in.type_foret,
    )
    db.add(db_forest)
    db.commit()
    db.refresh(db_forest)

    return schemas.ForestRead(
        id=db_forest.id,
        name=db_forest.name,
        description=db_forest.description,
        geometry=geometry_to_geojson(db_forest.geom),
        direction_secondaire_id=db_forest.direction_secondaire_id,
        direction_regionale_id=db_forest.direction_regionale_id,
        surface_ha=db_forest.surface_ha,
        type_foret=db_forest.type_foret,
    )

# Liste toutes les forêts (pagination + payload option via limit)
@router.get("/", response_model=List[schemas.ForestRead])
def list_forests(skip: int = 0, limit: int = 1000, db: Session = Depends(get_db), _: TokenPayload = Depends(get_current_user)):
    forests = db.query(models.Forest).offset(skip).limit(limit).all()
    return [
        schemas.ForestRead(
            id=f.id,
            name=f.name,
            description=f.description,
            geometry=geometry_to_geojson(f.geom),
            direction_secondaire_id=f.direction_secondaire_id,
            direction_regionale_id=f.direction_regionale_id,
            surface_ha=f.surface_ha,
            type_foret=f.type_foret,
        )
        for f in forests
    ]


@router.get("/summary", response_model=List[schemas.ForestSummaryRead])
def list_forests_summary(
    skip: int = 0,
    limit: int = 1000,
    db: Session = Depends(get_db),
    _: TokenPayload = Depends(get_current_user),
):
    """
    Light payload for list views (no GeoJSON geometry).
    Useful when the frontend only needs name/description.
    """
    forests = db.query(models.Forest).offset(skip).limit(limit).all()
    return [
        schemas.ForestSummaryRead(
            id=f.id,
            name=f.name,
            description=f.description,
            direction_secondaire_id=f.direction_secondaire_id,
            surface_ha=f.surface_ha,
            type_foret=f.type_foret,
        )
        for f in forests
    ]

# Obtenir une forêt par id
@router.get("/{forest_id}", response_model=schemas.ForestRead)
def get_forest(forest_id: int, db: Session = Depends(get_db), _: TokenPayload = Depends(get_current_user)):
    forest = db.query(models.Forest).get(forest_id)
    if not forest:
        raise HTTPException(status_code=404, detail="Forêt non trouvée")
    return schemas.ForestRead(
        id=forest.id,
        name=forest.name,
        description=forest.description,
        geometry=geometry_to_geojson(forest.geom),
        direction_secondaire_id=forest.direction_secondaire_id,
        direction_regionale_id=forest.direction_regionale_id,
        surface_ha=forest.surface_ha,
        type_foret=forest.type_foret,
    )

# Met à jour une forêt par id (partiel)
@router.put("/{forest_id}", response_model=schemas.ForestRead)
def update_forest(forest_id: int, forest_in: schemas.ForestUpdate, db: Session = Depends(get_db), _: TokenPayload = Depends(require_roles("admin", "superviseur"))):
    forest = db.query(models.Forest).get(forest_id)
    if not forest:
        raise HTTPException(status_code=404, detail="Forêt non trouvée")

    data = forest_in.dict(exclude_unset=True)
    if "geometry" in data:
        new_geojson = data.get("geometry")
        if new_geojson is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La géométrie de la forêt ne peut pas être nulle",
            )

        geom = geojson_to_geometry(new_geojson)

        # Re-check "no intersection" against other forests (same semantic as create).
        overlapping_forests = db.query(models.Forest).filter(
            models.Forest.id != forest_id,
            models.Forest.geom.ST_Intersects(geom),
        ).all()

        if overlapping_forests:
            overlapping_names = [f.name for f in overlapping_forests]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La forêt chevauche les forêts existantes : {', '.join(overlapping_names)}",
            )

        forest.geom = geom
        data.pop("geometry", None)

    for field, value in data.items():
        setattr(forest, field, value)

    db.commit()
    db.refresh(forest)
    return schemas.ForestRead(
        id=forest.id,
        name=forest.name,
        description=forest.description,
        geometry=geometry_to_geojson(forest.geom),
        direction_secondaire_id=forest.direction_secondaire_id,
        direction_regionale_id=forest.direction_regionale_id,
        surface_ha=forest.surface_ha,
        type_foret=forest.type_foret,
    )

# Supprime une forêt par id
@router.delete("/{forest_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_forest(forest_id: int, db: Session = Depends(get_db), _: TokenPayload = Depends(require_roles("admin", "superviseur"))):
    forest = db.query(models.Forest).get(forest_id)
    if not forest:
        raise HTTPException(status_code=404, detail="Forêt non trouvée")
    db.delete(forest)
    db.commit()
    return

