"""Create appointments table

Revision ID: c003
Revises: c002_doctor_portal
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa

revision      = 'c003_appointments'
down_revision = 'c002_doctor_portal'
branch_labels = None
depends_on    = None


def upgrade():
    op.create_table(
        'appointments',
        sa.Column('id',               sa.Integer(),     nullable=False, primary_key=True),
        sa.Column('user_id',          sa.Integer(),     nullable=False),
        sa.Column('doctor_id',        sa.Integer(),     nullable=False),
        sa.Column('appointment_date', sa.Date(),        nullable=False),
        sa.Column('appointment_time', sa.String(20),    nullable=False),
        sa.Column('note',             sa.Text(),        nullable=True),
        sa.Column('status',           sa.String(20),    nullable=False, server_default='confirmed'),
        sa.Column('fee_snapshot',     sa.Float(),       nullable=False, server_default='0'),
        sa.Column('created_at',       sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'],   ['users.id'],   ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_appointments_user_id',   'appointments', ['user_id'])
    op.create_index('ix_appointments_doctor_id', 'appointments', ['doctor_id'])
    op.create_index('ix_appointments_status',    'appointments', ['status'])


def downgrade():
    op.drop_index('ix_appointments_status',    table_name='appointments')
    op.drop_index('ix_appointments_doctor_id', table_name='appointments')
    op.drop_index('ix_appointments_user_id',   table_name='appointments')
    op.drop_table('appointments')
