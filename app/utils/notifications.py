"""
app/utils/notifications.py — Unified notification facade
══════════════════════════════════════════════════════════════════════════════
Single import point for all notification calls made from routes.

Delegates to:
  • app/services/telegram_service.py  — Telegram Bot API
  • app/services/email_service.py     — Flask-Mail / SMTP

════════════════════════════════════════════════════════════════════════════
TELEGRAM  (admin receives all alerts)
  send_telegram_alert(message)               — generic raw alert
  alert_new_doctor_registration(doctor,user) — new application submitted
  alert_doctor_approved(doctor, admin_name)  — doctor was approved
  alert_doctor_rejected(doctor, reason, ...)  — doctor was rejected
  alert_new_appointment(apt, patient, doctor) — appointment booked
  alert_high_severity_scan(scan, user)       — ≥ 85% PNEUMONIA (re-export)

EMAIL → DOCTOR
  send_email_to_doctor(email, subject, body) — generic
  email_doctor_application_received(doctor)  — "We got your application"
  email_doctor_approved(doctor, login_url)   — "You are approved — login here"
  email_doctor_rejected(doctor, reason)      — "Application rejected + reason"
  email_doctor_new_appointment(doctor, apt, patient) — new booking

EMAIL → PATIENT
  send_email_to_patient(email, subject, body) — generic
  email_patient_appointment_confirmed(patient, apt, doctor)
  email_patient_appointment_cancelled(patient, apt, doctor)
  email_patient_review_request(patient, apt, doctor)

UTILS
  generate_meeting_link(appointment_id)      — mock Google Meet URL
══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── base URL for email links (override via APP_BASE_URL env var) ──────────────
_BASE_URL = "http://localhost:5000"

try:
    from flask import current_app
    _BASE_URL = current_app.config.get("APP_BASE_URL", _BASE_URL)
except Exception:
    pass


# ════════════════════════════════════════════════════════════════════════════
#  UTILS
# ════════════════════════════════════════════════════════════════════════════

def generate_meeting_link(appointment_id: int) -> str:
    """
    Return a mock Google Meet link for the given appointment.
    In production, replace with a real Google Meet / Zoom API call.

    Format: https://meet.google.com/smx-<zero-padded id>
    """
    padded = str(appointment_id).zfill(3)
    return f"https://meet.google.com/smx-{padded}"


def _ts() -> str:
    """Return current UTC timestamp as a formatted string."""
    return datetime.now(timezone.utc).strftime("%d %b %Y  %H:%M UTC")


def _base_url() -> str:
    """Return the app base URL from config (with runtime lookup)."""
    try:
        from flask import current_app
        return current_app.config.get("APP_BASE_URL", _BASE_URL)
    except Exception:
        return _BASE_URL


# ════════════════════════════════════════════════════════════════════════════
#  TELEGRAM NOTIFICATIONS
# ════════════════════════════════════════════════════════════════════════════

def send_telegram_alert(message: str) -> bool:
    """
    Send a raw HTML message to the admin Telegram chat.
    Wrapper around telegram_service._send / send_telegram_alert.
    """
    try:
        from app.services.telegram_service import send_telegram_alert as _tg_send
        return _tg_send(message)
    except Exception as exc:
        logger.warning("send_telegram_alert failed: %s", exc)
        return False


def alert_new_doctor_registration(doctor, user) -> None:
    """
    Bilingual (EN + KH) Telegram alert when a doctor submits a new application.
    Triggered by POST /api/doctor/register.
    """
    ts  = _ts()
    url = f"{_base_url()}/admin/marketplace"

    msg = (
        "🩺 <b>NEW DOCTOR APPLICATION</b>\n"
        "🩺 <b>ពាក្យស្នើតួវេជ្ជបណ្ឌិតថ្មី</b>\n"
        "─────────────────────────\n\n"
        "👤 <b>Name / ឈ្មោះ:</b>  {name}\n"
        "🏥 <b>Specialty / ជំនាញ:</b>  {specialty}\n"
        "🎓 <b>University / សាកលវិទ្យាល័យ:</b>  {uni}\n"
        "🪪 <b>License / អាជ្ញាបណ្ណ:</b>  <code>{license}</code>\n"
        "📧 <b>Email:</b>  <code>{email}</code>\n\n"
        "🕐 <b>Submitted / ដាក់ស្នើ:</b>  {ts}\n\n"
        "─────────────────────────\n"
        "👉 <a href='{url}'>Review application in Admin Panel →</a>"
    ).format(
        name     = getattr(doctor, "full_name",      "—"),
        specialty= getattr(doctor, "specialty",      "—"),
        uni      = getattr(doctor, "university",     "—"),
        license  = getattr(doctor, "license_number", None)
                   or getattr(doctor, "license_no",  "—"),
        email    = getattr(user, "email",            "—"),
        ts       = ts,
        url      = url,
    )
    send_telegram_alert(msg)


def alert_doctor_approved(doctor, admin_name: str = "Admin") -> None:
    """
    Bilingual Telegram alert when a doctor is approved.
    Triggered by PATCH /api/admin/doctors/<id>/approve.
    """
    ts = _ts()
    msg = (
        "✅ <b>DOCTOR APPROVED</b>\n"
        "✅ <b>វេជ្ជបណ្ឌិតត្រូវបានអនុម័ត</b>\n"
        "─────────────────────────\n\n"
        "👤 <b>Doctor / វេជ្ជបណ្ឌិត:</b>  {name}\n"
        "🏥 <b>Specialty / ជំនាញ:</b>  {specialty}\n"
        "🎓 <b>University / សាកលវិទ្យាល័យ:</b>  {uni}\n\n"
        "👮 <b>Approved by / អនុម័តដោយ:</b>  {admin}\n"
        "🕐 <b>Time / ពេលវេលា:</b>  {ts}"
    ).format(
        name     = getattr(doctor, "full_name",  "—"),
        specialty= getattr(doctor, "specialty",  "—"),
        uni      = getattr(doctor, "university", "—"),
        admin    = admin_name,
        ts       = ts,
    )
    send_telegram_alert(msg)


def alert_doctor_rejected(
    doctor,
    reason: str,
    admin_name: str = "Admin",
) -> None:
    """
    Bilingual Telegram alert when a doctor application is rejected.
    Triggered by PATCH /api/admin/doctors/<id>/reject.
    """
    ts     = _ts()
    reason = (reason or "No reason provided.")[:200]
    msg = (
        "❌ <b>DOCTOR APPLICATION REJECTED</b>\n"
        "❌ <b>ពាក្យស្នើតួវេជ្ជបណ្ឌិតត្រូវបានបដិសេធ</b>\n"
        "─────────────────────────\n\n"
        "👤 <b>Doctor / វេជ្ជបណ្ឌិត:</b>  {name}\n"
        "🏥 <b>Specialty / ជំនាញ:</b>  {specialty}\n\n"
        "💬 <b>Reason / ហេតុផល:</b>\n"
        "<i>{reason}</i>\n\n"
        "👮 <b>Rejected by / បដិសេធដោយ:</b>  {admin}\n"
        "🕐 <b>Time / ពេលវេលា:</b>  {ts}"
    ).format(
        name     = getattr(doctor, "full_name",  "—"),
        specialty= getattr(doctor, "specialty",  "—"),
        reason   = reason,
        admin    = admin_name,
        ts       = ts,
    )
    send_telegram_alert(msg)


def alert_new_appointment(appointment, patient, doctor) -> None:
    """
    Telegram alert to admin when a new appointment is booked.
    Triggered by POST /api/appointments/book.
    """
    ts = _ts()

    # Handle both old and new appointment date formats
    sched = getattr(appointment, "scheduled_at", None)
    if sched:
        date_str = sched.strftime("%d %b %Y  %H:%M") if hasattr(sched, "strftime") else str(sched)
    else:
        apt_date = getattr(appointment, "appointment_date", "—")
        apt_time = getattr(appointment, "appointment_time", "—")
        date_str = f"{apt_date}  {apt_time}"

    fee = (
        getattr(appointment, "fee_amount",   None)
        or getattr(appointment, "fee_snapshot", 0.0)
    )
    msg = (
        "📅 <b>NEW APPOINTMENT BOOKED</b>\n"
        "📅 <b>ណាត់ជួបថ្មីត្រូវបានកក់</b>\n"
        "─────────────────────────\n\n"
        "🧑‍⚕️ <b>Doctor / វេជ្ជបណ្ឌិត:</b>  {doctor}\n"
        "👤 <b>Patient / អ្នកជំងឺ:</b>  {patient}\n"
        "🗓 <b>Date &amp; Time / កាលបរិច្ឆេទ:</b>  {date}\n"
        "💵 <b>Fee / ថ្លៃ:</b>  ${fee:.2f}\n"
        "💳 <b>Payment / ការទូទាត់:</b>  ABA KHQR\n\n"
        "🕐 <b>Booked at:</b>  {ts}"
    ).format(
        doctor  = getattr(doctor,  "full_name", "—"),
        patient = getattr(patient, "full_name", getattr(patient, "email", "—")),
        date    = date_str,
        fee     = float(fee or 0),
        ts      = ts,
    )
    send_telegram_alert(msg)


def alert_high_severity_scan(scan, user) -> None:
    """
    Re-export of the existing high-severity scan alert.
    Kept here so routes can import everything from one place.
    """
    try:
        from app.services.telegram_service import alert_high_severity_pneumonia
        alert_high_severity_pneumonia(scan, user)
    except Exception as exc:
        logger.warning("alert_high_severity_scan failed: %s", exc)


# ════════════════════════════════════════════════════════════════════════════
#  EMAIL — GENERIC WRAPPERS
# ════════════════════════════════════════════════════════════════════════════

def send_email_to_doctor(doctor_email: str, subject: str, body: str) -> None:
    """
    Send a plain-body email to a doctor.
    Wraps body in a simple SmartX-Ray branded HTML frame.
    """
    _send_html(
        recipients = [doctor_email],
        subject    = subject,
        html       = _wrap_email(body, subject),
    )


def send_email_to_patient(patient_email: str, subject: str, body: str) -> None:
    """
    Send a plain-body email to a patient.
    Wraps body in the SmartX-Ray branded HTML frame.
    """
    _send_html(
        recipients = [patient_email],
        subject    = subject,
        html       = _wrap_email(body, subject),
    )


# ════════════════════════════════════════════════════════════════════════════
#  EMAIL — DOCTOR-SPECIFIC
# ════════════════════════════════════════════════════════════════════════════

def email_doctor_application_received(doctor) -> None:
    """
    Sent when a doctor submits an application (status = pending).
    Triggered by POST /api/doctor/register.
    """
    name  = getattr(doctor, "full_name", "Doctor")
    email = getattr(doctor, "email", None)
    if not email:
        return

    html = f"""
