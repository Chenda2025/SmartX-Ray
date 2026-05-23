import os
import logging
import click
import platform
from datetime import datetime, timezone
from flask import Flask, jsonify, request
from config import config_map
from app.extensions import db, migrate, jwt, cors, mail

logger = logging.getLogger(__name__)


def create_app(env: str | None = None) -> Flask:
    env = env or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__, static_folder="../static", template_folder="../templates")
    app.config.from_object(config_map[env])

    # ── Extensions ─────────────────────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
    mail.init_app(app)

    # ── Blueprints ─────────────────────────────────────────────────────────
    from app.routes.auth import auth_bp
    from app.routes.scan import scan_bp
    from app.routes.subscription import subscription_bp
    from app.routes.marketplace import marketplace_bp
    from app.routes.ads import ads_bp
    from app.routes.pages import pages_bp
    from app.routes.admin import admin_bp, admin_api_bp

    app.register_blueprint(auth_bp,         url_prefix="/api/auth")
    app.register_blueprint(scan_bp,         url_prefix="/api/scan")
    app.register_blueprint(subscription_bp, url_prefix="/api/subscription")
    app.register_blueprint(marketplace_bp,  url_prefix="/api/marketplace")
    app.register_blueprint(ads_bp,          url_prefix="/api/ads")
    app.register_blueprint(pages_bp)
    app.register_blueprint(admin_bp,        url_prefix="/admin")
    app.register_blueprint(admin_api_bp,    url_prefix="/api/admin")

    # ── Upload folders ──────────────────────────────────────────────────────
    for folder_key in ("UPLOAD_FOLDER", "HEATMAP_FOLDER", "REPORT_FOLDER"):
        os.makedirs(app.config[folder_key], exist_ok=True)

    # ── Security headers ────────────────────────────────────────────────────
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"]        = "SAMEORIGIN"
        response.headers["Referrer-Policy"]        = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"]      = "1; mode=block"
        return response

    # ── Error handlers ──────────────────────────────────────────────────────
    def _is_api(req) -> bool:
        return req.path.startswith("/api/")

    def _render_error(code: int, title: str, message: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{code} — {title} | SmartX-Ray</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
</head>
<body class="bg-light d-flex align-items-center justify-content-center min-vh-100">
  <div class="text-center p-5">
    <h1 class="display-1 fw-bold text-primary">{code}</h1>
    <h4 class="fw-bold mb-2">{title}</h4>
    <p class="text-muted mb-4">{message}</p>
    <a href="/" class="btn btn-primary me-2">Go Home</a>
    <a href="/dashboard" class="btn btn-outline-primary">Dashboard</a>
  </div>
</body>
</html>"""

    @app.errorhandler(400)
    def bad_request(e):
        if _is_api(request):
            return jsonify({"error": "Bad request.", "detail": str(e.description)}), 400
        return _render_error(400, "Bad Request", "The request could not be understood."), 400

    @app.errorhandler(401)
    def unauthorized(e):
        if _is_api(request):
            return jsonify({"error": "Authentication required."}), 401
        return _render_error(401, "Unauthorized", "Please log in to access this page."), 401

    @app.errorhandler(403)
    def forbidden(e):
        if _is_api(request):
            return jsonify({"error": "Permission denied.", "upgrade_url": "/pricing"}), 403
        return _render_error(403, "Access Denied",
                             "This feature requires a Pro subscription."), 403

    @app.errorhandler(404)
    def not_found(e):
        if _is_api(request):
            return jsonify({"error": "Resource not found."}), 404
        return _render_error(404, "Page Not Found",
                             "The page you're looking for doesn't exist."), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        if _is_api(request):
            return jsonify({"error": "Method not allowed."}), 405
        return _render_error(405, "Method Not Allowed", str(e.description)), 405

    @app.errorhandler(413)
    def payload_too_large(e):
        if _is_api(request):
            return jsonify({"error": "File too large. Maximum upload size is 16 MB."}), 413
        return _render_error(413, "File Too Large", "Maximum upload size is 16 MB."), 413

    @app.errorhandler(429)
    def too_many_requests(e):
        if _is_api(request):
            return jsonify({
                "error": "Daily scan limit reached. Upgrade to Pro for unlimited scans.",
                "upgrade_url": "/pricing",
            }), 429
        return _render_error(429, "Limit Reached",
                             "You've used all your free scans for today. "
                             '<a href="/pricing">Upgrade to Pro</a> for unlimited scans.'), 429

    @app.errorhandler(500)
    def server_error(e):
        logger.exception("Unhandled 500 error on %s %s", request.method, request.path)
        if _is_api(request):
            return jsonify({"error": "An internal server error occurred. Please try again."}), 500
        return _render_error(500, "Server Error",
                             "Something went wrong on our end. Please try again in a moment."), 500

    # ── Health check ────────────────────────────────────────────────────────
    @app.route("/health")
    def health():
        from flask import render_template

        checks = {}
        try:
            db.session.execute(db.text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as exc:
            logger.warning("Health check — DB unreachable: %s", exc)
            checks["database"] = "error"
        try:
            from app.services.ai_service import _model
            checks["model"] = "loaded" if _model is not None else "not_loaded"
        except Exception:
            checks["model"] = "unknown"

        overall    = "ok" if all(v in ("ok", "loaded", "not_loaded") for v in checks.values()) else "degraded"
        http_code  = 200 if overall == "ok" else 503
        payload    = {
            "status":    overall,
            "checks":    checks,
            "version":   "1.0.0",
            "env":       app.config.get("ENV", env),
            "python":    platform.python_version(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Return HTML when opened in a browser; JSON for API/curl clients
        wants_json = (
            request.args.get("format") == "json"
            or request.accept_mimetypes.best == "application/json"
            or "curl" in request.headers.get("User-Agent", "").lower()
        )
        if wants_json:
            return jsonify(payload), http_code

        return render_template("health.html", **payload), http_code

    # ── Shell context ───────────────────────────────────────────────────────
    @app.shell_context_processor
    def make_shell_context():
        from app.models.user         import User
        from app.models.scan         import Scan
        from app.models.subscription import Subscription
        from app.models.ad           import Ad
        from app.models.doctor       import Doctor
        from app.models.report       import Report
        from app.models.transaction  import Transaction
        from app.models.system_log   import SystemLog
        return dict(
            db=db,
            User=User, Scan=Scan, Subscription=Subscription,
            Ad=Ad, Doctor=Doctor, Report=Report, Transaction=Transaction,
            SystemLog=SystemLog,
        )

    # ── CLI commands ────────────────────────────────────────────────────────
    @app.cli.command("seed-db")
    def seed_db():
        """Seed the database with demo users, doctors, and ads."""
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location(
            "seed", pathlib.Path(__file__).parent.parent / "seed.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.seed()

    @app.cli.command("create-admin")
    @click.argument("email")
    @click.argument("password")
    @click.option("--name", default="Admin User", help="Full name")
    def create_admin(email, password, name):
        """Create a Pro-tier admin user."""
        from app.models.user import User
        if User.query.filter_by(email=email.lower()).first():
            click.echo(f"User {email} already exists.")
            return
        u = User(email=email.lower(), full_name=name,
                 tier="pro", is_verified=True, is_admin=True, is_active=True)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        click.echo(f"✓ Admin user created: {email}")

    @app.cli.command("list-users")
    @click.option("--tier", default=None, help="Filter by tier: free or pro")
    def list_users(tier):
        """List all registered users."""
        from app.models.user import User
        q = User.query
        if tier:
            q = q.filter_by(tier=tier)
        users = q.order_by(User.created_at.desc()).all()
        click.echo(f"\n{'ID':<6} {'Email':<35} {'Tier':<8} {'Scans Today'}")
        click.echo("-" * 60)
        for u in users:
            click.echo(f"{u.id:<6} {u.email:<35} {u.tier:<8} {u.scans_today}")
        click.echo(f"\nTotal: {len(users)}")

    @app.cli.command("stats")
    def stats():
        """Show a quick dashboard of application statistics."""
        from app.models.user         import User
        from app.models.scan         import Scan
        from app.models.subscription import Subscription
        from app.models.doctor       import Doctor
        from app.models.ad           import Ad

        total_users   = User.query.count()
        free_users    = User.query.filter_by(tier="free").count()
        pro_users     = User.query.filter_by(tier="pro").count()
        total_scans   = Scan.query.count()
        pneumonia     = Scan.query.filter_by(prediction="PNEUMONIA").count()
        normal        = Scan.query.filter_by(prediction="NORMAL").count()
        active_subs   = Subscription.query.filter_by(status="active").count()
        total_doctors = Doctor.query.filter_by(is_active=True).count()
        total_ads     = Ad.query.filter_by(is_active=True).count()
        total_clicks  = db.session.query(db.func.sum(Ad.clicks)).scalar() or 0
        total_impress = db.session.query(db.func.sum(Ad.impressions)).scalar() or 0

        click.echo("\n══════════════ SmartX-Ray Stats ══════════════")
        click.echo(f"  Users        : {total_users}  (free: {free_users}, pro: {pro_users})")
        click.echo(f"  Subscriptions: {active_subs} active")
        click.echo(f"  Scans        : {total_scans}  (pneumonia: {pneumonia}, normal: {normal})")
        click.echo(f"  Doctors      : {total_doctors} active listings")
        click.echo(f"  Ads          : {total_ads} active  |  {total_impress:,} impressions  |  {total_clicks:,} clicks")
        click.echo("══════════════════════════════════════════════\n")

    @app.cli.command("reset-quota")
    def reset_quota():
        """Manually reset today's scan counter for all free users."""
        from app.models.user import User
        now = datetime.now(timezone.utc)
        n = User.query.filter_by(tier="free").update(
            {"scans_today": 0, "scans_reset_at": now}
        )
        db.session.commit()
        click.echo(f"✓ Reset quota for {n} free user(s).")

    return app
