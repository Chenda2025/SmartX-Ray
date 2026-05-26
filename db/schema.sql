-- ════════════════════════════════════════════════════════════════════════════
--  SmartX-Ray  —  Complete PostgreSQL Schema  (9 tables)
--  Authoritative source for the Admin → Doctor → Patient connection flow.
--
--  Usage (fresh database):
--    psql -U postgres -c "CREATE DATABASE smartxray;"
--    psql -U postgres -d smartxray -f db/schema.sql
--
--  Usage (existing database — run migrations instead):
--    flask db upgrade
-- ════════════════════════════════════════════════════════════════════════════

\connect smartxray

-- ── Extensions ───────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid(), pgp_sym_encrypt

-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 1 : users
--   Covers all three actors — admin, doctor, patient.
--   role  : 'admin' | 'doctor' | 'patient'
--   tier  : 'free'  | 'pro'
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    -- identity
    id              SERIAL          PRIMARY KEY,
    username        VARCHAR(100),
    email           VARCHAR(150)    UNIQUE NOT NULL,
    password_hash   VARCHAR(255)    NOT NULL,

    -- role & tier
    role            VARCHAR(20)     NOT NULL DEFAULT 'patient',   -- admin | doctor | patient
    tier            VARCHAR(20)     NOT NULL DEFAULT 'free',       -- free  | pro

    -- profile
    full_name       VARCHAR(255)    NOT NULL DEFAULT '',
    university      VARCHAR(100),                                  -- RUPP | IU | NUM | AUSF | UHS | other
    avatar_url      VARCHAR(512),

    -- flags
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN         NOT NULL DEFAULT FALSE,
    is_admin        BOOLEAN         NOT NULL DEFAULT FALSE,        -- kept for legacy compat

    -- scan quota (free tier)
    scan_count      INTEGER         NOT NULL DEFAULT 0,
    scans_today     INTEGER         NOT NULL DEFAULT 0,
    scans_reset_at  TIMESTAMPTZ,

    -- timestamps
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email    ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role     ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_is_admin ON users(is_admin) WHERE is_admin = TRUE;


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 2 : doctors
--   Each approved doctor has ONE user account (user_id FK).
--   Admin creates the doctor record; doctor self-registers and links account.
--   status : 'pending' | 'approved' | 'rejected'
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS doctors (
    -- identity
    id                  SERIAL          PRIMARY KEY,
    user_id             INTEGER         REFERENCES users(id) ON DELETE SET NULL,

    -- profile
    full_name           VARCHAR(150)    NOT NULL,
    specialty           VARCHAR(100)    NOT NULL,
    qualifications      VARCHAR(512),                              -- MBBS, MD, etc.
    license_number      VARCHAR(100)    UNIQUE,                   -- KH-MED-XXXX
    license_doc_url     VARCHAR(300),                             -- uploaded document
    university          VARCHAR(100),                             -- where they trained
    experience_years    INTEGER         NOT NULL DEFAULT 0,
    bio                 TEXT,
    photo_url           VARCHAR(300),                             -- profile picture
    avatar_url          VARCHAR(512),                             -- alias kept for compat
    hospital            VARCHAR(255),
    city                VARCHAR(100),
    country             VARCHAR(100)    DEFAULT 'Cambodia',

    -- contact
    email               VARCHAR(255),
    phone               VARCHAR(50),
    website             VARCHAR(512),
    google_maps_url     VARCHAR(1024),

    -- consultation
    rate_per_session    NUMERIC(8,2)    NOT NULL DEFAULT 15.00,
    availability        VARCHAR(200),                             -- "Mon–Fri 9:00–17:00"

    -- approval workflow
    status              VARCHAR(20)     NOT NULL DEFAULT 'pending',  -- pending | approved | rejected
    reject_reason       TEXT,
    rejection_reason    TEXT,                                     -- alias kept for compat
    reviewed_by         INTEGER         REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at         TIMESTAMPTZ,

    -- aggregate stats (updated by app logic after each review)
    avg_rating          NUMERIC(3,2)    NOT NULL DEFAULT 0.00,
    rating              FLOAT           NOT NULL DEFAULT 0.0,     -- alias kept for compat
    total_reviews       INTEGER         NOT NULL DEFAULT 0,
    review_count        INTEGER         NOT NULL DEFAULT 0,       -- alias kept for compat
    total_earnings      NUMERIC(10,2)   NOT NULL DEFAULT 0.00,

    -- visibility flags (kept for backward compat)
    is_verified         BOOLEAN         NOT NULL DEFAULT FALSE,
    is_featured         BOOLEAN         NOT NULL DEFAULT FALSE,
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,

    -- timestamps
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_doctors_user_id   ON doctors(user_id);
CREATE INDEX IF NOT EXISTS idx_doctors_status    ON doctors(status);
CREATE INDEX IF NOT EXISTS idx_doctors_specialty ON doctors(specialty);
CREATE INDEX IF NOT EXISTS idx_doctors_university ON doctors(university);


-- ────────────────────────────────────────────────────────────────────────────
-- SUPPORTING TABLE : reports  (must precede scans due to FK)
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reports (
    id                  SERIAL          PRIMARY KEY,
    user_id             INTEGER         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    file_path           VARCHAR(512)    NOT NULL,
    file_size           INTEGER,
    title               VARCHAR(255)    DEFAULT 'SmartX-Ray Diagnostic Report',
    summary             TEXT,
    is_pro              BOOLEAN         NOT NULL DEFAULT TRUE,
    download_count      INTEGER         NOT NULL DEFAULT 0,
    last_downloaded_at  TIMESTAMPTZ,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_user ON reports(user_id);


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 3 : scans
--   One scan per upload. result_label mirrors prediction for new schema naming.
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scans (
    id              SERIAL          PRIMARY KEY,
    user_id         INTEGER         NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- file paths (relative to static/)
    image_path      VARCHAR(300)    NOT NULL,
    heatmap_path    VARCHAR(300),

    -- AI result
    result_label    VARCHAR(50),                                  -- PNEUMONIA | NORMAL
    prediction      VARCHAR(50),                                  -- alias (old name)
    confidence_pct  NUMERIC(5,2),                                 -- 0.00 – 100.00
    confidence      FLOAT,                                        -- 0.0 – 1.0 (old format)
    raw_score       FLOAT,
    ai_time_ms      INTEGER,                                      -- inference time in ms
    model_version   VARCHAR(50)     DEFAULT 'CNN+ANN v1.0',

    -- grad-cam
    gradcam_status  VARCHAR(20)     DEFAULT 'pending',            -- pending | done | failed

    -- report link (Pro only)
    report_id       INTEGER         REFERENCES reports(id) ON DELETE SET NULL,

    notes           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scans_user    ON scans(user_id);
CREATE INDEX IF NOT EXISTS idx_scans_created ON scans(created_at DESC);


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 4 : appointments
--   Patient books a session with an approved doctor.
--   payment_status: 'paid' | 'pending' | 'refunded'
--   status        : 'confirmed' | 'completed' | 'cancelled' | 'no_show'
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS appointments (
    id              SERIAL          PRIMARY KEY,

    -- parties
    patient_id      INTEGER         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    doctor_id       INTEGER         NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,

    -- scheduling — new unified timestamp (preferred)
    scheduled_at    TIMESTAMPTZ     NOT NULL,
    duration_min    INTEGER         NOT NULL DEFAULT 30,

    -- legacy date/time columns (kept for backward compat with old routes)
    appointment_date DATE,
    appointment_time VARCHAR(20),

    -- meeting
    meeting_link    VARCHAR(300),

    -- patient info
    patient_note    TEXT,
    note            TEXT,                                         -- alias kept for compat

    -- financials
    fee_amount      NUMERIC(8,2),
    fee_snapshot    FLOAT           DEFAULT 0.0,                  -- alias kept for compat
    payment_method  VARCHAR(50)     DEFAULT 'ABA KHQR',
    payment_status  VARCHAR(20)     DEFAULT 'paid',

    -- status
    status          VARCHAR(20)     NOT NULL DEFAULT 'confirmed',

    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_appointments_patient  ON appointments(patient_id);
CREATE INDEX IF NOT EXISTS idx_appointments_doctor   ON appointments(doctor_id);
CREATE INDEX IF NOT EXISTS idx_appointments_schedule ON appointments(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_appointments_status   ON appointments(status);


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 5 : reviews
--   One review per completed appointment.
--   After insert/update, app recalculates doctors.avg_rating.
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reviews (
    id              SERIAL          PRIMARY KEY,
    appointment_id  INTEGER         UNIQUE REFERENCES appointments(id) ON DELETE CASCADE,
    patient_id      INTEGER         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    doctor_id       INTEGER         NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    rating          INTEGER         NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment         TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reviews_doctor  ON reviews(doctor_id);
CREATE INDEX IF NOT EXISTS idx_reviews_patient ON reviews(patient_id);


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 6 : subscriptions
--   One row per user.  Stripe fields nullable when using mock payment.
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS subscriptions (
    id                      SERIAL          PRIMARY KEY,
    user_id                 INTEGER         UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- plan
    plan                    VARCHAR(20)     NOT NULL,              -- monthly | yearly | pro
    price                   NUMERIC(8,2)    NOT NULL DEFAULT 9.99,
    status                  VARCHAR(30)     NOT NULL DEFAULT 'active',  -- active | cancelled | expired

    -- period
    started_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    expires_at              TIMESTAMPTZ     NOT NULL,
    cancel_at_period_end    BOOLEAN         DEFAULT FALSE,
    canceled_at             TIMESTAMPTZ,

    -- stripe (nullable for mock / ABA KHQR payments)
    stripe_customer_id      VARCHAR(255)    UNIQUE,
    stripe_subscription_id  VARCHAR(255)    UNIQUE,
    stripe_price_id         VARCHAR(255),

    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user   ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 7 : ads
--   Admin-managed ad banners / sidebar / result-page ads.
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ads (
    id              SERIAL          PRIMARY KEY,
    title           VARCHAR(200)    NOT NULL,
    body            TEXT,
    image_url       VARCHAR(300),
    target_url      VARCHAR(512)    NOT NULL DEFAULT '/',
    sponsor_name    VARCHAR(200),
    advertiser      VARCHAR(255),                                 -- alias kept for compat
    placement       VARCHAR(100)    NOT NULL DEFAULT 'banner',    -- banner | sidebar | result_page | interstitial
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    total_views     INTEGER         NOT NULL DEFAULT 0,
    impressions     INTEGER         NOT NULL DEFAULT 0,           -- alias kept for compat
    total_clicks    INTEGER         NOT NULL DEFAULT 0,
    clicks          INTEGER         NOT NULL DEFAULT 0,           -- alias kept for compat
    priority        INTEGER         NOT NULL DEFAULT 0,
    start_date      TIMESTAMPTZ,
    end_date        TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ads_placement_active ON ads(placement, is_active);


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 8 : system_logs
--   Audit trail for scans, auth events, admin actions, Telegram alerts.
--   Supports soft-delete so admin can "clear" without losing data.
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS system_logs (
    id              SERIAL          PRIMARY KEY,

    -- context
    scan_id         INTEGER         REFERENCES scans(id) ON DELETE SET NULL,
    user_id         INTEGER         REFERENCES users(id) ON DELETE SET NULL,

    -- event
    event_type      VARCHAR(100)    NOT NULL,  -- scan | auth_login | auth_fail | admin_action | telegram_alert | error
    severity        VARCHAR(20)     NOT NULL DEFAULT 'info',  -- info | warning | high | critical
    message         TEXT            NOT NULL,
    ai_time_ms      INTEGER,                   -- alias for processing_ms
    processing_ms   INTEGER,

    -- request metadata
    ip_address      VARCHAR(45),
    user_agent      VARCHAR(512),
    extra           JSONB,
    details         TEXT,                      -- human-readable detail

    -- soft-delete
    is_deleted      BOOLEAN         NOT NULL DEFAULT FALSE,
    deleted_at      TIMESTAMPTZ,

    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_logs_event_type ON system_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_logs_severity   ON system_logs(severity);
CREATE INDEX IF NOT EXISTS idx_logs_user_id    ON system_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_logs_scan_id    ON system_logs(scan_id);
CREATE INDEX IF NOT EXISTS idx_logs_created    ON system_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_not_deleted ON system_logs(is_deleted) WHERE is_deleted = FALSE;


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE 9 : telegram_configs
--   Admin sets bot token + chat ID from /admin/telegram UI.
--   Only one active row expected (id=1).
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS telegram_configs (
    id              SERIAL          PRIMARY KEY,
    bot_token       VARCHAR(300),
    chat_id         VARCHAR(100),
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    threshold_pct   NUMERIC(5,2)    NOT NULL DEFAULT 85.00,  -- confidence % that triggers alert
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);


-- ────────────────────────────────────────────────────────────────────────────
-- SUPPORTING TABLE : transactions  (retained from existing schema)
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transactions (
    id                          SERIAL          PRIMARY KEY,
    user_id                     INTEGER         REFERENCES users(id) ON DELETE SET NULL,
    stripe_payment_intent_id    VARCHAR(255)    UNIQUE,
    stripe_invoice_id           VARCHAR(255),
    stripe_customer_id          VARCHAR(255),
    amount                      NUMERIC(10,2)   NOT NULL,
    currency                    VARCHAR(10)     NOT NULL DEFAULT 'usd',
    product_type                VARCHAR(50)     NOT NULL,
    plan                        VARCHAR(20),
    status                      VARCHAR(30)     NOT NULL DEFAULT 'pending',
    failure_reason              VARCHAR(255),
    receipt_url                 VARCHAR(512),
    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transactions_user   ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);


-- ════════════════════════════════════════════════════════════════════════════
--  FUNCTIONS & TRIGGERS
-- ════════════════════════════════════════════════════════════════════════════

-- Auto-update updated_at on every UPDATE
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to tables that have updated_at
DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'users', 'doctors', 'subscriptions', 'ads', 'transactions', 'telegram_configs'
    ]
    LOOP
        EXECUTE format(
            'DROP TRIGGER IF EXISTS trg_%s_updated_at ON %I;
             CREATE TRIGGER trg_%s_updated_at
             BEFORE UPDATE ON %I
             FOR EACH ROW EXECUTE FUNCTION update_updated_at();',
            t, t, t, t
        );
    END LOOP;
END;
$$;


-- Recalculate doctor avg_rating + total_reviews after review insert/update/delete
CREATE OR REPLACE FUNCTION recalc_doctor_rating()
RETURNS TRIGGER AS $$
DECLARE
    v_doctor_id INTEGER;
    v_avg       NUMERIC(3,2);
    v_count     INTEGER;
BEGIN
    -- Determine which doctor_id to recalculate
    IF TG_OP = 'DELETE' THEN
        v_doctor_id := OLD.doctor_id;
    ELSE
        v_doctor_id := NEW.doctor_id;
    END IF;

    SELECT
        COALESCE(ROUND(AVG(rating)::NUMERIC, 2), 0.00),
        COUNT(*)
    INTO v_avg, v_count
    FROM reviews
    WHERE doctor_id = v_doctor_id;

    UPDATE doctors
    SET
        avg_rating    = v_avg,
        rating        = v_avg,         -- keep alias in sync
        total_reviews = v_count,
        review_count  = v_count,       -- keep alias in sync
        updated_at    = NOW()
    WHERE id = v_doctor_id;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_reviews_recalc_rating ON reviews;
CREATE TRIGGER trg_reviews_recalc_rating
AFTER INSERT OR UPDATE OR DELETE ON reviews
FOR EACH ROW EXECUTE FUNCTION recalc_doctor_rating();


-- ════════════════════════════════════════════════════════════════════════════
--  VIEWS  (convenient for admin dashboard queries)
-- ════════════════════════════════════════════════════════════════════════════

-- Admin: pending doctors awaiting approval
CREATE OR REPLACE VIEW vw_pending_doctors AS
SELECT
    d.id,
    d.full_name,
    d.specialty,
    d.license_number,
    d.university,
    d.email,
    d.created_at     AS submitted_at,
    u.email          AS user_email
FROM doctors d
LEFT JOIN users u ON u.id = d.user_id
WHERE d.status = 'pending'
ORDER BY d.created_at ASC;


-- Admin: appointment dashboard
CREATE OR REPLACE VIEW vw_appointment_details AS
SELECT
    a.id,
    a.scheduled_at,
    a.duration_min,
    a.status,
    a.payment_status,
    a.fee_amount,
    a.meeting_link,
    a.patient_note,
    -- patient
    pu.id           AS patient_id,
    pu.full_name    AS patient_name,
    pu.email        AS patient_email,
    -- doctor
    d.id            AS doctor_id,
    d.full_name     AS doctor_name,
    d.specialty     AS doctor_specialty
FROM appointments a
JOIN users   pu ON pu.id = a.patient_id
JOIN doctors d  ON d.id  = a.doctor_id;


-- ════════════════════════════════════════════════════════════════════════════
--  INITIAL SEED DATA (system defaults only — demo data is in db/seed.py)
-- ════════════════════════════════════════════════════════════════════════════

-- Default Telegram config placeholder
INSERT INTO telegram_configs (bot_token, chat_id, is_active, threshold_pct)
SELECT 'YOUR_BOT_TOKEN', 'YOUR_CHAT_ID', TRUE, 85.00
WHERE NOT EXISTS (SELECT 1 FROM telegram_configs WHERE id = 1);

-- Default system ads
INSERT INTO ads (title, body, target_url, advertiser, sponsor_name, placement, priority)
SELECT 'Upgrade to Pro', 'Unlock unlimited scans, PDF reports & priority support.',
       '/pricing', 'SmartX-Ray', 'SmartX-Ray', 'banner', 10
WHERE NOT EXISTS (SELECT 1 FROM ads WHERE title = 'Upgrade to Pro');

INSERT INTO ads (title, body, target_url, advertiser, sponsor_name, placement, priority)
SELECT 'Find a Specialist', 'Connect with verified Cambodian doctors.',
       '/find-doctor', 'SmartX-Ray', 'SmartX-Ray', 'result_page', 5
WHERE NOT EXISTS (SELECT 1 FROM ads WHERE title = 'Find a Specialist');

-- ════════════════════════════════════════════════════════════════════════════
--  END OF SCHEMA
-- ════════════════════════════════════════════════════════════════════════════
