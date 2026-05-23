from datetime import datetime, timezone
from app.extensions import db


class Subscription(db.Model):
    __tablename__ = "subscriptions"

    id                       = db.Column(db.Integer, primary_key=True)
    user_id                  = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                                         nullable=False, unique=True, index=True)

    # Stripe identifiers
    stripe_customer_id       = db.Column(db.String(255), unique=True)
    stripe_subscription_id   = db.Column(db.String(255), unique=True)
    stripe_price_id          = db.Column(db.String(255))

    # Plan
    plan                     = db.Column(db.String(20), nullable=False)   # monthly | yearly
    status                   = db.Column(db.String(30), nullable=False, default="inactive")
    # inactive | active | past_due | canceled | trialing

    # Billing cycle
    current_period_start     = db.Column(db.DateTime(timezone=True))
    current_period_end       = db.Column(db.DateTime(timezone=True))
    cancel_at_period_end     = db.Column(db.Boolean, default=False)
    canceled_at              = db.Column(db.DateTime(timezone=True))

    created_at               = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at               = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                                         onupdate=lambda: datetime.now(timezone.utc))

    # ── Relationships ──────────────────────────────────────────────────────
    user = db.relationship("User", back_populates="subscription")

    @property
    def is_active(self) -> bool:
        return self.status in ("active", "trialing")

    def to_dict(self) -> dict:
        return {
            "id":                   self.id,
            "plan":                 self.plan,
            "status":               self.status,
            "current_period_end":   self.current_period_end.isoformat() if self.current_period_end else None,
            "cancel_at_period_end": self.cancel_at_period_end,
        }

    def __repr__(self) -> str:
        return f"<Subscription user={self.user_id} plan={self.plan} status={self.status}>"
