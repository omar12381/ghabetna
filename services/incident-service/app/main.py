import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings

app = FastAPI(title="Ghabetna — Incident Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_origin_regex=r"http://localhost(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MEDIA_DIR = "/media/incidents"

# Créer le dossier avant le mount — StaticFiles vérifie l'existence au chargement du module
os.makedirs(MEDIA_DIR, exist_ok=True)

# Servir les photos uploadées (T15)
app.mount("/media/incidents", StaticFiles(directory=MEDIA_DIR), name="media")


@app.on_event("startup")
async def on_startup():
    # Alembic gère le schéma (alembic upgrade head lancé dans le CMD du Dockerfile)
    # Seed données de référence (T3)
    from .database import SessionLocal
    from .utils.seed import run_seed
    db = SessionLocal()
    try:
        run_seed(db)
    finally:
        db.close()

from .routers import incidents
app.include_router(incidents.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "incident-service"}
