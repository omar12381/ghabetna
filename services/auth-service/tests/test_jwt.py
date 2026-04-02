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

from app.utils.jwt import create_access_token, create_refresh_token, decode_token, ALGORITHM
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


def test_refresh_token_has_unique_jti():
    import re
    data = {"sub": 7, "role": "superviseur"}
    token1 = create_refresh_token(data)
    token2 = create_refresh_token(data)

    payload1 = jwt.decode(token1, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])
    payload2 = jwt.decode(token2, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])

    # jti must be present
    assert "jti" in payload1
    assert "jti" in payload2

    # jti must look like a UUID4
    uuid4_re = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    )
    assert uuid4_re.match(payload1["jti"]), f"jti not UUID4: {payload1['jti']}"

    # each call produces a different jti
    assert payload1["jti"] != payload2["jti"]

    # type must be "refresh"
    assert payload1["type"] == "refresh"
