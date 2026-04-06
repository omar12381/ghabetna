from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..utils.jwt_guard import TokenPayload, require_roles, verify_service_secret


router = APIRouter()
# Hash le mot de passe
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# Hash le mot de passe
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


# Crée un utilisateur ; retourne UserRead (201) ou 400 si email/username déjà utilisé
@router.post("/", response_model=schemas.UserRead, status_code=status.HTTP_201_CREATED)
def create_user(user_in: schemas.UserCreate, db: Session = Depends(get_db), _: TokenPayload = Depends(require_roles("admin"))):
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
@router.get("/by-email/{email}", response_model=schemas.UserAuthRead, include_in_schema=False)
def get_user_by_email(
    email: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_service_secret),
):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User non trouvé")
    return schemas.UserAuthRead(
        id=user.id,
        email=user.email,
        hashed_password=user.hashed_password,
        role=user.role.name,
        actif=user.actif,
        direction_secondaire_id=user.direction_secondaire_id,
        direction_regionale_id=user.direction_regionale_id,
    )


# Endpoint interne service-to-service — lecture user par id (incident-service)
@router.get("/{user_id}/internal", response_model=schemas.UserRead, include_in_schema=False)
def get_user_internal(
    user_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_service_secret),
):
    user = db.query(models.User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User non trouvé")
    return user


# Endpoint interne service-to-service — mise à jour direction (incident-service)
@router.patch("/{user_id}/internal", status_code=status.HTTP_204_NO_CONTENT, include_in_schema=False)
def patch_user_direction_secondaire(
    user_id: int,
    body: schemas.UserInternalUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_service_secret),
):
    user = db.query(models.User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User non trouvé")
    user.direction_secondaire_id = body.direction_secondaire_id
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Agents de l'équipe du superviseur + agents libres de sa région
@router.get("/agents/mon-equipe", response_model=List[dict[str, Any]])
def list_agents_mon_equipe(
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(require_roles("superviseur")),
):
    ds_id = current_user.direction_secondaire_id
    dr_id = current_user.direction_regionale_id
    if ds_id is None or dr_id is None:
        raise HTTPException(400, "Votre compte superviseur n'a pas de direction assignée")

    rows = db.execute(text("""
        SELECT u.id, u.username, u.email, u.telephone, u.actif,
               u.direction_secondaire_id, u.direction_regionale_id,
               apa.parcelle_id, p.name AS parcelle_name,
               f.id AS forest_id, f.name AS forest_name
        FROM users u
        JOIN roles r ON r.id = u.role_id AND r.name = 'agent_forestier'
        LEFT JOIN agent_parcelle_assignments apa ON apa.agent_id = u.id AND apa.actif = TRUE
        LEFT JOIN parcelles p ON p.id = apa.parcelle_id
        LEFT JOIN forests f ON f.id = p.forest_id
        WHERE u.direction_secondaire_id = :ds_id
           OR (u.direction_regionale_id = :dr_id AND apa.agent_id IS NULL)
        ORDER BY u.direction_secondaire_id NULLS LAST, u.username
    """), {"ds_id": ds_id, "dr_id": dr_id}).mappings().all()

    result = []
    for row in rows:
        agent_type = "equipe_directe" if row["direction_secondaire_id"] == ds_id else "libre_region"
        result.append({
            "id": row["id"],
            "username": row["username"],
            "email": row["email"],
            "telephone": row["telephone"],
            "actif": row["actif"],
            "direction_secondaire_id": row["direction_secondaire_id"],
            "direction_regionale_id": row["direction_regionale_id"],
            "parcelle_id": row["parcelle_id"],
            "parcelle_name": row["parcelle_name"],
            "forest_id": row["forest_id"],
            "forest_name": row["forest_name"],
            "type": agent_type,
        })
    return result


# Agents libres de la région du superviseur (non encore affectés)
@router.get("/agents/disponibles", response_model=List[dict[str, Any]])
def list_agents_disponibles(
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(require_roles("superviseur")),
):
    agents = list_agents_mon_equipe(db=db, current_user=current_user)
    return [a for a in agents if a["type"] == "libre_region"]


# Liste tous les utilisateurs
@router.get("/", response_model=List[schemas.UserRead])
def list_users(db: Session = Depends(get_db), _: TokenPayload = Depends(require_roles("admin", "superviseur"))):
    return db.query(models.User).all()


# Liste uniquement les superviseurs (role_id=3) — utilisé par AssignSuperviseurScreen
@router.get("/superviseurs", response_model=List[schemas.UserRead])
def list_superviseurs(db: Session = Depends(get_db), _: TokenPayload = Depends(require_roles("admin"))):
    role_superviseur = db.query(models.Role).filter(models.Role.name == "superviseur").first()
    if not role_superviseur:
        return []
    return db.query(models.User).filter(models.User.role_id == role_superviseur.id).all()

# Liste un utilisateur par id
@router.get("/{user_id}", response_model=schemas.UserRead)
def get_user(user_id: int, db: Session = Depends(get_db), _: TokenPayload = Depends(require_roles("admin", "superviseur"))):
    user = db.query(models.User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User non trouvé")
    return user

# Met à jour un utilisateur par id
@router.put("/{user_id}", response_model=schemas.UserRead)
def update_user(user_id: int, user_in: schemas.UserUpdate, db: Session = Depends(get_db), _: TokenPayload = Depends(require_roles("admin"))):
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
def delete_user(user_id: int, db: Session = Depends(get_db), _: TokenPayload = Depends(require_roles("admin"))):
    user = db.query(models.User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User non trouvé")
    # Supprimer l'historique des affectations avant l'utilisateur (FK constraint)
    db.query(models.AgentParcelleAssignment).filter(
        models.AgentParcelleAssignment.agent_id == user_id
    ).delete(synchronize_session=False)
    db.delete(user)
    db.commit()
    return

