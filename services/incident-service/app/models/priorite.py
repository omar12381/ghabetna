from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Priorite(Base):
    __tablename__ = "priorites"

    id:                  Mapped[int]  = mapped_column(primary_key=True)
    code:                Mapped[str]  = mapped_column(String(20), nullable=False, unique=True)
    label:               Mapped[str]  = mapped_column(String(50), nullable=False)
    declenche_telegram:  Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relation inverse
    incident_types: Mapped[list["IncidentType"]] = relationship(back_populates="priorite")  # noqa: F821
