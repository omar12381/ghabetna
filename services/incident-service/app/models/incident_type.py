from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class IncidentType(Base):
    __tablename__ = "incident_types"

    id:          Mapped[int]           = mapped_column(primary_key=True)
    code:        Mapped[str]           = mapped_column(String(50), nullable=False, unique=True)
    label:       Mapped[str]           = mapped_column(String(100), nullable=False)
    priorite_id: Mapped[int]           = mapped_column(ForeignKey("priorites.id"), nullable=False)
    description: Mapped[str | None]    = mapped_column(Text, nullable=True)

    # Relations
    priorite:  Mapped["Priorite"]        = relationship(back_populates="incident_types")  # noqa: F821
    incidents: Mapped[list["Incident"]]  = relationship(back_populates="type")             # noqa: F821
