import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..db import get_redis
from ..models import AccessTokenResponse, LoginRequest, RefreshRequest, TokenResponse
from ..services import auth_service as svc

router = APIRouter()


async def _check_rate_limit(request: Request, redis: aioredis.Redis) -> None:
    ip = request.client.host
    key = f"rate_limit:login:{ip}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 60)
    if count > 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again in 1 minute.",
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    redis: aioredis.Redis = Depends(get_redis),
):
    await _check_rate_limit(request, redis)
    return await svc.login(body.email, body.password, redis)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    body: RefreshRequest,
    redis: aioredis.Redis = Depends(get_redis),
):
    return await svc.refresh(body.refresh_token, redis)


@router.post("/logout")
async def logout(
    body: RefreshRequest,
    redis: aioredis.Redis = Depends(get_redis),
):
    await svc.logout(body.refresh_token, redis)
    return {"message": "Logged out successfully"}
