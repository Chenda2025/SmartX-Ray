"""
Admin Dashboard blueprints
──────────────────────────
admin_bp     → /admin/          (server-rendered HTML pages)
admin_api_bp → /api/admin/      (JSON REST API)

Authentication
──────────────
Admin users have is_admin=True in the DB.
POST /api/admin/login  issues a JWT with {"is_admin": True} in additional
claims and an 8-hour expiry.  Every /api/admin/* route is protected by the
@admin_required decorator from app.utils.auth_helpers.
"""

from datetime import timedelta, datetime, timezone
from flask import (
    Blueprint, jsonify, render_template, request, redirect, url_for
)
from flask_jwt_extended import create_access_token
from sqlalchemy import func, desc

from app.extensions import db
from app.utils.auth_helpers import admin_required

# ── Blueprints ─────────────────────────────────────────────────────────────
admin_bp     = Blueprint("admin",     __name__)   # HTML pages
admin_api_bp = Blueprint("admin_api", __name__)   # JSON API


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE ROUTES  (server-rendered Jinja2 shells — data loaded via AJAX)
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route("/")
def admin_root():
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/login")
def admin_login_page():
    return render_template("admin/login.html")


@admin_bp.route("/dashboard")
def admin_dashboard():
    return render_template("admin/dashboard.html", active="dashboard")


@admin_bp.route("/users")
def admin_users_page():
    return render_template("admin/users.html", active="users")


@admin_bp.route("/ads")
def admin_ads_page():
    return render_template("admin/ads.html", active="ads")


@admin_bp.route("/subscriptions")
def admin_subscriptions_page():
    return render_template("admin/subscriptions.html", active="subscriptions")


@admin_bp.route("/marketplace")
def admin_marketplace_page():
    return render_template("admin/marketplace.html", active="marketplace")


@admin_bp.route("/logs")
def admin_logs_page():
    return render_template("admin/logs.html", active="logs")


# ══════════════════════════════════════════════════════════════════════════════
#  API: AUTHENTICATION
# ══════════════════════════════════════════════════════════════════════════════

