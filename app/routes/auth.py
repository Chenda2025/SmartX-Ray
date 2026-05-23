from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity,
)
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from app.extensions import db
from app.models.user import User
from app.utils.validators import validate_email, validate_password
from app.utils.auth_helpers import jwt_required_user, _get_current_user

auth_bp = Blueprint("auth", __name__)


# ── POST /api/auth/register ────────────────────────────────────────────────
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    email     = (data.get("email") or "").strip().lower()
    password  = data.get("password", "")
    full_name = (data.get("full_name") or "").strip()

    err = validate_email(email) or validate_password(password)
    if err:
        return jsonify({"error": err}), 400
    if not full_name:
        return jsonify({"error": "Full name is required."}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered."}), 409

    user = User(email=email, full_name=full_name)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    access  = create_access_token(identity=str(user.id))
    refresh = create_refresh_token(identity=str(user.id))
    return jsonify({
        "message": "Account created.",
        "user":    user.to_dict(),
        "access_token":  access,
        "refresh_token": refresh,
    }), 201


# ── POST /api/auth/login ───────────────────────────────────────────────────
@auth_bp.route("/login", methods=["POST"])
def login():
    data     = request.get_json(silent=True) or {}
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password", "")

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password."}), 401
    if not user.is_active:
        return jsonify({"error": "Account is disabled."}), 403

    access  = create_access_token(identity=str(user.id))
    refresh = create_refresh_token(identity=str(user.id))
    return jsonify({
        "user":          user.to_dict(),
        "access_token":  access,
        "refresh_token": refresh,
    }), 200


# ── POST /api/auth/refresh ────────────────────────────────────────────────
@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    access  = create_access_token(identity=user_id)
    return jsonify({"access_token": access}), 200


# ── GET /api/auth/me ──────────────────────────────────────────────────────
@auth_bp.route("/me", methods=["GET"])
@jwt_required_user
def me():
    user = _get_current_user()
    data = user.to_dict()

    # Include subscription status if exists
    if user.subscription:
        data["subscription"] = user.subscription.to_dict()

    # Include today's scan usage
    data["scans_today"] = user.scans_today
    return jsonify(data), 200


# ── PATCH /api/auth/me ────────────────────────────────────────────────────
@auth_bp.route("/me", methods=["PATCH"])
@jwt_required_user
def update_me():
    user = _get_current_user()
    data = request.get_json(silent=True) or {}

    if "full_name" in data:
        name = data["full_name"].strip()
        if not name:
            return jsonify({"error": "Full name cannot be empty."}), 400
        user.full_name = name

    if "avatar_url" in data:
        user.avatar_url = data["avatar_url"]

    if "password" in data:
        err = validate_password(data["password"])
        if err:
            return jsonify({"error": err}), 400
        if not data.get("current_password") or not user.check_password(data["current_password"]):
            return jsonify({"error": "Current password is incorrect."}), 403
        user.set_password(data["password"])

    db.session.commit()
    return jsonify({"user": user.to_dict()}), 200


# ── POST /api/auth/logout ─────────────────────────────────────────────────
@auth_bp.route("/logout", methods=["POST"])
@jwt_required_user
def logout():
    # Stateless JWT — client must discard tokens.
    # Add a token blocklist here if needed in production.
    return jsonify({"message": "Logged out."}), 200


# ── POST /api/auth/forgot-password ────────────────────────────────────────
@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if validate_email(email):
        return jsonify({"error": "Invalid email address."}), 400

    user = User.query.filter_by(email=email).first()
    # Always return 200 to prevent user enumeration
    if user:
        s     = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        token = s.dumps(user.email, salt="password-reset")
        from app.services.email_service import send_password_reset
        send_password_reset(user, token)

    return jsonify({"message": "If that email is registered, a reset link has been sent."}), 200


# ── POST /api/auth/reset-password ─────────────────────────────────────────
@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    data     = request.get_json(silent=True) or {}
    token    = data.get("token", "")
    password = data.get("password", "")

    err = validate_password(password)
    if err:
        return jsonify({"error": err}), 400

    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        email = s.loads(token, salt="password-reset", max_age=1800)  # 30 min
    except SignatureExpired:
        return jsonify({"error": "Reset link has expired. Please request a new one."}), 400
    except BadSignature:
        return jsonify({"error": "Invalid or tampered reset link."}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User not found."}), 404

    user.set_password(password)
    db.session.commit()
    return jsonify({"message": "Password updated. You can now log in."}), 200
