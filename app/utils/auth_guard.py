"""
app/utils/auth_guard.py — Role-based access control decorators
══════════════════════════════════════════════════════════════════════════════
Four decorators that guard Flask API endpoints by role.

  @admin_required     JWT valid  +  user.is_admin = True
  @doctor_required    JWT valid  +  doctor.status = 'approved'  +  is_active
  @patient_required   JWT valid  +  user is active  +  not admin
  @pro_required       JWT valid  +  user.tier = 'pro'

Injections (set on Flask g):
  g.current_user    — User model instance  (all decorators)
  g.current_doctor  — Doctor model instance (doctor_required only)

Usage:
    from app.utils.auth_guard import doctor_required, admin_required

    @doctor_bp.route("/dashboard")
    @doctor_required
    def dashboard():
        doctor = g.current_doctor   # safe to access directly
        user   = g.current_user
        ...

Backward compat:
    admin_required and pro_required here supersede the ones in
    app/utils/auth_helpers.py (identical behaviour, also sets g.current_user).
══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import wraps

from flask import current_app, jsonify, g
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from app.extensions import db

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_user(raw_identity):
    """Return User by JWT identity (stored as string), or None."""
    from app.models.user import User
    try:
        uid = int(raw_identity)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, uid)


def _load_doctor(user) -> object | None:
    """
    Return Doctor model linked to this user.
    Tries user_id FK first (post-migration), falls back to email match.
    """
    from app.models.doctor import Doctor

    # Post-migration: user_id FK
    try:
        doc = Doctor.query.filter_by(user_id=user.id).first()
        if doc:
            return doc
    except Exception:
        pass

    # Pre-migration: match by email
    try:
        return Doctor.query.filter_by(email=user.email).first()
    except Exception:
        return None


def _doctor_status(doctor) -> str:
    """
    Return the doctor's status string.
    Prefers an explicit 'status' column; falls back to the derived property
    that reads is_verified + is_active flags (pre-migration).
    """
    # The ORM model exposes 'status' either as a column (post-migration)
    # or as a @property that derives from flags (pre-migration).
    # Either way, doctor.status works.
    return doctor.status  # 'approved' | 'pending' | 'rejected'


# ─────────────────────────────────────────────────────────────────────────────
# @admin_required
# ─────────────────────────────────────────────────────────────────────────────

def admin_required(fn):
    """
    Guard: valid JWT  +  is_admin claim in token  +  user.is_admin in DB.

    Two-layer check:
      1. JWT claims: must contain is_admin=True  (fast, no DB query)
      2. Database  : user must still be active + is_admin (revocation check)

    Sets g.current_user on success.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()

        # ── Layer 1: JWT claim (fast path) ────────────────────────────
        claims = get_jwt()
        if not claims.get("is_admin"):
            return jsonify({
                "error":   "admin_required",
                "message": "Admin access required.",
            }), 403

        # ── Layer 2: DB check (revocation / account change) ───────────
        user = _load_user(get_jwt_identity())
        if not user:
            return jsonify({"error": "Account not found."}), 401
        if not user.is_active:
            return jsonify({
                "error":   "account_disabled",
                "message": "This account has been disabled.",
            }), 403
        if not user.is_admin:
            return jsonify({
                "error":   "admin_required",
                "message": "Admin privileges have been revoked.",
            }), 403

        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# @doctor_required
# ─────────────────────────────────────────────────────────────────────────────

