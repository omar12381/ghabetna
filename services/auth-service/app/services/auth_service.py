import httpx
import redis.asyncio as aioredis
from fastapi import HTTPException, status

from ..config import settings
from ..models import TokenResponse
from ..utils.jwt import create_access_token, create_refresh_token, decode_token
from ..utils.password import verify_password


async def get_user_by_email(email: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.USER_SERVICE_URL}/users/by-email/{email}",
                headers={"X-Service-Secret": settings.SERVICE_SECRET},
            )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User service timeout",
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"User service error: {e.response.status_code}",
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User service unavailable",
        )


async def login(email: str, password: str, redis: aioredis.Redis) -> TokenResponse:
    user = await get_user_by_email(email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.get("actif", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    if user.get("role") not in ["admin", "superviseur"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé aux administrateurs et superviseurs")
    if not verify_password(password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token_data = {
        "sub": user["id"],
        "role": user["role"],
        "direction_secondaire_id": user.get("direction_secondaire_id"),
        "direction_regionale_id": user.get("direction_regionale_id"),
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    payload = decode_token(refresh_token)
    jti = payload["jti"]
    ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    await redis.setex(f"refresh:{jti}", ttl, str(user["id"]))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        role=user["role"],
    )


async def refresh(refresh_token: str, redis: aioredis.Redis) -> dict:
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    jti = payload.get("jti")
    if not jti or not await redis.exists(f"refresh:{jti}"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked or expired")

    await redis.delete(f"refresh:{jti}")

    token_data = {
        "sub": payload["sub"],
        "role": payload["role"],
        "direction_secondaire_id": payload.get("direction_secondaire_id"),
        "direction_regionale_id": payload.get("direction_regionale_id"),
    }
    new_access = create_access_token(token_data)
    new_refresh = create_refresh_token(token_data)

    new_payload = decode_token(new_refresh)
    new_jti = new_payload["jti"]
    ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    await redis.setex(f"refresh:{new_jti}", ttl, str(payload["sub"]))

    return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}


async def logout(refresh_token: str, redis: aioredis.Redis) -> None:
    try:
        payload = decode_token(refresh_token)
        jti = payload.get("jti")
        if jti:
            await redis.delete(f"refresh:{jti}")
    except HTTPException:
        pass  # logout est idempotent — token expiré ou invalide, on ignore
