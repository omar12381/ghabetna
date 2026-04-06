"""004 — table incident_status_history

Revision ID: 004
Revises: 003
Create Date: 2026-04-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "incident_status_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "incident_id",
            sa.Integer(),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # NULL pour le premier enregistrement (création de l'incident)
        sa.Column(
            "old_statut_id",
            sa.Integer(),
            sa.ForeignKey("statuts.id"),
            nullable=True,
        ),
        sa.Column(
            "new_statut_id",
            sa.Integer(),
            sa.ForeignKey("statuts.id"),
            nullable=False,
        ),
        sa.Column("changed_by", sa.Integer(), nullable=False),  # FK logique → forest_db.users
        sa.Column(
            "changed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("commentaire", sa.Text(), nullable=True),
    )
    op.create_index("ix_history_incident", "incident_status_history", ["incident_id"])
    op.create_index(
        "ix_history_changed",
        "incident_status_history",
        [sa.text("changed_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_history_changed",  table_name="incident_status_history")
    op.drop_index("ix_history_incident", table_name="incident_status_history")
    op.drop_table("incident_status_history")
