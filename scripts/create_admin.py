#!/usr/bin/env python3
"""
Create or update the admin user from environment variables.

Required env vars:
  ADMIN_EMAIL     — admin login email
  ADMIN_PASSWORD  — admin login password

Run during deploy (after flask db upgrade):
  python scripts/create_admin.py
"""
import os
import sys

ADMIN_EMAIL    = os.environ.get("ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "").strip()
ADMIN_NAME     = os.environ.get("ADMIN_NAME", "Admin").strip()

def main():
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        print("⚠  ADMIN_EMAIL or ADMIN_PASSWORD not set — skipping admin creation.")
        return 0

    # Import inside app context
    from app import create_app
    from app.extensions import db
    from app.models.user import User

    app = create_app()
    with app.app_context():
        existing = User.query.filter_by(email=ADMIN_EMAIL).first()

        if existing:
            # Update password + ensure is_admin=True
            existing.set_password(ADMIN_PASSWORD)
            existing.is_admin  = True
            existing.is_active = True
            existing.full_name = ADMIN_NAME
            db.session.commit()
            print(f"✓ Admin updated: {ADMIN_EMAIL}")
        else:
            admin = User(
                email     = ADMIN_EMAIL,
                full_name = ADMIN_NAME,
                is_admin  = True,
                is_active = True,
            )
            admin.set_password(ADMIN_PASSWORD)
            db.session.add(admin)
            db.session.commit()
            print(f"✓ Admin created: {ADMIN_EMAIL}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
