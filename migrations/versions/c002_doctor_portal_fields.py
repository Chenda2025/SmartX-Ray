"""Add doctor portal fields: license_no, rate_per_session, availability, rejection_reason

Revision ID: c002
Revises: c001
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa

revision = 'c002_doctor_portal'
down_revision = 'c001_soft_delete_logs'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('doctors', sa.Column('license_no',       sa.String(100),  nullable=True))
    op.add_column('doctors', sa.Column('rate_per_session', sa.Float(),       nullable=True, server_default='0'))
    op.add_column('doctors', sa.Column('availability',     sa.String(255),   nullable=True))
    op.add_column('doctors', sa.Column('rejection_reason', sa.Text(),        nullable=True))


def downgrade():
    op.drop_column('doctors', 'rejection_reason')
    op.drop_column('doctors', 'availability')
    op.drop_column('doctors', 'rate_per_session')
    op.drop_column('doctors', 'license_no')