<h2 style="color:#0ea5e9;">Application Received — SmartX-Ray</h2>
<p>Dear <strong>{name}</strong>,</p>
<p>Thank you for submitting your application to join SmartX-Ray as a verified doctor.</p>

<div style="background:#f0f9ff;border-left:4px solid #0ea5e9;padding:16px;border-radius:6px;margin:20px 0;">
  <p style="margin:0;font-weight:600;">⏳ Your application is currently under review.</p>
  <p style="margin:8px 0 0;">An admin will review your submission within <strong>24 hours</strong>.
  You will receive a separate email once a decision has been made.</p>
</div>

<p><strong>What happens next?</strong></p>
<ol>
  <li>Admin reviews your license and credentials</li>
  <li>You receive an approval or rejection email</li>
  <li>If approved, you can log in and start accepting patient bookings</li>
</ol>

<p>If you have any questions, contact us at
<a href="mailto:admin@smartxray.kh">admin@smartxray.kh</a>.</p>
"""
    _send_html([email], "Application Received — SmartX-Ray", _wrap_email(html, "Application Received"))


def email_doctor_approved(doctor, login_url: str = "") -> None:
    """
    Sent when admin approves the doctor's application.
    Triggered by PATCH /api/admin/doctors/<id>/approve.
    """
    name  = getattr(doctor, "full_name", "Doctor")
    email = getattr(doctor, "email",     None)
    if not email:
        return

    url   = login_url or f"{_base_url()}/doctor/login"
    rate  = getattr(doctor, "rate_per_session", 0)

    html = f"""
