"""001 — tables de référence : priorites, incident_types, statuts

Revision ID: 001
Revises:
Create Date: 2026-04-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── priorites ─────────────────────────────────────────────────────────────
    op.create_table(
        "priorites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("label", sa.String(50), nullable=False),
        sa.Column("declenche_telegram", sa.Boolean(), nullable=False, server_default="false"),
    )

    # ── incident_types ────────────────────────────────────────────────────────
    op.create_table(
        "incident_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column(
            "priorite_id",
            sa.Integer(),
            sa.ForeignKey("priorites.id"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
    )

    # ── statuts ───────────────────────────────────────────────────────────────
    op.create_table(
        "statuts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False, unique=True),
        sa.Column("label", sa.String(50), nullable=False),
        sa.Column("couleur", sa.String(7), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("incident_types")
    op.drop_table("statuts")
    op.drop_table("priorites")