@admin_api_bp.route("/login", methods=["POST"])
def admin_login():
    """POST /api/admin/login — authenticate and receive 8-hour JWT."""
    from app.models.user import User
    from app.models.system_log import SystemLog

    data     = request.get_json(silent=True) or {}
    email    = data.get("email", "").lower().strip()
    password = data.get("password", "")
    ip       = request.remote_addr

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        # Log failed attempt
        entry = SystemLog.log_auth(
            "auth_fail", user_id=user.id if user else None,
            ip=ip, message=f"Admin login failed for {email}"
        )
        db.session.add(entry)
        db.session.commit()
        return jsonify({"error": "Invalid credentials."}), 401

    if not user.is_admin:
        return jsonify({"error": "This account does not have admin access."}), 403

    if not user.is_active:
        return jsonify({"error": "Account is suspended."}), 403

    # Issue 8-hour admin JWT
    token = create_access_token(
        identity=str(user.id),
        expires_delta=timedelta(hours=8),
        additional_claims={"is_admin": True, "email": user.email},
    )

    entry = SystemLog.log_auth(
        "auth_login", user_id=user.id,
        ip=ip, message=f"Admin login: {email}"
    )
    db.session.add(entry)
    db.session.commit()

    return jsonify({
        "access_token": token,
        "admin": {
            "id":        user.id,
            "email":     user.email,
            "full_name": user.full_name,
        },
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
#  API: OVERVIEW STATS
# ══════════════════════════════════════════════════════════════════════════════

@admin_api_bp.route("/stats", methods=["GET"])
@admin_required
def admin_stats():
    """GET /api/admin/stats — dashboard overview numbers."""
    from app.models.user         import User
    from app.models.scan         import Scan
    from app.models.subscription import Subscription
    from app.models.ad           import Ad
    from app.models.doctor       import Doctor

    today = datetime.now(timezone.utc).date()

    total_users   = User.query.count()
    free_users    = User.query.filter_by(tier="free").count()
    pro_users     = User.query.filter_by(tier="pro").count()
    total_scans   = Scan.query.count()
    scans_today   = (
        Scan.query
        .filter(func.date(Scan.created_at) == today)
        .count()
    )
    pneumonia_cnt = Scan.query.filter_by(prediction="PNEUMONIA").count()
    normal_cnt    = Scan.query.filter_by(prediction="NORMAL").count()
    active_subs   = Subscription.query.filter_by(status="active").count()
    pending_docs  = Doctor.query.filter_by(is_verified=False, is_active=True).count()
    active_ads    = Ad.query.filter_by(is_active=True).count()

    total_impressions = db.session.query(func.sum(Ad.impressions)).scalar() or 0
    total_clicks      = db.session.query(func.sum(Ad.clicks)).scalar()      or 0

    # Rough revenue estimate (active pro users × monthly price)
    monthly_revenue = round(pro_users * 9.99, 2)

    return jsonify({
        "users": {
            "total": total_users,
            "free":  free_users,
            "pro":   pro_users,
        },
        "scans": {
            "total":     total_scans,
            "today":     scans_today,
            "pneumonia": pneumonia_cnt,
            "normal":    normal_cnt,
        },
        "subscriptions": {
            "active":           active_subs,
            "monthly_revenue":  monthly_revenue,
        },
        "ads": {
            "active":      active_ads,
            "impressions": total_impressions,
            "clicks":      total_clicks,
        },
        "marketplace": {
            "pending_approvals": pending_docs,
        },
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
#  API: USER MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

@admin_api_bp.route("/users", methods=["GET"])
@admin_required
def list_users():
    """GET /api/admin/users?tier=&status=&search=&order=desc|asc&page=&limit="""
    from app.models.user import User

    tier       = request.args.get("tier")
    status     = request.args.get("status")        # active | suspended
    search     = request.args.get("search", "").strip()
    order      = request.args.get("order", "desc") # desc = New→Old, asc = Old→New
    page       = request.args.get("page", 1, type=int)
    limit      = min(request.args.get("limit", 20, type=int), 100)

    q = User.query

    if tier:
        q = q.filter_by(tier=tier)
    if status == "active":
        q = q.filter_by(is_active=True)
    elif status == "suspended":
        q = q.filter_by(is_active=False)
    if search:
        pattern = f"%{search}%"
        q = q.filter(
            (User.email.ilike(pattern)) | (User.full_name.ilike(pattern))
        )

    sort_col = User.created_at.asc() if order == "asc" else desc(User.created_at)
    pag = q.order_by(sort_col).paginate(
        page=page, per_page=limit, error_out=False
    )

    return jsonify({
        "users":    [u.to_dict() for u in pag.items],
        "total":    pag.total,
        "page":     pag.page,
        "pages":    pag.pages,
        "has_next": pag.has_next,
    }), 200


@admin_api_bp.route("/users/<int:user_id>/tier", methods=["PATCH"])
@admin_required
def toggle_user_tier(user_id):
    """PATCH /api/admin/users/<id>/tier  body: {"tier": "free"|"pro"}"""
    from app.models.user import User
    from app.models.system_log import SystemLog

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404

    data    = request.get_json(silent=True) or {}
    new_tier = data.get("tier")
    if new_tier not in ("free", "pro"):
        return jsonify({"error": "tier must be 'free' or 'pro'."}), 400

    old_tier   = user.tier
    user.tier  = new_tier
    log = SystemLog(
        event_type="admin_action", severity="info", user_id=user_id,
        message=f"Tier changed {old_tier} → {new_tier} for {user.email}",
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({"message": f"Tier updated to {new_tier}.", "user": user.to_dict()}), 200


@admin_api_bp.route("/users/<int:user_id>/status", methods=["PATCH"])
@admin_required
def toggle_user_status(user_id):
    """PATCH /api/admin/users/<id>/status  body: {"is_active": true|false}"""
    from app.models.user import User
    from app.models.system_log import SystemLog

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404

    data      = request.get_json(silent=True) or {}
    is_active = data.get("is_active")
    if not isinstance(is_active, bool):
        return jsonify({"error": "is_active must be true or false."}), 400

    action        = "activated" if is_active else "suspended"
    user.is_active = is_active
    log = SystemLog(
        event_type="admin_action", severity="warning" if not is_active else "info",
        user_id=user_id,
        message=f"User {user.email} {action} by admin",
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({"message": f"User {action}.", "user": user.to_dict()}), 200


# ══════════════════════════════════════════════════════════════════════════════
#  API: AD MANAGER
# ══════════════════════════════════════════════════════════════════════════════

@admin_api_bp.route("/ads", methods=["GET"])
@admin_required
def list_ads():
    """GET /api/admin/ads"""
    from app.models.ad import Ad

    ads = Ad.query.order_by(desc(Ad.priority), desc(Ad.created_at)).all()
    return jsonify([{
        "id":          a.id,
        "title":       a.title,
        "body":        a.body,
        "image_url":   a.image_url,
        "target_url":  a.target_url,
        "advertiser":  a.advertiser,
        "placement":   a.placement,
        "is_active":   a.is_active,
        "priority":    a.priority,
        "impressions": a.impressions,
        "clicks":      a.clicks,
        "ctr":         round(a.ctr * 100, 2),   # percentage
        "start_date":  a.start_date.isoformat() if a.start_date else None,
        "end_date":    a.end_date.isoformat()   if a.end_date   else None,
        "created_at":  a.created_at.isoformat() if a.created_at else None,
    } for a in ads]), 200


@admin_api_bp.route("/ads", methods=["POST"])
@admin_required
def create_ad():
    """POST /api/admin/ads — create a new ad."""
    from app.models.ad import Ad
    from app.models.system_log import SystemLog

    data = request.get_json(silent=True) or {}
    for field in ("title", "body", "target_url"):
        if not data.get(field):
            return jsonify({"error": f"'{field}' is required."}), 400

    ad = Ad(
        title      = data["title"].strip(),
        body       = data["body"].strip(),
        image_url  = data.get("image_url", "").strip() or None,
        target_url = data["target_url"].strip(),
        advertiser = data.get("advertiser", "").strip() or None,
        placement  = data.get("placement", "banner"),
        priority   = int(data.get("priority", 0)),
        is_active  = bool(data.get("is_active", True)),
    )
    db.session.add(ad)
    db.session.flush()

    log = SystemLog(
        event_type="admin_action", severity="info",
        message=f"Ad created: '{ad.title}' (id={ad.id})",
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({"message": "Ad created.", "id": ad.id}), 201


@admin_api_bp.route("/ads/<int:ad_id>", methods=["PATCH"])
@admin_required
def update_ad(ad_id):
    """PATCH /api/admin/ads/<id> — update fields."""
    from app.models.ad import Ad

    ad = db.session.get(Ad, ad_id)
    if not ad:
        return jsonify({"error": "Ad not found."}), 404

    data = request.get_json(silent=True) or {}
    for field in ("title", "body", "image_url", "target_url", "advertiser",
                  "placement", "priority", "is_active"):
        if field in data:
            setattr(ad, field, data[field])

    db.session.commit()
    return jsonify({"message": "Ad updated."}), 200


@admin_api_bp.route("/ads/<int:ad_id>", methods=["DELETE"])
@admin_required
def delete_ad(ad_id):
    """DELETE /api/admin/ads/<id>"""
    from app.models.ad import Ad
    from app.models.system_log import SystemLog

    ad = db.session.get(Ad, ad_id)
    if not ad:
        return jsonify({"error": "Ad not found."}), 404

    title = ad.title
    db.session.delete(ad)
    log = SystemLog(
        event_type="admin_action", severity="warning",
        message=f"Ad deleted: '{title}' (id={ad_id})",
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({"message": "Ad deleted."}), 200


# ══════════════════════════════════════════════════════════════════════════════
#  API: SUBSCRIPTIONS
# ══════════════════════════════════════════════════════════════════════════════

@admin_api_bp.route("/subscriptions", methods=["GET"])
@admin_required
def list_subscriptions():
    """GET /api/admin/subscriptions — revenue stats + list."""
    from app.models.subscription import Subscription
    from app.models.user         import User

    page  = request.args.get("page", 1, type=int)
    limit = min(request.args.get("limit", 20, type=int), 100)

    pag = (
        Subscription.query
        .filter(Subscription.status.in_(["active", "trialing"]))
        .order_by(desc(Subscription.created_at))
        .paginate(page=page, per_page=limit, error_out=False)
    )

    monthly_count = Subscription.query.filter_by(
        status="active", plan="monthly"
    ).count()
    yearly_count  = Subscription.query.filter_by(
        status="active", plan="yearly"
    ).count()

    revenue_monthly = round(monthly_count * 9.99,  2)
    revenue_yearly  = round(yearly_count  * 79.99, 2)
    revenue_total   = round(revenue_monthly + revenue_yearly, 2)

    items = []
    for s in pag.items:
        u = db.session.get(User, s.user_id)
        items.append({
            "id":          s.id,
            "user_email":  u.email     if u else None,
            "user_name":   u.full_name if u else None,
            "plan":        s.plan,
            "status":      s.status,
            "period_end":  s.current_period_end.isoformat() if s.current_period_end else None,
            "cancel_at_end": s.cancel_at_period_end,
            "created_at":  s.created_at.isoformat() if s.created_at else None,
        })

    return jsonify({
        "revenue": {
            "monthly_subscribers": monthly_count,
            "yearly_subscribers":  yearly_count,
            "monthly_mrr":         revenue_monthly,
            "yearly_revenue":      revenue_yearly,
            "total_arr":           revenue_total,
        },
        "subscriptions": items,
        "total":   pag.total,
        "page":    pag.page,
        "pages":   pag.pages,
        "has_next": pag.has_next,
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
#  API: MARKETPLACE (DOCTOR APPROVAL)
# ══════════════════════════════════════════════════════════════════════════════

@admin_api_bp.route("/marketplace/doctors", methods=["GET"])
@admin_required
def list_marketplace_doctors():
    """GET /api/admin/marketplace/doctors?status=pending|approved|all"""
    from app.models.doctor import Doctor

    status = request.args.get("status", "pending")
    page   = request.args.get("page", 1, type=int)
    limit  = min(request.args.get("limit", 20, type=int), 100)

    q = Doctor.query
    if status == "pending":
        q = q.filter_by(is_verified=False, is_active=True)
    elif status == "approved":
        q = q.filter_by(is_verified=True)
    elif status == "rejected":
        q = q.filter_by(is_active=False)

    pag = q.order_by(desc(Doctor.created_at)).paginate(
        page=page, per_page=limit, error_out=False
    )

    return jsonify({
        "doctors": [d.to_dict() for d in pag.items],
        "total":   pag.total,
        "page":    pag.page,
        "pages":   pag.pages,
    }), 200


@admin_api_bp.route("/marketplace/doctors/<int:doctor_id>/approve", methods=["PATCH"])
@admin_required
def approve_doctor(doctor_id):
    """PATCH /api/admin/marketplace/doctors/<id>/approve"""
    from app.models.doctor import Doctor
    from app.models.system_log import SystemLog

    doctor = db.session.get(Doctor, doctor_id)
    if not doctor:
        return jsonify({"error": "Doctor not found."}), 404

    doctor.is_verified = True
    doctor.is_active   = True
    log = SystemLog(
        event_type="admin_action", severity="info",
        message=f"Doctor approved: {doctor.full_name} (id={doctor_id})",
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({"message": f"Dr. {doctor.full_name} approved.", "doctor": doctor.to_dict()}), 200


@admin_api_bp.route("/marketplace/doctors/<int:doctor_id>/reject", methods=["PATCH"])
@admin_required
def reject_doctor(doctor_id):
    """PATCH /api/admin/marketplace/doctors/<id>/reject"""
    from app.models.doctor import Doctor
    from app.models.system_log import SystemLog

    doctor = db.session.get(Doctor, doctor_id)
    if not doctor:
        return jsonify({"error": "Doctor not found."}), 404

    doctor.is_active   = False
    doctor.is_verified = False
    log = SystemLog(
        event_type="admin_action", severity="warning",
        message=f"Doctor rejected: {doctor.full_name} (id={doctor_id})",
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({"message": f"Dr. {doctor.full_name} rejected.", "doctor": doctor.to_dict()}), 200


# ══════════════════════════════════════════════════════════════════════════════
#  API: TELEGRAM BOT
# ══════════════════════════════════════════════════════════════════════════════

@admin_api_bp.route("/telegram/status", methods=["GET"])
@admin_required
def telegram_status():
    """
    GET /api/admin/telegram/status
    Returns whether the bot is configured and live info from Telegram getMe.
    """
    import requests as _req
    from flask import current_app

    token   = current_app.config.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = current_app.config.get("TELEGRAM_CHAT_ID",   "").strip()
    configured = bool(token and chat_id)

    bot_username = None
    bot_name     = None
    reachable    = False

    if configured:
        try:
            r = _req.get(
                f"https://api.telegram.org/bot{token}/getMe",
                timeout=5,
            )
            if r.ok:
                info         = r.json().get("result", {})
                bot_username = info.get("username")
                bot_name     = info.get("first_name")
                reachable    = True
        except Exception:
            pass

    # Mask chat_id: show first 3 chars then ***
    chat_id_preview = (chat_id[:3] + "***") if chat_id else None

    return jsonify({
        "configured":     configured,
        "reachable":      reachable,
        "token_set":      bool(token),
        "chat_id_set":    bool(chat_id),
        "chat_id_preview": chat_id_preview,
        "bot_username":   bot_username,
        "bot_name":       bot_name,
    }), 200


@admin_api_bp.route("/telegram/test", methods=["POST"])
@admin_required
def telegram_test():
    """
    POST /api/admin/telegram/test
    Sends a test alert to confirm the bot is working.
    """
    from flask import current_app
    from app.services.telegram_service import send_telegram_alert
    from app.models.system_log import SystemLog

    token   = current_app.config.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = current_app.config.get("TELEGRAM_CHAT_ID",   "").strip()

    if not token or not chat_id:
        return jsonify({
            "ok":      False,
            "message": "Telegram not configured. Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env and restart.",
        }), 400

    msg = (
        "✅ <b>SmartX-Ray — Test Alert</b>\n\n"
        "Telegram alerts are configured and working correctly! 🎉\n\n"
        "<i>Sent from the SmartX-Ray admin panel.</i>"
    )
    ok = send_telegram_alert(msg)

    log = SystemLog(
        event_type="admin_action",
        severity="info",
        message="Admin sent Telegram test alert",
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    if ok:
        return jsonify({"ok": True,  "message": "Test message sent — check your Telegram!"}), 200
    else:
        return jsonify({"ok": False, "message": "Bot is configured but message delivery failed. Check token and chat_id."}), 502


# ══════════════════════════════════════════════════════════════════════════════
#  API: SYSTEM LOGS
# ══════════════════════════════════════════════════════════════════════════════

@admin_api_bp.route("/logs", methods=["GET"])
@admin_required
def list_logs():
    """GET /api/admin/logs?severity=&event_type=&page=&limit="""
    from app.models.system_log import SystemLog

    severity   = request.args.get("severity")
    event_type = request.args.get("event_type")
    page       = request.args.get("page", 1, type=int)
    limit      = min(request.args.get("limit", 50, type=int), 200)

    q = SystemLog.query
    if severity:
        q = q.filter_by(severity=severity)
    if event_type:
        q = q.filter_by(event_type=event_type)

    pag = q.order_by(desc(SystemLog.created_at)).paginate(
        page=page, per_page=limit, error_out=False
    )

    return jsonify({
        "logs":     [l.to_dict() for l in pag.items],
        "total":    pag.total,
        "page":     pag.page,
        "pages":    pag.pages,
        "has_next": pag.has_next,
    }), 200