<h2 style="color:#22c55e;">🎉 You Are Approved — SmartX-Ray</h2>
<p>Dear <strong>{name}</strong>,</p>

<div style="background:#f0fdf4;border-left:4px solid #22c55e;padding:16px;border-radius:6px;margin:20px 0;">
  <p style="margin:0;font-weight:600;">✅ Your application has been approved!</p>
  <p style="margin:8px 0 0;">You are now a verified doctor on SmartX-Ray.
  Patients can find and book consultations with you on the marketplace.</p>
</div>

<p><strong>Your account details:</strong></p>
<ul>
  <li>Login email: <code>{email}</code></li>
  <li>Session rate: <strong>${rate:.2f} USD</strong></li>
  <li>Payment method: ABA KHQR</li>
</ul>

<p style="margin:24px 0;">
  <a href="{url}" style="background:#0ea5e9;color:white;padding:12px 28px;
     border-radius:8px;text-decoration:none;font-weight:600;font-size:15px;">
    Login to Your Dashboard →
  </a>
</p>

<p style="color:#64748b;font-size:13px;">
  If the button doesn't work, copy this link:<br>
  <code>{url}</code>
</p>
"""
    _send_html([email], "You Are Approved — SmartX-Ray", _wrap_email(html, "Approved!"))


def email_doctor_rejected(doctor, reason: str) -> None:
    """
    Sent when admin rejects the doctor's application.
    Triggered by PATCH /api/admin/doctors/<id>/reject.
    """
    name  = getattr(doctor, "full_name", "Doctor")
    email = getattr(doctor, "email",     None)
    if not email:
        return

    reason    = reason or "No specific reason provided."
    resubmit  = f"{_base_url()}/doctor/register"

    html = f"""
