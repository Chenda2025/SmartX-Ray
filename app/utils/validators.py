import re
from flask import current_app

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PASSWORD_MIN = 8


def validate_email(email: str) -> str | None:
    """Return error message or None if valid."""
    if not email or not EMAIL_RE.match(email.strip()):
        return "Invalid email address."
    return None


def validate_password(password: str) -> str | None:
    if not password or len(password) < PASSWORD_MIN:
        return f"Password must be at least {PASSWORD_MIN} characters."
    return None


def allowed_image(filename: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_EXTENSIONS"]
