#!/usr/bin/env python3
"""
db/seed.py — SmartX-Ray Cambodian Sample Data
══════════════════════════════════════════════════════════════════════════════
Seeds the database with realistic Cambodian actors for the Admin → Doctor →
Patient connection flow.

Data seeded
───────────
  • 1  admin user
  • 3  approved doctors   (Dr. Sophal Meas, Dr. Pisey Keo, Dr. Kosal Lim)
  • 1  pending  doctor    (Dr. Chanthy Sok — awaiting approval)
  • 3  patients            (Sopheap Chea [pro], Dara Heng [free], Maly Noun [free])
  • 3  scans               (Sopheap: PNEUMONIA 94%, NORMAL 88%, PNEUMONIA 76%)
  • 1  appointment         (Sopheap → Dr. Sophal Meas, 25 May 2026 10:00)
  • 1  review              (Sopheap → 5★ "Professional and thorough")
  • 1  telegram config     (placeholder tokens, threshold 85%)
  • 3  system log entries  (one per scan)
  • 4  ads                 (2 default banners, 1 sidebar, 1 result-page)

Prerequisites
─────────────
  flask db upgrade          ← apply all schema migrations first

Run
───
  flask seed-db             ← via Flask CLI  (registered in app/__init__.py)
  python db/seed.py         ← or directly as a script
  python -c "from db.seed import seed; seed()"

Idempotent: each block checks for existing rows before inserting.
All writes use raw SQL so the seed works regardless of which ORM models
have been updated at any given step.
══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import os
import sys

# Allow direct script execution (python db/seed.py)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash
from sqlalchemy import text

from app import create_app
from app.extensions import db

# ── Shared timestamp ──────────────────────────────────────────────────────────
NOW = datetime.now(timezone.utc)

# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY
# ─────────────────────────────────────────────────────────────────────────────
def seed() -> None:
    """Seed the database.  Called by `flask seed-db` or directly."""
    app = create_app("development")
    with app.app_context():
        print("\n🌱  SmartX-Ray — Cambodian Sample Data Seed")
        print("═" * 56)

        ids: dict = {}

        # ── Actors ────────────────────────────────────────────────────
        ids["admin"]        = _seed_admin()
        ids["doctors"]      = _seed_approved_doctors(ids["admin"])
        ids["pending"]      = _seed_pending_doctor()
        ids["patients"]     = _seed_patients()

        # ── Clinical data ─────────────────────────────────────────────
        ids["scans"]        = _seed_scans(ids["patients"]["sopheap"])
        ids["appointment"]  = _seed_appointment(
            ids["patients"]["sopheap"],
            ids["doctors"]["sophal"],
        )
        _seed_review(
            ids["appointment"],
            ids["patients"]["sopheap"],
            ids["doctors"]["sophal"],
        )

        # ── System / config ───────────────────────────────────────────
        _seed_telegram_config()
        _seed_system_logs(ids["scans"], ids["patients"]["sopheap"])
        _seed_ads()
        _seed_subscriptions(ids["patients"])

        db.session.commit()

        print("\n" + "═" * 56)
        _print_credentials()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — ADMIN USER
# ─────────────────────────────────────────────────────────────────────────────
def _seed_admin() -> int:
    print("\n[1/9] Admin user")

    uid = _find_user("admin@smartxray.kh")
    if uid:
        print(f"      ⟳  already exists (id={uid})")
        return uid

    uid = _insert_user(
        email       = "admin@smartxray.kh",
        full_name   = "SmartX Admin",
        password    = "Admin@123",
        role        = "admin",
        tier        = "pro",
        university  = None,
        is_admin    = True,
        is_active   = True,
        is_verified = True,
    )
    print(f"      ✓  admin@smartxray.kh  (id={uid})")
    return uid


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — APPROVED DOCTORS
# ─────────────────────────────────────────────────────────────────────────────
def _seed_approved_doctors(admin_id: int) -> dict:
    """Create user accounts + doctor profiles for 3 approved Cambodian doctors."""
    print("\n[2/9] Approved doctors")

    doctors_data = [
        {
            "key":           "sophal",
            "email":         "sophal.meas@smartxray.kh",
            "full_name":     "Dr. Sophal Meas",
            "specialty":     "Radiology",
            "license":       "KH-MED-2891",
            "university":    "RUPP",
            "experience":    8,
            "rate":          15.00,
            "avg_rating":    4.80,
            "total_reviews": 23,
            "availability":  "Mon–Fri  08:00–17:00",
            "bio": (
                "Radiologist at Calmette Hospital, specialising in chest X-ray "
                "interpretation and AI-assisted pneumonia diagnosis. "
                "RUPP graduate, 8 years clinical experience."
            ),
        },
        {
            "key":           "pisey",
            "email":         "pisey.keo@smartxray.kh",
            "full_name":     "Dr. Pisey Keo",
            "specialty":     "Pulmonology",
            "license":       "KH-MED-3042",
            "university":    "NUM",
            "experience":    11,
            "rate":          20.00,
            "avg_rating":    4.60,
            "total_reviews": 18,
            "availability":  "Mon–Sat  09:00–16:00",
            "bio": (
                "Pulmonologist at Khmer-Soviet Friendship Hospital. "
                "Specialist in respiratory infections, COPD, and post-COVID lung care. "
                "NUM graduate with fellowship in Pulmonary Medicine."
            ),
        },
        {
            "key":           "kosal",
            "email":         "kosal.lim@smartxray.kh",
            "full_name":     "Dr. Kosal Lim",
            "specialty":     "General Medicine",
            "license":       "KH-MED-3188",
            "university":    "IU",
            "experience":    5,
            "rate":          10.00,
            "avg_rating":    4.90,
            "total_reviews": 41,
            "availability":  "Mon–Sun  07:00–12:00",
            "bio": (
                "General practitioner focused on preventive care and chronic disease "
                "management. International University graduate. "
                "Serves patients in Phnom Penh and Kandal Province."
            ),
        },
    ]

    ids: dict = {}

    for d in doctors_data:
        # ── Create or fetch user account ──────────────────────────────
        uid = _find_user(d["email"])
        if not uid:
            uid = _insert_user(
                email       = d["email"],
                full_name   = d["full_name"],
                password    = "Doctor@123",
                role        = "doctor",
                tier        = "pro",
                university  = d["university"],
                is_admin    = False,
                is_active   = True,
                is_verified = True,
            )

        # ── Create or fetch doctor profile ────────────────────────────
        did = _find_doctor_by_license(d["license"])
        if not did:
            result = db.session.execute(text("""
                INSERT INTO doctors (
                    user_id, full_name, specialty,
                    license_number, license_no,
                    university, experience_years,
                    rate_per_session, availability, bio,
                    status, is_verified, is_active, is_featured,
                    avg_rating, rating,
                    total_reviews, review_count,
                    total_earnings,
                    country, email,
                    reviewed_by, reviewed_at,
                    created_at, updated_at
                ) VALUES (
                    :user_id, :full_name, :specialty,
                    :license, :license,
                    :university, :experience,
                    :rate, :avail, :bio,
                    'approved', TRUE, TRUE, FALSE,
                    :avg_rating, :avg_rating,
                    :reviews, :reviews,
                    :earnings,
                    'Cambodia', :email,
                    :reviewed_by, NOW(),
                    NOW(), NOW()
                ) RETURNING id
            """), {
                "user_id":    uid,
                "full_name":  d["full_name"],
                "specialty":  d["specialty"],
                "license":    d["license"],
                "university": d["university"],
                "experience": d["experience"],
                "rate":       d["rate"],
                "avail":      d["availability"],
                "bio":        d["bio"],
                "avg_rating": d["avg_rating"],
                "reviews":    d["total_reviews"],
                "earnings":   float(d["total_reviews"]) * d["rate"],
                "email":      d["email"],
                "reviewed_by": admin_id,
            })
            did = result.fetchone()[0]
            print(f"      ✓  {d['full_name']}  [{d['specialty']}]  id={did}")
        else:
            print(f"      ⟳  {d['full_name']} already exists (id={did})")

        ids[d["key"]] = did

    return ids


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — PENDING DOCTOR
# ─────────────────────────────────────────────────────────────────────────────
def _seed_pending_doctor() -> int:
    print("\n[3/9] Pending doctor")

    license_no = "KH-MED-3290"
    did = _find_doctor_by_license(license_no)
    if did:
        print(f"      ⟳  Dr. Chanthy Sok already exists (id={did})")
        return did

    # User account exists but is_active=FALSE (can't log in until approved)
    email = "chanthy.sok@smartxray.kh"
    uid   = _find_user(email)
    if not uid:
        uid = _insert_user(
            email       = email,
            full_name   = "Dr. Chanthy Sok",
            password    = "Doctor@123",
            role        = "doctor",
            tier        = "free",
            university  = "AUSF",
            is_admin    = False,
            is_active   = False,     # ← locked out until admin approves
            is_verified = False,
        )

    result = db.session.execute(text("""
        INSERT INTO doctors (
            user_id, full_name, specialty,
            license_number, license_no,
            university, experience_years,
            rate_per_session, availability, bio,
            status, is_verified, is_active, is_featured,
            country, email,
            created_at, updated_at
        ) VALUES (
            :user_id, 'Dr. Chanthy Sok', 'Cardiology',
            :license, :license,
            'AUSF', 4,
            25.00, 'Mon–Fri  10:00–15:00',
            'Cardiologist with 4 years of clinical practice. '
            'AUSF graduate. Focused on non-invasive cardiac imaging.',
            'pending', FALSE, FALSE, FALSE,
            'Cambodia', :email,
            NOW(), NOW()
        ) RETURNING id
    """), {"user_id": uid, "license": license_no, "email": email})

    did = result.fetchone()[0]
    print(f"      ✓  Dr. Chanthy Sok  [Cardiology / pending]  id={did}")
    return did


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — PATIENTS
# ─────────────────────────────────────────────────────────────────────────────
def _seed_patients() -> dict:
    print("\n[4/9] Patients")

    patients_data = [
        {
            "key":        "sopheap",
            "email":      "sopheap@rupp.edu.kh",
            "full_name":  "Sopheap Chea",
            "tier":       "pro",
            "university": "RUPP",
        },
        {
            "key":        "dara",
            "email":      "dara@iu.edu.kh",
            "full_name":  "Dara Heng",
            "tier":       "free",
            "university": "IU",
        },
        {
            "key":        "maly",
            "email":      "maly@num.edu.kh",
            "full_name":  "Maly Noun",
            "tier":       "free",
            "university": "NUM",
        },
    ]

    ids: dict = {}
    for p in patients_data:
        uid = _find_user(p["email"])
        if uid:
            print(f"      ⟳  {p['full_name']} already exists (id={uid})")
        else:
            uid = _insert_user(
                email       = p["email"],
                full_name   = p["full_name"],
                password    = "Patient@123",
                role        = "patient",
                tier        = p["tier"],
                university  = p["university"],
                is_admin    = False,
                is_active   = True,
                is_verified = True,
            )
            print(f"      ✓  {p['full_name']}  [{p['tier']}]  id={uid}")
        ids[p["key"]] = uid

    return ids


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — SCANS  (3 scans for Sopheap)
# ─────────────────────────────────────────────────────────────────────────────
def _seed_scans(sopheap_id: int) -> list[int]:
    print("\n[5/9] Sample scans  (Sopheap Chea)")

    scans_data = [
        {
            "image_path":    "uploads/seed_scan_sopheap_1.jpg",
            "result_label":  "PNEUMONIA",
            "confidence_pct": 94.00,
            "confidence":    0.94,
            "ai_time_ms":    1100,
            "created_at":    NOW - timedelta(days=5),
        },
        {
            "image_path":    "uploads/seed_scan_sopheap_2.jpg",
            "result_label":  "NORMAL",
            "confidence_pct": 88.00,
            "confidence":    0.88,
            "ai_time_ms":    900,
            "created_at":    NOW - timedelta(days=3),
        },
        {
            "image_path":    "uploads/seed_scan_sopheap_3.jpg",
            "result_label":  "PNEUMONIA",
            "confidence_pct": 76.00,
            "confidence":    0.76,
            "ai_time_ms":    1400,
            "created_at":    NOW - timedelta(days=1),
        },
    ]

    scan_ids: list[int] = []

    # Check how many scans already exist for Sopheap
    existing_count = db.session.execute(
        text("SELECT COUNT(*) FROM scans WHERE user_id = :uid"),
        {"uid": sopheap_id},
    ).scalar()

    if existing_count >= 3:
        existing = db.session.execute(
            text("SELECT id FROM scans WHERE user_id = :uid ORDER BY created_at LIMIT 3"),
            {"uid": sopheap_id},
        ).fetchall()
        scan_ids = [r[0] for r in existing]
        print(f"      ⟳  3 scans already exist for Sopheap")
        return scan_ids

    for s in scans_data:
        # Determine severity for system log
        is_high = s["result_label"] == "PNEUMONIA" and s["confidence"] >= 0.80

        result = db.session.execute(text("""
            INSERT INTO scans (
                user_id,
                image_path,
                prediction,
                confidence,
                model_version,
                gradcam_status,
                created_at
            ) VALUES (
                :uid,
                :img,
                :label,
                :conf,
                'CNN+ANN v1.0',
                'done',
                :created_at
            ) RETURNING id
        """), {
            "uid":        sopheap_id,
            "img":        s["image_path"],
            "label":      s["result_label"],
            "conf":       s["confidence"],
            "created_at": s["created_at"],
        })
        sid = result.fetchone()[0]
        scan_ids.append(sid)

        severity = "high" if is_high else "info"
        ms_str   = f'{s["ai_time_ms"] / 1000:.1f}s'
        print(
            f"      ✓  {s['result_label']:9s} {s['confidence_pct']:5.1f}%  "
            f"{ms_str:5s}  [{severity:4s}]  scan_id={sid}"
        )

    return scan_ids


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 — APPOINTMENT
# ─────────────────────────────────────────────────────────────────────────────
def _seed_appointment(sopheap_id: int, sophal_doctor_id: int) -> int:
    print("\n[6/9] Sample appointment")

    # Check for existing appointment
    existing = db.session.execute(text("""
        SELECT id FROM appointments
        WHERE patient_id = :pid AND doctor_id = :did
        LIMIT 1
    """), {"pid": sopheap_id, "did": sophal_doctor_id}).fetchone()

    # Fallback: check using old column name if patient_id column doesn't exist yet
    if existing is None:
        try:
            existing = db.session.execute(text("""
                SELECT id FROM appointments
                WHERE user_id = :pid AND doctor_id = :did
                LIMIT 1
            """), {"pid": sopheap_id, "did": sophal_doctor_id}).fetchone()
        except Exception:
            pass

    if existing:
        apt_id = existing[0]
        print(f"      ⟳  appointment already exists (id={apt_id})")
        return apt_id

    # Appointment: 25 May 2026 10:00 (yesterday — confirmed)
    scheduled = datetime(2026, 5, 25, 10, 0, 0, tzinfo=timezone.utc)

    try:
        # New schema  (patient_id + scheduled_at); user_id = patient_id (same column, both required)
        result = db.session.execute(text("""
            INSERT INTO appointments (
                user_id, patient_id, doctor_id,
                scheduled_at,
                appointment_date, appointment_time,
                duration_min,
                status,
                patient_note, note,
                meeting_link,
                fee_amount, fee_snapshot,
                payment_method, payment_status,
                created_at
            ) VALUES (
                :pid, :pid, :did,
                :scheduled,
                '2026-05-25', '10:00',
                30,
                'confirmed',
                :note, :note,
                'https://meet.jit.si/SmartXRay-apt-1',
                15.00, 15.00,
                'ABA KHQR', 'paid',
                NOW()
            ) RETURNING id
        """), {
            "pid":       sopheap_id,
            "did":       sophal_doctor_id,
            "scheduled": scheduled,
            "note":      "Chest pain follow-up after pneumonia scan",
        })
    except Exception:
        # Fallback: old schema (user_id + date/time separate)
        result = db.session.execute(text("""
            INSERT INTO appointments (
                user_id, doctor_id,
                appointment_date, appointment_time,
                note, status, fee_snapshot,
                created_at
            ) VALUES (
                :pid, :did,
                '2026-05-25', '10:00',
                :note, 'confirmed', 15.00,
                NOW()
            ) RETURNING id
        """), {
            "pid":  sopheap_id,
            "did":  sophal_doctor_id,
            "note": "Chest pain follow-up after pneumonia scan",
        })

    apt_id = result.fetchone()[0]
    print(f"      ✓  Sopheap → Dr. Sophal Meas")
    print(f"         25 May 2026 10:00 · confirmed · $15 ABA KHQR")
    print(f"         meeting: https://meet.jit.si/SmartXRay-apt-{apt_id}  (id={apt_id})")
    return apt_id


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7 — REVIEW
# ─────────────────────────────────────────────────────────────────────────────
def _seed_review(apt_id: int, sopheap_id: int, sophal_doctor_id: int) -> None:
    print("\n[7/9] Sample review")

    existing = db.session.execute(
        text("SELECT id FROM reviews WHERE appointment_id = :aid"),
        {"aid": apt_id},
    ).fetchone()

    if existing:
        print(f"      ⟳  review already exists (id={existing[0]})")
        return

    try:
        result = db.session.execute(text("""
            INSERT INTO reviews (
                appointment_id, patient_id, doctor_id,
                rating, comment, created_at
            ) VALUES (
                :aid, :pid, :did,
                5, 'Professional and thorough', NOW()
            ) RETURNING id
        """), {"aid": apt_id, "pid": sopheap_id, "did": sophal_doctor_id})

        rid = result.fetchone()[0]

        # Recalculate doctor avg_rating (trigger handles it in full DB,
        # but we do it manually here for safety / early-migration state)
        db.session.execute(text("""
            UPDATE doctors
            SET avg_rating    = (SELECT ROUND(AVG(rating)::NUMERIC, 2) FROM reviews WHERE doctor_id = :did),
                rating        = (SELECT ROUND(AVG(rating)::NUMERIC, 2) FROM reviews WHERE doctor_id = :did),
                total_reviews = (SELECT COUNT(*) FROM reviews WHERE doctor_id = :did),
                review_count  = (SELECT COUNT(*) FROM reviews WHERE doctor_id = :did)
            WHERE id = :did
        """), {"did": sophal_doctor_id})

        print(f"      ✓  Sopheap → Dr. Sophal Meas  ★★★★★  id={rid}")
        print(f"         \"Professional and thorough\"")

    except Exception as exc:
        print(f"      ⚠  reviews table not found yet — run migrations first  ({exc})")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8 — TELEGRAM CONFIG
# ─────────────────────────────────────────────────────────────────────────────
def _seed_telegram_config() -> None:
    print("\n[8/9] Telegram config")

    try:
        existing = db.session.execute(
            text("SELECT id FROM telegram_configs WHERE id = 1"),
        ).fetchone()

        if existing:
            print(f"      ⟳  config row id=1 already exists")
            return

        db.session.execute(text("""
            INSERT INTO telegram_configs (id, bot_token, chat_id, is_active, updated_at)
            VALUES (1, 'YOUR_BOT_TOKEN', 'YOUR_CHAT_ID', TRUE, NOW())
            ON CONFLICT (id) DO UPDATE
            SET updated_at = NOW()
        """))
        print("      ✓  telegram_configs id=1")
        print("      ℹ  Replace YOUR_BOT_TOKEN / YOUR_CHAT_ID in /admin/telegram")

    except Exception as exc:
        db.session.rollback()
        print(f"      ⚠  telegram_configs seed skipped  ({exc})")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9 — SYSTEM LOGS  (one entry per scan)
# ─────────────────────────────────────────────────────────────────────────────
def _seed_system_logs(scan_ids: list[int], sopheap_id: int) -> None:
    print("\n[9/9] System logs")

    # Map scan_id → details we already know
    scan_meta = [
        ("PNEUMONIA", 94.00, 1100, "high"),
        ("NORMAL",    88.00,  900, "info"),
        ("PNEUMONIA", 76.00, 1400, "info"),
    ]

    for i, (sid, (label, pct, ms, severity)) in enumerate(
        zip(scan_ids, scan_meta), start=1
    ):
        existing = db.session.execute(
            text("SELECT id FROM system_logs WHERE scan_id = :sid"),
            {"sid": sid},
        ).fetchone()

        if existing:
            print(f"      ⟳  log for scan_id={sid} already exists")
            continue

        db.session.execute(text("""
            INSERT INTO system_logs (
                event_type, severity,
                user_id, scan_id,
                message,
                processing_ms,
                ip_address,
                is_deleted, created_at
            ) VALUES (
                'scan', :severity,
                :uid, :sid,
                :msg,
                :ms,
                '127.0.0.1',
                FALSE, NOW()
            )
        """), {
            "severity": severity,
            "uid":      sopheap_id,
            "sid":      sid,
            "msg":      f"{label} detected ({pct:.1f}%) for sopheap@rupp.edu.kh",
            "ms":       ms,
        })
        print(f"      ✓  scan_id={sid}  [{label} {pct:.0f}%]  [{severity}]")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION A — SUBSCRIPTION  (Sopheap gets a pro sub record)
# ─────────────────────────────────────────────────────────────────────────────
def _seed_subscriptions(patient_ids: dict) -> None:
    """Create a Pro subscription record for Sopheap Chea."""
    sopheap_id = patient_ids.get("sopheap")
    if not sopheap_id:
        return

    existing = db.session.execute(
        text("SELECT id FROM subscriptions WHERE user_id = :uid"),
        {"uid": sopheap_id},
    ).fetchone()
    if existing:
        return  # silent — already seeded

    try:
        db.session.execute(text("""
            INSERT INTO subscriptions (
                user_id, plan, status,
                current_period_start, current_period_end,
                created_at, updated_at
            ) VALUES (
                :uid, 'monthly', 'active',
                NOW(),
                NOW() + INTERVAL '30 days',
                NOW(), NOW()
            )
        """), {"uid": sopheap_id})
    except Exception as exc:
        db.session.rollback()  # prevent transaction abort from blocking final commit
        print(f"      ⚠  subscription seed skipped: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION B — ADS
# ─────────────────────────────────────────────────────────────────────────────
def _seed_ads() -> None:
    """Ensure the 4 default platform ads exist."""
    ads = [
        {
            "title":       "Upgrade to Pro — Unlimited Scans",
            "body":        "Get unlimited X-ray analyses, Grad-CAM heatmaps, PDF reports, and priority support.",
            "target_url":  "/pricing",
            "advertiser":  "SmartX-Ray",
            "sponsor_name":"SmartX-Ray",
            "placement":   "banner",
            "priority":    10,
        },
        {
            "title":       "Find a Verified Doctor",
            "body":        "Connect with approved Cambodian specialists for a second opinion.",
            "target_url":  "/find-doctor",
            "advertiser":  "SmartX-Ray",
            "sponsor_name":"SmartX-Ray",
            "placement":   "result_page",
            "priority":    9,
        },
        {
            "title":       "Second Opinion Matters",
            "body":        "AI assists — but always confirm with a qualified physician.",
            "target_url":  "/find-doctor",
            "advertiser":  "SmartX-Ray",
            "sponsor_name":"SmartX-Ray",
            "placement":   "sidebar",
            "priority":    7,
        },
        {
            "title":       "Download Your PDF Report",
            "body":        "Pro users can download a clinical PDF report with heatmap annotations.",
            "target_url":  "/pricing",
            "advertiser":  "SmartX-Ray",
            "sponsor_name":"SmartX-Ray",
            "placement":   "interstitial",
            "priority":    5,
        },
    ]

    for ad in ads:
        existing = db.session.execute(
            text("SELECT id FROM ads WHERE title = :t"),
            {"t": ad["title"]},
        ).fetchone()
        if existing:
            continue

        db.session.execute(text("""
            INSERT INTO ads (
                title, body, target_url,
                advertiser,
                placement, priority, is_active,
                impressions, clicks,
                created_at, updated_at
            ) VALUES (
                :title, :body, :target_url,
                :advertiser,
                :placement, :priority, TRUE,
                0, 0,
                NOW(), NOW()
            )
        """), ad)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _find_user(email: str) -> int | None:
    """Return user.id if email exists, else None."""
    row = db.session.execute(
        text("SELECT id FROM users WHERE email = :e"), {"e": email}
    ).fetchone()
    return row[0] if row else None


def _insert_user(
    email: str,
    full_name: str,
    password: str,
    role: str,
    tier: str,
    university: str | None,
    is_admin: bool,
    is_active: bool,
    is_verified: bool,
) -> int:
    """Insert a new user row using only columns guaranteed to exist."""
    pw_hash = generate_password_hash(password)

    # Insert using actual schema columns (role added by c004, scan_count does not exist)
    result = db.session.execute(text("""
        INSERT INTO users (
            email, full_name, password_hash,
            role, tier, university,
            is_admin, is_active, is_verified,
            scans_today,
            created_at, updated_at
        ) VALUES (
            :email, :full_name, :pw_hash,
            :role, :tier, :university,
            :is_admin, :is_active, :is_verified,
            0,
            NOW(), NOW()
        ) RETURNING id
    """), {
        "email":       email,
        "full_name":   full_name,
        "pw_hash":     pw_hash,
        "role":        role,
        "tier":        tier,
        "university":  university,
        "is_admin":    is_admin,
        "is_active":   is_active,
        "is_verified": is_verified,
    })

    return result.fetchone()[0]


def _find_doctor_by_license(license_no: str) -> int | None:
    """Return doctor.id if license exists, else None."""
    # Try new column name first
    try:
        row = db.session.execute(
            text("SELECT id FROM doctors WHERE license_number = :l"), {"l": license_no}
        ).fetchone()
        if row:
            return row[0]
    except Exception:
        pass

    # Fallback: old column name
    try:
        row = db.session.execute(
            text("SELECT id FROM doctors WHERE license_no = :l"), {"l": license_no}
        ).fetchone()
        return row[0] if row else None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# CREDENTIALS PRINTOUT
# ─────────────────────────────────────────────────────────────────────────────
def _print_credentials() -> None:
    print("🔑  Login Credentials")
    print("─" * 56)
    print("ADMIN")
    print("  admin@smartxray.kh          Admin@123")
    print()
    print("APPROVED DOCTORS  (status=approved, is_active=TRUE)")
    print("  sophal.meas@smartxray.kh    Doctor@123   Radiology / RUPP")
    print("  pisey.keo@smartxray.kh      Doctor@123   Pulmonology / NUM")
    print("  kosal.lim@smartxray.kh      Doctor@123   General / IU")
    print()
    print("PENDING DOCTOR  (status=pending, is_active=FALSE — cannot login)")
    print("  chanthy.sok@smartxray.kh    Doctor@123   Cardiology / AUSF")
    print()
    print("PATIENTS")
    print("  sopheap@rupp.edu.kh         Patient@123  Pro tier / RUPP")
    print("  dara@iu.edu.kh              Patient@123  Free tier / IU")
    print("  maly@num.edu.kh             Patient@123  Free tier / NUM")
    print()
    print("  ℹ  Pro subscription: sopheap@rupp.edu.kh (30-day mock)")
    print("  ℹ  Telegram config: set real tokens in /admin/telegram")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# SCRIPT ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    seed()
