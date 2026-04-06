"""002 — table incidents + indexes

Revision ID: 002
Revises: 001
Create Date: 2026-04-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        # Clé primaire
        sa.Column("id", sa.Integer(), primary_key=True),

        # Acteur (FK logique → forest_db.users)
        sa.Column("agent_id", sa.Integer(), nullable=False),

        # Géographie résolue par GPS (FK logiques → forest_db)
        sa.Column("parcelle_id", sa.Integer(), nullable=False),
        sa.Column("forest_id", sa.Integer(), nullable=False),
        sa.Column("dir_secondaire_id", sa.Integer(), nullable=False),

        # GPS
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("gps_match_type", sa.String(10), nullable=False, server_default="exact"),

        # Classification (FK réelles → tables locales)
        sa.Column(
            "incident_type_id",
            sa.Integer(),
            sa.ForeignKey("incident_types.id"),
            nullable=False,
        ),
        sa.Column(
            "statut_id",
            sa.Integer(),
            sa.ForeignKey("statuts.id"),
            nullable=False,
            server_default="1",
        ),

        # Description
        sa.Column("description", sa.Text(), nullable=True),

        # Évaluation superviseur
        sa.Column(
            "note_superviseur",
            sa.Integer(),
            sa.CheckConstraint("note_superviseur BETWEEN 1 AND 5", name="ck_note_superviseur"),
            nullable=True,
        ),
        sa.Column("commentaire_superviseur", sa.Text(), nullable=True),

        # Traçabilité
        sa.Column("updated_by", sa.Integer(), nullable=True),   # FK logique → forest_db.users
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),

        # Timestamps
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # Index définis dans le schéma M3
    op.create_index("ix_inc_agent",      "incidents", ["agent_id"])
    op.create_index("ix_inc_forest",     "incidents", ["forest_id"])
    op.create_index("ix_inc_type",       "incidents", ["incident_type_id"])
    op.create_index("ix_inc_created",    "incidents", [sa.text("created_at DESC")])
    op.create_index(
        "ix_inc_deleted",
        "incidents",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_inc_dir_statut",
        "incidents",
        [sa.text("dir_secondaire_id"), sa.text("statut_id"), sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_inc_dir_statut",  table_name="incidents")
    op.drop_index("ix_inc_deleted",     table_name="incidents")
    op.drop_index("ix_inc_created",     table_name="incidents")
    op.drop_index("ix_inc_type",        table_name="incidents")
    op.drop_index("ix_inc_forest",      table_name="incidents")
    op.drop_index("ix_inc_agent",       table_name="incidents")
    op.drop_table("incidents")
