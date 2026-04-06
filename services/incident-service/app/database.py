from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

engine = create_engine(settings.DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_migrations: list[str] = []
# Index agent_parcelle_assignments supprimés — table migrée vers forest_db


#Ce fichier prépare le terrain pour que :

#Vos données soient structurées (Base).

#Vos accès soient propres et fermés après usage (get_db).

#Vos recherches soient ultra-rapides et vos règles métiers respectées (Index).

