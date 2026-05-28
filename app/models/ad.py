from datetime import datetime, timezone
from app.extensions import db


class Ad(db.Model):
    __tablename__ = "ads"

    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(255), nullable=False)
    body        = db.Column(db.Text, nullable=False)
    image_url   = db.Column(db.String(512))
    target_url  = db.Column(db.String(512), nullable=False)
    advertiser  = db.Column(db.String(255))

    # Placement: banner | sidebar | interstitial | result_page
    placement   = db.Column(db.String(50), nullable=False, default="banner")

    # Scheduling
    is_active   = db.Column(db.Boolean, default=True, nullable=False)
    start_date  = db.Column(db.DateTime(timezone=True))
    end_date    = db.Column(db.DateTime(timezone=True))

    # Analytics
    impressions = db.Column(db.Integer, default=0, nullable=False)
    clicks      = db.Column(db.Integer, default=0, nullable=False)

    # Higher priority ads are served first
    priority    = db.Column(db.Integer, default=0, nullable=False)

    created_at  = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at  = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))

    @property
    def ctr(self) -> float:
        return round(self.clicks / self.impressions, 4) if self.impressions else 0.0

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "title":      self.title,
            "body":       self.body,
            "image_url":  self.image_url,
            "target_url": self.target_url,
            "advertiser": self.advertiser,
            "placement":  self.placement,
        }

    def __repr__(self) -> str:
        return f"<Ad {self.id} '{self.title}' placement={self.placement}>"
