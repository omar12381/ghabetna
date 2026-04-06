from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Statut(Base):
    __tablename__ = "statuts"

    id:      Mapped[int] = mapped_column(primary_key=True)
    code:    Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    label:   Mapped[str] = mapped_column(String(50), nullable=False)
    couleur: Mapped[str] = mapped_column(String(7),  nullable=False)

    # Relations inverses
    incidents: Mapped[list["Incident"]] = relationship(  # noqa: F821
        back_populates="statut",
        foreign_keys="Incident.statut_id",
    )
