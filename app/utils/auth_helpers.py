from functools import wraps
from datetime import datetime, timezone, timedelta
from flask import jsonify, current_app
from flask_jwt_extended import get_jwt_identity, get_jwt, verify_jwt_in_request
from app.extensions import db


def _get_current_user():
    from app.models.user import User
    user_id = int(get_jwt_identity())   # identity stored as str, PK is int
    return db.session.get(User, user_id)


def jwt_required_user(fn):
    """Decorator: valid JWT + active user."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user = _get_current_user()
        if not user or not user.is_active:
            return jsonify({"error": "Account not found or disabled."}), 401
        return fn(*args, **kwargs)
    return wrapper


def pro_required(fn):
    """Decorator: valid JWT + Pro tier. Returns 403 with upgrade hint for free users."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user = _get_current_user()
        if not user or not user.is_active:
            return jsonify({"error": "Account not found or disabled."}), 401
        if not user.is_pro:
            return jsonify({
                "error": "Pro subscription required.",
                "upgrade_url": "/pricing",
            }), 403
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    """
    Decorator: valid JWT with is_admin claim + is_admin=True in the DB.
    Admin tokens are issued with 8-hour expiry via POST /api/admin/login.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        # Fast check: must have is_admin=True in JWT additional claims
        claims = get_jwt()
        if not claims.get("is_admin"):
            return jsonify({"error": "Admin access required."}), 403
        # DB check: user must still be active and admin
        user = _get_current_user()
        if not user or not user.is_active:
            return jsonify({"error": "Account not found or disabled."}), 401
        if not user.is_admin:
            return jsonify({"error": "Admin privileges revoked."}), 403
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
    # Reset if the last reset was on a different UTC day
    if not user.scans_reset_at or user.scans_reset_at.date() < now.date():
        user.scans_today = 0
        user.scans_reset_at = now
        db.session.flush()

    limit = current_app.config["FREE_SCANS_PER_DAY"]
    if user.scans_today >= limit:
        return False, f"Free tier limit reached ({limit} scans/day). Upgrade to Pro for unlimited scans."

    return True, None
