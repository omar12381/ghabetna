from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class IncidentComment(Base):
    __tablename__ = "incident_comments"

    id:          Mapped[int]      = mapped_column(primary_key=True)
    incident_id: Mapped[int]      = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    author_id:   Mapped[int]      = mapped_column(Integer, nullable=False)   # FK logique → forest_db.users
    author_role: Mapped[str]      = mapped_column(String(20), nullable=False)  # 'superviseur' | 'admin'
    content:     Mapped[str]      = mapped_column(Text, nullable=False)
    created_at:  Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default="NOW()")

    incident: Mapped["Incident"] = relationship(back_populates="comments")  # noqa: F821
