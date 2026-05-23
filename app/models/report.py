from datetime import datetime, timezone
from app.extensions import db


class Report(db.Model):
    __tablename__ = "reports"

    id                 = db.Column(db.Integer, primary_key=True)
    user_id            = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                                   nullable=False, index=True)

    # PDF file (path relative to static/)
    file_path          = db.Column(db.String(512), nullable=False)
    file_size          = db.Column(db.Integer)                          # bytes

    # Metadata
    title              = db.Column(db.String(255), default="SmartX-Ray Diagnostic Report")
    summary            = db.Column(db.Text)
    is_pro             = db.Column(db.Boolean, default=True, nullable=False)  # always True — Pro only

    # Download tracking
    download_count     = db.Column(db.Integer, default=0, nullable=False)
    last_downloaded_at = db.Column(db.DateTime(timezone=True))

    created_at         = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # ── Relationships ──────────────────────────────────────────────────────
    user  = db.relationship("User",  back_populates="reports")
    scans = db.relationship("Scan",  back_populates="report",
                            foreign_keys="[Scan.report_id]", lazy="dynamic")

    def to_dict(self) -> dict:
        return {
            "id":             self.id,
            "title":          self.title,
            "file_size":      self.file_size,
            "download_count": self.download_count,
            "created_at":     self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Report {self.id} user={self.user_id}>"
