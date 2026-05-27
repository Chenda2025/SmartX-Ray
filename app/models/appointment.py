from datetime import datetime, timezone
from app.extensions import db


class Appointment(db.Model):
    __tablename__ = "appointments"

    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey("users.id",   ondelete="CASCADE"), nullable=False)
    doctor_id        = db.Column(db.Integer, db.ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False)

    # Original booking fields
    appointment_date = db.Column(db.Date,       nullable=False)
    appointment_time = db.Column(db.String(20), nullable=False)   # e.g. "09:00 AM"
    note             = db.Column(db.Text)
    status           = db.Column(db.String(20), nullable=False, default="confirmed")
    fee_snapshot     = db.Column(db.Float,      nullable=False, default=0.0)

    # Extended fields — added by migration c004
    patient_id       = db.Column(db.Integer, nullable=True)        # denormalised copy of user_id
    scheduled_at     = db.Column(db.DateTime(timezone=True))       # parsed datetime of appointment
    duration_min     = db.Column(db.Integer, default=30)           # session length in minutes
    patient_note     = db.Column(db.Text)                          # patient's pre-consultation note
    fee_amount       = db.Column(db.Numeric(10, 2))                # final fee (may differ from snapshot)
    meeting_link     = db.Column(db.String(512))                   # Google Meet / video link
    payment_method   = db.Column(db.String(50), default="ABA KHQR")
    payment_status   = db.Column(db.String(20), default="paid")

    created_at       = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user   = db.relationship("User",   backref=db.backref("appointments", lazy="dynamic", passive_deletes=True))
    doctor = db.relationship("Doctor", backref=db.backref("appointments", lazy="dynamic", passive_deletes=True))

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "user_id":          self.user_id,
            "doctor_id":        self.doctor_id,
            "doctor_name":      self.doctor.full_name if self.doctor else "—",
            "doctor_specialty": self.doctor.specialty  if self.doctor else "—",
            "appointment_date": self.appointment_date.isoformat(),
            "appointment_time": self.appointment_time,
            "scheduled_at":     self.scheduled_at.isoformat() if self.scheduled_at else None,
            "duration_min":     self.duration_min,
            "note":             self.patient_note or self.note,
            "status":           self.status,
            "fee_amount":       float(self.fee_amount if self.fee_amount is not None else self.fee_snapshot if self.fee_snapshot is not None else 0),
            "meeting_link":     self.meeting_link,
            "payment_method":   self.payment_method,
            "payment_status":   self.payment_status,
            "created_at":       self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Appointment {self.id} user={self.user_id} doctor={self.doctor_id} {self.appointment_date} {self.status}>"
