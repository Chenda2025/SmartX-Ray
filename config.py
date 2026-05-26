import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # ── Core ──────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    DEBUG = False
    TESTING = False

    # ── Database ───────────────────────────────────────────────────────────
    # Render provides postgres:// but SQLAlchemy 2.x requires postgresql://
    _db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/smartxray",
    )
    SQLALCHEMY_DATABASE_URI = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── JWT ────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # ── File uploads ───────────────────────────────────────────────────────
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    HEATMAP_FOLDER = os.path.join(BASE_DIR, "static", "heatmaps")
    REPORT_FOLDER = os.path.join(BASE_DIR, "static", "reports")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

    # ── AI model ───────────────────────────────────────────────────────────
    MODEL_PATH = os.path.join(BASE_DIR, "models", "best_model.h5")
    IMAGE_SIZE = (224, 224)

    # ── Stripe ─────────────────────────────────────────────────────────────
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_MONTHLY = os.environ.get("STRIPE_PRICE_MONTHLY", "")   # $9.99/mo
    STRIPE_PRICE_YEARLY = os.environ.get("STRIPE_PRICE_YEARLY", "")     # $79.99/yr

    # ── Mail ───────────────────────────────────────────────────────────────
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@smartxray.com")

    # ── Redis / Celery ─────────────────────────────────────────────────────
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL

    # ── Telegram bot alerts ────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

    # Admin JWT: separate 8-hour expiry
    ADMIN_JWT_EXPIRES = timedelta(hours=8)

    # Cambodia universities whitelist
    CAMBODIA_UNIVERSITIES = ["RUPP", "IU", "NUM", "AUSF", "UHS", "other"]

    # Pneumonia high-severity threshold (triggers Telegram alert)
    PNEUMONIA_HIGH_SEVERITY_THRESHOLD = 0.80

    # ── Business rules ─────────────────────────────────────────────────────
    FREE_SCANS_PER_DAY = 3
    SUBSCRIPTION_MONTHLY_PRICE = 9.99
    SUBSCRIPTION_YEARLY_PRICE = 79.99


class DevelopmentConfig(Config):
    DEBUG = True
    # Suppress email sending when SMTP credentials are not configured locally
    MAIL_SUPPRESS_SEND = not bool(os.environ.get("MAIL_USERNAME"))


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://admin:121314@localhost:5432/smartxray_test",
    )
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
    # Suppress email/Stripe side-effects during tests
    MAIL_SUPPRESS_SEND = True
    STRIPE_SECRET_KEY = "sk_test_fake"


class ProductionConfig(Config):
    DEBUG = False


config_map = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