<h2 style="color:#ef4444;">Application Status — SmartX-Ray</h2>
<p>Dear <strong>{name}</strong>,</p>
<p>After reviewing your application, we are unable to approve your profile at this time.</p>

<div style="background:#fef2f2;border-left:4px solid #ef4444;padding:16px;border-radius:6px;margin:20px 0;">
  <p style="margin:0;font-weight:600;">❌ Rejection Reason</p>
  <p style="margin:8px 0 0;">{reason}</p>
</div>

<p><strong>What you can do:</strong></p>
<ol>
  <li>Review the reason above carefully</li>
  <li>Update your profile and license documentation</li>
  <li>Resubmit your application</li>
</ol>

<p style="margin:24px 0;">
  <a href="{resubmit}" style="background:#64748b;color:white;padding:12px 28px;
     border-radius:8px;text-decoration:none;font-weight:600;font-size:15px;">
    Update &amp; Resubmit →
  </a>
</p>

<p>If you believe this is a mistake, reply to this email or contact
<a href="mailto:admin@smartxray.kh">admin@smartxray.kh</a>.</p>
"""
    _send_html([email], "Application Update — SmartX-Ray", _wrap_email(html, "Application Rejected"))


def email_doctor_new_appointment(doctor, appointment, patient) -> None:
    """
    Notifies the doctor when a patient books an appointment.
    Triggered by POST /api/appointments/book.
    """
    email = getattr(doctor, "email", None)
    if not email:
        return

    doc_name     = getattr(doctor,      "full_name", "Doctor")
    patient_name = getattr(patient,     "full_name", getattr(patient, "email", "Patient"))
    note         = (
        getattr(appointment, "patient_note", None)
        or getattr(appointment, "note",       None)
        or "—"
    )
    fee = (
        getattr(appointment, "fee_amount",   None)
        or getattr(appointment, "fee_snapshot", 0.0)
    )
    meet_link = getattr(appointment, "meeting_link", "—") or "—"
    apt_id    = getattr(appointment, "id", "—")

    # Date string
    sched = getattr(appointment, "scheduled_at", None)
    if sched and hasattr(sched, "strftime"):
        date_str = sched.strftime("%A, %d %B %Y  at  %H:%M")
    else:
        apt_date = getattr(appointment, "appointment_date", "—")
        apt_time = getattr(appointment, "appointment_time", "—")
        date_str = f"{apt_date} at {apt_time}"

    dashboard_url = f"{_base_url()}/doctor/dashboard"

    html = f"""
