"""
JWT utilities pour incident-service.
Équivalent du jwt.py d'auth-service, mais sans dépendance sur les settings
d'auth-service — la clé secrète est passée en paramètre.
"""
from fastapi import HTTPException, status
from jose import ExpiredSignatureError, JWTError, jwt

ALGORITHM = "HS256"


def decode_token(token: str, secret_key: str) -> dict:
    """Décode et valide un JWT. Lève HTTPException 401 si invalide/expiré."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        return payload
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expiré")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")
