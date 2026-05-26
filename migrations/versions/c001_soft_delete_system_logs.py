"""Add soft-delete columns to system_logs

Revision ID: c001_soft_delete_logs
Revises: b001add_admin
Create Date: 2026-05-24 00:00:00.000000

Adds:
  - system_logs.is_deleted  BOOLEAN NOT NULL DEFAULT FALSE
  - system_logs.deleted_at  DATETIME(timezone) NULLABLE
"""

from alembic import op
import sqlalchemy as sa

revision     = 'c001_soft_delete_logs'
down_revision = 'b001add_admin'
branch_labels = None
depends_on    = None


def upgrade():
    op.add_column(
        'system_logs',
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'system_logs',
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_system_logs_is_deleted', 'system_logs', ['is_deleted'])


def downgrade():
    op.drop_index('ix_system_logs_is_deleted', table_name='system_logs')
    op.drop_column('system_logs', 'deleted_at')
    op.drop_column('system_logs', 'is_deleted')
