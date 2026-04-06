from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geometry

from .db import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)  # admin, agent_forestier, superviseur

    users = relationship("User", back_populates="role")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)

    direction_secondaire_id = Column(Integer, ForeignKey("direction_secondaire.id"), nullable=True, index=True)
    direction_regionale_id = Column(Integer, ForeignKey("direction_regionale.id"), nullable=True, index=True)
    telephone = Column(String, nullable=True)
    actif = Column(Boolean, default=True, nullable=False)

    role = relationship("Role", back_populates="users")
    direction_secondaire = relationship("DirectionSecondaire", back_populates="superviseurs")
    direction_regionale = relationship("DirectionRegionale")


class DirectionRegionale(Base):
    __tablename__ = "direction_regionale"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    nom = Column(String, nullable=False, unique=True)
    gouvernorat = Column(String, nullable=False)

    directions_secondaires = relationship(
        "DirectionSecondaire",
        back_populates="direction_regionale",
        cascade="all, delete-orphan",
    )


class DirectionSecondaire(Base):
    __tablename__ = "direction_secondaire"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    nom = Column(String, nullable=False)
    region_id = Column(Integer, ForeignKey("direction_regionale.id"), nullable=False, index=True)

    direction_regionale = relationship("DirectionRegionale", back_populates="directions_secondaires")
    superviseurs = relationship("User", back_populates="direction_secondaire")
    forests = relationship("Forest", back_populates="direction_secondaire")


class Forest(Base):
    __tablename__ = "forests"
    __table_args__ = (
        # Spatial index for faster ST_* queries (ST_Intersects/ST_Contains/ST_Disjoint).
        Index("ix_forests_geom", "geom", postgresql_using="GIST"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    # Géométrie POLYGON en WGS84
    geom = Column(Geometry(geometry_type="POLYGON", srid=4326), nullable=False)

    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by = relationship("User")

    direction_secondaire_id = Column(Integer, ForeignKey("direction_secondaire.id"), nullable=True, index=True)
    direction_regionale_id = Column(Integer, ForeignKey("direction_regionale.id"), nullable=True, index=True)
    surface_ha = Column(Float, nullable=True)
    type_foret = Column(String, nullable=True)
    direction_secondaire = relationship("DirectionSecondaire", back_populates="forests")
    direction_regionale = relationship("DirectionRegionale")

    parcelles = relationship("Parcelle", back_populates="forest", cascade="all, delete-orphan")


class Parcelle(Base):
    __tablename__ = "parcelles"
    __table_args__ = (
        # Spatial index for faster ST_* queries.
        Index("ix_parcelles_geom", "geom", postgresql_using="GIST"),
    )

    id = Column(Integer, primary_key=True, index=True)
    forest_id = Column(Integer, ForeignKey("forests.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    geom = Column(Geometry(geometry_type="POLYGON", srid=4326), nullable=False)
    surface_ha = Column(Float, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    forest = relationship("Forest", back_populates="parcelles")


class AgentParcelleAssignment(Base):
    __tablename__ = "agent_parcelle_assignments"

    id          = Column(Integer, primary_key=True, index=True)
    agent_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    parcelle_id = Column(Integer, ForeignKey("parcelles.id"), nullable=False)
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    actif       = Column(Boolean, nullable=False, default=True)
    # Pas de forest_id, dir_secondaire_id, dir_regionale_id
    # → résolus par JOIN à la lecture

