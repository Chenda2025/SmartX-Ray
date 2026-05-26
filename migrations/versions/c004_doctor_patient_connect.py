"""Doctor–patient connection: new columns on users, doctors, appointments + reviews/telegram tables

Adds:
  users        → role
  doctors      → user_id FK, status, university, experience_years, avg_rating, total_reviews,
                 total_earnings, license_number, reject_reason, reviewed_by, reviewed_at,
                 photo_url, phone, google_maps_url (already exists), city (already exists)
  appointments → patient_id, scheduled_at, duration_min, patient_note, fee_amount,
                 meeting_link, payment_method, payment_status
  reviews      (new table)
  telegram_configs (new table)
  transactions (new table, if not exists)

Revision ID: c004
Revises: c003_appointments
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision      = 'c004'
down_revision = 'c003_appointments'
branch_labels = None
depends_on    = None


def _column_exists(table, column):
    """Check whether a column exists in a PostgreSQL table."""
    bind = op.get_bind()
    res  = bind.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name=:t AND column_name=:c"
    ), {"t": table, "c": column})
    return res.fetchone() is not None


def _table_exists(table):
    bind = op.get_bind()
    res  = bind.execute(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name=:t"
    ), {"t": table})
    return res.fetchone() is not None


def upgrade():

    # ── users.role ───────────────────────────────────────────────────────────
    if not _column_exists('users', 'role'):
        op.add_column('users', sa.Column('role', sa.String(20), nullable=True,
                                          server_default='patient'))
        # Back-fill: admins get 'admin', others get 'patient'
        op.execute(text("UPDATE users SET role = 'admin'   WHERE is_admin = TRUE"))
        op.execute(text("UPDATE users SET role = 'patient' WHERE role IS NULL"))
        op.execute(text("ALTER TABLE users ALTER COLUMN role SET NOT NULL"))
        op.execute(text("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'patient'"))

    # ── doctors: new columns ─────────────────────────────────────────────────
    new_doctor_cols = [
        ('user_id',           sa.Integer(),        True),
        ('status',            sa.String(20),       True),
        ('university',        sa.String(255),      True),
        ('experience_years',  sa.Integer(),        True),
        ('avg_rating',        sa.Numeric(3, 2),    True),
        ('total_reviews',     sa.Integer(),        True),
        ('total_earnings',    sa.Numeric(12, 2),   True),
        ('license_number',    sa.String(100),      True),
        ('reject_reason',     sa.Text(),           True),
        ('reviewed_by',       sa.Integer(),        True),
        ('reviewed_at',       sa.DateTime(timezone=True), True),
        ('photo_url',         sa.String(512),      True),
        ('phone',             sa.String(50),       True),
    ]
    for col_name, col_type, nullable in new_doctor_cols:
        if not _column_exists('doctors', col_name):
            op.add_column('doctors', sa.Column(col_name, col_type, nullable=nullable))

    # status default back-fill
    op.execute(text("""
        UPDATE doctors
        SET status = CASE
            WHEN is_verified AND is_active  THEN 'approved'
            WHEN NOT is_active              THEN 'rejected'
            ELSE 'pending'
        END
        WHERE status IS NULL
    """))

    # avg_rating / total_reviews back-fill from rating/review_count
    op.execute(text("""
        UPDATE doctors
        SET avg_rating    = COALESCE(rating,       0),
            total_reviews = COALESCE(review_count, 0)
        WHERE avg_rating IS NULL
    """))

    # license_number ← license_no back-fill
    op.execute(text("""
        UPDATE doctors SET license_number = license_no
        WHERE license_number IS NULL AND license_no IS NOT NULL
    """))

    # user_id FK: add constraint if not already there
    bind = op.get_bind()
    fk_exists = bind.execute(text("""
        SELECT constraint_name FROM information_schema.table_constraints
        WHERE table_name='doctors' AND constraint_type='FOREIGN KEY'
        AND constraint_name='fk_doctors_user_id'
    """)).fetchone()
    if not fk_exists and _column_exists('doctors', 'user_id'):
        # Only create FK if there are no orphan rows
        try:
            op.create_foreign_key(
                'fk_doctors_user_id', 'doctors', 'users', ['user_id'], ['id'],
                ondelete='SET NULL',
            )
        except Exception:
            pass  # non-fatal if user_ids have no matching rows yet

    # ── appointments: new columns ────────────────────────────────────────────
    new_apt_cols = [
        ('patient_id',      sa.Integer(),        True),
        ('scheduled_at',    sa.DateTime(timezone=True), True),
        ('duration_min',    sa.Integer(),        True),
        ('patient_note',    sa.Text(),           True),
        ('fee_amount',      sa.Numeric(10, 2),   True),
        ('meeting_link',    sa.String(512),      True),
        ('payment_method',  sa.String(50),       True),
        ('payment_status',  sa.String(20),       True),
    ]
    for col_name, col_type, nullable in new_apt_cols:
        if not _column_exists('appointments', col_name):
            op.add_column('appointments', sa.Column(col_name, col_type, nullable=nullable))

    # patient_id ← user_id back-fill
    op.execute(text("""
        UPDATE appointments SET patient_id = user_id WHERE patient_id IS NULL
    """))

    # scheduled_at ← appointment_date + appointment_time back-fill
    # Note: escape ':00' by splitting the colon out to avoid SQLAlchemy treating it as a bind param
    op.execute(text("""
        UPDATE appointments
        SET scheduled_at = (appointment_date::TEXT || 'T' || appointment_time || CAST(':' AS TEXT) || '00')::TIMESTAMPTZ
        WHERE scheduled_at IS NULL AND appointment_time ~ '^[0-9]{2}:[0-9]{2}'
    """))

    # fee_amount ← fee_snapshot
    op.execute(text("""
        UPDATE appointments SET fee_amount = fee_snapshot WHERE fee_amount IS NULL
    """))

    # duration_min default
    op.execute(text("""
        UPDATE appointments SET duration_min = 30 WHERE duration_min IS NULL
    """))

    # payment defaults
    op.execute(text("""
        UPDATE appointments
        SET payment_method = 'ABA KHQR', payment_status = 'paid'
        WHERE payment_method IS NULL
    """))

    # ── reviews table ────────────────────────────────────────────────────────
    if not _table_exists('reviews'):
        op.create_table(
            'reviews',
            sa.Column('id',             sa.Integer(),  nullable=False, primary_key=True),
            sa.Column('appointment_id', sa.Integer(),  nullable=False),
            sa.Column('patient_id',     sa.Integer(),  nullable=False),
            sa.Column('doctor_id',      sa.Integer(),  nullable=False),
            sa.Column('rating',         sa.SmallInteger(), nullable=False),
            sa.Column('comment',        sa.Text(),     nullable=True),
            sa.Column('created_at',     sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['patient_id'],     ['users.id'],        ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['doctor_id'],      ['doctors.id'],      ondelete='CASCADE'),
            sa.UniqueConstraint('appointment_id', name='uq_reviews_appointment'),
        )
        op.create_index('ix_reviews_doctor_id',  'reviews', ['doctor_id'])
        op.create_index('ix_reviews_patient_id', 'reviews', ['patient_id'])

    # ── telegram_configs table ───────────────────────────────────────────────
    if not _table_exists('telegram_configs'):
        op.create_table(
            'telegram_configs',
            sa.Column('id',          sa.Integer(), nullable=False, primary_key=True),
            sa.Column('bot_token',   sa.String(512), nullable=True),
            sa.Column('chat_id',     sa.String(100), nullable=True),
            sa.Column('is_active',   sa.Boolean(),   nullable=False, server_default='TRUE'),
            sa.Column('created_at',  sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at',  sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
        )

    # ── transactions table ───────────────────────────────────────────────────
    if not _table_exists('transactions'):
        op.create_table(
            'transactions',
            sa.Column('id',             sa.Integer(),     nullable=False, primary_key=True),
            sa.Column('user_id',        sa.Integer(),     nullable=False),
            sa.Column('appointment_id', sa.Integer(),     nullable=True),
            sa.Column('amount',         sa.Numeric(10,2), nullable=False),
            sa.Column('currency',       sa.String(10),    nullable=False, server_default='USD'),
            sa.Column('method',         sa.String(50),    nullable=True),
            sa.Column('status',         sa.String(20),    nullable=False, server_default='completed'),
            sa.Column('reference',      sa.String(255),   nullable=True),
            sa.Column('created_at',     sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        )
        op.create_index('ix_transactions_user_id', 'transactions', ['user_id'])


def downgrade():
    # Drop new tables
    for tbl in ('transactions', 'telegram_configs', 'reviews'):
        if _table_exists(tbl):
            op.drop_table(tbl)

    # Drop appointment columns
    for col in ('payment_status','payment_method','meeting_link','fee_amount',
                'patient_note','duration_min','scheduled_at','patient_id'):
        if _column_exists('appointments', col):
            op.drop_column('appointments', col)

    # Drop doctor columns
    for col in ('phone','photo_url','reviewed_at','reviewed_by','reject_reason',
                'license_number','total_earnings','total_reviews','avg_rating',
                'experience_years','university','status','user_id'):
        if _column_exists('doctors', col):
            op.drop_column('doctors', col)

    # Drop users.role
    if _column_exists('users', 'role'):
        op.drop_column('users', 'role')
