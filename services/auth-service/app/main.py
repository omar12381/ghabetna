import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_redis
from .routers.auth import router as auth_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GHABETNA Auth Service", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_origin_regex=r"http://localhost(:\d+)?",
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    app.state.redis = await init_redis()
    await app.state.redis.ping()
    logger.info("Redis connected at %s", settings.REDIS_URL)
    logger.info("ACCESS_TOKEN_EXPIRE_MINUTES=%s", settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    logger.info("REFRESH_TOKEN_EXPIRE_DAYS=%s", settings.REFRESH_TOKEN_EXPIRE_DAYS)
    logger.info("USER_SERVICE_URL=%s", settings.USER_SERVICE_URL)
    logger.info("CORS_ORIGINS=%s", settings.CORS_ORIGINS)


@app.on_event("shutdown")
async def on_shutdown():
    await app.state.redis.aclose()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth-service"}


app.include_router(auth_router, prefix="/auth", tags=["auth"])
