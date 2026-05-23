"""
Telegram Bot alert service.

Sends high-severity pneumonia alerts to the configured Telegram chat.
Silently no-ops if TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are not set.
"""
import logging
import requests
from flask import current_app

logger = logging.getLogger(__name__)

_TIMEOUT = 5  # seconds


def send_telegram_alert(message: str) -> bool:
    """
    Send a plain HTML-formatted message to the configured Telegram chat.
    Returns True on success, False otherwise (non-raising).
    """
    token   = current_app.config.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = current_app.config.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        logger.debug("Telegram not configured — skipping alert.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        logger.info("Telegram alert sent (chat_id=%s).", chat_id)
        return True
    except requests.RequestException as exc:
        logger.warning("Telegram alert failed: %s", exc)
        return False


def alert_high_severity_pneumonia(scan, user) -> None:
    """
    Send an alert for a high-confidence PNEUMONIA scan (≥ 80 %).
    Called from app/routes/scan.py after commit.
    """
    confidence_pct = round(scan.confidence * 100, 1)
    ts = (
        scan.created_at.strftime("%Y-%m-%d %H:%M UTC")
        if scan.created_at else "N/A"
    )
    msg = (
        "🚨 <b>HIGH-SEVERITY PNEUMONIA DETECTED</b>\n\n"
        f"👤 Patient : <code>{user.email}</code>\n"
        f"📊 Confidence : <b>{confidence_pct}%</b>\n"
        f"🆔 Scan ID : <code>{scan.id}</code>\n"
        f"🕐 Time : {ts}\n\n"
        "⚠️ <i>Please review this scan in the SmartX-Ray admin panel immediately.</i>"
    )
    send_telegram_alert(msg)


def send_db_health_alert(status: str, detail: str = "") -> None:
    """Notify when the database health check fails."""
    msg = (
        f"⚠️ <b>SmartX-Ray DB Health Check</b>\n"
        f"Status: <b>{status}</b>\n"
        + (f"Detail: {detail}" if detail else "")
    )
    send_telegram_alert(msg)
