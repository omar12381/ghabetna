from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import Base, engine
from .routers import affectations

app = FastAPI(title="Ghabetna — Incident Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_origin_regex=r"http://localhost(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    Base.metadata.create_all(bind=engine)


# app.include_router(affectations.router, prefix="/affectations", tags=["Affectations"])
# Désactivé jusqu'à M3 — endpoints affectation migrés vers user-forest-service

#endpoint tres important pour vérifier que le service est bien vivant et prêt à recevoir des requêtes. C'est un peu comme faire un "ping" à votre service pour s'assurer qu'il répond correctement. le service l'appele régulièrement (par exemple via un outil de monitoring ou un orchestrateur comme Kubernetes) pour vérifier sa santé. Si ce endpoint retourne une réponse "ok", cela signifie que le service est opérationnel. Sinon, cela peut indiquer un problème qui nécessite une attention immédiate.
@app.get("/health")
def health():
    return {"status": "ok", "service": "incident-service"}


