from datetime import datetime, timezone
from app.extensions import db


class Doctor(db.Model):
    __tablename__ = "doctors"

    id              = db.Column(db.Integer, primary_key=True)
    full_name       = db.Column(db.String(255), nullable=False)
    specialty       = db.Column(db.String(255), nullable=False)   # e.g. Pulmonologist
    qualifications  = db.Column(db.String(512))                   # MBBS, MD, etc.
    hospital        = db.Column(db.String(255))
    city            = db.Column(db.String(100))
    country         = db.Column(db.String(100))
    phone           = db.Column(db.String(50))
    email           = db.Column(db.String(255))
    website         = db.Column(db.String(512))
    bio             = db.Column(db.Text)
    avatar_url      = db.Column(db.String(512))
    google_maps_url = db.Column(db.String(1024))

    # Rating (aggregate — updated via trigger or app logic)
    rating          = db.Column(db.Float, default=0.0)
    review_count    = db.Column(db.Integer, default=0)

    # Doctor-portal fields (used by /doctor/dashboard)
    license_no        = db.Column(db.String(100))
    rate_per_session  = db.Column(db.Float, default=0.0)       # USD per session
    availability      = db.Column(db.String(255))              # e.g. "Mon–Fri 9–5"
    rejection_reason  = db.Column(db.Text)                     # set by admin on reject

    # Visibility flags
    is_verified     = db.Column(db.Boolean, default=False, nullable=False)
    is_featured     = db.Column(db.Boolean, default=False, nullable=False)
    is_active       = db.Column(db.Boolean, default=True, nullable=False)

    created_at      = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at      = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                                onupdate=lambda: datetime.now(timezone.utc))

    @property
    def status(self) -> str:
        """Derive dashboard state from flags."""
        if self.is_verified and self.is_active:
            return "approved"
        if self.is_active:
            return "pending"
        return "rejected"

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "full_name":        self.full_name,
            "specialty":        self.specialty,
            "qualifications":   self.qualifications,
            "license_no":       self.license_no,
            "hospital":         self.hospital,
            "city":             self.city,
            "country":          self.country,
            "phone":            self.phone,
            "email":            self.email,
            "website":          self.website,
            "bio":              self.bio,
            "avatar_url":       self.avatar_url,
            "google_maps_url":  self.google_maps_url,
            "rating":           self.rating,
            "review_count":     self.review_count,
            "rate_per_session": self.rate_per_session,
            "availability":     self.availability,
            "rejection_reason": self.rejection_reason,
            "is_verified":      self.is_verified,
            "is_featured":      self.is_featured,
            "is_active":        self.is_active,
            "status":           self.status,
            "created_at":       self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Doctor {self.id} '{self.full_name}' {self.specialty}>"
