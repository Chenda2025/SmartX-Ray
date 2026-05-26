"""
Telegram Bot alert service — SmartX-Ray
────────────────────────────────────────
Sends real-time notifications to the configured Telegram chat.
Supports multiple alert types; each can be individually toggled
via TELEGRAM_ALERT_* environment variables.

Alert types
-----------
  pneumonia      → high-confidence PNEUMONIA scan (≥ 80 %)
  auth_fail      → repeated authentication failures
  critical_error → uncaught exceptions / system errors
  db_health      → database health-check failures
  daily_summary  → scheduled daily stats report
  test           → manual test sent from admin panel
"""

import logging
import os
import requests
from flask import current_app

logger    = logging.getLogger(__name__)
_TIMEOUT  = 6          # seconds per Telegram API request
_MAX_LEN  = 4096       # Telegram HTML message limit


# ══════════════════════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _is_alert_enabled(alert_key: str, default: bool = True) -> bool:
    """
    Check whether a specific alert type is enabled.
    Reads TELEGRAM_ALERT_<KEY> from Flask config (loaded from .env).
    Defaults to `default` if the key is not set.
    """
    raw = current_app.config.get(f"TELEGRAM_ALERT_{alert_key.upper()}", None)
    if raw is None:
        return default
    return str(raw).strip().lower() not in ("false", "0", "no", "off")


def discover_chat_id(token: str) -> str | None:
    """
    Call getUpdates to find the first chat that messaged the bot.
    Returns the chat_id string or None if no updates exist yet.
    """
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"limit": 1, "timeout": 0},
            timeout=_TIMEOUT,
        )
        if not r.ok:
            return None
        updates = r.json().get("result", [])
        if not updates:
            return None
        upd  = updates[0]
        msg  = upd.get("message") or upd.get("channel_post") or {}
        chat = msg.get("chat", {})
        return str(chat.get("id")) if chat.get("id") else None
    except Exception as exc:
        logger.warning("discover_chat_id failed: %s", exc)
        return None


def _get_chat_id() -> str:
    """
    Return the chat_id from config, auto-discovering and persisting it if missing.
    """
    chat_id = current_app.config.get("TELEGRAM_CHAT_ID", "").strip()
    if chat_id:
        return chat_id

    token = current_app.config.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return ""

    found = discover_chat_id(token)
    if found:
        current_app.config["TELEGRAM_CHAT_ID"] = found
        try:
            from dotenv import set_key
            env_path = os.path.normpath(
                os.path.join(current_app.root_path, "..", ".env")
            )
            set_key(env_path, "TELEGRAM_CHAT_ID", found)
            logger.info("Auto-saved TELEGRAM_CHAT_ID=%s to .env", found)
        except Exception as e:
            logger.warning("Could not persist TELEGRAM_CHAT_ID to .env: %s", e)
    return found or ""


def _send(message: str) -> bool:
    """
    Low-level: POST a single HTML message to the Telegram Bot API.
    Returns True on success, False otherwise (non-raising).
    """
    token   = current_app.config.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = _get_chat_id()

    if not token or not chat_id:
        logger.debug("Telegram not configured — skipping alert.")
        return False

    # Truncate if over Telegram's limit
    if len(message) > _MAX_LEN:
        message = message[:_MAX_LEN - 30] + "\n… <i>(truncated)</i>"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        logger.info("Telegram message sent (chat_id=%s, %d chars).", chat_id, len(message))
        return True
    except requests.RequestException as exc:
        logger.warning("Telegram send failed: %s", exc)
        return False


# Public alias kept for backward-compat
def send_telegram_alert(message: str) -> bool:
    return _send(message)


# ══════════════════════════════════════════════════════════════════════════════
#  ALERT FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def alert_high_severity_pneumonia(scan, user) -> None:
    """
    Bilingual (EN + KM) alert for a high-confidence PNEUMONIA scan (≥ 80 %).
    Called from app/routes/scan.py after commit.
    Respects TELEGRAM_ALERT_PNEUMONIA setting.
    """
    if not _is_alert_enabled("pneumonia", default=True):
        logger.debug("Pneumonia Telegram alert is disabled — skipping.")
        return

    confidence_pct = round(scan.confidence * 100, 1)
    ts = (
        scan.created_at.strftime("%Y-%m-%d %H:%M UTC")
        if scan.created_at else "N/A"
    )
    msg = (
        "🚨 <b>HIGH-SEVERITY PNEUMONIA DETECTED</b>\n"
        "🚨 <b>រកឃើញជំងឺរលាកសួតកម្រិតធ្ងន់</b>\n"
        "─────────────────────────\n\n"
        "👤 <b>Patient / អ្នកជំងឺ :</b>\n"
        "   <code>{email}</code>\n\n"
        "📊 <b>AI Confidence / ភាពជឿជាក់ AI :</b>\n"
        "   <b>{pct}%</b> — above critical threshold\n\n"
        "🆔 <b>Scan ID :</b> <code>{sid}</code>\n"
        "🕐 <b>Time / ពេលវេលា :</b> {ts}\n\n"
        "─────────────────────────\n"
        "⚠️ <i>Please review this scan in the SmartX-Ray admin panel immediately.</i>\n"
        "⚠️ <i>សូមពិនិត្យការស្កែននេះក្នុងផ្ទាំងគ្រប់គ្រង SmartX-Ray ភ្លាមៗ។</i>"
    ).format(email=user.email, pct=confidence_pct, sid=scan.id, ts=ts)

    _send(msg)