def doctor_required(fn):
    """
    Guard: valid JWT  +  doctor record exists  +  status = 'approved'  +  is_active.

    Error codes returned in JSON body:
      pending_approval   — application submitted but not yet reviewed
      profile_rejected   — application was rejected (includes reject_reason)
      no_doctor_profile  — JWT valid but no Doctor row linked to this user
      account_disabled   — user.is_active = False

    Sets g.current_user and g.current_doctor on success.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()

        # ── 1. Load user ──────────────────────────────────────────────
        user = _load_user(get_jwt_identity())
        if not user:
            return jsonify({"error": "User not found."}), 404

        if not user.is_active:
            return jsonify({
                "error":   "account_disabled",
                "message": "Your account has been disabled. Contact the admin.",
            }), 403

        # ── 2. Load doctor profile ────────────────────────────────────
        doctor = _load_doctor(user)
        if not doctor:
            return jsonify({
                "error":   "no_doctor_profile",
                "message": "No doctor profile is linked to this account.",
                "hint":    "POST /api/doctor/register to create one.",
            }), 403

        # ── 3. Check approval status ──────────────────────────────────
        status = _doctor_status(doctor)

        if status == "pending":
            return jsonify({
                "error":   "pending_approval",
                "message": "Your application is under review. "
                           "You will receive an email when a decision is made "
                           "(within 24 hours).",
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
                                 "Please update your profile and resubmit.",
                "reject_reason": reason,
                "status":        "rejected",
            }), 403

        if status != "approved":
            # Catch any unexpected status values
            logger.warning(
                "Unexpected doctor status '%s' for doctor_id=%s", status, doctor.id
            )
            return jsonify({
                "error":   "not_approved",
                "message": "Doctor account is not approved.",
            }), 403

        # ── 4. Inject into Flask g ────────────────────────────────────
        g.current_user   = user
        g.current_doctor = doctor
        return fn(*args, **kwargs)

    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# @patient_required
# ─────────────────────────────────────────────────────────────────────────────

def patient_required(fn):
    """
    Guard: valid JWT  +  user is active  +  user is NOT an admin.

    This decorator is intentionally permissive about the exact role:
    both 'patient' (post-migration) and regular non-admin users (pre-migration)
    are allowed through.  Admin and doctor accounts are blocked.

    Sets g.current_user on success.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()

        user = _load_user(get_jwt_identity())
        if not user:
            return jsonify({"error": "User not found."}), 404
        if not user.is_active:
            return jsonify({
                "error":   "account_disabled",
                "message": "Your account has been disabled.",
            }), 403

        # Admins should not call patient endpoints
        if user.is_admin:
            return jsonify({
                "error":   "wrong_role",
                "message": "Admin accounts cannot access patient endpoints.",
            }), 403

        # Post-migration role check (role column exists)
        role = getattr(user, "role", None)
        if role and role not in ("patient",):
            return jsonify({
                "error":   "wrong_role",
                "message": "This endpoint is for patients only.",
            }), 403

        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# @pro_required
# ─────────────────────────────────────────────────────────────────────────────

def pro_required(fn):
    """
    Guard: valid JWT  +  user.tier = 'pro'.

    Returns 403 with upgrade_url for free-tier users.
    Sets g.current_user on success.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()

        user = _load_user(get_jwt_identity())
        if not user:
            return jsonify({"error": "User not found."}), 404
        if not user.is_active:
            return jsonify({
                "error":   "account_disabled",
                "message": "Account not found or disabled.",
            }), 401

        if not user.is_pro:
            return jsonify({
                "error":        "upgrade_required",
                "message":      "This feature requires a Pro subscription.",
                "upgrade_url":  "/pricing",
                "current_tier": user.tier,
            }), 403

        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# Convenience re-exports (keeps existing imports from auth_helpers working)
# ─────────────────────────────────────────────────────────────────────────────

#: Alias — identical to admin_required above.
#: Existing code using ``from app.utils.auth_helpers import admin_required``
#: should be migrated to ``from app.utils.auth_guard import admin_required``.
jwt_required_admin = admin_required
jwt_required_pro   = pro_required


# ─────────────────────────────────────────────────────────────────────────────
# Compat shims  (replaces app/utils/auth_helpers.py entirely)
# ─────────────────────────────────────────────────────────────────────────────

def _get_current_user():
    """Return the User for the current JWT identity (raises if no active JWT)."""
    from app.models.user import User
    try:
        uid = int(get_jwt_identity())
    except (TypeError, ValueError):
        return None
    return db.session.get(User, uid)


def jwt_required_user(fn):
    """Decorator: valid JWT + active user (any role)."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user = _get_current_user()
        if not user or not user.is_active:
            return jsonify({"error": "Account not found or disabled."}), 401
        return fn(*args, **kwargs)
    return wrapper


def check_scan_quota(user) -> tuple[bool, str | None]:
    """
    Returns (allowed: bool, error_msg: str | None).
    Resets daily counter if it's a new UTC day.
    Pro users are never rate-limited.
    """
    if user.is_pro:
        return True, None

    now = datetime.now(timezone.utc)
    if not user.scans_reset_at or user.scans_reset_at.date() < now.date():
        user.scans_today = 0
        user.scans_reset_at = now
        db.session.flush()

    limit = current_app.config["FREE_SCANS_PER_DAY"]
    if user.scans_today >= limit:
        return False, (
            f"Free tier limit reached ({limit} scans/day). "
            "Upgrade to Pro for unlimited scans."
        )
    return True, None
