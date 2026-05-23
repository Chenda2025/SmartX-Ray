from datetime import datetime, timezone
from app.extensions import db


class Transaction(db.Model):
    __tablename__ = "transactions"

    id                       = db.Column(db.Integer, primary_key=True)
    user_id                  = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"),
                                         nullable=True, index=True)

    # Stripe references
    stripe_payment_intent_id = db.Column(db.String(255), unique=True)
    stripe_invoice_id        = db.Column(db.String(255))
    stripe_customer_id       = db.Column(db.String(255))

    # Amount
    amount           = db.Column(db.Numeric(10, 2), nullable=False)  # e.g. 9.99
    currency         = db.Column(db.String(10), default="usd", nullable=False)

    # What was purchased
    product_type     = db.Column(db.String(50), nullable=False)
    # subscription_monthly | subscription_yearly | report_one_off

    plan             = db.Column(db.String(20))   # monthly | yearly

    # Status
    status           = db.Column(db.String(30), nullable=False, default="pending")
    # pending | succeeded | failed | refunded

    failure_reason   = db.Column(db.String(255))
    receipt_url      = db.Column(db.String(512))

    created_at       = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at       = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                                 onupdate=lambda: datetime.now(timezone.utc))

    # ── Relationships ──────────────────────────────────────────────────────
    user = db.relationship("User", back_populates="transactions")

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "amount":       float(self.amount),
            "currency":     self.currency,
            "product_type": self.product_type,
            "status":       self.status,
            "receipt_url":  self.receipt_url,
            "created_at":   self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Transaction {self.id} user={self.user_id} {self.amount}{self.currency} {self.status}>"
