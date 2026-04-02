import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .db import engine, Base
from . import models  # noqa: F401
from .routers import users, forests, parcelles, roles
from .routers.directions import router_regionales, router_secondaires
from .routers.geo import router as geo_router


app = FastAPI(title="User & Forest Management API")

allow_origins = os.getenv("CORS_ORIGINS", "http://localhost").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    # Crée les tables si elles n'existent pas encore
    Base.metadata.create_all(bind=engine)
    # Initialise quelques rôles par défaut
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO roles (name) "
                "SELECT unnest(:names) "
                "WHERE NOT EXISTS (SELECT 1 FROM roles)"
            ),
            {"names": ["admin", "agent_forestier", "superviseur"]},
        )

    # Évolutions de schéma ponctuelles — chaque instruction dans sa propre
    # transaction pour qu'un échec isolé ne bloque pas les autres.
    _migrations = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS direction_secondaire_id INTEGER REFERENCES direction_secondaire(id)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS telephone VARCHAR(50)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS actif BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS direction_regionale_id INTEGER REFERENCES direction_regionale(id)",
        "ALTER TABLE forests ADD COLUMN IF NOT EXISTS direction_secondaire_id INTEGER REFERENCES direction_secondaire(id)",
        "ALTER TABLE forests ADD COLUMN IF NOT EXISTS direction_regionale_id INTEGER REFERENCES direction_regionale(id)",
    ]
    for _sql in _migrations:
        try:
            with engine.begin() as _conn:
                _conn.execute(text(_sql))
        except Exception:
            pass  # colonne déjà présente ou erreur non bloquante

    # Spatial indexes (PostGIS geometry).
    # These improve performance for ST_Intersects/ST_Contains/ST_Disjoint queries.
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_forests_geom ON forests USING GIST (geom)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_parcelles_geom ON parcelles USING GIST (geom)"
            )
        )


@app.get("/health")
def health():
    return {"status": "ok", "service": "user-forest-service"}


app.include_router(roles.router, prefix="/roles", tags=["roles"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(forests.router, prefix="/forests", tags=["forests"])
app.include_router(parcelles.router, prefix="/parcelles", tags=["parcelles"])
app.include_router(router_regionales, prefix="/directions-regionales", tags=["directions"])
app.include_router(router_secondaires, prefix="/directions-secondaires", tags=["directions"])
app.include_router(geo_router, prefix="/geo", tags=["geo"])

