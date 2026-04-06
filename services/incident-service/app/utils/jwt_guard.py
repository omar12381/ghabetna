from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from ..config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://localhost:8001/auth/login")


@dataclass
class CurrentUser:
    id: int
    role: str
    direction_secondaire_id: int | None
    direction_regionale_id: int | None


def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
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


def verify_service_secret(x_service_secret: str = Header(alias="X-Service-Secret")) -> None:
    if x_service_secret != settings.SERVICE_SECRET:
        raise HTTPException(403, "Secret inter-service invalide")