<h2 style="color:#0ea5e9;">📅 New Appointment Booked</h2>
<p>Dear <strong>{doc_name}</strong>,</p>
<p>A patient has booked a consultation with you.</p>

<table style="border-collapse:collapse;width:100%;margin:20px 0;">
  <tr style="background:#f8fafc;">
    <td style="padding:10px 14px;font-weight:600;width:140px;">Patient</td>
    <td style="padding:10px 14px;">{patient_name}</td>
  </tr>
  <tr>
    <td style="padding:10px 14px;font-weight:600;">Date &amp; Time</td>
    <td style="padding:10px 14px;color:#0ea5e9;font-weight:600;">{date_str}</td>
  </tr>
  <tr style="background:#f8fafc;">
    <td style="padding:10px 14px;font-weight:600;">Patient Note</td>
    <td style="padding:10px 14px;font-style:italic;">{note}</td>
  </tr>
  <tr>
    <td style="padding:10px 14px;font-weight:600;">Session Fee</td>
    <td style="padding:10px 14px;">${float(fee or 0):.2f} (ABA KHQR)</td>
  </tr>
  <tr style="background:#f8fafc;">
    <td style="padding:10px 14px;font-weight:600;">Meeting Link</td>
    <td style="padding:10px 14px;">
      <a href="{meet_link}">{meet_link}</a>
    </td>
  </tr>
  <tr>
    <td style="padding:10px 14px;font-weight:600;">Appointment ID</td>
    <td style="padding:10px 14px;"><code>#{apt_id}</code></td>
  </tr>
</table>

<p style="margin:24px 0;">
  <a href="{dashboard_url}" style="background:#0ea5e9;color:white;padding:12px 28px;
     border-radius:8px;text-decoration:none;font-weight:600;font-size:15px;">
    View in Dashboard →
  </a>
</p>
"""
    _send_html([email], f"New Appointment — {patient_name}", _wrap_email(html, "New Appointment"))


# ════════════════════════════════════════════════════════════════════════════
#  EMAIL — PATIENT-SPECIFIC
# ════════════════════════════════════════════════════════════════════════════

def email_patient_appointment_confirmed(patient, appointment, doctor) -> None:
    """
    Notifies the patient when their booking is confirmed.
    Triggered by POST /api/appointments/book (after commit).
    """
    email = getattr(patient, "email", None)
    if not email:
        return

    patient_name = getattr(patient, "full_name", "Patient")
    doc_name     = getattr(doctor,  "full_name", "Doctor")
    doc_spec     = getattr(doctor,  "specialty", "")
    meet_link    = getattr(appointment, "meeting_link", "") or ""
    apt_id       = getattr(appointment, "id", "—")
    fee = (
        getattr(appointment, "fee_amount",   None)
        or getattr(appointment, "fee_snapshot", 0.0)
    )

    sched = getattr(appointment, "scheduled_at", None)
    if sched and hasattr(sched, "strftime"):
        date_str = sched.strftime("%A, %d %B %Y  at  %H:%M")
    else:
        apt_date = getattr(appointment, "appointment_date", "—")
        apt_time = getattr(appointment, "appointment_time", "—")
        date_str = f"{apt_date} at {apt_time}"

    apts_url = f"{_base_url()}/my-appointments"

    html = f"""
