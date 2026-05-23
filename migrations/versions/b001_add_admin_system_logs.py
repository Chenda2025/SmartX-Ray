"""add admin fields + system_logs table

Revision ID: b001add_admin
Revises: a4afe26093ec
Create Date: 2026-05-23 00:00:00.000000

Adds:
  - users.is_admin   BOOLEAN NOT NULL DEFAULT FALSE
  - users.university VARCHAR(100)
  - system_logs      table (full schema)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "b001add_admin"
down_revision = "a4afe26093ec"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users table ──────────────────────────────────────────────────────
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "users",
        sa.Column("university", sa.String(length=100), nullable=True),
    )

    # ── system_logs table ─────────────────────────────────────────────────
    op.create_table(
        "system_logs",
        sa.Column("id",            sa.Integer(),  primary_key=True),
        sa.Column("event_type",    sa.String(50),  nullable=False),
        sa.Column("severity",      sa.String(20),  nullable=False, server_default="info"),
        sa.Column("user_id",       sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scan_id",       sa.Integer(),
                  sa.ForeignKey("scans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("message",       sa.Text(),      nullable=False),
        sa.Column("processing_ms", sa.Integer(),   nullable=True),
        sa.Column("ip_address",    sa.String(45),  nullable=True),
        sa.Column("user_agent",    sa.String(512), nullable=True),
        sa.Column("extra",         sa.JSON(),      nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_system_logs_event_type", "system_logs", ["event_type"])
    op.create_index("ix_system_logs_severity",   "system_logs", ["severity"])
    op.create_index("ix_system_logs_user_id",    "system_logs", ["user_id"])
    op.create_index("ix_system_logs_created_at", "system_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_system_logs_created_at", table_name="system_logs")
    op.drop_index("ix_system_logs_user_id",    table_name="system_logs")
    op.drop_index("ix_system_logs_severity",   table_name="system_logs")
    op.drop_index("ix_system_logs_event_type", table_name="system_logs")
    op.drop_table("system_logs")
    op.drop_column("users", "university")
    op.drop_column("users", "is_admin")
