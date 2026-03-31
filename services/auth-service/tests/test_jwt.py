from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from jose import jwt

# Les tests s'exécutent avec JWT_SECRET_KEY défini via env ou valeur de test
import os
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("USER_SERVICE_URL", "http://localhost:8000")
os.environ.setdefault("SERVICE_SECRET", "test-service-secret")

from app.utils.jwt import create_access_token, decode_token, ALGORITHM
from app.config import settings


def test_valid_token():
    data = {"sub": 42, "role": "admin"}
    token = create_access_token(data)
    payload = decode_token(token)

    assert payload["sub"] == 42
    assert payload["role"] == "admin"
    assert payload["type"] == "access"


def test_expired_token():
    payload = {
        "sub": "1",
        "role": "admin",
        "type": "access",
        "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)

    with pytest.raises(HTTPException) as exc_info:
        decode_token(token)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_invalid_token():
    with pytest.raises(HTTPException) as exc_info:
        decode_token("this.is.not.a.valid.token")
    assert exc_info.value.status_code == 401
    assert "invalid" in exc_info.value.detail.lower()