<h2 style="color:#22c55e;">✅ Appointment Confirmed!</h2>
<p>Dear <strong>{patient_name}</strong>,</p>
<p>Your consultation has been booked successfully.</p>

<div style="background:#f0fdf4;border-left:4px solid #22c55e;padding:16px;border-radius:6px;margin:20px 0;">
  <p style="margin:0;font-weight:600;">{doc_name}</p>
  <p style="margin:4px 0 0;color:#64748b;">{doc_spec}</p>
  <p style="margin:12px 0 0;font-size:18px;font-weight:700;color:#0ea5e9;">{date_str}</p>
</div>

<table style="border-collapse:collapse;width:100%;margin:20px 0;">
  <tr style="background:#f8fafc;">
    <td style="padding:10px 14px;font-weight:600;width:140px;">Session Fee</td>
    <td style="padding:10px 14px;">${float(fee or 0):.2f} USD</td>
  </tr>
  <tr>
    <td style="padding:10px 14px;font-weight:600;">Payment</td>
    <td style="padding:10px 14px;">ABA KHQR ✓ Paid</td>
  </tr>
  <tr style="background:#f8fafc;">
    <td style="padding:10px 14px;font-weight:600;">Appointment ID</td>
    <td style="padding:10px 14px;"><code>#{apt_id}</code></td>
  </tr>
  {"<tr><td style='padding:10px 14px;font-weight:600;'>Meeting Link</td>" +
   f"<td style='padding:10px 14px;'><a href='{meet_link}' style='color:#0ea5e9;'>{meet_link}</a></td></tr>"
   if meet_link else ""}
</table>

<p>💡 <strong>Tip:</strong> The [Join Meeting] button becomes active 15 minutes before your appointment time.</p>

<p style="margin:24px 0;">
  <a href="{apts_url}" style="background:#0ea5e9;color:white;padding:12px 28px;
     border-radius:8px;text-decoration:none;font-weight:600;font-size:15px;">
    View My Appointments →
  </a>
</p>
"""
    _send_html([email], f"Appointment Confirmed — {doc_name}", _wrap_email(html, "Appointment Confirmed"))


def email_patient_appointment_cancelled(patient, appointment, doctor) -> None:
    """
    Notifies the patient when an appointment is cancelled.
    Triggered by PATCH /api/appointments/<id>/cancel.
    """
    email = getattr(patient, "email", None)
    if not email:
        return

    patient_name = getattr(patient, "full_name", "Patient")
    doc_name     = getattr(doctor,  "full_name", "Doctor")
    apt_id       = getattr(appointment, "id", "—")
    find_url     = f"{_base_url()}/find-doctor"

    sched = getattr(appointment, "scheduled_at", None)
    if sched and hasattr(sched, "strftime"):
        date_str = sched.strftime("%A, %d %B %Y  at  %H:%M")
    else:
        apt_date = getattr(appointment, "appointment_date", "—")
        apt_time = getattr(appointment, "appointment_time", "—")
        date_str = f"{apt_date} at {apt_time}"

    html = f"""
<h2 style="color:#ef4444;">Appointment Cancelled</h2>
<p>Dear <strong>{patient_name}</strong>,</p>
<p>Your appointment has been cancelled.</p>

<div style="background:#fef2f2;border-left:4px solid #ef4444;padding:16px;border-radius:6px;margin:20px 0;">
  <p style="margin:0;font-weight:600;">{doc_name}</p>
  <p style="margin:4px 0;color:#64748b;">Appointment #{apt_id}</p>
  <p style="margin:4px 0;text-decoration:line-through;color:#94a3b8;">{date_str}</p>
</div>

<p>Would you like to book a new appointment?</p>

