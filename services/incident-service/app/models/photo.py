from datetime import datetime

from sqlalchemy import ForeignKey, String, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class IncidentPhoto(Base):
    __tablename__ = "incident_photos"

    id:          Mapped[int]      = mapped_column(primary_key=True)
    incident_id: Mapped[int]      = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    photo_url:   Mapped[str]      = mapped_column(String(500), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default="NOW()")

    incident: Mapped["Incident"] = relationship(back_populates="photos")  # noqa: F821
