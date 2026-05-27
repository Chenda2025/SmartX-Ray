from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id             = db.Column(db.Integer, primary_key=True)
    email          = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash  = db.Column(db.String(255), nullable=False)
    full_name      = db.Column(db.String(255), nullable=False)
    tier           = db.Column(db.String(20), nullable=False, default="free")  # free | pro
    is_active      = db.Column(db.Boolean, default=True, nullable=False)
    is_verified    = db.Column(db.Boolean, default=False, nullable=False)
    is_admin       = db.Column(db.Boolean, default=False, nullable=False)
    role           = db.Column(db.String(20), nullable=False, default="patient")  # patient | admin
    university     = db.Column(db.String(100))  # RUPP | IU | NUM | AUSF | UHS | other
    avatar_url     = db.Column(db.String(512))
    scans_today    = db.Column(db.Integer, default=0, nullable=False)
    scans_reset_at = db.Column(db.DateTime(timezone=True))
    created_at     = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at     = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                               onupdate=lambda: datetime.now(timezone.utc))

    # ── Relationships ──────────────────────────────────────────────────────
    scans        = db.relationship("Scan",         back_populates="user", lazy="dynamic")
    subscription = db.relationship("Subscription", back_populates="user", uselist=False)
    reports      = db.relationship("Report",       back_populates="user", lazy="dynamic")
    transactions = db.relationship("Transaction",  back_populates="user", lazy="dynamic")

    # ── Auth helpers ───────────────────────────────────────────────────────
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_pro(self) -> bool:
        return self.tier == "pro"

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "email":       self.email,
            "full_name":   self.full_name,
            "tier":        self.tier,
            "role":        self.role,
            "is_active":   self.is_active,
            "is_admin":    self.is_admin,
            "university":  self.university,
            "avatar_url":  self.avatar_url,
            "scans_today": self.scans_today,
            "created_at":  self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<User {self.email} [{self.tier}]>"
