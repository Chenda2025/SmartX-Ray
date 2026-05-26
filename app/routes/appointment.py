"""
Appointments + Public Doctor Listing  —  3 blueprints
══════════════════════════════════════════════════════════════════════════════
appointment_bp   → /api/appointments/*     (booking flow)
doctors_bp       → /api/doctors/*          (public doctor listing)
patient_bp       → /api/patient/*          (patient-specific views)

Appointment lifecycle
─────────────────────
  POST  /api/appointments/book              — patient books a slot
  GET   /api/appointments/<id>/join         — get meeting link (±15 min window)
  PATCH /api/appointments/<id>/cancel       — patient cancels
  PATCH /api/appointments/<id>/complete     — doctor marks completed
  POST  /api/appointments/<id>/review       — patient leaves review (post-complete)
  GET   /api/appointments/<id>              — detail view (owner or doctor)

Public Doctor Listing
─────────────────────
  GET   /api/doctors                        — paginated approved-doctor cards
  GET   /api/doctors/<id>                   — full profile + reviews + slots
  GET   /api/doctors/<id>/slots             — available time slots for a date

Patient
───────
  GET   /api/patient/appointments           — upcoming + past split
  GET   /api/patient/dashboard              — lightweight patient stats
══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import random
import string
from datetime import date, datetime, time, timedelta, timezone

from flask import Blueprint, g, jsonify, request
from sqlalchemy import func, distinct, or_, text

from app.extensions import db
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.user import User
from app.utils.auth_guard import doctor_required, patient_required

# ── Blueprints ──────────────────────────────────────────────────────────────
appointment_bp = Blueprint("appointment", __name__)
doctors_bp     = Blueprint("doctors",     __name__)
patient_bp     = Blueprint("patient",     __name__)


# ════════════════════════════════════════════════════════════════════════════
#  SECTION A  —  PUBLIC DOCTOR LISTING
#  GET /api/doctors
#  GET /api/doctors/<id>
#  GET /api/doctors/<id>/slots
# ════════════════════════════════════════════════════════════════════════════

@doctors_bp.route("", methods=["GET"])
def list_approved_doctors():
    """
    GET /api/doctors
    Returns only approved / verified doctors.

    Query params:
      specialty   — partial match (ilike)
      university  — partial match (ilike)
      min_rating  — float  (e.g. 4.0)
      search      — name or specialty keyword
      sort        — rating_desc (default) | rating_asc | rate_asc | rate_desc
      page, limit
    """
    specialty  = request.args.get("specialty",  "").strip()
    university = request.args.get("university", "").strip()
    search     = request.args.get("search",     "").strip()
    min_rating = request.args.get("min_rating", 0, type=float)
    sort       = request.args.get("sort",       "rating_desc")
    page       = request.args.get("page",  1,  type=int)
    limit      = min(request.args.get("limit", 12, type=int), 50)

    # ── Only approved doctors ─────────────────────────────────────────
    # Doctor.status is a @property (not a DB column pre-migration).
    # Use is_verified + is_active flags which map to "approved" in both schemas.
    q = Doctor.query.filter(
        Doctor.is_verified == True,
        Doctor.is_active   == True,
    )

    if specialty:
        q = q.filter(Doctor.specialty.ilike(f"%{specialty}%"))

    if university:
        try:
            # university is a post-migration column; raw text avoids Pylance warning
            q = q.filter(text("doctors.university ILIKE :uni")).params(uni=f"%{university}%")
        except Exception:
            pass  # column may not exist pre-migration

    if search:
        term = f"%{search}%"
        q = q.filter(or_(
            Doctor.full_name.ilike(term),
            Doctor.specialty.ilike(term),
        ))

    if min_rating > 0:
        rating_col = _rating_col()
        q = q.filter(getattr(Doctor, rating_col) >= min_rating)

    # ── Sorting ───────────────────────────────────────────────────────
    rating_col = _rating_col()
    if sort == "rating_asc":
        q = q.order_by(getattr(Doctor, rating_col).asc())
    elif sort == "rate_asc":
        q = q.order_by(Doctor.rate_per_session.asc())
    elif sort == "rate_desc":
        q = q.order_by(Doctor.rate_per_session.desc())
    else:
        q = q.order_by(getattr(Doctor, rating_col).desc())

    pag = q.paginate(page=page, per_page=limit, error_out=False)

    return jsonify({
        "doctors":  [_doctor_card(d) for d in pag.items],
        "total":    pag.total,
        "page":     pag.page,
        "pages":    pag.pages,
        "has_next": pag.has_next,
    }), 200


@doctors_bp.route("/<int:doctor_id>", methods=["GET"])
def get_doctor_profile(doctor_id):
    """
    GET /api/doctors/<id>
    Full doctor profile page — includes last 5 reviews + available slots.
    """
    doctor = db.session.get(Doctor, doctor_id)
    if not doctor or not doctor.is_active:
        return jsonify({"error": "Doctor not found."}), 404

    profile = _doctor_card(doctor)

    # ── Full profile additions ────────────────────────────────────────
    profile["bio"]           = doctor.bio
    profile["hospital"]      = getattr(doctor, "hospital", None)
    profile["city"]          = getattr(doctor, "city",     None)
    profile["phone"]         = getattr(doctor, "phone",    None)
    profile["google_maps_url"] = getattr(doctor, "google_maps_url", None)
    profile["experience_years"] = getattr(doctor, "experience_years", 0)
    profile["license_masked"] = _mask_license(
        getattr(doctor, "license_number", None)
        or getattr(doctor, "license_no",  None)
    )

    # ── Reviews ───────────────────────────────────────────────────────
    profile["reviews"] = _get_reviews(doctor_id, limit=5)

    # ── Available time slots (next 14 days) ───────────────────────────
    profile["available_slots"] = _get_available_slots(doctor, days_ahead=14)
    profile["availability"]    = doctor.availability

    # ── Stats ─────────────────────────────────────────────────────────
    total_apts = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.status.in_(["confirmed", "completed"]),
    ).count()
    profile["total_appointments"] = total_apts

    return jsonify({"doctor": profile}), 200


@doctors_bp.route("/<int:doctor_id>/slots", methods=["GET"])
def get_doctor_slots(doctor_id):
    """
    GET /api/doctors/<id>/slots?date=YYYY-MM-DD
    Return 30-min available slots for a specific date.
    """
    doctor = db.session.get(Doctor, doctor_id)
    if not doctor or not doctor.is_active:
        return jsonify({"error": "Doctor not found."}), 404

    date_str = request.args.get("date", "")
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        target_date = date.today() + timedelta(days=1)

    booked_times = _get_booked_times(doctor_id, target_date)
    avail        = _parse_availability(doctor.availability or "")
    all_slots    = _slots_for_date(target_date, avail)

    slots = [
        {
            "time":      slot,
            "available": slot not in booked_times,
        }
        for slot in all_slots
    ]
    return jsonify({
        "date":        target_date.isoformat(),
        "doctor_name": doctor.full_name,
        "slots":       slots,
    }), 200


# ════════════════════════════════════════════════════════════════════════════
#  SECTION B  —  APPOINTMENT BOOKING FLOW
#  POST  /api/appointments/book
#  GET   /api/appointments/<id>
#  GET   /api/appointments/<id>/join
#  PATCH /api/appointments/<id>/cancel
#  PATCH /api/appointments/<id>/complete
#  POST  /api/appointments/<id>/review
# ════════════════════════════════════════════════════════════════════════════

@appointment_bp.route("/book", methods=["POST"])
@patient_required
def book_appointment():
    """
    POST /api/appointments/book
    Body:
      doctor_id*,
      scheduled_at     — ISO datetime  e.g. "2026-06-01T10:00:00"
      OR
      appointment_date — "YYYY-MM-DD"
      appointment_time — "HH:MM"
      patient_note     — optional text

    Returns: { appointment_id, meeting_link, scheduled_at, fee }
    """
    patient: User = g.current_user
    data = request.get_json(silent=True) or {}

    # ── Required: doctor_id ───────────────────────────────────────────
    doctor_id = data.get("doctor_id")
    if not doctor_id:
        return jsonify({"error": "doctor_id is required."}), 400

    doctor = db.session.get(Doctor, int(doctor_id))
    if not doctor:
        return jsonify({"error": "Doctor not found."}), 404
    if not doctor.is_active:
        return jsonify({"error": "This doctor is not currently accepting appointments."}), 400

    # Only approved doctors can be booked
    doctor_status = doctor.status  # property or column
    if doctor_status != "approved":
        return jsonify({"error": "Doctor is not verified."}), 400

    # ── Parse datetime ────────────────────────────────────────────────
    scheduled_at, apt_date, apt_time = _parse_appointment_datetime(data)
    if not apt_date:
        return jsonify({
            "error": "scheduled_at (ISO datetime) or appointment_date + appointment_time required."
        }), 400

    if apt_date < date.today():
        return jsonify({"error": "Appointment date cannot be in the past."}), 400

    # ── Duplicate check ───────────────────────────────────────────────
    existing = Appointment.query.filter_by(
        doctor_id        = doctor.id,
        appointment_date = apt_date,
        appointment_time = apt_time,
        status           = "confirmed",
    ).first()
    if existing:
        return jsonify({
            "error": "That time slot is already booked. Please choose another.",
        }), 409

    # Also check patient doesn't already have this slot
    patient_col = _patient_col()
    try:
        dup = Appointment.query.filter_by(
            **{patient_col: patient.id},
            doctor_id        = doctor.id,
            appointment_date = apt_date,
            appointment_time = apt_time,
        ).filter(Appointment.status != "cancelled").first()
        if dup:
            return jsonify({"error": "You already have this appointment booked."}), 409
    except Exception:
        pass

    # ── Optional fields ───────────────────────────────────────────────
    patient_note = (data.get("patient_note") or data.get("note") or "").strip() or None
    duration_min = int(data.get("duration_min", 30))
    fee_amount   = float(doctor.rate_per_session or 15.00)

    # ── Create appointment ────────────────────────────────────────────
    apt = Appointment(
        user_id          = patient.id,       # backward compat (NOT NULL)
        doctor_id        = doctor.id,
        appointment_date = apt_date,
        appointment_time = apt_time,
        note             = patient_note,     # backward compat
        status           = "confirmed",
        fee_snapshot     = fee_amount,       # backward compat
    )
    # New columns (post-migration) — safe
    _safe_set(apt, "patient_id",     patient.id)
    _safe_set(apt, "scheduled_at",   scheduled_at)
    _safe_set(apt, "duration_min",   duration_min)
    _safe_set(apt, "patient_note",   patient_note)
    _safe_set(apt, "fee_amount",     fee_amount)
    _safe_set(apt, "payment_method", "ABA KHQR")
    _safe_set(apt, "payment_status", "paid")

    db.session.add(apt)
    db.session.flush()   # get apt.id before commit

    # ── Generate meeting link ─────────────────────────────────────────
    from app.utils.notifications import generate_meeting_link
    meeting_link = generate_meeting_link(apt.id)
    _safe_set(apt, "meeting_link", meeting_link)

    db.session.commit()

    # ── Notifications (non-blocking) ─────────────────────────────────
    try:
        from app.utils.notifications import (
            email_doctor_new_appointment,
            email_patient_appointment_confirmed,
            alert_new_appointment,
        )
        email_doctor_new_appointment(doctor, apt, patient)
        email_patient_appointment_confirmed(patient, apt, doctor)
        alert_new_appointment(apt, patient, doctor)
    except Exception:
        pass

    return jsonify({
        "message":        "Appointment booked successfully.",
        "appointment_id": apt.id,
        "meeting_link":   meeting_link,
        "scheduled_at":   scheduled_at.isoformat() if scheduled_at else f"{apt_date}T{apt_time}",
        "fee":            fee_amount,
        "payment_method": "ABA KHQR",
        "payment_status": "paid",
        "doctor": {
            "id":        doctor.id,
            "full_name": doctor.full_name,
            "specialty": doctor.specialty,
        },
    }), 201


@appointment_bp.route("/<int:apt_id>", methods=["GET"])
@patient_required
def get_appointment(apt_id):
    """GET /api/appointments/<id> — detail for patient or doctor."""
    patient = g.current_user
    apt     = db.session.get(Appointment, apt_id)
    if not apt:
        return jsonify({"error": "Appointment not found."}), 404

    patient_id = getattr(apt, "patient_id", None) or getattr(apt, "user_id", None)
    if patient_id != patient.id:
        return jsonify({"error": "Access denied."}), 403

    return jsonify({"appointment": _format_apt_for_patient(apt)}), 200


@appointment_bp.route("/<int:apt_id>/join", methods=["GET"])
@patient_required
def join_meeting(apt_id):
    """
    GET /api/appointments/<id>/join

    Checks:
      1. Appointment belongs to this patient
      2. Status is 'confirmed'
      3. Scheduled time is within the join window:
         −15 minutes (early entry) to +120 minutes (late join)

    Returns: { meeting_link, scheduled_at, minutes_until }
    """
    patient = g.current_user
    apt     = db.session.get(Appointment, apt_id)
    if not apt:
        return jsonify({"error": "Appointment not found."}), 404

    # Ownership check
    patient_id = getattr(apt, "patient_id", None) or getattr(apt, "user_id", None)
    if patient_id != patient.id:
        return jsonify({"error": "This appointment does not belong to you."}), 403

    # Status check
    if apt.status == "cancelled":
        return jsonify({"error": "This appointment has been cancelled."}), 400
    if apt.status == "completed":
        return jsonify({"error": "This appointment has already been completed."}), 400
    if apt.status != "confirmed":
        return jsonify({"error": "Appointment is not confirmed."}), 400

    # Time window check
    now          = datetime.now(timezone.utc)
    scheduled_dt = _get_scheduled_datetime(apt)

    if scheduled_dt is None:
        # Can't determine time — allow join (safety fallback)
        minutes_until = 0
    else:
        # Make both timezone-aware
        if scheduled_dt.tzinfo is None:
            scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)
        diff_minutes  = (scheduled_dt - now).total_seconds() / 60
        minutes_until = int(diff_minutes)

        EARLY_ENTRY_MIN = 15    # can join 15 min before
        LATE_JOIN_MIN   = 120   # can join up to 2 hours after start

        if diff_minutes > EARLY_ENTRY_MIN:
            return jsonify({
                "error":         "too_early",
                "message":       f"Meeting link becomes active 15 minutes before the appointment.",
                "minutes_until": minutes_until,
                "scheduled_at":  scheduled_dt.isoformat(),
            }), 400

        if diff_minutes < -LATE_JOIN_MIN:
            return jsonify({
                "error":   "expired",
                "message": "This appointment time has passed.",
            }), 400

    # Fetch or generate meeting link
    meeting_link = getattr(apt, "meeting_link", None)
    if not meeting_link:
        from app.utils.notifications import generate_meeting_link
        meeting_link = generate_meeting_link(apt_id)

    return jsonify({
        "meeting_link":  meeting_link,
        "scheduled_at":  scheduled_dt.isoformat() if scheduled_dt else None,
        "minutes_until": minutes_until,
        "message":       "Meeting link ready. Join now!",
    }), 200


@appointment_bp.route("/<int:apt_id>/cancel", methods=["PATCH"])
@patient_required
def cancel_appointment(apt_id):
    """PATCH /api/appointments/<id>/cancel — patient cancels."""
    patient = g.current_user
    apt     = db.session.get(Appointment, apt_id)
    if not apt:
        return jsonify({"error": "Appointment not found."}), 404

    patient_id = getattr(apt, "patient_id", None) or getattr(apt, "user_id", None)
    if patient_id != patient.id:
        return jsonify({"error": "Access denied."}), 403

    if apt.status == "cancelled":
        return jsonify({"error": "Already cancelled."}), 400
    if apt.status == "completed":
        return jsonify({"error": "Cannot cancel a completed appointment."}), 400

    apt.status = "cancelled"
    db.session.commit()

    # Notify patient + doctor
    try:
        doctor = db.session.get(Doctor, apt.doctor_id)
        from app.utils.notifications import email_patient_appointment_cancelled
        email_patient_appointment_cancelled(patient, apt, doctor)
    except Exception:
        pass

    return jsonify({
        "message":     "Appointment cancelled.",
        "appointment": _format_apt_for_patient(apt),
    }), 200


@appointment_bp.route("/<int:apt_id>/complete", methods=["PATCH"])
@doctor_required
def complete_appointment(apt_id):
    """
    PATCH /api/appointments/<id>/complete
    @doctor_required — only the assigned doctor can mark it complete.

    - Sets status = 'completed'
    - Adds fee to doctor.total_earnings
    - Sends review-request email to patient
    """
    doctor: Doctor = g.current_doctor

    apt = db.session.get(Appointment, apt_id)
    if not apt:
        return jsonify({"error": "Appointment not found."}), 404

    if apt.doctor_id != doctor.id:
        return jsonify({"error": "This appointment does not belong to you."}), 403

    if apt.status == "completed":
        return jsonify({"error": "Already marked as completed."}), 400
    if apt.status == "cancelled":
        return jsonify({"error": "Cannot complete a cancelled appointment."}), 400
    if apt.status != "confirmed":
        return jsonify({"error": "Appointment must be confirmed before completing."}), 400

    # ── Mark complete ─────────────────────────────────────────────────
    apt.status = "completed"

    # ── Update doctor total earnings ──────────────────────────────────
    fee = (
        getattr(apt, "fee_amount",   None)
        or getattr(apt, "fee_snapshot", 0.0)
    ) or 0.0

    try:
        current_earnings = getattr(doctor, "total_earnings", 0.0) or 0.0
        doctor.total_earnings = float(current_earnings) + float(fee)
    except Exception:
        pass

    db.session.commit()

    # ── Send review request to patient ────────────────────────────────
    try:
        patient_id = getattr(apt, "patient_id", None) or getattr(apt, "user_id", None)
        patient    = db.session.get(User, patient_id) if patient_id else None
        if patient:
            from app.utils.notifications import email_patient_review_request
            email_patient_review_request(patient, apt, doctor)
    except Exception:
        pass

    return jsonify({
        "message":        "Appointment marked as completed.",
        "appointment_id": apt.id,
        "fee_collected":  float(fee),
    }), 200


@appointment_bp.route("/<int:apt_id>/review", methods=["POST"])
@patient_required
def leave_review(apt_id):
    """
    POST /api/appointments/<id>/review
    Body: { rating: 1–5, comment: "..." }

    - Checks appointment belongs to patient and is completed
    - Inserts into reviews table (raw SQL — model created in later step)
    - Triggers avg_rating recalculation on doctors table
    """
    patient: User = g.current_user
    data = request.get_json(silent=True) or {}

    apt = db.session.get(Appointment, apt_id)
    if not apt:
        return jsonify({"error": "Appointment not found."}), 404

    patient_id = getattr(apt, "patient_id", None) or getattr(apt, "user_id", None)
    if patient_id != patient.id:
        return jsonify({"error": "This appointment does not belong to you."}), 403

    if apt.status != "completed":
        return jsonify({
            "error":   "not_completed",
            "message": "You can only review a completed appointment.",
        }), 400

    # ── Validate rating ───────────────────────────────────────────────
    rating = data.get("rating")
    if rating is None:
        return jsonify({"error": "rating (1–5) is required."}), 400
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        return jsonify({"error": "rating must be an integer."}), 400
    if rating not in (1, 2, 3, 4, 5):
        return jsonify({"error": "rating must be between 1 and 5."}), 400

    comment = (data.get("comment") or "").strip() or None

    # ── Check for existing review ─────────────────────────────────────
    try:
        existing = db.session.execute(
            text("SELECT id FROM reviews WHERE appointment_id = :aid"),
            {"aid": apt_id},
        ).fetchone()
        if existing:
            return jsonify({
                "error":   "already_reviewed",
                "message": "You have already reviewed this appointment.",
            }), 409
    except Exception:
        return jsonify({
            "error":   "reviews_unavailable",
            "message": "Review system is not available yet. Run flask db upgrade.",
        }), 503

    # ── Insert review ─────────────────────────────────────────────────
    result = db.session.execute(text("""
        INSERT INTO reviews (
            appointment_id, patient_id, doctor_id,
            rating, comment, created_at
        ) VALUES (
            :apt_id, :pat_id, :doc_id,
            :rating, :comment, NOW()
        ) RETURNING id
    """), {
        "apt_id":  apt_id,
        "pat_id":  patient.id,
        "doc_id":  apt.doctor_id,
        "rating":  rating,
        "comment": comment,
    })
    row = result.fetchone()
    review_id = row[0] if row else None

    # ── Recalculate doctor avg_rating ─────────────────────────────────
    db.session.execute(text("""
        UPDATE doctors
        SET
            avg_rating    = COALESCE(
                                (SELECT ROUND(AVG(rating)::NUMERIC, 2)
                                 FROM reviews WHERE doctor_id = :did), 0.00),
            rating        = COALESCE(
                                (SELECT ROUND(AVG(rating)::NUMERIC, 2)
                                 FROM reviews WHERE doctor_id = :did), 0.00),
            total_reviews = (SELECT COUNT(*) FROM reviews WHERE doctor_id = :did),
            review_count  = (SELECT COUNT(*) FROM reviews WHERE doctor_id = :did)
        WHERE id = :did
    """), {"did": apt.doctor_id})

    db.session.commit()

    return jsonify({
        "message":   "Review submitted. Thank you!",
        "review_id": review_id,
        "rating":    rating,
        "comment":   comment,
    }), 201


# ════════════════════════════════════════════════════════════════════════════
#  SECTION C  —  PATIENT-SPECIFIC VIEWS
#  GET /api/patient/appointments
#  GET /api/patient/dashboard
# ════════════════════════════════════════════════════════════════════════════

@patient_bp.route("/appointments", methods=["GET"])
@patient_required
def patient_appointments():
    """
    GET /api/patient/appointments
    Returns appointments split into upcoming and past tabs.
    Optional: ?status=confirmed|completed|cancelled
    """
    patient     = g.current_user
    patient_col = _patient_col()
    status      = request.args.get("status")

    q = Appointment.query.filter(
        getattr(Appointment, patient_col) == patient.id
    )
    if status:
        q = q.filter(Appointment.status == status)

    all_apts = q.order_by(
        Appointment.appointment_date.desc(),
        Appointment.appointment_time.desc(),
    ).all()

    today = date.today()
    upcoming, past = [], []

    for a in all_apts:
        serialized = _format_apt_for_patient(a)
        apt_date   = getattr(a, "appointment_date", None)
        if apt_date and apt_date >= today and a.status == "confirmed":
            upcoming.append(serialized)
        else:
            past.append(serialized)

    # Add has_review flag to past appointments
    for item in past:
        item["has_review"] = _apt_has_review(item["id"])

    return jsonify({
        "upcoming": upcoming,
        "past":     past,
        "total":    len(all_apts),
    }), 200


@patient_bp.route("/dashboard", methods=["GET"])
@patient_required
def patient_dashboard_stats():
    """
    GET /api/patient/dashboard
    Lightweight stats for the patient dashboard header.
    """
    patient     = g.current_user
    patient_col = _patient_col()

    try:
        total_apts = Appointment.query.filter(
            getattr(Appointment, patient_col) == patient.id,
        ).count()

        upcoming_count = Appointment.query.filter(
            getattr(Appointment, patient_col) == patient.id,
            Appointment.status          == "confirmed",
            Appointment.appointment_date >= date.today(),
        ).count()

        completed_count = Appointment.query.filter(
            getattr(Appointment, patient_col) == patient.id,
            Appointment.status == "completed",
        ).count()
    except Exception:
        total_apts = upcoming_count = completed_count = 0

    # Scans
    from app.models.scan import Scan
    total_scans    = Scan.query.filter_by(user_id=patient.id).count()
    pneumonia_scans = Scan.query.filter_by(user_id=patient.id, prediction="PNEUMONIA").count()

    return jsonify({
        "user": {
            "full_name":  patient.full_name,
            "email":      patient.email,
            "tier":       patient.tier,
            "university": getattr(patient, "university", None),
        },
        "scans": {
            "total":     total_scans,
            "pneumonia": pneumonia_scans,
            "normal":    total_scans - pneumonia_scans,
        },
        "appointments": {
            "total":     total_apts,
            "upcoming":  upcoming_count,
            "completed": completed_count,
        },
    }), 200


# ════════════════════════════════════════════════════════════════════════════
#  HELPERS — serialization
# ════════════════════════════════════════════════════════════════════════════

def _format_apt_for_patient(a: Appointment) -> dict:
    """Serialize an Appointment for the patient-facing API."""
    doctor       = db.session.get(Doctor, a.doctor_id)
    meeting_link = getattr(a, "meeting_link", None)
    if not meeting_link:
        from app.utils.notifications import generate_meeting_link
        meeting_link = generate_meeting_link(a.id)

    note = getattr(a, "patient_note", None) or getattr(a, "note", None)
    fee  = getattr(a, "fee_amount", None)  or getattr(a, "fee_snapshot", 0.0)

    sched = getattr(a, "scheduled_at", None)
    if sched and hasattr(sched, "isoformat"):
        scheduled_str = sched.isoformat()
    else:
        apt_date = getattr(a, "appointment_date", None)
        apt_time = getattr(a, "appointment_time", "")
        scheduled_str = f"{apt_date}T{apt_time}" if apt_date else None

    # Can this appointment be joined right now?
    can_join = _can_join_now(a)

    return {
        "id":              a.id,
        "scheduled_at":    scheduled_str,
        "date":            str(getattr(a, "appointment_date", "") or ""),
        "time":            getattr(a, "appointment_time", ""),
        "status":          a.status,
        "patient_note":    note,
        "meeting_link":    meeting_link,
        "can_join":        can_join,
        "fee":             float(fee or 0),
        "payment_method":  getattr(a, "payment_method", "ABA KHQR"),
        "payment_status":  getattr(a, "payment_status", "paid"),
        "duration_min":    getattr(a, "duration_min", 30),
        "doctor": {
            "id":        doctor.id        if doctor else None,
            "full_name": doctor.full_name if doctor else "—",
            "specialty": doctor.specialty if doctor else "—",
            "photo_url": (
                getattr(doctor, "photo_url",  None)
                or getattr(doctor, "avatar_url", None)
            ) if doctor else None,
        },
    }


def _doctor_card(d: Doctor) -> dict:
    """Serialize a Doctor for the listing / card view."""
    avg_rating   = getattr(d, "avg_rating", None)   or getattr(d, "rating",       0.0)
    total_reviews = getattr(d, "total_reviews", None) or getattr(d, "review_count", 0)
    university   = getattr(d, "university",   None)
    license_no   = (
        getattr(d, "license_number", None)
        or getattr(d, "license_no",   None)
    )

    return {
        "id":               d.id,
        "full_name":        d.full_name,
        "specialty":        d.specialty,
        "university":       university,
        "license_masked":   _mask_license(license_no),
        "avg_rating":       float(avg_rating or 0),
        "total_reviews":    int(total_reviews or 0),
        "rate_per_session": float(d.rate_per_session or 0),
        "availability":     d.availability,
        "photo_url":        getattr(d, "photo_url", None) or getattr(d, "avatar_url", None),
        "is_verified":      d.is_verified,
        "status":           d.status,
        "experience_years": getattr(d, "experience_years", 0),
    }


def _mask_license(license_no: str | None) -> str:
    """KH-MED-2891  →  KH-MED-****"""
    if not license_no:
        return "—"
    parts = license_no.rsplit("-", 1)
    if len(parts) == 2:
        return f"{parts[0]}-****"
    return "****"


# ════════════════════════════════════════════════════════════════════════════
#  HELPERS — time & slot logic
# ════════════════════════════════════════════════════════════════════════════

_DAY_MAP = {
    "mon": 0, "monday":    0,
    "tue": 1, "tuesday":   1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thursday":  3,
    "fri": 4, "friday":    4,
    "sat": 5, "saturday":  5,
    "sun": 6, "sunday":    6,
}

_SLOT_DURATION = 30   # minutes per slot


def _parse_availability(availability: str) -> dict:
    """
    Parse "Mon–Fri 08:00–17:00" or "Mon–Sat 09:00–16:00" into
    { days: [0,1,2,3,4], start: time(8,0), end: time(17,0) }
    Returns default weekdays 09:00–17:00 on parse failure.
    """
    default = {"days": [0, 1, 2, 3, 4], "start": time(9, 0), "end": time(17, 0)}
    if not availability:
        return default

    import re
    # Normalise dashes
    s = availability.replace("–", "-").replace("—", "-").strip()

    # Extract time range  HH:MM-HH:MM
    time_match = re.search(r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})", s)
    if not time_match:
        return default

    try:
        start = time.fromisoformat(time_match.group(1))
        end   = time.fromisoformat(time_match.group(2))
    except ValueError:
        return default

    # Extract day range  Mon-Fri
    day_match = re.search(r"([a-zA-Z]+)\s*[-–]\s*([a-zA-Z]+)", s)
    if not day_match:
        return {**default, "start": start, "end": end}

    d1 = _DAY_MAP.get(day_match.group(1).lower()[:3])
    d2 = _DAY_MAP.get(day_match.group(2).lower()[:3])
    if d1 is None or d2 is None:
        return {**default, "start": start, "end": end}

    if d1 <= d2:
        days = list(range(d1, d2 + 1))
    else:                              # wraps around: Sat(5)–Tue(1)
        days = list(range(d1, 7)) + list(range(0, d2 + 1))

    return {"days": days, "start": start, "end": end}


def _slots_for_date(target: date, avail: dict) -> list[str]:
    """Generate HH:MM slot strings for a date if it falls in avail.days."""
    if target.weekday() not in avail["days"]:
        return []

    slots = []
    cur   = datetime.combine(target, avail["start"])
    end   = datetime.combine(target, avail["end"])
    while cur < end:
        slots.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=_SLOT_DURATION)
    return slots


def _get_booked_times(doctor_id: int, target: date) -> set[str]:
    """Return set of booked appointment_time strings for a doctor on a date."""
    rows = Appointment.query.filter_by(
        doctor_id        = doctor_id,
        appointment_date = target,
        status           = "confirmed",
    ).with_entities(Appointment.appointment_time).all()
    return {r[0] for r in rows if r[0]}


def _get_available_slots(doctor: Doctor, days_ahead: int = 14) -> list[dict]:
    """
    Return a list of date → slots dicts for the next `days_ahead` days.
    Each dict: { date, day_name, slots: [{time, available}] }
    """
    avail  = _parse_availability(doctor.availability or "")
    result = []
    today  = date.today()

    for offset in range(1, days_ahead + 1):
        d     = today + timedelta(days=offset)
        times = _slots_for_date(d, avail)
        if not times:
            continue
        booked = _get_booked_times(doctor.id, d)
        result.append({
            "date":     d.isoformat(),
            "day_name": d.strftime("%A"),
            "slots": [
                {"time": t, "available": t not in booked}
                for t in times
            ],
        })

    return result


def _parse_appointment_datetime(data: dict) -> tuple:
    """
    Parse (scheduled_at datetime, appointment_date date, appointment_time str)
    from request body.  Accepts either:
      - scheduled_at: "2026-06-01T10:00:00"  (ISO)
      - appointment_date: "2026-06-01" + appointment_time: "10:00"
    Returns (None, None, None) on failure.
    """
    scheduled_at = None
    apt_date     = None
    apt_time     = None

    raw_sched = (data.get("scheduled_at") or "").strip()
    if raw_sched:
        try:
            scheduled_at = datetime.fromisoformat(raw_sched.replace("Z", "+00:00"))
            if scheduled_at.tzinfo is None:
                scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
            apt_date = scheduled_at.date()
            apt_time = scheduled_at.strftime("%H:%M")
        except ValueError:
            pass

    if not apt_date:
        raw_date = (data.get("appointment_date") or "").strip()
        raw_time = (data.get("appointment_time") or "").strip()
        if raw_date and raw_time:
            try:
                apt_date = date.fromisoformat(raw_date)
                apt_time = raw_time
                # Build combined datetime (UTC assumed)
                h, m = map(int, raw_time.split(":")[:2])
                scheduled_at = datetime(
                    apt_date.year, apt_date.month, apt_date.day,
                    h, m, tzinfo=timezone.utc,
                )
            except (ValueError, AttributeError):
                pass

    return scheduled_at, apt_date, apt_time


def _get_scheduled_datetime(apt: Appointment) -> datetime | None:
    """Get scheduled datetime from appointment (new or old columns)."""
    sched = getattr(apt, "scheduled_at", None)
    if sched:
        if isinstance(sched, datetime):
            return sched
        try:
            return datetime.fromisoformat(str(sched))
        except Exception:
            pass

    apt_date = getattr(apt, "appointment_date", None)
    apt_time = getattr(apt, "appointment_time", None)
    if apt_date and apt_time:
        try:
            h, m = map(int, str(apt_time).split(":")[:2])
            return datetime(
                apt_date.year, apt_date.month, apt_date.day,
                h, m, tzinfo=timezone.utc,
            )
        except Exception:
            pass

    return None


def _can_join_now(apt: Appointment) -> bool:
    """Return True if the join window is currently active (−15 min to +120 min)."""
    if apt.status != "confirmed":
        return False
    scheduled_dt = _get_scheduled_datetime(apt)
    if scheduled_dt is None:
        return True   # safety fallback
    if scheduled_dt.tzinfo is None:
        scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)
    now  = datetime.now(timezone.utc)
    diff = (scheduled_dt - now).total_seconds() / 60
    return -120 <= diff <= 15


def _apt_has_review(appointment_id: int) -> bool:
    """Check if a review already exists for this appointment."""
    try:
        row = db.session.execute(
            text("SELECT id FROM reviews WHERE appointment_id = :aid LIMIT 1"),
            {"aid": appointment_id},
        ).fetchone()
        return row is not None
    except Exception:
        return False


def _get_reviews(doctor_id: int, limit: int = 5) -> list[dict]:
    """Fetch recent reviews for a doctor via raw SQL."""
    try:
        rows = db.session.execute(text("""
            SELECT
                r.id,
                r.rating,
                r.comment,
                r.created_at,
                u.full_name AS patient_name
            FROM reviews r
            LEFT JOIN users u ON u.id = r.patient_id
            WHERE r.doctor_id = :did
            ORDER BY r.created_at DESC
            LIMIT :lim
        """), {"did": doctor_id, "lim": limit}).fetchall()

        return [
            {
                "id":           row[0],
                "rating":       row[1],
                "comment":      row[2],
                "created_at":   row[3].isoformat() if row[3] else None,
                "patient_name": row[4] or "Patient",
            }
            for row in rows
        ]
    except Exception:
        return []


# ════════════════════════════════════════════════════════════════════════════
#  HELPERS — model compatibility
# ════════════════════════════════════════════════════════════════════════════

def _patient_col() -> str:
    """Return 'patient_id' if the column exists on Appointment, else 'user_id'."""
    return "patient_id" if hasattr(Appointment, "patient_id") else "user_id"


def _rating_col() -> str:
    """Return 'avg_rating' if it exists on Doctor, else 'rating'."""
    return "avg_rating" if hasattr(Doctor, "avg_rating") else "rating"


def _safe_set(obj, attr: str, value) -> None:
    """Set attribute only if the column is mapped on the model."""
    try:
        setattr(obj, attr, value)
    except (AttributeError, Exception):
        pass