<p style="margin:24px 0;">
  <a href="{find_url}" style="background:#64748b;color:white;padding:12px 28px;
     border-radius:8px;text-decoration:none;font-weight:600;font-size:15px;">
    Find Another Doctor →
  </a>
</p>
"""
    _send_html([email], "Appointment Cancelled — SmartX-Ray", _wrap_email(html, "Appointment Cancelled"))


def email_patient_review_request(patient, appointment, doctor) -> None:
    """
    Asks the patient to leave a review after a completed appointment.
    Triggered by PATCH /api/appointments/<id>/complete.
    """
    email = getattr(patient, "email", None)
    if not email:
        return

    patient_name = getattr(patient, "full_name", "Patient")
    doc_name     = getattr(doctor,  "full_name", "Doctor")
    apt_id       = getattr(appointment, "id", "—")
    review_url   = f"{_base_url()}/my-appointments?review={apt_id}"

    html = f"""
<h2 style="color:#f59e0b;">⭐ How Was Your Consultation?</h2>
<p>Dear <strong>{patient_name}</strong>,</p>
<p>Your consultation with <strong>{doc_name}</strong> has been marked as completed.</p>
<p>We'd love to hear your feedback — it helps other patients find the right doctor.</p>

<div style="background:#fffbeb;border-left:4px solid #f59e0b;padding:16px;border-radius:6px;margin:20px 0;">
  <p style="margin:0;font-size:28px;letter-spacing:4px;">⭐⭐⭐⭐⭐</p>
  <p style="margin:8px 0 0;color:#64748b;">Takes less than 30 seconds</p>
</div>

<p style="margin:24px 0;">
  <a href="{review_url}" style="background:#f59e0b;color:white;padding:12px 28px;
     border-radius:8px;text-decoration:none;font-weight:600;font-size:15px;">
    Leave a Review →
  </a>
</p>

<p style="color:#94a3b8;font-size:12px;">
  If you don't wish to leave a review, you can ignore this email.
</p>
"""
    _send_html([email], f"How was your session with {doc_name}?", _wrap_email(html, "Leave a Review"))


# ════════════════════════════════════════════════════════════════════════════
#  INTERNAL EMAIL HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _wrap_email(body_html: str, title: str = "SmartX-Ray") -> str:
    """
    Wrap an HTML email body in a consistent SmartX-Ray branded template.
    """
    year = datetime.now().year
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 16px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0"
               style="background:#ffffff;border-radius:12px;overflow:hidden;
                      box-shadow:0 1px 3px rgba(0,0,0,.1);">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#0f172a,#1e40af);
                        padding:28px 32px;">
              <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;
                          letter-spacing:-0.3px;">
                🫁 SmartX-Ray
              </h1>
              <p style="margin:4px 0 0;color:#93c5fd;font-size:13px;">
                AI-Powered Pneumonia Detection — Cambodia
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:32px;">
              <div style="font-size:15px;line-height:1.6;color:#1e293b;">
                {body_html}
              </div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#f8fafc;padding:20px 32px;border-top:1px solid #e2e8f0;">
              <p style="margin:0;font-size:12px;color:#94a3b8;text-align:center;">
                © {year} SmartX-Ray · Phnom Penh, Cambodia<br>
                <em>This is an automated message. Do not reply to this email.</em>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _send_html(recipients: list[str], subject: str, html: str) -> None:
    """
    Send an HTML email via Flask-Mail.
    Silently logs and swallows errors so a mail failure never crashes a request.
    """
    try:
        from app.extensions import mail
        from flask_mail import Message
        from flask import current_app

        msg = Message(
            subject    = subject,
            recipients = recipients,
            html       = html,
            sender     = current_app.config.get(
                "MAIL_DEFAULT_SENDER", "noreply@smartxray.kh"
            ),
        )
        mail.send(msg)
        logger.info("Email sent  to=%s  subject=%s", recipients, subject)
    except Exception as exc:
        logger.warning("Email send failed  to=%s  subject=%s  err=%s", recipients, subject, exc)
