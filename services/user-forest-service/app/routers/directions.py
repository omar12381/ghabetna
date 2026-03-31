from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models, schemas

router_regionales = APIRouter()
router_secondaires = APIRouter()


# ── Directions Régionales ────────────────────────────────────────────────────

@router_regionales.get("/", response_model=List[schemas.DirectionRegionaleRead])
def list_directions_regionales(db: Session = Depends(get_db)):
    return db.query(models.DirectionRegionale).all()


@router_regionales.post("/", response_model=schemas.DirectionRegionaleRead, status_code=status.HTTP_201_CREATED)
def create_direction_regionale(
    direction_in: schemas.DirectionRegionaleCreate,
    db: Session = Depends(get_db),
):
    try:
        db_obj = models.DirectionRegionale(
            nom=direction_in.nom,
            gouvernorat=direction_in.gouvernorat,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}") from e


@router_regionales.put("/{region_id}", response_model=schemas.DirectionRegionaleRead)
def update_direction_regionale(
    region_id: int,
    direction_in: schemas.DirectionRegionaleCreate,
    db: Session = Depends(get_db),
):
    direction = db.query(models.DirectionRegionale).filter(
        models.DirectionRegionale.id == region_id
    ).first()
    if not direction:
        raise HTTPException(status_code=404, detail="Direction régionale non trouvée")
    try:
        direction.nom = direction_in.nom
        direction.gouvernorat = direction_in.gouvernorat
        db.commit()
        db.refresh(direction)
        return direction
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}") from e


@router_regionales.delete("/{region_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_direction_regionale(region_id: int, db: Session = Depends(get_db)):
    direction = db.query(models.DirectionRegionale).filter(
        models.DirectionRegionale.id == region_id
    ).first()
    if not direction:
        raise HTTPException(status_code=404, detail="Direction régionale non trouvée")

    if db.query(models.DirectionSecondaire).filter(
        models.DirectionSecondaire.region_id == region_id
    ).first():
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer : des directions secondaires référencent cette direction régionale",
        )
    if db.query(models.User).filter(
        models.User.direction_regionale_id == region_id
    ).first():
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer : des utilisateurs référencent cette direction régionale",
        )

    try:
        db.delete(direction)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}") from e


# ── Directions Secondaires ───────────────────────────────────────────────────

@router_secondaires.get("/", response_model=List[schemas.DirectionSecondaireRead])
def list_directions_secondaires(db: Session = Depends(get_db)):
    return db.query(models.DirectionSecondaire).all()


@router_secondaires.get("/by-regionale/{regionale_id}", response_model=List[schemas.DirectionSecondaireRead])
def list_directions_secondaires_by_regionale(
    regionale_id: int, db: Session = Depends(get_db)
):
    return db.query(models.DirectionSecondaire).filter(
        models.DirectionSecondaire.region_id == regionale_id
    ).all()


@router_secondaires.post("/", response_model=schemas.DirectionSecondaireRead, status_code=status.HTTP_201_CREATED)
def create_direction_secondaire(
    direction_in: schemas.DirectionSecondaireCreate,
    db: Session = Depends(get_db),
):
    parent = db.query(models.DirectionRegionale).filter(
        models.DirectionRegionale.id == direction_in.region_id
    ).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Direction régionale parente non trouvée")
    try:
        db_obj = models.DirectionSecondaire(
            nom=direction_in.nom,
            region_id=direction_in.region_id,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}") from e


@router_secondaires.put("/{secondaire_id}", response_model=schemas.DirectionSecondaireRead)
def update_direction_secondaire(
    secondaire_id: int,
    direction_in: schemas.DirectionSecondaireCreate,
    db: Session = Depends(get_db),
):
    direction = db.query(models.DirectionSecondaire).filter(
        models.DirectionSecondaire.id == secondaire_id
    ).first()
    if not direction:
        raise HTTPException(status_code=404, detail="Direction secondaire non trouvée")

    parent = db.query(models.DirectionRegionale).filter(
        models.DirectionRegionale.id == direction_in.region_id
    ).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Direction régionale parente non trouvée")

    try:
        direction.nom = direction_in.nom
        direction.region_id = direction_in.region_id
        db.commit()
        db.refresh(direction)
        return direction
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}") from e


@router_secondaires.delete("/{secondaire_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_direction_secondaire(secondaire_id: int, db: Session = Depends(get_db)):
    direction = db.query(models.DirectionSecondaire).filter(
        models.DirectionSecondaire.id == secondaire_id
    ).first()
    if not direction:
        raise HTTPException(status_code=404, detail="Direction secondaire non trouvée")

    if db.query(models.User).filter(
        models.User.direction_secondaire_id == secondaire_id
    ).first():
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer : des utilisateurs référencent cette direction secondaire",
        )

    try:
        db.delete(direction)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}") from e
