from datetime import datetime, timezone
from app.extensions import db


class SystemLog(db.Model):
    __tablename__ = "system_logs"

    id            = db.Column(db.Integer, primary_key=True)

    # event_type: scan | health_check | auth_login | auth_fail |
    #             admin_action | telegram_alert | error
    event_type    = db.Column(db.String(50), nullable=False, index=True)

    # severity: info | warning | high | critical
    severity      = db.Column(db.String(20), nullable=False, default="info", index=True)

    user_id       = db.Column(db.Integer,
                              db.ForeignKey("users.id", ondelete="SET NULL"),
                              nullable=True, index=True)
    scan_id       = db.Column(db.Integer,
                              db.ForeignKey("scans.id", ondelete="SET NULL"),
                              nullable=True)

    message       = db.Column(db.Text, nullable=False)
    processing_ms = db.Column(db.Integer)           # AI inference time (ms)
    ip_address    = db.Column(db.String(45))        # IPv4 or IPv6
    user_agent    = db.Column(db.String(512))
    extra         = db.Column(db.JSON)              # arbitrary context dict

    created_at    = db.Column(db.DateTime(timezone=True),
                              default=lambda: datetime.now(timezone.utc),
                              index=True)

    # ── Relationships ──────────────────────────────────────────────────────
    user = db.relationship("User", foreign_keys=[user_id], lazy="joined")
    scan = db.relationship("Scan", foreign_keys=[scan_id], lazy="joined")

    # ── Factory helpers ────────────────────────────────────────────────────
    @classmethod
    def log_scan(cls, scan, user, processing_ms: int, ip: str = None) -> "SystemLog":
        """Create a log entry for a completed scan."""
        confidence_pct = round(scan.confidence * 100, 1)
        severity = "high" if (
            scan.prediction == "PNEUMONIA" and scan.confidence >= 0.80
        ) else "info"
        return cls(
            event_type=    "scan",
            severity=      severity,
            user_id=       user.id,
            scan_id=       scan.id,
            message=       (
                f"{scan.prediction} detected ({confidence_pct}%) "
                f"for {user.email}"
            ),
            processing_ms= processing_ms,
            ip_address=    ip,
            extra={
                "prediction":  scan.prediction,
                "confidence":  scan.confidence,
                "model_version": scan.model_version,
            },
        )

    @classmethod
    def log_auth(cls, event: str, user_id: int = None, ip: str = None,
                 message: str = "") -> "SystemLog":
        """Create a log entry for an authentication event."""
        return cls(
            event_type=event,
            severity=  "warning" if "fail" in event else "info",
            user_id=   user_id,
            message=   message or event,
            ip_address=ip,
        )

    # ── Serialisation ──────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "event_type":    self.event_type,
            "severity":      self.severity,
            "user_id":       self.user_id,
            "user_email":    self.user.email if self.user else None,
            "scan_id":       self.scan_id,
            "message":       self.message,
            "processing_ms": self.processing_ms,
            "ip_address":    self.ip_address,
            "extra":         self.extra or {},
            "created_at":    self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<SystemLog {self.id} [{self.severity}] {self.event_type}>"