def send_auth_failure_alert(failed_count: int, ip: str = "",
                            email: str = "") -> bool:
    """
    Alert when the same IP has too many consecutive auth failures.
    Respects TELEGRAM_ALERT_AUTH_FAIL setting.
    """
    if not _is_alert_enabled("auth_fail", default=True):
        return False

    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    detail = ""
    if email:
        detail += f"👤 <b>Target / គោលដៅ:</b> <code>{email}</code>\n"
    if ip:
        detail += f"🌐 <b>IP Address:</b> <code>{ip}</code>\n"

    msg = (
        "🛡️ <b>AUTH FAILURE ALERT</b>\n"
        "🛡️ <b>ការព្រមាន: Login ច្រើនដងបរាជ័យ</b>\n"
        "─────────────────────────\n\n"
        f"🔢 <b>Failed Attempts / ចំនួនពេលបរាជ័យ:</b> <b>{failed_count}</b>\n"
        f"{detail}"
        f"🕐 <b>Time / ពេលវេលា:</b> {ts}\n\n"
        "─────────────────────────\n"
        "⚠️ <i>A brute-force attempt may be in progress.\n"
        "   Check admin logs for details.</i>\n"
        "⚠️ <i>អាចមានការព្យាយាម brute-force ។\n"
        "   សូមពិនិត្យ admin logs ភ្លាមៗ។</i>"
    )
    return _send(msg)


def send_critical_error_alert(error_msg: str, source: str = "system") -> bool:
    """
    Alert for critical / uncaught system errors.
    Respects TELEGRAM_ALERT_CRITICAL_ERROR setting.
    """
    if not _is_alert_enabled("critical_error", default=True):
        return False

    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Limit error text
    safe_err = str(error_msg)[:300].replace("<", "&lt;").replace(">", "&gt;")

    msg = (
        "🔴 <b>CRITICAL SYSTEM ERROR</b>\n"
        "🔴 <b>កំហុសសំខាន់ក្នុងប្រព័ន្ធ</b>\n"
        "─────────────────────────\n\n"
        f"📍 <b>Source / ប្រភព:</b> <code>{source}</code>\n\n"
        f"💬 <b>Error / កំហុស:</b>\n<code>{safe_err}</code>\n\n"
        f"🕐 <b>Time / ពេលវេលា:</b> {ts}\n\n"
        "─────────────────────────\n"
        "⚠️ <i>Immediate attention required in the SmartX-Ray admin panel.</i>\n"
        "⚠️ <i>ត្រូវការការយកចិត្តទុកដាក់ភ្លាមៗ ក្នុង SmartX-Ray admin panel ។</i>"
    )
    return _send(msg)


def send_db_health_alert(status: str, detail: str = "") -> bool:
    """
    Bilingual DB health alert.
    Respects TELEGRAM_ALERT_DB_HEALTH setting.
    """
    if not _is_alert_enabled("db_health", default=True):
        return False

    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    detail_line = (
        f"\n🔍 <b>Detail / លម្អិត:</b> {detail}" if detail else ""
    )
    msg = (
        "⚠️ <b>DATABASE HEALTH ALERT</b>\n"
        "⚠️ <b>ការព្រមាន: បញ្ហាមូលដ្ឋានទិន្នន័យ</b>\n"
        "─────────────────────────\n\n"
        f"📊 <b>Status / ស្ថានភាព:</b> <b>{status}</b>"
        f"{detail_line}\n"
        f"🕐 <b>Time / ពេលវេលា:</b> {ts}\n\n"
        "─────────────────────────\n"
        "⚠️ <i>Check the SmartX-Ray database connection immediately.</i>\n"
        "⚠️ <i>សូមពិនិត្យការតភ្ជាប់មូលដ្ឋានទិន្នន័យ SmartX-Ray ភ្លាមៗ។</i>"
    )
    return _send(msg)


