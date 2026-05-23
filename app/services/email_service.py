"""
Email service — wraps Flask-Mail for transactional emails.
"""

import logging
from flask import current_app
from flask_mail import Message
from app.extensions import mail

logger = logging.getLogger(__name__)


def _send(subject: str, recipients: list[str], html: str) -> None:
    try:
        msg = Message(
            subject=subject,
            recipients=recipients,
            html=html,
            sender=current_app.config["MAIL_DEFAULT_SENDER"],
        )
        mail.send(msg)
        logger.info("Email sent to %s: %s", recipients, subject)
    except Exception:
        logger.exception("Failed to send email to %s", recipients)


# ── Transactional emails ───────────────────────────────────────────────────

def send_welcome(user) -> None:
    html = f"""
    <h2>Welcome to SmartX-Ray, {user.full_name}!</h2>
    <p>Your account has been created successfully.</p>
    <p>Start by uploading a chest X-ray on your
       <a href="http://localhost:5000/dashboard">dashboard</a>.</p>
    <p>Free tier: <strong>3 scans per day</strong>.<br>
       Upgrade to <strong>Pro</strong> for unlimited scans + PDF reports.</p>
    <hr>
    <small>SmartX-Ray &mdash; AI-Powered Pneumonia Detection</small>
    """
    _send("Welcome to SmartX-Ray!", [user.email], html)


def send_scan_result(user, scan) -> None:
    colour = "#D93025" if scan.prediction == "PNEUMONIA" else "#1E8E3E"
    conf   = round(scan.confidence * 100, 2)
    html = f"""
    <h2>Your X-Ray Result is Ready</h2>
    <p>Hi {user.full_name},</p>
    <p>Your scan (#{scan.id}) has been analysed:</p>
    <p style="font-size:22px; color:{colour}; font-weight:bold;">
        {scan.prediction}
    </p>
    <p>Confidence: <strong>{conf}%</strong></p>
    {"<p>A PDF report has been generated in your dashboard.</p>" if scan.report_id else ""}
    <p><a href="http://localhost:5000/scan/{scan.id}">View full result with heatmap →</a></p>
    <hr>
    <small><em>This is an AI-assisted result. Always consult a qualified physician.</em></small>
    """
    _send("Your SmartX-Ray Result", [user.email], html)


def send_subscription_confirmation(user, plan: str) -> None:
    plan_label = "Monthly ($9.99/month)" if plan == "monthly" else "Yearly ($79.99/year)"
    html = f"""
    <h2>You're now a Pro member!</h2>
    <p>Hi {user.full_name},</p>
    <p>Your <strong>{plan_label}</strong> subscription is active.</p>
    <ul>
        <li>Unlimited scans</li>
        <li>PDF diagnostic reports</li>
        <li>No ads</li>
        <li>Priority support</li>
    </ul>
    <p><a href="http://localhost:5000/dashboard">Go to your dashboard →</a></p>
    <hr>
    <small>Manage your subscription at any time from Account Settings.</small>
    """
    _send("SmartX-Ray Pro — Subscription Confirmed", [user.email], html)


def send_subscription_canceled(user) -> None:
    html = f"""
    <h2>Subscription Cancellation Notice</h2>
    <p>Hi {user.full_name},</p>
    <p>Your Pro subscription has been set to cancel at the end of the current
       billing period. You will retain Pro access until then.</p>
    <p>Changed your mind?
       <a href="http://localhost:5000/pricing">Reactivate here →</a></p>
    <hr>
    <small>SmartX-Ray &mdash; AI-Powered Pneumonia Detection</small>
    """
    _send("SmartX-Ray — Subscription Cancellation", [user.email], html)


def send_password_reset(user, reset_token: str) -> None:
    reset_url = f"http://localhost:5000/reset-password?token={reset_token}"
    html = f"""
    <h2>Password Reset Request</h2>
    <p>Hi {user.full_name},</p>
    <p>Click below to reset your password. This link expires in 30 minutes.</p>
    <p><a href="{reset_url}">Reset Password →</a></p>
    <p>If you did not request this, you can safely ignore this email.</p>
    <hr>
    <small>SmartX-Ray &mdash; AI-Powered Pneumonia Detection</small>
    """
    _send("SmartX-Ray — Password Reset", [user.email], html)
