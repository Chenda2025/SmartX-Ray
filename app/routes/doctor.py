"""
Doctor Portal API  —  /api/doctor/…
══════════════════════════════════════════════════════════════════════════════
Handles the full doctor lifecycle:

  POST  /api/doctor/register       — self-register (creates user + doctor row)
  POST  /api/doctor/login          — login (blocks pending / rejected accounts)
  GET   /api/doctor/dashboard      — full KPI + schedule + earnings + reviews
  GET   /api/doctor/profile        — read doctor profile
  PUT   /api/doctor/profile        — update profile / resubmit after rejection
  GET   /api/doctor/check          — public: does this email have a doctor row?

Admin approve/reject live in:
  PATCH /api/admin/doctors/<id>/approve   (app/routes/admin.py)
  PATCH /api/admin/doctors/<id>/reject    (app/routes/admin.py)
══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from app.utils.time_utils import cambodia_today

import os
from flask import Blueprint, current_app, g, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
)
from sqlalchemy import func, distinct, text

from app.extensions import db
from app.models.doctor import Doctor
from app.models.user import User
from app.utils.auth_guard import doctor_required
from app.utils.validators import validate_email, validate_password

doctor_bp = Blueprint("doctor", __name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _current_user() -> User | None:
    uid = get_jwt_identity()
    return db.session.get(User, int(uid)) if uid else None


def _doctor_for_user(user: User) -> Doctor | None:
    """Try user_id FK first (post-migration), then fall back to email match."""
    try:
        doc = Doctor.query.filter_by(user_id=user.id).first()
        if doc:
            return doc
    except Exception:
        pass
    return Doctor.query.filter_by(email=user.email).first()


def _doctor_status(doctor: Doctor) -> str:
    """Return status string; works before and after migration."""
    return doctor.status          # @property on model covers pre-migration


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 1 — POST /api/doctor/register
# Doctor self-registers — creates user + doctor record, sends Telegram alert.
# Account is locked (is_active=False) until admin approves.
# ─────────────────────────────────────────────────────────────────────────────

@doctor_bp.route("/register", methods=["POST"])
def register_doctor():
    """
    Public endpoint — no JWT required.
    Accepts multipart/form-data OR JSON.
    Fields: full_name*, email*, password*, specialty*, license_number*,
            university, experience_years, rate_per_session, availability, bio
    Files:  photo (optional), license_doc (optional PDF/JPG/PNG)
    Returns: 201 { message, doctor_id }
    """
    import os
    from werkzeug.utils import secure_filename as _secure

    # Accept both multipart/form-data and JSON
    if request.content_type and "multipart" in request.content_type:
        get = lambda k, d="": (request.form.get(k) or d)
    else:
        _json = request.get_json(silent=True) or {}
        get   = lambda k, d="": (_json.get(k) or d)

    # ── Required fields ───────────────────────────────────────────────
    full_name      = get("full_name").strip()
    email          = get("email").strip().lower()
    password       = get("password")
    specialty      = get("specialty").strip()
    license_number = (get("license_number") or get("license_no")).strip()

    if not full_name:
        return jsonify({"error": "full_name is required."}), 400
    if not specialty:
        return jsonify({"error": "specialty is required."}), 400
    if not license_number:
        return jsonify({"error": "license_number is required."}), 400

    err = validate_email(email)
    if err:
        return jsonify({"error": err}), 400
    err = validate_password(password)
    if err:
        return jsonify({"error": err}), 400

    # ── Duplicate checks ──────────────────────────────────────────────
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered."}), 409

    existing_lic = _check_duplicate_license(license_number)
    if existing_lic:
        return jsonify({"error": "License number already registered."}), 409

    # ── Optional fields ───────────────────────────────────────────────
    university       = get("university").strip() or None
    experience_years = int(get("experience_years") or 0)
    rate_per_session = float(get("rate_per_session") or 15.00)
    availability     = get("availability").strip() or None
    bio              = get("bio").strip() or None

    # ── 1. Create locked user account ─────────────────────────────────
    user = User(
        email       = email,
        full_name   = full_name,
        tier        = "pro",
        is_active   = False,
        is_verified = False,
    )
    try:
        user.role = "doctor"
    except AttributeError:
        pass
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    # ── 2. Create doctor profile (pending) ────────────────────────────
    doctor = Doctor(
        email            = email,
        full_name        = full_name,
        specialty        = specialty,
        license_no       = license_number,
        bio              = bio,
        rate_per_session = rate_per_session,
        availability     = availability,
        is_active        = True,
        is_verified      = False,
    )
    _safe_set(doctor, "user_id",          user.id)
    _safe_set(doctor, "license_number",   license_number)
    _safe_set(doctor, "university",       university)
    _safe_set(doctor, "experience_years", experience_years)
    _safe_set(doctor, "status",           "pending")

    db.session.add(doctor)
    db.session.flush()   # get doctor.id for filenames

    # ── 3. Save uploaded profile photo ───────────────────────────────
    photo_file = request.files.get("photo")
    if photo_file and photo_file.filename:
        ext = os.path.splitext(_secure(photo_file.filename))[1].lower()
        if ext in {".jpg", ".jpeg", ".png", ".webp"}:
            save_dir = os.path.join(
                current_app.root_path, "..", "static", "uploads", "doctors"
            )
            os.makedirs(save_dir, exist_ok=True)
            fname     = f"doctor_{doctor.id}{ext}"
            photo_file.save(os.path.join(save_dir, fname))
            photo_url = f"/static/uploads/doctors/{fname}"
            _safe_set(doctor, "photo_url",  photo_url)
            _safe_set(doctor, "avatar_url", photo_url)

    # ── 4. Save uploaded license document ────────────────────────────
    lic_file = request.files.get("license_doc")
    if lic_file and lic_file.filename:
        ext = os.path.splitext(_secure(lic_file.filename))[1].lower()
        if ext in {".pdf", ".jpg", ".jpeg", ".png"}:
            save_dir = os.path.join(
                current_app.root_path, "..", "static", "uploads", "doctors", "licenses"
            )
            os.makedirs(save_dir, exist_ok=True)
            fname   = f"license_{doctor.id}{ext}"
            lic_file.save(os.path.join(save_dir, fname))
            lic_url = f"/static/uploads/doctors/licenses/{fname}"
            _safe_set(doctor, "license_doc_url", lic_url)

    db.session.commit()

    # ── 3. Telegram alert to admin ────────────────────────────────────
    try:
        from app.utils.notifications import alert_new_doctor_registration
        alert_new_doctor_registration(doctor, user)
    except Exception:
        pass  # notification failure must not break registration

    # ── 4. Confirmation email to doctor ──────────────────────────────
    try:
        from app.utils.notifications import email_doctor_application_received
        email_doctor_application_received(doctor)
    except Exception:
        pass

    return jsonify({
        "message":   "Application submitted. An admin will review within 24 hours.",
        "doctor_id": doctor.id,
        "status":    "pending",
    }), 201


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE — POST /api/doctor/claim
# Admin-created doctors set their password here (no User account yet).
# ─────────────────────────────────────────────────────────────────────────────

@doctor_bp.route("/claim", methods=["POST"])
def claim_account():
    """
    Body: { email, password }
    Returns:
      201 { access_token, refresh_token, doctor, user }  — success
      400 { error }                                       — validation
      404 { error }                                       — no doctor profile
      409 { error }                                       — account already exists
    """
    data     = request.get_json(silent=True) or {}
    email    = (data.get("email")    or "").strip().lower()
    password = (data.get("password") or "")

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    err = validate_password(password)
    if err:
        return jsonify({"error": err}), 400

    doctor = Doctor.query.filter_by(email=email).first()
    if not doctor:
        return jsonify({"error": "No doctor profile found for this email."}), 404

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Account already claimed. Please log in instead."}), 409

    is_approved = doctor.is_verified and doctor.is_active
    user = User(
        email       = email,
        full_name   = doctor.full_name,
        tier        = "pro",
        is_active   = is_approved,
        is_verified = is_approved,
    )
    try:
        user.role = "doctor"
    except AttributeError:
        pass
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    _safe_set(doctor, "user_id", user.id)
    db.session.commit()

    access  = create_access_token(
        identity          = str(user.id),
        additional_claims = {"role": "doctor", "doctor_id": doctor.id},
    )
    refresh = create_refresh_token(identity=str(user.id))

    return jsonify({
        "access_token":  access,
        "refresh_token": refresh,
        "user":          user.to_dict(),
        "doctor":        doctor.to_dict(),
    }), 201


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 4 — POST /api/doctor/login
# Doctor-specific login with status checks.
# Blocks pending and rejected accounts with structured error codes.
# ─────────────────────────────────────────────────────────────────────────────

@doctor_bp.route("/login", methods=["POST"])
def doctor_login():
    """
    Body: { email, password }
    Returns:
      200 { access_token, refresh_token, doctor, user }      — approved
      403 { error: 'pending_approval', message, status }     — pending
      403 { error: 'profile_rejected', reject_reason, ... }  — rejected
      401 { error }                                           — bad credentials
    """
    data     = request.get_json(silent=True) or {}
    email    = (data.get("email")    or "").strip().lower()
    password = (data.get("password") or "")

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    # ── Authenticate ──────────────────────────────────────────────────
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password."}), 401

    # ── Find doctor profile ───────────────────────────────────────────
    doctor = _doctor_for_user(user)
    if not doctor:
        # Could be a regular patient trying to hit this endpoint
        return jsonify({
            "error":   "no_doctor_profile",
            "message": "No doctor profile linked to this email. "
                       "Please register at /api/doctor/register.",
        }), 403

    # ── Check approval status ─────────────────────────────────────────
    status = _doctor_status(doctor)

    if status == "pending":
        return jsonify({
            "error":   "pending_approval",
            "message": "Your application is under review. "
                       "You will receive an email when a decision is made.",
            "status":  "pending",
        }), 403

    if status == "rejected":
        reason = (
            getattr(doctor, "reject_reason",    None)
            or getattr(doctor, "rejection_reason", None)
            or "No reason provided."
        )
        return jsonify({
            "error":         "profile_rejected",
            "message":       "Your application was rejected. "
                             "Update your profile and resubmit.",
            "reject_reason": reason,
            "status":        "rejected",
        }), 403

    # ── Verify account is active (approved) ───────────────────────────
    if not user.is_active:
        return jsonify({
            "error":   "account_disabled",
            "message": "Account is disabled. Contact admin@smartxray.kh.",
        }), 403

    # ── Issue JWT ─────────────────────────────────────────────────────
    access  = create_access_token(
        identity        = str(user.id),
        additional_claims = {"role": "doctor", "doctor_id": doctor.id},
    )
    refresh = create_refresh_token(identity=str(user.id))

    return jsonify({
        "access_token":  access,
        "refresh_token": refresh,
        "user":          user.to_dict(),
        "doctor":        doctor.to_dict(),
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 5 — GET /api/doctor/dashboard
# Full dashboard data: KPIs + today's schedule + upcoming + earnings + reviews
# ─────────────────────────────────────────────────────────────────────────────

@doctor_bp.route("/dashboard", methods=["GET"])
@doctor_required
def doctor_dashboard():
    """
    Returns all real data for the doctor dashboard.
    Requires @doctor_required — only approved doctors can reach this.
    """
    doctor: Doctor = g.current_doctor
    user:   User   = g.current_user

    today       = cambodia_today()
    month_start = today.replace(day=1)

    # ── Import models locally to avoid circular imports ───────────────
    from app.models.appointment import Appointment

    # ── KPI: total appointments (confirmed + completed) ───────────────
    total_apts = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.status.in_(["confirmed", "completed"]),
    ).count()

    # ── KPI: today's confirmed appointments ───────────────────────────
    today_apts = Appointment.query.filter(
        Appointment.doctor_id   == doctor.id,
        Appointment.status      == "confirmed",
        Appointment.appointment_date == today,
    ).count()

    # ── KPI: unique patients ──────────────────────────────────────────
    patient_col = _get_patient_col()
    try:
        total_patients = db.session.query(
            func.count(distinct(getattr(Appointment, patient_col)))
        ).filter(
            Appointment.doctor_id == doctor.id,
            Appointment.status.in_(["confirmed", "completed"]),
        ).scalar() or 0
    except Exception:
        total_patients = 0

    # ── KPI: earnings this month (confirmed + completed — payment collected at booking) ──
    fee_col = _get_fee_col()
    try:
        earnings_month = db.session.query(
            func.sum(getattr(Appointment, fee_col))
        ).filter(
            Appointment.doctor_id == doctor.id,
            Appointment.status.in_(["confirmed", "completed"]),
            Appointment.appointment_date >= month_start,
        ).scalar() or 0.0
    except Exception:
        earnings_month = 0.0

    # ── Earnings: all-time (confirmed + completed) ────────────────────
    try:
        earnings_total = db.session.query(
            func.sum(getattr(Appointment, fee_col))
        ).filter(
            Appointment.doctor_id == doctor.id,
            Appointment.status.in_(["confirmed", "completed"]),
        ).scalar() or 0.0
    except Exception:
        earnings_total = 0.0

    # ── Earnings: pending (confirmed, not yet consulted) ──────────────
    try:
        earnings_pending = db.session.query(
            func.sum(getattr(Appointment, fee_col))
        ).filter(
            Appointment.doctor_id == doctor.id,
            Appointment.status    == "confirmed",
        ).scalar() or 0.0
    except Exception:
        earnings_pending = 0.0

    # ── Today's schedule (confirmed + completed for today) ───────────
    today_schedule_rows = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.status.in_(["confirmed", "completed"]),
        Appointment.appointment_date == today,
    ).order_by(Appointment.appointment_time.asc()).all()

    today_schedule = [_format_appointment(a) for a in today_schedule_rows]

    # ── Upcoming (next 14 days, excluding today) ──────────────────────
    two_weeks = today + timedelta(days=14)
    upcoming_rows = Appointment.query.filter(
        Appointment.doctor_id    == doctor.id,
        Appointment.status       == "confirmed",
        Appointment.appointment_date > today,
        Appointment.appointment_date <= two_weeks,
    ).order_by(
        Appointment.appointment_date.asc(),
        Appointment.appointment_time.asc(),
    ).limit(10).all()

    upcoming = [_format_appointment(a) for a in upcoming_rows]

    # ── Recent reviews ────────────────────────────────────────────────
    recent_reviews = _get_recent_reviews(doctor.id, limit=3)

    # ── Doctor profile ────────────────────────────────────────────────
    avg_rating   = (
        getattr(doctor, "avg_rating", None)
        or getattr(doctor, "rating",   0.0)
    )
    total_reviews = (
        getattr(doctor, "total_reviews", None)
        or getattr(doctor, "review_count", 0)
    )
    doc_profile = {
        "id":              doctor.id,
        "full_name":       doctor.full_name,
        "specialty":       doctor.specialty,
        "university":      getattr(doctor, "university", None),
        "license_number":  (
            getattr(doctor, "license_number", None)
            or getattr(doctor, "license_no",  None)
        ),
        "rate_per_session": doctor.rate_per_session,
        "availability":    doctor.availability,
        "bio":             doctor.bio,
        "photo_url":       getattr(doctor, "photo_url", doctor.avatar_url),
        "status":          _doctor_status(doctor),
        "avg_rating":      float(avg_rating or 0),
        "total_reviews":   int(total_reviews or 0),
        "experience_years": getattr(doctor, "experience_years", 0),
    }

    # ── Star distribution for ratings chart ──────────────────────────
    star_dist = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    try:
        dist_rows = db.session.execute(text("""
            SELECT CAST(rating AS INTEGER) AS stars, COUNT(*) AS cnt
            FROM reviews
            WHERE doctor_id = :did AND rating BETWEEN 1 AND 5
            GROUP BY CAST(rating AS INTEGER)
        """), {"did": doctor.id}).fetchall()
        for row in dist_rows:
            k = str(max(1, min(5, int(row[0] or 1))))
            star_dist[k] = star_dist.get(k, 0) + int(row[1] or 0)
    except Exception:
        pass

    return jsonify({
        "doctor_profile": doc_profile,
        "kpi": {
            "total_appointments":  total_apts,
            "today_count":         today_apts,
            "total_patients":      total_patients,
            "earnings_this_month": round(float(earnings_month), 2),
        },
        "today_schedule":   today_schedule,
        "upcoming":         upcoming,
        "earnings_summary": {
            "this_month":     round(float(earnings_month),  2),
            "pending":        round(float(earnings_pending), 2),
            "total_all_time": round(float(earnings_total), 2),
        },
        "recent_reviews":   recent_reviews,
        "star_distribution": star_dist,
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/doctor/profile  — read doctor profile
# ─────────────────────────────────────────────────────────────────────────────

@doctor_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    """
    Returns the doctor profile for the current user.
    Works for any status (pending / approved / rejected).
    Used by the frontend to decide which dashboard state to render.
    """
    user = _current_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    doctor = _doctor_for_user(user)
    if not doctor:
        return jsonify({
            "error":  "no_doctor_profile",
            "message": "No doctor profile linked to this account.",
        }), 404

    return jsonify({
        "doctor": doctor.to_dict(),
        "status": _doctor_status(doctor),
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# PUT /api/doctor/profile  — update + resubmit after rejection
# ─────────────────────────────────────────────────────────────────────────────

@doctor_bp.route("/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    """
    Update doctor profile fields.
    If mode='resubmit' (default) → resets status to pending and notifies admin.
    If mode='complete'           → updates without changing approval status.
    """
    user = _current_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    doctor = _doctor_for_user(user)
    if not doctor:
        return jsonify({"error": "No doctor profile linked to this account."}), 404

    data = request.get_json(silent=True) or {}
    mode = (data.get("mode") or "resubmit").strip()

    # Editable fields
    _update_if_present(doctor, data, {
        "full_name":        "full_name",
        "specialty":        "specialty",
        "license_no":       "license_no",
        "license_number":   "license_number",
        "bio":              "bio",
        "availability":     "availability",
        "rate_per_session": "rate_per_session",
        "university":       "university",
        "experience_years": "experience_years",
        "phone":            "phone",
        "hospital":         "hospital",
    })

    if mode == "complete":
        msg = "Profile updated successfully."
    else:
        # Resubmit after rejection → reset to pending
        doctor.is_active   = True
        doctor.is_verified = False
        _safe_set(doctor, "status",           "pending")
        _safe_set(doctor, "reject_reason",    None)
        _safe_set(doctor, "rejection_reason", None)

        db.session.commit()

        # Notify admin
        try:
            from app.utils.notifications import alert_new_doctor_registration
            alert_new_doctor_registration(doctor, user)
        except Exception:
            pass
        try:
            from app.utils.notifications import email_doctor_application_received
            email_doctor_application_received(doctor)
        except Exception:
            pass

        return jsonify({
            "message": "Profile updated and resubmitted for review.",
            "doctor":  doctor.to_dict(),
            "status":  "pending",
        }), 200

    db.session.commit()
    return jsonify({"message": msg, "doctor": doctor.to_dict()}), 200


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/doctor/photo  — upload profile photo
# ─────────────────────────────────────────────────────────────────────────────

@doctor_bp.route("/photo", methods=["POST"])
@jwt_required()
def upload_photo():
    """
    Upload or replace the doctor's profile photo.
    Accepts multipart/form-data with field name 'photo'.
    Returns the public URL of the saved image.
    """
    from werkzeug.utils import secure_filename

    user = _current_user()
    if not user:
        return jsonify({"error": "User not found."}), 404
    doctor = _doctor_for_user(user)
    if not doctor:
        return jsonify({"error": "No doctor profile linked to this account."}), 404

    if "photo" not in request.files:
        return jsonify({"error": "No photo file uploaded."}), 400

    file = request.files["photo"]
    if not file or not file.filename:
        return jsonify({"error": "Empty file."}), 400

    ext = os.path.splitext(secure_filename(file.filename))[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return jsonify({"error": "Unsupported file type. Use JPG, PNG, or WEBP."}), 400

    # Save to static/uploads/doctors/
    save_dir = os.path.join(
        current_app.root_path, "..", "static", "uploads", "doctors"
    )
    os.makedirs(save_dir, exist_ok=True)
    filename = f"doctor_{doctor.id}{ext}"
    file.save(os.path.join(save_dir, filename))

    photo_url = f"/static/uploads/doctors/{filename}"
    _safe_set(doctor, "photo_url",   photo_url)
    _safe_set(doctor, "avatar_url",  photo_url)
    db.session.commit()

    return jsonify({"photo_url": photo_url, "doctor": doctor.to_dict()}), 200


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/doctor/check?email=…  — public email lookup
# ─────────────────────────────────────────────────────────────────────────────

@doctor_bp.route("/check", methods=["GET"])
def check_email():
    """
    Public.  Returns { exists, status, has_account, doctor_name }.
    Used by the login page to show the right form.
    """
    email = (request.args.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "email query parameter required."}), 400

    doctor = Doctor.query.filter_by(email=email).first()
    if not doctor:
        return jsonify({
            "exists":       False,
            "has_account":  False,
            "doctor_name":  None,
            "status":       None,
        }), 200

    user = User.query.filter_by(email=email).first()
    return jsonify({
        "exists":      True,
        "has_account": user is not None,
        "doctor_name": doctor.full_name,
        "status":      _doctor_status(doctor),
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/doctor/stats  — KPI stats (lightweight, no schedule)
# ─────────────────────────────────────────────────────────────────────────────

@doctor_bp.route("/stats", methods=["GET"])
@doctor_required
def get_stats():
    """Lightweight KPI stats endpoint (used by dashboard header cards)."""
    doctor = g.current_doctor
    from app.models.appointment import Appointment

    today       = cambodia_today()
    month_start = today.replace(day=1)
    fee_col     = _get_fee_col()
    patient_col = _get_patient_col()

    total_apts = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.status.in_(["confirmed", "completed"]),
    ).count()

    today_apts = Appointment.query.filter(
        Appointment.doctor_id   == doctor.id,
        Appointment.status      == "confirmed",
        Appointment.appointment_date == today,
    ).count()

    try:
        total_patients = db.session.query(
            func.count(distinct(getattr(Appointment, patient_col)))
        ).filter(
            Appointment.doctor_id == doctor.id,
            Appointment.status.in_(["confirmed", "completed"]),
        ).scalar() or 0
    except Exception:
        total_patients = 0

    try:
        earnings_month = db.session.query(
            func.sum(getattr(Appointment, fee_col))
        ).filter(
            Appointment.doctor_id == doctor.id,
            Appointment.status.in_(["confirmed", "completed"]),
            Appointment.appointment_date >= month_start,
        ).scalar() or 0.0
    except Exception:
        earnings_month = 0.0

    try:
        earnings_total = db.session.query(
            func.sum(getattr(Appointment, fee_col))
        ).filter(
            Appointment.doctor_id == doctor.id,
            Appointment.status.in_(["confirmed", "completed"]),
        ).scalar() or 0.0
    except Exception:
        earnings_total = 0.0

    avg_rating   = getattr(doctor, "avg_rating", None) or getattr(doctor, "rating", 0.0)
    total_reviews = getattr(doctor, "total_reviews", None) or getattr(doctor, "review_count", 0)

    return jsonify({
        "total_appointments": total_apts,
        "today_schedule":     today_apts,
        "total_patients":     total_patients,
        "earnings_month":     round(float(earnings_month), 2),
        "total_earnings":     round(float(earnings_total), 2),
        "rating":             float(avg_rating or 0),
        "review_count":       int(total_reviews or 0),
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_set(obj, attr: str, value) -> None:
    """Set an attribute only if the column exists on the mapped model."""
    try:
        setattr(obj, attr, value)
    except (AttributeError, Exception):
        pass


def _update_if_present(obj, data: dict, field_map: dict) -> None:
    """Update model fields from request data; coerce types as needed."""
    for src, dst in field_map.items():
        if src not in data:
            continue
        val = data[src]
        if isinstance(val, str):
            val = val.strip() or None
        elif dst == "rate_per_session":
            try:
                val = float(val or 0)
            except (TypeError, ValueError):
                continue
        elif dst == "experience_years":
            try:
                val = int(val or 0)
            except (TypeError, ValueError):
                continue
        _safe_set(obj, dst, val)


def _check_duplicate_license(license_number: str) -> bool:
    """Return True if license_number already exists in either column."""
    try:
        if Doctor.query.filter_by(license_number=license_number).first():
            return True
    except Exception:
        pass
    try:
        if Doctor.query.filter_by(license_no=license_number).first():
            return True
    except Exception:
        pass
    return False


def _get_patient_col() -> str:
    """Return 'patient_id' if the column exists, else fall back to 'user_id'."""
    from app.models.appointment import Appointment
    return "patient_id" if hasattr(Appointment, "patient_id") else "user_id"


def _get_fee_col() -> str:
    """Return 'fee_amount' if the column exists, else fall back to 'fee_snapshot'."""
    from app.models.appointment import Appointment
    return "fee_amount" if hasattr(Appointment, "fee_amount") else "fee_snapshot"


def _format_appointment(a) -> dict:
    """Serialize an Appointment for the dashboard schedule/upcoming lists."""
    from app.models.user import User as UserModel

    patient_id = (
        getattr(a, "patient_id", None)
        or getattr(a, "user_id",  None)
    )
    patient_name  = "—"
    patient_email = ""
    if patient_id:
        patient = db.session.get(UserModel, patient_id)
        if patient:
            patient_name  = patient.full_name or patient.email
            patient_email = patient.email or ""

    # Meeting link — upgrade old fake Google Meet links to real Jitsi rooms
    meeting_link = getattr(a, "meeting_link", None)
    if not meeting_link or "meet.google.com/smx" in str(meeting_link):
        try:
            from app.utils.notifications import generate_meeting_link
            meeting_link = generate_meeting_link(a.id)
        except Exception:
            meeting_link = f"https://meet.jit.si/SmartXRay-apt-{a.id}"

    note = (
        getattr(a, "patient_note", None)
        or getattr(a, "note",       None)
    )
    fee = (
        getattr(a, "fee_amount",   None)
        or getattr(a, "fee_snapshot", 0.0)
    )

    # Scheduled datetime string (prefer new column, fall back to old)
    sched = getattr(a, "scheduled_at", None)
    if sched and hasattr(sched, "isoformat"):
        scheduled_at_str = sched.isoformat()
    else:
        apt_date = getattr(a, "appointment_date", None)
        apt_time = getattr(a, "appointment_time", "00:00")
        scheduled_at_str = f"{apt_date}T{apt_time}" if apt_date else None

    # Attached scan — patient may have included their X-ray for the doctor to review
    attached_scan = None
    scan_id = getattr(a, "scan_id", None)
    if scan_id:
        try:
            from app.models.scan import Scan as ScanModel
            s = db.session.get(ScanModel, scan_id)
            if s:
                attached_scan = {
                    "id":          s.id,
                    "prediction":  s.prediction,
                    "confidence":  round(s.confidence * 100, 2),
                    "created_at":  s.created_at.isoformat() if s.created_at else None,
                    "image_url":   f"/static/{s.image_path}" if s.image_path else None,
                    "heatmap_url": f"/static/{s.heatmap_path}" if s.heatmap_path else None,
                    "report_id":   s.report_id,
                    "report_url":  f"/api/appointments/{a.id}/scan-report" if s.report_id else None,
                }
        except Exception:
            pass

    return {
        "appointment_id":  a.id,
        "patient_id":      patient_id,
        "patient_name":    patient_name,
        "patient_email":   patient_email,
        "scheduled_at":    scheduled_at_str,
        "date":            str(getattr(a, "appointment_date", None) or ""),
        "time":            getattr(a, "appointment_time", ""),
        "status":          a.status,
        "patient_note":    note,
        "meeting_link":    meeting_link,
        "fee":             float(fee or 0),
        "payment_method":  getattr(a, "payment_method", "ABA KHQR"),
        "payment_status":  getattr(a, "payment_status", "paid"),
        "duration_min":    getattr(a, "duration_min", 30),
        "attached_scan":   attached_scan,
    }


def _get_recent_reviews(doctor_id: int, limit: int = 3) -> list:
    """
    Return last `limit` reviews for this doctor.
    Uses raw SQL so it works before the Review ORM model is created.
    """
    try:
        rows = db.session.execute(text("""
            SELECT
                r.id,
                r.rating,
                r.comment,
                r.created_at,
                u.full_name  AS patient_name
            FROM reviews r
            JOIN users u ON u.id = r.patient_id
            WHERE r.doctor_id = :did
            ORDER BY r.created_at DESC
            LIMIT :lim
        """), {"did": doctor_id, "lim": limit}).fetchall()

        return [
            {
                "review_id":    row[0],
                "rating":       row[1],
                "comment":      row[2],
                "created_at":   row[3].isoformat() if row[3] else None,
                "patient_name": row[4] or "Patient",
            }
            for row in rows
        ]
    except Exception:
        # reviews table doesn't exist yet — return empty list
        return []
