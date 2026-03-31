import logging

import redis.asyncio as aioredis
from fastapi import Request

from .config import settings

logger = logging.getLogger(__name__)


async def init_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def get_redis(request: Request) -> aioredis.Redis:
    return request.app.state.redis
