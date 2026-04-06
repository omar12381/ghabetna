"""003 — tables incident_photos et incident_comments

Revision ID: 003
Revises: 002
Create Date: 2026-04-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── incident_photos ───────────────────────────────────────────────────────
    op.create_table(
        "incident_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "incident_id",
            sa.Integer(),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("photo_url", sa.String(500), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_photos_incident", "incident_photos", ["incident_id"])

    # ── incident_comments ─────────────────────────────────────────────────────
    op.create_table(
        "incident_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "incident_id",
            sa.Integer(),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("author_id", sa.Integer(), nullable=False),   # FK logique → forest_db.users
        sa.Column("author_role", sa.String(20), nullable=False),  # 'superviseur' | 'admin'
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_comments_incident", "incident_comments", ["incident_id"])


def downgrade() -> None:
    op.drop_index("ix_comments_incident", table_name="incident_comments")
    op.drop_table("incident_comments")
    op.drop_index("ix_photos_incident", table_name="incident_photos")
    op.drop_table("incident_photos")
