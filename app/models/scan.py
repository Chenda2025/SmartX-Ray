from datetime import datetime, timezone
from app.extensions import db


class Scan(db.Model):
    __tablename__ = "scans"

    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                               nullable=False, index=True)

    # File paths (relative to static/)
    image_path     = db.Column(db.String(512), nullable=False)
    heatmap_path   = db.Column(db.String(512))

    # AI prediction results
    prediction     = db.Column(db.String(50), nullable=False)   # PNEUMONIA | NORMAL
    confidence     = db.Column(db.Float, nullable=False)         # 0.0 – 1.0
    raw_score      = db.Column(db.Float)                         # raw sigmoid output
    model_version  = db.Column(db.String(50), default="v1.0")

    # Grad-CAM status
    gradcam_status = db.Column(db.String(20), default="pending")  # pending | done | failed

    # Report link (nullable — Pro only)
    report_id      = db.Column(db.Integer, db.ForeignKey("reports.id", ondelete="SET NULL"))

    # Metadata
    notes          = db.Column(db.Text)
    created_at     = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # ── Relationships ──────────────────────────────────────────────────────
    user   = db.relationship("User",   back_populates="scans")
    report = db.relationship("Report", back_populates="scans", foreign_keys=[report_id])

    def to_dict(self, include_paths: bool = False) -> dict:
        data = {
            "id":            self.id,
            "prediction":    self.prediction,
            "confidence":    round(self.confidence * 100, 2),
            "model_version": self.model_version,
            "gradcam_status": self.gradcam_status,
            "created_at":    self.created_at.isoformat() if self.created_at else None,
        }
        if include_paths:
            data["image_path"]   = self.image_path
            data["heatmap_path"] = self.heatmap_path
        return data

    def __repr__(self) -> str:
        return f"<Scan {self.id} user={self.user_id} result={self.prediction} {self.confidence:.2%}>"
