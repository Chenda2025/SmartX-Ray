# app/utils/__init__.py
# Convenience re-exports so routes can import from the package directly.
#
#   from app.utils import admin_required, doctor_required
#   from app.utils import send_telegram_alert, generate_meeting_link

from app.utils.auth_guard import (   # noqa: F401
    admin_required,
    doctor_required,
    patient_required,
    pro_required,
)
from app.utils.notifications import (  # noqa: F401
    send_telegram_alert,
    generate_meeting_link,
    alert_new_doctor_registration,
    alert_doctor_approved,
    alert_doctor_rejected,
    alert_new_appointment,
    alert_high_severity_scan,
    send_email_to_doctor,
    send_email_to_patient,
    email_doctor_application_received,
    email_doctor_approved,
    email_doctor_rejected,
    email_doctor_new_appointment,
    email_patient_appointment_confirmed,
    email_patient_appointment_cancelled,
    email_patient_review_request,
)
