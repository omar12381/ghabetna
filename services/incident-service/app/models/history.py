from datetime import datetime

from sqlalchemy import ForeignKey, Integer, Text, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class IncidentStatusHistory(Base):
    __tablename__ = "incident_status_history"

    id:            Mapped[int]           = mapped_column(primary_key=True)
    incident_id:   Mapped[int]           = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    old_statut_id: Mapped[int | None]    = mapped_column(ForeignKey("statuts.id"), nullable=True)   # NULL pour le premier enregistrement
    new_statut_id: Mapped[int]           = mapped_column(ForeignKey("statuts.id"), nullable=False)
    changed_by:    Mapped[int]           = mapped_column(Integer, nullable=False)  # FK logique → forest_db.users
    changed_at:    Mapped[datetime]      = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default="NOW()")
    commentaire:   Mapped[str | None]    = mapped_column(Text, nullable=True)

    incident:    Mapped["Incident"] = relationship(back_populates="history")           # noqa: F821
    old_statut:  Mapped["Statut | None"] = relationship(foreign_keys=[old_statut_id])  # noqa: F821
    new_statut:  Mapped["Statut"]        = relationship(foreign_keys=[new_statut_id])  # noqa: F821
