from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from ..config import settings
from .jwt_utils import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://localhost:8001/auth/login")


@dataclass
class CurrentUser:
    id: int
    role: str
    direction_secondaire_id: int | None
    direction_regionale_id: int | None


def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    try:
        payload = decode_token(token, settings.SECRET_KEY)
        if payload.get("type") != "access":
            raise HTTPException(401, "Token invalide")
        return CurrentUser(
            id=int(payload["sub"]),
            role=payload["role"],
            direction_secondaire_id=payload.get("direction_secondaire_id"),
            direction_regionale_id=payload.get("direction_regionale_id"),
        )
    except JWTError:
        raise HTTPException(401, "Token invalide ou expiré")


def require_roles(*roles: str):
    def checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(403, f"Accès réservé aux rôles : {', '.join(roles)}")
        return user
    return checker


def verify_internal_key(x_internal_key: str = Header(alias="X-Internal-Key")) -> None:
    """Protège les endpoints inter-services (incident-service → user-forest-service)."""
    if x_internal_key != settings.INTERNAL_API_KEY:
        raise HTTPException(403, "Clé inter-service invalide")
