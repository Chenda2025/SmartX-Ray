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
@admin_required decorator from app.utils.auth_guard.
"""

from datetime import timedelta, datetime, timezone
from flask import (
    Blueprint, g, jsonify, render_template, request, redirect, url_for,
    current_app,
)
from flask_jwt_extended import create_access_token
from sqlalchemy import func, desc

from app.extensions import db
from app.utils.auth_guard import admin_required


def _base_url() -> str:
    """Return APP_BASE_URL config or fallback to localhost."""
    try:
        return current_app.config.get("APP_BASE_URL", "http://localhost:5000")
    except RuntimeError:
        return "http://localhost:5000"

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


@admin_bp.route("/telegram")
def admin_telegram_page():
    return render_template("admin/telegram.html", active="telegram")


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

    total_users     = User.query.count()
    free_users      = User.query.filter_by(tier="free").count()
    pro_users       = User.query.filter_by(tier="pro").count()
    active_users    = User.query.filter_by(is_active=True).count()
    suspended_users = User.query.filter_by(is_active=False).count()
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
            "total":     total_users,
            "free":      free_users,
            "pro":       pro_users,
            "active":    active_users,
            "suspended": suspended_users,
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


@admin_api_bp.route("/users/export", methods=["GET"])
@admin_required
def export_users():
    """
    GET /api/admin/users/export
    Returns all users as a UTF-8 CSV file (respects same filters as list_users).
    """
    import csv, io
    from app.models.user import User

    tier   = request.args.get("tier")
    status = request.args.get("status")
    search = request.args.get("search", "").strip()
    order  = request.args.get("order", "desc")

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
    users = q.order_by(sort_col).all()

    KH_MONTHS = ["","មករា","កុម្ភៈ","មីនា","មេសា","ឧសភា","មិថុនា",
                  "កក្កដា","សីហា","កញ្ញា","តុលា","វិច្ឆិកា","ធ្នូ"]

    def kh_date(dt):
        if not dt:
            return "—"
        return f"{dt.day:02d}/{dt.month:02d}/{dt.year}"   # DD/MM/YYYY (Cambodia standard)

    output = io.StringIO()
    writer = csv.writer(output)
    # Bilingual headers (Khmer / English)
    writer.writerow([
        "លេខ / ID",
        "ឈ្មោះពេញ / Full Name",
        "អ៊ីមែល / Email",
        "កម្រិត / Tier",
        "ស្ថានភាព / Status",
        "ចំនួនស្កែនថ្ងៃនេះ / Scans Today",
        "កាលបរិច្ឆេទចូលរួម / Joined (DD/MM/YYYY)",
    ])
    for u in users:
        tier_kh   = "Pro ★" if u.tier == "pro" else "ឥតគិតថ្លៃ (Free)"
        status_kh = "សកម្ម (Active)" if u.is_active else "ព្យួរ (Suspended)"
        writer.writerow([
            u.id,
            u.full_name or "—",
            u.email,
            tier_kh,
            status_kh,
            u.scans_today,
            kh_date(u.created_at),
        ])

    from flask import Response
    return Response(
        "﻿" + output.getvalue(),      # UTF-8 BOM — required for Excel Khmer
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=smartxray_users.csv"},
    )


@admin_api_bp.route("/users/export/pdf", methods=["GET"])
@admin_required
def export_users_pdf():
    """
    GET /api/admin/users/export/pdf
    Bilingual Khmer/English PDF using the 3-font Khmer OS system:
      KhmerMuol (headers) · KhmerBattambang (titles) · KhmerSiemreap (body)
    """
    from datetime import datetime, timezone
    from flask import Response, current_app
    from app.models.user import User
    from app.services.pdf_service import generate_user_report_pdf

    # ── Filters (unchanged) ───────────────────────────────────────────────
    tier   = request.args.get("tier")
    status = request.args.get("status")
    search = request.args.get("search", "").strip()
    order  = request.args.get("order", "desc")

    q = User.query
    if tier:
        q = q.filter_by(tier=tier)
    if status == "active":
        q = q.filter_by(is_active=True)
    elif status == "suspended":
        q = q.filter_by(is_active=False)
    if search:
        p = f"%{search}%"
        q = q.filter((User.email.ilike(p)) | (User.full_name.ilike(p)))
    sort_col = User.created_at.asc() if order == "asc" else desc(User.created_at)
    users = q.order_by(sort_col).all()

    # ── Build PDF via shared service (Khmer OS 3-font system) ────────────
    font_dir = None  # pdf_service resolves it automatically
    buf = generate_user_report_pdf(users, font_dir=font_dir)

    fname = f"smartxray_users_{datetime.now(timezone.utc).strftime('%d-%m-%Y')}.pdf"
    return Response(
        buf.read(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


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

@admin_api_bp.route("/ads/upload-image", methods=["POST"])
@admin_required
def upload_ad_image():
    """
    POST /api/admin/ads/upload-image
    Accepts multipart/form-data with field 'image'.
    Saves to static/uploads/ads/ and returns {"url": "/static/uploads/ads/<filename>"}.
    """
    import os, uuid
    from flask import current_app

    if "image" not in request.files:
        return jsonify({"error": "No image field in request."}), 400

    file = request.files["image"]
    if not file or not file.filename:
        return jsonify({"error": "Empty file."}), 400

    allowed = {"png", "jpg", "jpeg", "webp", "gif"}
    ext = (file.filename.rsplit(".", 1)[-1] or "").lower()
    if ext not in allowed:
        return jsonify({"error": f"File type .{ext} not allowed. Use: {', '.join(allowed)}"}), 400

    # Check file size ≤ 5 MB
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > 5 * 1024 * 1024:
        return jsonify({"error": "Image must be under 5 MB."}), 400

    upload_dir = os.path.normpath(
        os.path.join(current_app.root_path, "..", "static", "uploads", "ads")
    )
    os.makedirs(upload_dir, exist_ok=True)

    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(upload_dir, filename))

    return jsonify({"url": f"/static/uploads/ads/{filename}"}), 201


@admin_api_bp.route("/ads/export/pdf", methods=["GET"])
@admin_required
def export_ads_pdf():
    """
    GET /api/admin/ads/export/pdf?lang=en|km
    Returns a bilingual A4 PDF of all advertisements.
    """
    from datetime import datetime, timezone
    from flask import Response
    from app.models.ad import Ad
    from app.services.pdf_service import generate_ad_report_pdf

    lang = request.args.get("lang", "en").lower()
    if lang not in ("en", "km"):
        lang = "en"

    ads = Ad.query.order_by(desc(Ad.priority), desc(Ad.created_at)).all()
    buf = generate_ad_report_pdf(ads, lang=lang)

    fname = f"smartxray_ads_{datetime.now(timezone.utc).strftime('%d-%m-%Y')}.pdf"
    return Response(
        buf.read(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


@admin_api_bp.route("/ads/export/docx", methods=["GET"])
@admin_required
def export_ads_docx():
    """
    GET /api/admin/ads/export/docx?lang=en|km
    Returns a bilingual DOCX report of all advertisements.
    """
    from datetime import datetime, timezone
    from flask import Response
    from app.models.ad import Ad
    from app.services.pdf_service import generate_ad_report_docx

    lang = request.args.get("lang", "en").lower()
    if lang not in ("en", "km"):
        lang = "en"

    ads = Ad.query.order_by(desc(Ad.priority), desc(Ad.created_at)).all()
    buf = generate_ad_report_docx(ads, lang=lang)

    fname = f"smartxray_ads_{datetime.now(timezone.utc).strftime('%d-%m-%Y')}.docx"
    return Response(
        buf.read(),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


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

@admin_api_bp.route("/subscriptions/export/pdf", methods=["GET"])
@admin_required
def export_subscriptions_pdf():
    """
    GET /api/admin/subscriptions/export/pdf?lang=en|km
    Returns a bilingual A4 PDF of all subscriptions.
    """
    from datetime import datetime, timezone
    from flask import Response
    from app.models.subscription import Subscription
    from app.models.user         import User
    from app.services.pdf_service import generate_subscription_report_pdf

    lang = request.args.get("lang", "en").lower()
    if lang not in ("en", "km"):
        lang = "en"

    subs = Subscription.query.order_by(desc(Subscription.created_at)).all()
    # Attach user info
    sub_data = []
    for s in subs:
        u = db.session.get(User, s.user_id)
        sub_data.append({
            "id":           s.id,
            "user_name":    u.full_name if u else None,
            "user_email":   u.email     if u else None,
            "plan":         s.plan,
            "status":       s.status,
            "period_end":   s.current_period_end,
            "cancel_at_end": s.cancel_at_period_end,
            "created_at":   s.created_at,
        })

    buf   = generate_subscription_report_pdf(sub_data, lang=lang)
    fname = f"smartxray_subscriptions_{datetime.now(timezone.utc).strftime('%d-%m-%Y')}.pdf"
    return Response(
        buf.read(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


@admin_api_bp.route("/subscriptions/export/docx", methods=["GET"])
@admin_required
def export_subscriptions_docx():
    """
    GET /api/admin/subscriptions/export/docx?lang=en|km
    Returns a bilingual DOCX of all subscriptions.
    """
    from datetime import datetime, timezone
    from flask import Response
    from app.models.subscription import Subscription
    from app.models.user         import User
    from app.services.pdf_service import generate_subscription_report_docx

    lang = request.args.get("lang", "en").lower()
    if lang not in ("en", "km"):
        lang = "en"

    subs = Subscription.query.order_by(desc(Subscription.created_at)).all()
    sub_data = []
    for s in subs:
        u = db.session.get(User, s.user_id)
        sub_data.append({
            "id":           s.id,
            "user_name":    u.full_name if u else None,
            "user_email":   u.email     if u else None,
            "plan":         s.plan,
            "status":       s.status,
            "period_end":   s.current_period_end,
            "cancel_at_end": s.cancel_at_period_end,
            "created_at":   s.created_at,
        })

    buf   = generate_subscription_report_docx(sub_data, lang=lang)
    fname = f"smartxray_subscriptions_{datetime.now(timezone.utc).strftime('%d-%m-%Y')}.docx"
    return Response(
        buf.read(),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


@admin_api_bp.route("/subscriptions/<int:sub_id>/toggle-renew", methods=["PATCH"])
@admin_required
def toggle_subscription_renew(sub_id):
    """
    PATCH /api/admin/subscriptions/<id>/toggle-renew
    Body: {"cancel_at_end": true|false}
    Toggles whether the subscription cancels at the current period end.
    """
    from app.models.subscription import Subscription
    from app.models.system_log   import SystemLog

    sub = db.session.get(Subscription, sub_id)
    if not sub:
        return jsonify({"error": "Subscription not found."}), 404

    data         = request.get_json(silent=True) or {}
    cancel_at_end = data.get("cancel_at_end")
    if not isinstance(cancel_at_end, bool):
        return jsonify({"error": "cancel_at_end must be true or false."}), 400

    sub.cancel_at_period_end = cancel_at_end
    action = "disabled" if cancel_at_end else "enabled"

    log = SystemLog(
        event_type="admin_action", severity="info",
        message=f"Subscription #{sub_id} auto-renew {action} by admin",
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({
        "message":      f"Auto-renew {action}.",
        "cancel_at_end": sub.cancel_at_period_end,
    }), 200


@admin_api_bp.route("/subscriptions", methods=["GET"])
@admin_required
def list_subscriptions():
    """
    GET /api/admin/subscriptions — revenue stats + paginated list.

    Query params
    ─────────────
    page    : int  (default 1)
    limit   : int  (default 20, max 1 000)
    status  : all | active | trialing | past_due | canceled (default active+trialing)
    """
    from app.models.subscription import Subscription
    from app.models.user         import User

    page        = request.args.get("page",   1,   type=int)
    limit       = min(request.args.get("limit", 20, type=int), 1000)
    status_arg  = request.args.get("status", "")

    # ── Build query ──────────────────────────────────────────────────────────
    q = Subscription.query
    if status_arg == "all":
        pass                                       # no status filter
    elif status_arg and status_arg != "":
        q = q.filter_by(status=status_arg)
    else:
        q = q.filter(Subscription.status.in_(["active", "trialing"]))

    pag = q.order_by(desc(Subscription.created_at)).paginate(
        page=page, per_page=limit, error_out=False
    )

    # ── Revenue stats (always computed over ALL active subscriptions) ────────
    monthly_count = Subscription.query.filter_by(status="active", plan="monthly").count()
    yearly_count  = Subscription.query.filter_by(status="active", plan="yearly").count()
    trial_count   = Subscription.query.filter_by(status="trialing").count()

    revenue_monthly = round(monthly_count * 9.99,  2)
    revenue_yearly  = round(yearly_count  * 79.99, 2)
    revenue_total   = round(revenue_monthly + revenue_yearly, 2)

    items = []
    for s in pag.items:
        u = db.session.get(User, s.user_id)
        items.append({
            "id":            s.id,
            "user_email":    u.email     if u else None,
            "user_name":     u.full_name if u else None,
            "plan":          s.plan,
            "status":        s.status,
            "period_end":    s.current_period_end.isoformat() if s.current_period_end else None,
            "period_start":  s.current_period_start.isoformat() if s.current_period_start else None,
            "cancel_at_end": s.cancel_at_period_end,
            "created_at":    s.created_at.isoformat() if s.created_at else None,
        })

    return jsonify({
        "revenue": {
            "monthly_subscribers": monthly_count,
            "yearly_subscribers":  yearly_count,
            "trial_subscribers":   trial_count,
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

@admin_api_bp.route("/marketplace/doctors/export/pdf", methods=["GET"])
@admin_required
def export_doctors_pdf():
    """
    GET /api/admin/marketplace/doctors/export/pdf?lang=en|km
    Returns a bilingual A4 PDF of all doctors.
    """
    from datetime import datetime, timezone
    from flask import Response
    from app.models.doctor import Doctor
    from app.services.pdf_service import generate_doctor_report_pdf

    lang = request.args.get("lang", "en").lower()
    if lang not in ("en", "km"):
        lang = "en"

    doctors = Doctor.query.order_by(desc(Doctor.created_at)).all()
    buf     = generate_doctor_report_pdf(doctors, lang=lang)

    fname = f"smartxray_doctors_{datetime.now(timezone.utc).strftime('%d-%m-%Y')}.pdf"
    return Response(
        buf.read(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


@admin_api_bp.route("/marketplace/doctors/export/docx", methods=["GET"])
@admin_required
def export_doctors_docx():
    """
    GET /api/admin/marketplace/doctors/export/docx?lang=en|km
    Returns a bilingual DOCX report of all doctors.
    """
    from datetime import datetime, timezone
    from flask import Response
    from app.models.doctor import Doctor
    from app.services.pdf_service import generate_doctor_report_docx

    lang = request.args.get("lang", "en").lower()
    if lang not in ("en", "km"):
        lang = "en"

    doctors = Doctor.query.order_by(desc(Doctor.created_at)).all()
    buf     = generate_doctor_report_docx(doctors, lang=lang)

    fname = f"smartxray_doctors_{datetime.now(timezone.utc).strftime('%d-%m-%Y')}.docx"
    return Response(
        buf.read(),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


@admin_api_bp.route("/marketplace/doctors", methods=["GET"])
@admin_required
def list_marketplace_doctors():
    """
    GET /api/admin/marketplace/doctors?status=pending|approved|rejected|all
    Supports limit up to 1 000 for client-side pagination.
    Response includes is_active and created_at in addition to to_dict() fields.
    """
    from app.models.doctor import Doctor

    status = request.args.get("status", "pending")
    page   = request.args.get("page",  1,  type=int)
    limit  = min(request.args.get("limit", 20, type=int), 1000)

    q = Doctor.query
    if status == "pending":
        q = q.filter_by(is_verified=False, is_active=True)
    elif status == "approved":
        q = q.filter_by(is_verified=True)
    elif status == "rejected":
        q = q.filter_by(is_active=False)
    # status == "all" → no filter

    pag = q.order_by(desc(Doctor.created_at)).paginate(
        page=page, per_page=limit, error_out=False
    )

    def _doc_dict(d):
        base = d.to_dict()
        base["is_active"]  = d.is_active
        base["created_at"] = d.created_at.isoformat() if d.created_at else None
        return base

    return jsonify({
        "doctors": [_doc_dict(d) for d in pag.items],
        "total":   pag.total,
        "page":    pag.page,
        "pages":   pag.pages,
    }), 200


@admin_api_bp.route("/marketplace/doctors/<int:doctor_id>/approve", methods=["PATCH"])
@admin_api_bp.route("/doctors/<int:doctor_id>/approve",             methods=["PATCH"])  # spec alias
@admin_required
def approve_doctor(doctor_id):
    """
    PATCH /api/admin/doctors/<id>/approve
    PATCH /api/admin/marketplace/doctors/<id>/approve  (legacy alias)

    - Sets doctor.status = 'approved', is_verified = True, is_active = True
    - Activates the linked user account (user.is_active = True)
    - Records reviewed_by + reviewed_at
    - Sends approval email to doctor
    - Sends Telegram alert to admin channel
    """
    from app.models.doctor     import Doctor
    from app.models.user       import User
    from app.models.system_log import SystemLog
    from app.utils.auth_guard  import _load_user
    from flask_jwt_extended    import get_jwt_identity
    from datetime              import datetime, timezone

    doctor = db.session.get(Doctor, doctor_id)
    if not doctor:
        return jsonify({"error": "Doctor not found."}), 404

    # ── Update doctor record ──────────────────────────────────────────
    doctor.is_verified = True
    doctor.is_active   = True

    # New columns (post-migration) — safe set
    now = datetime.now(timezone.utc)
    try: doctor.status      = "approved"
    except Exception: pass
    try: doctor.reviewed_at = now
    except Exception: pass

    # reviewed_by: current admin's user id
    try:
        admin = _load_user(get_jwt_identity())
        if admin:
            doctor.reviewed_by = admin.id
    except Exception:
        pass

    # ── Activate linked user account ──────────────────────────────────
    linked_user = None
    try:
        uid = getattr(doctor, "user_id", None)
        if uid:
            linked_user = db.session.get(User, uid)
        if not linked_user:
            linked_user = User.query.filter_by(email=doctor.email).first()
        if linked_user:
            linked_user.is_active = True
    except Exception:
        pass

    log = SystemLog(
        event_type="admin_action", severity="info",
        message=f"Doctor approved: {doctor.full_name} (id={doctor_id})",
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    # ── Notifications (non-blocking) ──────────────────────────────────
    try:
        from app.utils.notifications import alert_doctor_approved
        admin_name = getattr(g, "current_user", None)
        admin_name = admin_name.full_name if admin_name else "Admin"
        alert_doctor_approved(doctor, admin_name)
    except Exception:
        pass
    try:
        from app.utils.notifications import email_doctor_approved
        login_url = f"{_base_url()}/doctor/login"
        email_doctor_approved(doctor, login_url)
    except Exception:
        pass

    return jsonify({
        "message": f"Dr. {doctor.full_name} approved.",
        "doctor":  doctor.to_dict(),
    }), 200


@admin_api_bp.route("/marketplace/doctors/<int:doctor_id>/reject", methods=["PATCH"])
@admin_api_bp.route("/doctors/<int:doctor_id>/reject",             methods=["PATCH"])  # spec alias
@admin_required
def reject_doctor(doctor_id):
    """
    PATCH /api/admin/doctors/<id>/reject
    PATCH /api/admin/marketplace/doctors/<id>/reject  (legacy alias)

    Body: { "reason": "Missing valid license document." }

    - Sets doctor.status = 'rejected', is_active = False, is_verified = False
    - Locks the linked user account (is_active = False)
    - Saves reject_reason
    - Sends rejection email to doctor with reason
    - Sends Telegram alert
    """
    from app.models.doctor     import Doctor
    from app.models.user       import User
    from app.models.system_log import SystemLog
    from app.utils.auth_guard  import _load_user
    from flask_jwt_extended    import get_jwt_identity
    from datetime              import datetime, timezone

    doctor = db.session.get(Doctor, doctor_id)
    if not doctor:
        return jsonify({"error": "Doctor not found."}), 404

    body   = request.get_json(silent=True) or {}
    reason = (body.get("reason") or body.get("reject_reason") or "").strip() or None

    # ── Update doctor record ──────────────────────────────────────────
    doctor.is_active   = False
    doctor.is_verified = False
    try: doctor.rejection_reason = reason
    except Exception: pass
    try: doctor.reject_reason    = reason
    except Exception: pass
    try: doctor.status           = "rejected"
    except Exception: pass

    now = datetime.now(timezone.utc)
    try: doctor.reviewed_at = now
    except Exception: pass
    try:
        admin = _load_user(get_jwt_identity())
        if admin:
            doctor.reviewed_by = admin.id
    except Exception:
        pass

    # ── Lock linked user account ──────────────────────────────────────
    try:
        uid = getattr(doctor, "user_id", None)
        linked_user = db.session.get(User, uid) if uid else None
        if not linked_user:
            linked_user = User.query.filter_by(email=doctor.email).first()
        if linked_user:
            linked_user.is_active = False
    except Exception:
        pass

    log = SystemLog(
        event_type="admin_action", severity="warning",
        message=(
            f"Doctor rejected: {doctor.full_name} (id={doctor_id})"
            + (f" — reason: {reason}" if reason else "")
        ),
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    # ── Notifications (non-blocking) ──────────────────────────────────
    try:
        from app.utils.notifications import alert_doctor_rejected
        admin_name = getattr(g, "current_user", None)
        admin_name = admin_name.full_name if admin_name else "Admin"
        alert_doctor_rejected(doctor, reason or "No reason provided.", admin_name)
    except Exception:
        pass
    try:
        from app.utils.notifications import email_doctor_rejected
        email_doctor_rejected(doctor, reason or "No reason provided.")
    except Exception:
        pass

    return jsonify({
        "message": f"Dr. {doctor.full_name} rejected.",
        "doctor":  doctor.to_dict(),
    }), 200


@admin_api_bp.route("/marketplace/doctors/<int:doctor_id>/revoke", methods=["PATCH"])
@admin_required
def revoke_doctor(doctor_id):
    """
    PATCH /api/admin/marketplace/doctors/<id>/revoke
    Move an approved doctor back to pending review
    (is_verified=False, is_active=True).
    """
    from app.models.doctor import Doctor
    from app.models.system_log import SystemLog

    doctor = db.session.get(Doctor, doctor_id)
    if not doctor:
        return jsonify({"error": "Doctor not found."}), 404

    doctor.is_verified = False
    doctor.is_active   = True
    log = SystemLog(
        event_type="admin_action", severity="warning",
        message=f"Doctor approval revoked (→ pending): {doctor.full_name} (id={doctor_id})",
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({"message": f"Dr. {doctor.full_name} moved back to pending.", "doctor": doctor.to_dict()}), 200


@admin_api_bp.route("/marketplace/doctors/<int:doctor_id>/restore", methods=["PATCH"])
@admin_required
def restore_doctor(doctor_id):
    """
    PATCH /api/admin/marketplace/doctors/<id>/restore
    Restore a rejected doctor back to pending review
    (is_active=True, is_verified=False).
    """
    from app.models.doctor import Doctor
    from app.models.system_log import SystemLog

    doctor = db.session.get(Doctor, doctor_id)
    if not doctor:
        return jsonify({"error": "Doctor not found."}), 404

    doctor.is_active   = True
    doctor.is_verified = False
    log = SystemLog(
        event_type="admin_action", severity="info",
        message=f"Doctor restored (→ pending): {doctor.full_name} (id={doctor_id})",
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({"message": f"Dr. {doctor.full_name} restored to pending.", "doctor": doctor.to_dict()}), 200


@admin_api_bp.route("/marketplace/doctors/<int:doctor_id>/feature", methods=["PATCH"])
@admin_required
def feature_doctor(doctor_id):
    """
    PATCH /api/admin/marketplace/doctors/<id>/feature
    Body: {"is_featured": true|false}
    Toggles the doctor's featured status.
    """
    from app.models.doctor import Doctor
    from app.models.system_log import SystemLog

    doctor = db.session.get(Doctor, doctor_id)
    if not doctor:
        return jsonify({"error": "Doctor not found."}), 404

    data       = request.get_json(silent=True) or {}
    is_featured = data.get("is_featured")
    if not isinstance(is_featured, bool):
        return jsonify({"error": "is_featured must be true or false."}), 400

    doctor.is_featured = is_featured
    action = "featured" if is_featured else "unfeatured"
    log = SystemLog(
        event_type="admin_action", severity="info",
        message=f"Doctor {action}: {doctor.full_name} (id={doctor_id})",
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({
        "message":     f"Dr. {doctor.full_name} {action}.",
        "is_featured": doctor.is_featured,
        "doctor":      doctor.to_dict(),
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
#  API: TELEGRAM BOT
# ══════════════════════════════════════════════════════════════════════════════

@admin_api_bp.route("/telegram/status", methods=["GET"])
@admin_required
def telegram_status():
    """
    GET /api/admin/telegram/status
    Returns whether the bot is configured and live info from Telegram getMe.
    token_only=True  → token present but no chat_id yet (prompt user to message the bot)
    configured=True  → both token + chat_id present
    """
    import requests as _req
    from flask import current_app

    token   = current_app.config.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = current_app.config.get("TELEGRAM_CHAT_ID",   "").strip()

    token_only   = bool(token and not chat_id)
    configured   = bool(token and chat_id)

    bot_username = None
    bot_name     = None
    reachable    = False

    # Verify token via getMe whenever a token is present
    if token:
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
        "configured":      configured,
        "token_only":      token_only,
        "reachable":       reachable,
        "token_set":       bool(token),
        "chat_id_set":     bool(chat_id),
        "chat_id_preview": chat_id_preview,
        "bot_username":    bot_username,
        "bot_name":        bot_name,
    }), 200


@admin_api_bp.route("/telegram/discover", methods=["POST"])
@admin_required
def telegram_discover():
    """
    POST /api/admin/telegram/discover
    Calls getUpdates to auto-detect the chat_id from recent bot messages.
    Persists the discovered chat_id to .env and running config.
    """
    import requests as _req
    from flask import current_app
    from app.services.telegram_service import discover_chat_id

    token = current_app.config.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return jsonify({"ok": False, "message": "No TELEGRAM_BOT_TOKEN in .env."}), 400

    chat_id = discover_chat_id(token)
    if not chat_id:
        return jsonify({
            "ok": False,
            "message": "No messages found. Send any message to your bot on Telegram, then try again.",
        }), 404

    # Persist to runtime config
    current_app.config["TELEGRAM_CHAT_ID"] = chat_id

    # Persist to .env
    try:
        import os
        from dotenv import set_key
        env_path = os.path.normpath(
            os.path.join(current_app.root_path, "..", ".env")
        )
        set_key(env_path, "TELEGRAM_CHAT_ID", chat_id)
    except Exception as e:
        return jsonify({
            "ok": True,
            "chat_id": chat_id,
            "message": f"Chat ID discovered ({chat_id}) but could not write to .env: {e}. Add it manually.",
        }), 200

    return jsonify({
        "ok":      True,
        "chat_id": chat_id,
        "message": f"Chat ID discovered and saved! ({chat_id})",
    }), 200


@admin_api_bp.route("/telegram/test", methods=["POST"])
@admin_required
def telegram_test():
    """
    POST /api/admin/telegram/test
    Sends a test alert. Works with token-only — auto-discovers chat_id if missing.
    """
    from flask import current_app
    from app.services.telegram_service import send_test_alert, _get_chat_id
    from app.models.system_log import SystemLog

    token = current_app.config.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return jsonify({
            "ok":      False,
            "message": "No TELEGRAM_BOT_TOKEN set in .env.",
        }), 400

    # Auto-discover chat_id if missing
    chat_id = _get_chat_id()
    if not chat_id:
        return jsonify({
            "ok":      False,
            "message": "No Chat ID found. Send any message to your bot on Telegram first, then try again.",
        }), 400

    ok = send_test_alert()

    log = SystemLog(
        event_type="admin_action",
        severity="info",
        message="Admin sent Telegram test alert (bilingual EN/KM)",
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    if ok:
        return jsonify({"ok": True,  "message": "Test message sent — check your Telegram!"}), 200
    else:
        return jsonify({"ok": False, "message": "Delivery failed. Check your token is valid."}), 502


@admin_api_bp.route("/telegram/test/<alert_type>", methods=["POST"])
@admin_required
def telegram_test_by_type(alert_type):
    """
    POST /api/admin/telegram/test/<type>
    Send a test alert for a specific alert type.
    type: generic | pneumonia | auth_fail | critical_error | db_health | daily_summary
    """
    from flask import current_app
    from app.services.telegram_service import send_test_alert
    from app.models.system_log import SystemLog

    token = current_app.config.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return jsonify({"ok": False, "message": "No TELEGRAM_BOT_TOKEN set in .env."}), 400

    ok = send_test_alert(alert_type)

    log = SystemLog(
        event_type="telegram_alert",
        severity="info",
        message=f"Test alert ({alert_type}) sent from admin panel",
        ip_address=request.remote_addr,
        extra={"alert_type": alert_type, "test": True},
    )
    db.session.add(log)
    db.session.commit()

    if ok:
        return jsonify({"ok": True, "message": f"Test {alert_type} alert sent!"}), 200
    else:
        return jsonify({"ok": False, "message": "Delivery failed. Check your token / chat ID."}), 502


@admin_api_bp.route("/telegram/settings", methods=["GET"])
@admin_required
def telegram_get_settings():
    """
    GET /api/admin/telegram/settings
    Returns current alert toggle states from Flask config.
    """
    from flask import current_app

    def _enabled(key, default=True):
        raw = current_app.config.get(f"TELEGRAM_ALERT_{key.upper()}", None)
        if raw is None:
            return default
        return str(raw).strip().lower() not in ("false", "0", "no", "off")

    return jsonify({
        "pneumonia":      _enabled("pneumonia",      True),
        "auth_fail":      _enabled("auth_fail",      True),
        "critical_error": _enabled("critical_error", True),
        "db_health":      _enabled("db_health",      True),
        "daily_summary":  _enabled("daily_summary",  False),
    }), 200


@admin_api_bp.route("/telegram/settings", methods=["POST"])
@admin_required
def telegram_save_settings():
    """
    POST /api/admin/telegram/settings
    Body: {"pneumonia": true, "auth_fail": true, ...}
    Persists settings to runtime config + .env file.
    """
    import os
    from flask import current_app
    from app.models.system_log import SystemLog

    VALID_KEYS = ("pneumonia", "auth_fail", "critical_error", "db_health", "daily_summary")
    data = request.get_json(silent=True) or {}

    try:
        from dotenv import set_key
        env_path = os.path.normpath(
            os.path.join(current_app.root_path, "..", ".env")
        )
    except ImportError:
        env_path = None

    saved = {}
    for key in VALID_KEYS:
        if key in data:
            val     = bool(data[key])
            cfg_key = f"TELEGRAM_ALERT_{key.upper()}"
            current_app.config[cfg_key] = val
            if env_path:
                set_key(env_path, cfg_key, "true" if val else "false")
            saved[key] = val

    log = SystemLog(
        event_type="admin_action", severity="info",
        message=f"Telegram alert settings updated: {saved}",
        ip_address=request.remote_addr,
        extra={"settings": saved},
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({"ok": True, "saved": saved,
                    "message": "Alert settings saved."}), 200


@admin_api_bp.route("/telegram/history", methods=["GET"])
@admin_required
def telegram_history():
    """
    GET /api/admin/telegram/history?limit=20
    Returns recent telegram_alert log entries.
    """
    from app.models.system_log import SystemLog

    limit = min(request.args.get("limit", 20, type=int), 100)
    logs = (
        SystemLog.query
        .filter_by(event_type="telegram_alert", is_deleted=False)
        .order_by(desc(SystemLog.created_at))
        .limit(limit).all()
    )
    total = (
        SystemLog.query
        .filter_by(event_type="telegram_alert", is_deleted=False)
        .count()
    )
    today_count = (
        SystemLog.query
        .filter_by(event_type="telegram_alert", is_deleted=False)
        .filter(SystemLog.created_at >= func.date_trunc(
            'day', func.now()
        ))
        .count()
    )
    return jsonify({
        "history":     [l.to_dict() for l in logs],
        "total":       total,
        "today":       today_count,
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
#  API: SYSTEM LOGS
# ══════════════════════════════════════════════════════════════════════════════

@admin_api_bp.route("/logs/export/pdf", methods=["GET"])
@admin_required
def export_logs_pdf():
    """
    GET /api/admin/logs/export/pdf?lang=en|km[&severity=][&event_type=][&search=]
    Returns a bilingual A4 PDF of (filtered) system logs.
    """
    from datetime import datetime, timezone
    from flask import Response
    from app.models.system_log import SystemLog
    from app.services.pdf_service import generate_log_report_pdf

    lang       = request.args.get("lang",       "en").lower()
    severity   = request.args.get("severity")
    event_type = request.args.get("event_type")
    search     = request.args.get("search", "").strip()
    if lang not in ("en", "km"):
        lang = "en"

    q = SystemLog.query.filter_by(is_deleted=False)
    if severity:
        q = q.filter_by(severity=severity)
    if event_type:
        q = q.filter_by(event_type=event_type)
    if search:
        p = f"%{search}%"
        q = q.filter(SystemLog.message.ilike(p))

    logs  = q.order_by(desc(SystemLog.created_at)).limit(500).all()
    buf   = generate_log_report_pdf(logs, lang=lang)
    fname = f"smartxray_logs_{datetime.now(timezone.utc).strftime('%d-%m-%Y')}.pdf"
    return Response(
        buf.read(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


@admin_api_bp.route("/logs/export/docx", methods=["GET"])
@admin_required
def export_logs_docx():
    """
    GET /api/admin/logs/export/docx?lang=en|km[&severity=][&event_type=][&search=]
    Returns a bilingual DOCX of (filtered) system logs.
    """
    from datetime import datetime, timezone
    from flask import Response
    from app.models.system_log import SystemLog
    from app.services.pdf_service import generate_log_report_docx

    lang       = request.args.get("lang",       "en").lower()
    severity   = request.args.get("severity")
    event_type = request.args.get("event_type")
    search     = request.args.get("search", "").strip()
    if lang not in ("en", "km"):
        lang = "en"

    q = SystemLog.query.filter_by(is_deleted=False)
    if severity:
        q = q.filter_by(severity=severity)
    if event_type:
        q = q.filter_by(event_type=event_type)
    if search:
        p = f"%{search}%"
        q = q.filter(SystemLog.message.ilike(p))

    logs  = q.order_by(desc(SystemLog.created_at)).limit(500).all()
    buf   = generate_log_report_docx(logs, lang=lang)
    fname = f"smartxray_logs_{datetime.now(timezone.utc).strftime('%d-%m-%Y')}.docx"
    return Response(
        buf.read(),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


@admin_api_bp.route("/logs", methods=["GET"])
@admin_required
def list_logs():
    """
    GET /api/admin/logs
    Query params: severity, event_type, search, page, limit (max 200),
                  show_deleted=1  (view the trash instead of active logs)
    Always returns aggregate KPI stats in 'stats' block.
    """
    from app.models.system_log import SystemLog

    severity     = request.args.get("severity")
    event_type   = request.args.get("event_type")
    search       = request.args.get("search", "").strip()
    page         = request.args.get("page",  1,  type=int)
    limit        = min(request.args.get("limit", 50, type=int), 200)
    show_deleted = request.args.get("show_deleted", "0") == "1"

    q = SystemLog.query.filter_by(is_deleted=show_deleted)
    if severity:
        q = q.filter_by(severity=severity)
    if event_type:
        q = q.filter_by(event_type=event_type)
    if search:
        p = f"%{search}%"
        q = q.filter(SystemLog.message.ilike(p))

    pag = q.order_by(desc(SystemLog.created_at)).paginate(
        page=page, per_page=limit, error_out=False
    )

    # ── Aggregate KPI stats (always over active logs only) ────────────────
    active_q = SystemLog.query.filter_by(is_deleted=False)
    stats = {
        "total":     active_q.count(),
        "critical":  active_q.filter_by(severity="critical").count(),
        "high":      active_q.filter_by(severity="high").count(),
        "warning":   active_q.filter_by(severity="warning").count(),
        "auth_fail": active_q.filter_by(event_type="auth_fail").count(),
        "deleted":   SystemLog.query.filter_by(is_deleted=True).count(),
    }

    return jsonify({
        "logs":     [l.to_dict() for l in pag.items],
        "total":    pag.total,
        "page":     pag.page,
        "pages":    pag.pages,
        "has_next": pag.has_next,
        "stats":    stats,
    }), 200


@admin_api_bp.route("/logs/<int:log_id>", methods=["DELETE"])
@admin_required
def soft_delete_log(log_id):
    """
    DELETE /api/admin/logs/<id>
    Soft-deletes a single log entry (sets is_deleted=True).
    The record stays in the DB and can be restored.
    """
    from app.models.system_log import SystemLog

    log = db.session.get(SystemLog, log_id)
    if not log:
        return jsonify({"error": "Log not found."}), 404
    if log.is_deleted:
        return jsonify({"error": "Log is already in trash."}), 400

    log.is_deleted = True
    log.deleted_at = datetime.now(timezone.utc)

    audit = SystemLog(
        event_type="admin_action", severity="warning",
        message=f"Log #{log_id} soft-deleted by admin",
        ip_address=request.remote_addr,
    )
    db.session.add(audit)
    db.session.commit()
    return jsonify({"message": f"Log #{log_id} moved to trash."}), 200


@admin_api_bp.route("/logs/<int:log_id>/restore", methods=["PATCH"])
@admin_required
def restore_log(log_id):
    """
    PATCH /api/admin/logs/<id>/restore
    Restores a soft-deleted log (sets is_deleted=False).
    """
    from app.models.system_log import SystemLog

    log = db.session.get(SystemLog, log_id)
    if not log:
        return jsonify({"error": "Log not found."}), 404
    if not log.is_deleted:
        return jsonify({"error": "Log is not in trash."}), 400

    log.is_deleted = False
    log.deleted_at = None

    audit = SystemLog(
        event_type="admin_action", severity="info",
        message=f"Log #{log_id} restored from trash by admin",
        ip_address=request.remote_addr,
    )
    db.session.add(audit)
    db.session.commit()
    return jsonify({"message": f"Log #{log_id} restored."}), 200


@admin_api_bp.route("/logs/bulk-delete", methods=["POST"])
@admin_required
def bulk_soft_delete_logs():
    """
    POST /api/admin/logs/bulk-delete
    Body: {"ids": [1, 2, 3, ...]}
    Soft-deletes all listed log IDs in one transaction.
    """
    from app.models.system_log import SystemLog

    data = request.get_json(silent=True) or {}
    ids  = data.get("ids", [])
    if not ids or not isinstance(ids, list):
        return jsonify({"error": "ids must be a non-empty list."}), 400

    now = datetime.now(timezone.utc)
    updated = (
        db.session.query(SystemLog)
        .filter(SystemLog.id.in_(ids), SystemLog.is_deleted == False)  # noqa: E712
        .all()
    )
    count = len(updated)
    for log in updated:
        log.is_deleted = True
        log.deleted_at = now

    audit = SystemLog(
        event_type="admin_action", severity="warning",
        message=f"Bulk soft-delete: {count} log(s) moved to trash by admin",
        ip_address=request.remote_addr,
    )
    db.session.add(audit)
    db.session.commit()
    return jsonify({"message": f"{count} log(s) moved to trash.", "count": count}), 200


@admin_api_bp.route("/logs/bulk-restore", methods=["POST"])
@admin_required
def bulk_restore_logs():
    """
    POST /api/admin/logs/bulk-restore
    Body: {"ids": [1, 2, 3, ...]}
    Restores all listed soft-deleted log IDs.
    """
    from app.models.system_log import SystemLog

    data = request.get_json(silent=True) or {}
    ids  = data.get("ids", [])
    if not ids or not isinstance(ids, list):
        return jsonify({"error": "ids must be a non-empty list."}), 400

    updated = (
        db.session.query(SystemLog)
        .filter(SystemLog.id.in_(ids), SystemLog.is_deleted == True)  # noqa: E712
        .all()
    )
    count = len(updated)
    for log in updated:
        log.is_deleted = False
        log.deleted_at = None

    audit = SystemLog(
        event_type="admin_action", severity="info",
        message=f"Bulk restore: {count} log(s) restored from trash by admin",
        ip_address=request.remote_addr,
    )
    db.session.add(audit)
    db.session.commit()
    return jsonify({"message": f"{count} log(s) restored.", "count": count}), 200
