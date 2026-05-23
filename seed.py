"""
seed.py — Populate the database with demo data.
Run:  python seed.py

Creates:
  • 2 demo users   (free + pro)
  • 6 doctors      (varied specialties and cities)
  • 4 ads          (banner, sidebar, result_page, interstitial)
"""

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.doctor import Doctor
from app.models.ad import Ad

app = create_app("development")


def seed():
    with app.app_context():
        print("Seeding database…")

        # ── Demo users ─────────────────────────────────────────────────────
        users = [
            {"email": "demo@smartxray.com",   "full_name": "Demo User",    "tier": "free", "pw": "Demo1234!"},
            {"email": "pro@smartxray.com",     "full_name": "Pro Member",   "tier": "pro",  "pw": "Demo1234!"},
        ]
        for u_data in users:
            if not User.query.filter_by(email=u_data["email"]).first():
                u = User(email=u_data["email"], full_name=u_data["full_name"], tier=u_data["tier"])
                u.set_password(u_data["pw"])
                db.session.add(u)
                print(f"  ✓ User: {u_data['email']}  ({u_data['tier']})")

        # ── Doctors ────────────────────────────────────────────────────────
        doctors_data = [
            {
                "full_name": "Dr. Sarah Mitchell",
                "specialty": "Pulmonologist",
                "qualifications": "MBBS, MD (Pulmonology), FCCP",
                "hospital": "City General Hospital",
                "city": "New York",
                "country": "USA",
                "phone": "+1-212-555-0101",
                "email": "s.mitchell@citygeneral.com",
                "bio": "Specialist in respiratory diseases with 15 years of experience. "
                       "Expert in pneumonia diagnosis and treatment.",
                "rating": 4.8, "review_count": 124,
                "is_verified": True, "is_featured": True,
            },
            {
                "full_name": "Dr. James Okafor",
                "specialty": "Radiologist",
                "qualifications": "MBBS, FRCR, MD",
                "hospital": "Royal London Hospital",
                "city": "London",
                "country": "UK",
                "phone": "+44-20-7946-0101",
                "email": "j.okafor@rlh.nhs.uk",
                "bio": "Chest radiologist specialising in infectious lung diseases and AI-assisted diagnosis.",
                "rating": 4.9, "review_count": 87,
                "is_verified": True, "is_featured": True,
            },
            {
                "full_name": "Dr. Aisha Rahman",
                "specialty": "Infectious Disease Specialist",
                "qualifications": "MBBS, MD, DTM&H",
                "hospital": "Aga Khan University Hospital",
                "city": "Karachi",
                "country": "Pakistan",
                "phone": "+92-21-3493-0051",
                "email": "a.rahman@aku.edu",
                "bio": "Expert in respiratory infections and tropical pulmonology.",
                "rating": 4.7, "review_count": 63,
                "is_verified": True, "is_featured": False,
            },
            {
                "full_name": "Dr. Marcus Weber",
                "specialty": "Pulmonologist",
                "qualifications": "MD, PhD, FERS",
                "hospital": "Charité – Universitätsmedizin",
                "city": "Berlin",
                "country": "Germany",
                "phone": "+49-30-450-553002",
                "email": "m.weber@charite.de",
                "bio": "Research focus on AI-assisted radiology and pneumonia early detection.",
                "rating": 4.6, "review_count": 41,
                "is_verified": True, "is_featured": False,
            },
            {
                "full_name": "Dr. Li Wei",
                "specialty": "Radiologist",
                "qualifications": "MD, MSc Radiology",
                "hospital": "Peking Union Medical College Hospital",
                "city": "Beijing",
                "country": "China",
                "phone": "+86-10-6915-6114",
                "email": "li.wei@pumch.cn",
                "bio": "Specialises in chest imaging and AI-assisted pneumonia classification.",
                "rating": 4.5, "review_count": 99,
                "is_verified": True, "is_featured": False,
            },
            {
                "full_name": "Dr. Fatima Al-Sayed",
                "specialty": "Pulmonologist",
                "qualifications": "MBBS, MRCP, FCCP",
                "hospital": "King Faisal Specialist Hospital",
                "city": "Riyadh",
                "country": "Saudi Arabia",
                "phone": "+966-11-442-7272",
                "email": "f.alsayed@kfsh.med.sa",
                "bio": "Senior consultant in respiratory medicine with expertise in community-acquired pneumonia.",
                "rating": 4.9, "review_count": 156,
                "is_verified": True, "is_featured": True,
            },
        ]
        for d_data in doctors_data:
            if not Doctor.query.filter_by(email=d_data.get("email")).first():
                db.session.add(Doctor(**d_data))
                print(f"  ✓ Doctor: {d_data['full_name']}  ({d_data['city']})")

        # ── Ads ────────────────────────────────────────────────────────────
        ads_data = [
            {
                "title": "Upgrade to Pro — Unlimited Scans",
                "body":  "Get unlimited X-ray analyses, Grad-CAM heatmaps, PDF reports, and no ads.",
                "target_url": "/pricing",
                "advertiser": "SmartX-Ray",
                "placement": "banner",
                "priority": 10,
                "is_active": True,
            },
            {
                "title": "Find a Specialist Near You",
                "body":  "Connect with verified pulmonologists and radiologists in your city.",
                "target_url": "/marketplace",
                "advertiser": "SmartX-Ray",
                "placement": "sidebar",
                "priority": 8,
                "is_active": True,
            },
            {
                "title": "Download Your PDF Report",
                "body":  "Upgrade to Pro to generate a full diagnostic PDF with heatmaps and clinical notes.",
                "target_url": "/pricing",
                "advertiser": "SmartX-Ray",
                "placement": "result_page",
                "priority": 9,
                "is_active": True,
            },
            {
                "title": "Get a Second Opinion",
                "body":  "AI is a tool — always confirm your results with a qualified physician.",
                "target_url": "/marketplace",
                "advertiser": "SmartX-Ray",
                "placement": "interstitial",
                "priority": 5,
                "is_active": True,
            },
        ]
        for a_data in ads_data:
            if not Ad.query.filter_by(title=a_data["title"]).first():
                db.session.add(Ad(**a_data))
                print(f"  ✓ Ad: '{a_data['title']}'  [{a_data['placement']}]")

        db.session.commit()
        print("\nDone! Demo credentials:")
        print("  Free user → demo@smartxray.com / Demo1234!")
        print("  Pro  user → pro@smartxray.com  / Demo1234!")


if __name__ == "__main__":
    seed()
