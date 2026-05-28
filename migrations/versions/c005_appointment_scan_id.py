"""Add scan_id FK to appointments for patient X-ray attachment

Revision ID: c005
Revises: c004
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision      = 'c005'
down_revision = 'c004'
branch_labels = None
depends_on    = None


def _column_exists(table, column):
    bind = op.get_bind()
    res  = bind.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name=:t AND column_name=:c"
    ), {"t": table, "c": column})
    return res.fetchone() is not None


def upgrade():
    if not _column_exists("appointments", "scan_id"):
        op.add_column(
            "appointments",
            sa.Column(
                "scan_id",
                sa.Integer(),
                sa.ForeignKey("scans.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )


def downgrade():
    if _column_exists("appointments", "scan_id"):
        op.drop_column("appointments", "scan_id")
