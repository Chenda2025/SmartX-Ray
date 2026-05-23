from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.ad import Ad
from app.utils.auth_helpers import jwt_required_user, _get_current_user

ads_bp = Blueprint("ads", __name__)

VALID_PLACEMENTS = {"banner", "sidebar", "interstitial", "result_page"}


# ── GET /api/ads?placement=banner ────────────────────────────────────────
@ads_bp.route("", methods=["GET"])
@jwt_required_user
def get_ads():
    """
    Returns ads for the requesting user.
    Pro users receive an empty list — they see no ads.
    """
    user      = _get_current_user()
    placement = request.args.get("placement", "banner").lower()

    if user.is_pro:
        return jsonify({"ads": [], "pro": True}), 200

    if placement not in VALID_PLACEMENTS:
        return jsonify({"error": f"Invalid placement. Choose from: {', '.join(VALID_PLACEMENTS)}"}), 400

    now = datetime.now(timezone.utc)
    ads = (
        Ad.query
        .filter(
            Ad.placement  == placement,
            Ad.is_active  == True,
            db.or_(Ad.start_date.is_(None), Ad.start_date <= now),
            db.or_(Ad.end_date.is_(None),   Ad.end_date   >= now),
        )
        .order_by(Ad.priority.desc())
        .limit(3)
        .all()
    )

    # Record impressions
    for ad in ads:
        ad.impressions += 1
    db.session.commit()

    return jsonify({"ads": [a.to_dict() for a in ads], "pro": False}), 200


# ── POST /api/ads/<ad_id>/click ───────────────────────────────────────────
@ads_bp.route("/<int:ad_id>/click", methods=["POST"])
def track_click(ad_id):
    """Pixel-style click tracker — no auth required."""
    ad = db.session.get(Ad, ad_id)
    if not ad:
        return jsonify({"error": "Ad not found."}), 404
    ad.clicks += 1
    db.session.commit()
    return jsonify({"clicked": True, "target_url": ad.target_url}), 200


# ── POST /api/ads (admin) ─────────────────────────────────────────────────
@ads_bp.route("", methods=["POST"])
@jwt_required_user
def create_ad():
    """Create a new ad (admin use)."""
    data = request.get_json(silent=True) or {}
    required = ("title", "body", "target_url")
    missing  = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    placement = data.get("placement", "banner")
    if placement not in VALID_PLACEMENTS:
        return jsonify({"error": f"Invalid placement."}), 400

    ad = Ad(
        title      = data["title"].strip(),
        body       = data["body"].strip(),
        target_url = data["target_url"].strip(),
        image_url  = data.get("image_url"),
        advertiser = data.get("advertiser"),
        placement  = placement,
        priority   = int(data.get("priority", 0)),
    )
    db.session.add(ad)
    db.session.commit()
    return jsonify(ad.to_dict()), 201


# ── PATCH /api/ads/<ad_id> (admin) ───────────────────────────────────────
@ads_bp.route("/<int:ad_id>", methods=["PATCH"])
@jwt_required_user
def update_ad(ad_id):
    ad = db.session.get(Ad, ad_id)
    if not ad:
        return jsonify({"error": "Ad not found."}), 404

    data = request.get_json(silent=True) or {}
    for field in ("title", "body", "target_url", "image_url", "advertiser", "placement", "priority", "is_active"):
        if field in data:
            setattr(ad, field, data[field])

    db.session.commit()
    return jsonify(ad.to_dict()), 200
