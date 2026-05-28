import os
import time
import uuid
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from app.extensions import db
from app.models.scan import Scan
from app.models.ad import Ad
from app.models.report import Report
from app.utils.auth_guard import jwt_required_user, pro_required, _get_current_user, check_scan_quota
from app.utils.validators import allowed_image
from app.services.cloudinary_service import (
    upload_image as _cloud_upload,
    upload_file  as _cloud_upload_file,
    delete_image as _cloud_delete,
)


def _image_url(path: str | None) -> str | None:
    """Resolve a stored image path to a public URL.
    Cloudinary URLs are stored as full https:// strings.
    Legacy local paths are relative (e.g. 'uploads/abc.jpg').
    """
    if not path:
        return None
    return path if path.startswith("http") else f"/static/{path}"

scan_bp = Blueprint("scan", __name__)


# ── POST /api/scan/upload ─────────────────────────────────────────────────
@scan_bp.route("/upload", methods=["POST"])
@jwt_required_user
def upload_scan():
    user = _get_current_user()

    # ── Quota check (free tier: 3 scans/day) ──────────────────────────────
    allowed, quota_err = check_scan_quota(user)
    if not allowed:
        return jsonify({"error": quota_err, "upgrade_url": "/pricing"}), 429

    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400

    file = request.files["file"]
    if not file.filename or not allowed_image(file.filename):
        return jsonify({"error": "Only PNG / JPG / JPEG images are accepted."}), 400

    # ── Save uploaded image ───────────────────────────────────────────────
    ext      = file.filename.rsplit(".", 1)[-1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    # ── Run AI prediction + Grad-CAM (time the inference) ────────────────
    from app.services.ai_service import predict
    from app.services.gradcam import generate_gradcam

    t0 = time.time()
    try:
        prediction, confidence, raw_score = predict(save_path)
    except FileNotFoundError as exc:
        current_app.logger.error("AI model file missing: %s", exc)
        return jsonify({"error": "AI model is not available. Please contact support."}), 503
    except Exception as exc:
        current_app.logger.exception("AI prediction failed for %s", filename)
        return jsonify({"error": "AI analysis failed. Please try again."}), 500
    processing_ms = int((time.time() - t0) * 1000)

    heatmap_filename = generate_gradcam(save_path, filename)

    # ── Upload to Cloudinary (persists across Render redeployments) ───────
    heatmap_abs = None
    if heatmap_filename:
        heatmap_abs = os.path.join(current_app.config["HEATMAP_FOLDER"], heatmap_filename)

    cloud_image_url   = _cloud_upload(save_path,    folder="smartxray/scans")
    cloud_heatmap_url = _cloud_upload(heatmap_abs,  folder="smartxray/heatmaps") if heatmap_abs else None

    # Prefer Cloudinary URL; fall back to local relative path
    stored_image_path   = cloud_image_url   or f"uploads/{filename}"
    stored_heatmap_path = cloud_heatmap_url or (f"heatmaps/{heatmap_filename}" if heatmap_filename else None)

    # ── Persist scan record ───────────────────────────────────────────────
    scan = Scan(
        user_id       = user.id,
        image_path    = stored_image_path,
        heatmap_path  = stored_heatmap_path,
        prediction    = prediction,
        confidence    = confidence,
        raw_score     = raw_score,
        gradcam_status= "done" if heatmap_filename else "failed",
    )
    db.session.add(scan)

    # Increment daily counter
    user.scans_today += 1

    # ── System log ────────────────────────────────────────────────────────
    from app.models.system_log import SystemLog
    log = SystemLog.log_scan(scan, user, processing_ms, ip=request.remote_addr)
    db.session.add(log)

    db.session.commit()

    # ── Telegram alert for high-severity pneumonia ────────────────────────
    threshold = current_app.config.get("PNEUMONIA_HIGH_SEVERITY_THRESHOLD", 0.80)
    if prediction == "PNEUMONIA" and confidence >= threshold:
        try:
            from app.services.telegram_service import alert_high_severity_pneumonia
            alert_high_severity_pneumonia(scan, user)
        except Exception:
            current_app.logger.exception("Telegram alert failed for scan %s", scan.id)

    # ── Build response ────────────────────────────────────────────────────
    result = scan.to_dict(include_paths=True)
    result["image_url"]   = _image_url(scan.image_path)
    result["heatmap_url"] = _image_url(scan.heatmap_path)

    # ── Pro: auto-generate PDF report ────────────────────────────────────
    if user.is_pro:
        try:
            from app.services.pdf_service import generate_report
            from app.services.email_service import send_scan_result

            pdf_filename, pdf_size = generate_report(
                scan, user, current_app.config["REPORT_FOLDER"]
            )
            pdf_abs = os.path.join(current_app.config["REPORT_FOLDER"], pdf_filename)
            cloud_pdf_url = _cloud_upload_file(pdf_abs, folder="smartxray/reports")
            stored_pdf_path = cloud_pdf_url or f"reports/{pdf_filename}"

            report = Report(
                user_id   = user.id,
                file_path = stored_pdf_path,
                file_size = pdf_size,
                summary   = f"{prediction} detected with {round(confidence*100,2)}% confidence.",
            )
            db.session.add(report)
            db.session.flush()          # get report.id before commit

            scan.report_id = report.id
            db.session.commit()

            result["report_id"]  = report.id
            result["report_url"] = f"/api/scan/report/{report.id}/download"

            send_scan_result(user, scan)
        except Exception:
            current_app.logger.exception("PDF generation failed for scan %s", scan.id)

    # ── Free: inject result-page ad ───────────────────────────────────────
    else:
        ad = (
            Ad.query
            .filter_by(placement="result_page", is_active=True)
            .order_by(Ad.priority.desc())
            .first()
        )
        if ad:
            ad.impressions += 1
            db.session.commit()
            result["ad"] = ad.to_dict()

    return jsonify(result), 201


# ── GET /api/scan/history ─────────────────────────────────────────────────
@scan_bp.route("/history", methods=["GET"])
@jwt_required_user
def scan_history():
    user  = _get_current_user()
    page  = request.args.get("page",  1, type=int)
    limit = min(request.args.get("limit", 10, type=int), 50)

    pagination = (
        Scan.query
        .filter_by(user_id=user.id)
        .order_by(Scan.created_at.desc())
        .paginate(page=page, per_page=limit, error_out=False)
    )

    return jsonify({
        "scans":   [s.to_dict(include_paths=True) for s in pagination.items],
        "total":   pagination.total,
        "page":    pagination.page,
        "pages":   pagination.pages,
        "has_next": pagination.has_next,
    }), 200


# ── GET /api/scan/<scan_id> ───────────────────────────────────────────────
@scan_bp.route("/<int:scan_id>", methods=["GET"])
@jwt_required_user
def get_scan(scan_id):
    user = _get_current_user()
    scan = db.session.get(Scan, scan_id)

    if not scan or scan.user_id != user.id:
        return jsonify({"error": "Scan not found."}), 404

    result = scan.to_dict(include_paths=True)
    result["image_url"]   = _image_url(scan.image_path)
    result["heatmap_url"] = _image_url(scan.heatmap_path)

    # Link to report if one exists (Pro)
    if scan.report_id:
        result["report_id"] = scan.report_id

    return jsonify(result), 200


# ── DELETE /api/scan/<scan_id> ────────────────────────────────────────────
@scan_bp.route("/<int:scan_id>", methods=["DELETE"])
@jwt_required_user
def delete_scan(scan_id):
    user = _get_current_user()
    scan = db.session.get(Scan, scan_id)

    if not scan or scan.user_id != user.id:
        return jsonify({"error": "Scan not found."}), 404

    # Remove from Cloudinary (full URLs) or local disk (relative paths)
    for path in (scan.image_path, scan.heatmap_path):
        if not path:
            continue
        if path.startswith("http"):
            _cloud_delete(path)
        else:
            abs_path = os.path.join(current_app.root_path, "..", "static", path)
            if os.path.exists(abs_path):
                os.remove(abs_path)

    db.session.delete(scan)
    db.session.commit()
    return jsonify({"message": "Scan deleted."}), 200


# ── GET /api/scan/report/<report_id>/download (Pro only) ──────────────────
@scan_bp.route("/report/<int:report_id>/download", methods=["GET"])
@pro_required
def download_report(report_id):
    user   = _get_current_user()
    report = db.session.get(Report, report_id)

    if not report or report.user_id != user.id:
        return jsonify({"error": "Report not found."}), 404

    report.download_count += 1
    from datetime import datetime, timezone
    report.last_downloaded_at = datetime.now(timezone.utc)
    db.session.commit()

    # Cloudinary-stored PDF
    if report.file_path.startswith("http"):
        import requests as _req
        from flask import Response
        try:
            r = _req.get(report.file_path, timeout=15)
            r.raise_for_status()
        except Exception:
            return jsonify({"error": "Could not fetch report from cloud storage."}), 502
        filename = os.path.basename(report.file_path.split("?")[0])
        return Response(
            r.content,
            mimetype="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    reports_dir = current_app.config["REPORT_FOLDER"]
    filename    = os.path.basename(report.file_path)
    return send_from_directory(reports_dir, filename, as_attachment=True)