def send_daily_summary(stats: dict) -> bool:
    """
    Daily stats summary — typically called by a scheduled job.
    Respects TELEGRAM_ALERT_DAILY_SUMMARY setting.

    Expected `stats` keys:
      scans_today, pneumonia, normal, total_users, new_users_today,
      active_subs, pending_doctors  (all int)
    """
    if not _is_alert_enabled("daily_summary", default=False):
        return False

    from datetime import datetime, timezone
    date_str       = datetime.now(timezone.utc).strftime("%d %B %Y")
    scans_today    = stats.get("scans_today",    0)
    pneumonia      = stats.get("pneumonia",       0)
    normal         = stats.get("normal",          0)
    total_users    = stats.get("total_users",    0)
    new_users      = stats.get("new_users_today", 0)
    active_subs    = stats.get("active_subs",    0)
    pending_docs   = stats.get("pending_doctors", 0)

    pct = round(pneumonia / scans_today * 100, 1) if scans_today else 0

    pending_line = (
        f"\n🩺 <b>Pending Doctors / វេជ្ជបណ្ឌិតរង់ចាំ:</b> {pending_docs} awaiting review"
        if pending_docs else ""
    )

    msg = (
        f"📊 <b>SmartX-Ray — Daily Report {date_str}</b>\n"
        f"📊 <b>SmartX-Ray — របាយការណ៍ប្រចាំថ្ងៃ {date_str}</b>\n"
        "─────────────────────────\n\n"
        f"🔬 <b>Scans Today / ការស្កែន:</b> {scans_today}\n"
        f"🫁 <b>Pneumonia / ជំងឺរលាកសួត:</b> {pneumonia} ({pct}%)\n"
        f"✅ <b>Normal / ធម្មតា:</b> {normal}\n\n"
        f"👥 <b>Total Users / អ្នកប្រើ:</b> {total_users}\n"
        f"🆕 <b>New Today / ថ្មីថ្ងៃនេះ:</b> {new_users}\n"
        f"⭐ <b>Pro Subscribers / ជាវ Pro:</b> {active_subs}"
        f"{pending_line}\n\n"
        "─────────────────────────\n"
        "<i>SmartX-Ray Admin Panel — Automated Daily Report</i>"
    )
    return _send(msg)


def send_test_alert(alert_type: str = "generic") -> bool:
    """
    Test alert for the given type.  `alert_type` is one of:
    generic | pneumonia | auth_fail | critical_error | db_health | daily_summary
    Always sends regardless of enabled settings (it's a manual test).
    """
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    previews = {
        "pneumonia": (
            "🚨 <b>TEST — High-Severity Pneumonia</b>\n\n"
            "👤 <b>Patient:</b> <code>patient@example.com</code>\n"
            "📊 <b>Confidence:</b> <b>92.5%</b>\n"
            "🆔 <b>Scan ID:</b> <code>#999</code>\n"
            f"🕐 <b>Time:</b> {ts}"
        ),
        "auth_fail": (
            "🛡️ <b>TEST — Auth Failure Alert</b>\n\n"
            "🔢 <b>Failed Attempts:</b> <b>7</b>\n"
            "👤 <b>Target:</b> <code>admin@smartxray.com</code>\n"
            "🌐 <b>IP Address:</b> <code>192.168.1.100</code>\n"
            f"🕐 <b>Time:</b> {ts}"
        ),
        "critical_error": (
            "🔴 <b>TEST — Critical System Error</b>\n\n"
            "📍 <b>Source:</b> <code>scan_route</code>\n"
            "💬 <b>Error:</b> <code>Simulated error for testing purposes</code>\n"
            f"🕐 <b>Time:</b> {ts}"
        ),
        "db_health": (
            "⚠️ <b>TEST — Database Health Alert</b>\n\n"
            "📊 <b>Status:</b> <b>degraded</b>\n"
            "🔍 <b>Detail:</b> Connection pool exhausted\n"
            f"🕐 <b>Time:</b> {ts}"
        ),
        "daily_summary": (
            "📊 <b>TEST — Daily Summary Report</b>\n\n"
            "🔬 <b>Scans Today:</b> 24\n"
            "🫁 <b>Pneumonia:</b> 6 (25%)\n"
            "✅ <b>Normal:</b> 18\n"
            "👥 <b>Total Users:</b> 142\n"
            "🆕 <b>New Today:</b> 3\n"
            "⭐ <b>Pro Subscribers:</b> 28"
        ),
    }

    body = previews.get(alert_type, None)
    if body is None:
        body = (
            "✅ <b>TEST ALERT — SmartX-Ray</b>\n"
            "✅ <b>ការជូនដំណឹងសាកល្បង — SmartX-Ray</b>\n\n"
            "🇬🇧 Telegram alerts are working correctly! 🎉\n"
            "🇰🇭 ការជូនដំណឹង Telegram ដំណើរការបានត្រឹមត្រូវ! 🎉"
        )

    msg = (
        f"{body}\n\n"
        "─────────────────────────\n"
        f"<i>Test sent from SmartX-Ray Admin Panel\n{ts}</i>"
    )
    return _send(msg)
