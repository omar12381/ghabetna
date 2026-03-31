from typing import List

from fastapi import APIRouter, Depends, Header, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from ..db import get_db, settings
from .. import models, schemas


router = APIRouter()
# Hash le mot de passe
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# Hash le mot de passe
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


# Crée un utilisateur ; retourne UserRead (201) ou 400 si email/username déjà utilisé
@router.post("/", response_model=schemas.UserRead, status_code=status.HTTP_201_CREATED)
def create_user(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == user_in.email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    if db.query(models.User).filter(models.User.username == user_in.username).first():
        raise HTTPException(status_code=400, detail="Username déjà utilisé")

    db_user = models.User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        role_id=user_in.role_id,
        direction_secondaire_id=user_in.direction_secondaire_id,
        direction_regionale_id=user_in.direction_regionale_id,
        telephone=user_in.telephone,
        actif=user_in.actif if user_in.actif is not None else True,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# Endpoint interne service-to-service — utilisé par auth-service uniquement
@router.get("/by-email/{email}", response_model=schemas.UserAuthRead)
def get_user_by_email(
    email: str,
    x_service_secret: str = Header(..., alias="X-Service-Secret"),
    db: Session = Depends(get_db),
):
    if x_service_secret != settings.SERVICE_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid service secret")
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User non trouvé")
    return schemas.UserAuthRead(
        id=user.id,
        hashed_password=user.hashed_password,
        role=user.role.name,
        actif=user.actif,
    )


# Liste tous les utilisateurs
@router.get("/", response_model=List[schemas.UserRead])
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()


# Liste uniquement les superviseurs (role_id=3) — utilisé par AssignSuperviseurScreen
@router.get("/superviseurs", response_model=List[schemas.UserRead])
def list_superviseurs(db: Session = Depends(get_db)):
    role_superviseur = db.query(models.Role).filter(models.Role.name == "superviseur").first()
    if not role_superviseur:
        return []
    return db.query(models.User).filter(models.User.role_id == role_superviseur.id).all()

# Liste un utilisateur par id
@router.get("/{user_id}", response_model=schemas.UserRead)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User non trouvé")
    return user

# Met à jour un utilisateur par id
@router.put("/{user_id}", response_model=schemas.UserRead)
def update_user(user_id: int, user_in: schemas.UserUpdate, db: Session = Depends(get_db)):
    user = db.query(models.User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User non trouvé")

    update_data = user_in.dict(exclude_unset=True)
    if "password" in update_data:
        user.hashed_password = hash_password(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user

# Supprime un utilisateur par id
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User non trouvé")
    db.delete(user)
    db.commit()
    return

