-- SmartX-Ray PostgreSQL Schema
-- Run once to create the database, then use Flask-Migrate for changes.

CREATE DATABASE smartxray;
\c smartxray;

-- ── 1. users ───────────────────────────────────────────────────────────────
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    tier            VARCHAR(20)  NOT NULL DEFAULT 'free',   -- free | pro
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN      NOT NULL DEFAULT FALSE,
    avatar_url      VARCHAR(512),
    scans_today     INTEGER      NOT NULL DEFAULT 0,
    scans_reset_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_users_email ON users(email);

-- ── 2. subscriptions ───────────────────────────────────────────────────────
CREATE TABLE subscriptions (
    id                      SERIAL PRIMARY KEY,
    user_id                 INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stripe_customer_id      VARCHAR(255) UNIQUE,
    stripe_subscription_id  VARCHAR(255) UNIQUE,
    stripe_price_id         VARCHAR(255),
    plan                    VARCHAR(20)  NOT NULL,              -- monthly | yearly
    status                  VARCHAR(30)  NOT NULL DEFAULT 'inactive',
    current_period_start    TIMESTAMPTZ,
    current_period_end      TIMESTAMPTZ,
    cancel_at_period_end    BOOLEAN DEFAULT FALSE,
    canceled_at             TIMESTAMPTZ,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ── 3. reports ─────────────────────────────────────────────────────────────
CREATE TABLE reports (
    id                 SERIAL PRIMARY KEY,
    user_id            INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    file_path          VARCHAR(512) NOT NULL,
    file_size          INTEGER,
    title              VARCHAR(255) DEFAULT 'SmartX-Ray Diagnostic Report',
    summary            TEXT,
    is_pro             BOOLEAN NOT NULL DEFAULT TRUE,
    download_count     INTEGER NOT NULL DEFAULT 0,
    last_downloaded_at TIMESTAMPTZ,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_reports_user ON reports(user_id);

-- ── 4. scans ───────────────────────────────────────────────────────────────
CREATE TABLE scans (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    image_path      VARCHAR(512) NOT NULL,
    heatmap_path    VARCHAR(512),
    prediction      VARCHAR(50)  NOT NULL,   -- PNEUMONIA | NORMAL
    confidence      FLOAT        NOT NULL,   -- 0.0 – 1.0
    raw_score       FLOAT,
    model_version   VARCHAR(50)  DEFAULT 'v1.0',
    gradcam_status  VARCHAR(20)  DEFAULT 'pending',  -- pending | done | failed
    report_id       INTEGER REFERENCES reports(id) ON DELETE SET NULL,
    notes           TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_scans_user ON scans(user_id);
CREATE INDEX idx_scans_created ON scans(created_at DESC);

-- ── 5. ads ─────────────────────────────────────────────────────────────────
CREATE TABLE ads (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(255) NOT NULL,
    body        TEXT         NOT NULL,
    image_url   VARCHAR(512),
    target_url  VARCHAR(512) NOT NULL,
    advertiser  VARCHAR(255),
    placement   VARCHAR(50)  NOT NULL DEFAULT 'banner',
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    start_date  TIMESTAMPTZ,
    end_date    TIMESTAMPTZ,
    impressions INTEGER      NOT NULL DEFAULT 0,
    clicks      INTEGER      NOT NULL DEFAULT 0,
    priority    INTEGER      NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_ads_placement_active ON ads(placement, is_active);

-- ── 6. doctors ─────────────────────────────────────────────────────────────
CREATE TABLE doctors (
    id              SERIAL PRIMARY KEY,
    full_name       VARCHAR(255) NOT NULL,
    specialty       VARCHAR(255) NOT NULL,
    qualifications  VARCHAR(512),
    hospital        VARCHAR(255),
    city            VARCHAR(100),
    country         VARCHAR(100),
    phone           VARCHAR(50),
    email           VARCHAR(255),
    website         VARCHAR(512),
    bio             TEXT,
    avatar_url      VARCHAR(512),
    google_maps_url VARCHAR(1024),
    rating          FLOAT        DEFAULT 0.0,
    review_count    INTEGER      DEFAULT 0,
    is_verified     BOOLEAN      NOT NULL DEFAULT FALSE,
    is_featured     BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_doctors_specialty ON doctors(specialty);
CREATE INDEX idx_doctors_city      ON doctors(city);

-- ── 7. transactions ────────────────────────────────────────────────────────
CREATE TABLE transactions (
    id                       SERIAL PRIMARY KEY,
    user_id                  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    stripe_payment_intent_id VARCHAR(255) UNIQUE,
    stripe_invoice_id        VARCHAR(255),
    stripe_customer_id       VARCHAR(255),
    amount                   NUMERIC(10, 2) NOT NULL,
    currency                 VARCHAR(10)    NOT NULL DEFAULT 'usd',
    product_type             VARCHAR(50)    NOT NULL,
    plan                     VARCHAR(20),
    status                   VARCHAR(30)    NOT NULL DEFAULT 'pending',
    failure_reason           VARCHAR(255),
    receipt_url              VARCHAR(512),
    created_at               TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_transactions_user   ON transactions(user_id);
CREATE INDEX idx_transactions_status ON transactions(status);

-- ── Seed data: sample ads ──────────────────────────────────────────────────
INSERT INTO ads (title, body, target_url, advertiser, placement, priority) VALUES
    ('Upgrade to Pro', 'Unlock PDF reports, unlimited scans & priority support.',
     '/pricing', 'SmartX-Ray', 'banner', 10),
    ('Find a Specialist', 'Connect with top pulmonologists near you.',
     '/marketplace', 'SmartX-Ray', 'result_page', 5);
