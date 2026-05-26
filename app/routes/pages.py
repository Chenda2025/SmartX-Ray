from flask import Blueprint, redirect, render_template, url_for

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
    return redirect(url_for("pages.upgrade"), 302)

@pages_bp.route("/upgrade")
def upgrade():
    return render_template("user/upgrade.html")

@pages_bp.route("/marketplace")
def marketplace():
    return redirect(url_for("pages.find_doctor"), 301)

@pages_bp.route("/forgot-password")
def forgot_password():
    return render_template("forgot_password.html")

@pages_bp.route("/reset-password")
def reset_password():
    return render_template("reset_password.html")

@pages_bp.route("/doctor/register")
def doctor_register():
    return render_template("doctor/register.html")

@pages_bp.route("/doctor/login")
def doctor_login():
    return render_template("doctor/login.html")

@pages_bp.route("/doctor/dashboard")
def doctor_dashboard():
    return render_template("doctor/dashboard.html")


# ── Patient portal pages ────────────────────────────────────────────────────

@pages_bp.route("/find-doctor")
def find_doctor():
    return render_template("user/find_doctor.html")

@pages_bp.route("/doctor/<int:doctor_id>")
def doctor_profile(doctor_id):
    return render_template("user/doctor_profile.html", doctor_id=doctor_id)

@pages_bp.route("/my-appointments")
def my_appointments():
    return render_template("user/my_appointments.html")

@pages_bp.route("/book/<int:doctor_id>")
def book_appointment(doctor_id):
    return render_template("user/book_appointment.html", doctor_id=doctor_id)
