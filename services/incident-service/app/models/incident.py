from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Incident(Base):
    __tablename__ = "incidents"

    id:                     Mapped[int]           = mapped_column(primary_key=True)

    # Acteur (FK logique → forest_db.users)
    agent_id:               Mapped[int]           = mapped_column(Integer, nullable=False)

    # Géographie résolue par GPS (FK logiques → forest_db)
    parcelle_id:            Mapped[int]           = mapped_column(Integer, nullable=False)
    forest_id:              Mapped[int]           = mapped_column(Integer, nullable=False)
    dir_secondaire_id:      Mapped[int]           = mapped_column(Integer, nullable=False)

    # GPS
    latitude:               Mapped[float]         = mapped_column(Float, nullable=False)
    longitude:              Mapped[float]         = mapped_column(Float, nullable=False)
    gps_match_type:         Mapped[str]           = mapped_column(String(10), nullable=False, default="exact")

    # Classification (FK réelles → tables locales)
    incident_type_id:       Mapped[int]           = mapped_column(ForeignKey("incident_types.id"), nullable=False)
    statut_id:              Mapped[int]           = mapped_column(ForeignKey("statuts.id"), nullable=False)

    # Description
    description:            Mapped[str | None]    = mapped_column(Text, nullable=True)

    # Évaluation superviseur
    note_superviseur:       Mapped[int | None]    = mapped_column(Integer, nullable=True)
    commentaire_superviseur: Mapped[str | None]   = mapped_column(Text, nullable=True)

    # Traçabilité
    updated_by:             Mapped[int | None]    = mapped_column(Integer, nullable=True)
    deleted_at:             Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Timestamps
    created_at:             Mapped[datetime]      = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="NOW()"
    )
    updated_at:             Mapped[datetime]      = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="NOW()"
    )

    # Relations
    type:    Mapped["IncidentType"]                   = relationship(back_populates="incidents")      # noqa: F821
    statut:  Mapped["Statut"]                         = relationship(                                 # noqa: F821
        back_populates="incidents",
        foreign_keys=[statut_id],
    )
    photos:   Mapped[list["IncidentPhoto"]]           = relationship(back_populates="incident", cascade="all, delete-orphan")   # noqa: F821
    comments: Mapped[list["IncidentComment"]]         = relationship(back_populates="incident", cascade="all, delete-orphan")   # noqa: F821
    history:  Mapped[list["IncidentStatusHistory"]]   = relationship(back_populates="incident", cascade="all, delete-orphan")   # noqa: F821
