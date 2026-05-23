from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.doctor import Doctor
from app.utils.auth_helpers import jwt_required_user

marketplace_bp = Blueprint("marketplace", __name__)


# ── GET /api/marketplace/doctors ─────────────────────────────────────────
@marketplace_bp.route("/doctors", methods=["GET"])
def list_doctors():
    """Public endpoint — no login required to browse the marketplace."""
    page      = request.args.get("page",      1,    type=int)
    limit     = min(request.args.get("limit", 12,   type=int), 50)
    specialty = request.args.get("specialty", "").strip()
    city      = request.args.get("city",      "").strip()
    country   = request.args.get("country",   "").strip()
    search    = request.args.get("search",    "").strip()
    featured  = request.args.get("featured",  "").lower() == "true"

    q = Doctor.query.filter_by(is_active=True)

    if featured:
        q = q.filter_by(is_featured=True)
    if specialty:
        q = q.filter(Doctor.specialty.ilike(f"%{specialty}%"))
    if city:
        q = q.filter(Doctor.city.ilike(f"%{city}%"))
    if country:
        q = q.filter(Doctor.country.ilike(f"%{country}%"))
    if search:
        term = f"%{search}%"
        q = q.filter(
            db.or_(
                Doctor.full_name.ilike(term),
                Doctor.specialty.ilike(term),
                Doctor.hospital.ilike(term),
                Doctor.city.ilike(term),
            )
        )

    # Featured + highest-rated first
    q = q.order_by(Doctor.is_featured.desc(), Doctor.rating.desc())
    pagination = q.paginate(page=page, per_page=limit, error_out=False)

    return jsonify({
        "doctors":  [d.to_dict() for d in pagination.items],
        "total":    pagination.total,
        "page":     pagination.page,
        "pages":    pagination.pages,
        "has_next": pagination.has_next,
    }), 200


# ── GET /api/marketplace/doctors/<id> ────────────────────────────────────
@marketplace_bp.route("/doctors/<int:doctor_id>", methods=["GET"])
def get_doctor(doctor_id):
    doctor = db.session.get(Doctor, doctor_id)
    if not doctor or not doctor.is_active:
        return jsonify({"error": "Doctor not found."}), 404
    return jsonify(doctor.to_dict()), 200


# ── GET /api/marketplace/specialties ─────────────────────────────────────
@marketplace_bp.route("/specialties", methods=["GET"])
def list_specialties():
    """Return distinct specialties for filter dropdowns."""
    rows = (
        db.session.query(Doctor.specialty)
        .filter_by(is_active=True)
        .distinct()
        .order_by(Doctor.specialty)
        .all()
    )
    return jsonify({"specialties": [r[0] for r in rows]}), 200


# ── GET /api/marketplace/cities ──────────────────────────────────────────
@marketplace_bp.route("/cities", methods=["GET"])
def list_cities():
    rows = (
        db.session.query(Doctor.city)
        .filter(Doctor.is_active == True, Doctor.city.isnot(None))
        .distinct()
        .order_by(Doctor.city)
        .all()
    )
    return jsonify({"cities": [r[0] for r in rows]}), 200


# ── POST /api/marketplace/doctors (admin) ────────────────────────────────
@marketplace_bp.route("/doctors", methods=["POST"])
@jwt_required_user
def add_doctor():
    """Simplified admin route — add a doctor listing."""
    data = request.get_json(silent=True) or {}
    required = ("full_name", "specialty")
    missing  = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    doctor = Doctor(
        full_name       = data["full_name"].strip(),
        specialty       = data["specialty"].strip(),
        qualifications  = data.get("qualifications"),
        hospital        = data.get("hospital"),
        city            = data.get("city"),
        country         = data.get("country"),
        phone           = data.get("phone"),
        email           = data.get("email"),
        website         = data.get("website"),
        bio             = data.get("bio"),
        avatar_url      = data.get("avatar_url"),
        google_maps_url = data.get("google_maps_url"),
    )
    db.session.add(doctor)
    db.session.commit()
    return jsonify(doctor.to_dict()), 201
