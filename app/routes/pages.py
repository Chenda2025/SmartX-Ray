from flask import Blueprint, render_template

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    return render_template("index.html")

@pages_bp.route("/login")
def login():
    return render_template("auth.html")

@pages_bp.route("/dashboard")
def dashboard():
    return render_template("user/dashboard.html")

@pages_bp.route("/scan/<int:scan_id>")
def result(scan_id):
    return render_template("result.html", scan_id=scan_id)

@pages_bp.route("/pricing")
def pricing():
    return render_template("pricing.html")

@pages_bp.route("/marketplace")
def marketplace():
    return render_template("marketplace.html")

@pages_bp.route("/forgot-password")
def forgot_password():
    return render_template("forgot_password.html")

@pages_bp.route("/reset-password")
def reset_password():
    return render_template("reset_password.html")
