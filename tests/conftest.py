"""
Shared pytest fixtures for the SmartX-Ray test suite.
Fixtures defined here are automatically available to all test files.
"""

import os
import pytest

os.environ.setdefault("FLASK_ENV", "testing")

from app import create_app
from app.extensions import db as _db
from app.models.user import User
from app.models.ad import Ad
from app.models.doctor import Doctor


# ── App + DB ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    application = create_app("testing")
    with application.app_context():
        _db.create_all()
        _seed_base_data()
        yield application
        # Use CASCADE so dependent tables (reviews, etc.) don't block drop_all
        _db.session.execute(_db.text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        _db.session.commit()


def _seed_base_data():
    """Minimal seed data shared across all tests."""
    if not Ad.query.first():
        _db.session.add(Ad(
            title="Test Ad", body="Upgrade now", target_url="/pricing",
            placement="result_page", is_active=True, priority=1,
        ))
        _db.session.add(Ad(
            title="Banner Ad", body="Try Pro", target_url="/pricing",
            placement="banner", is_active=True, priority=2,
        ))
        _db.session.add(Ad(
            title="Sidebar Ad", body="Find a doctor", target_url="/marketplace",
            placement="sidebar", is_active=True, priority=1,
        ))
    if not Doctor.query.first():
        _db.session.add(Doctor(
            full_name="Dr. Jane Smith", specialty="Pulmonologist",
            city="London", country="UK",
            is_active=True, is_verified=True, rating=4.8, review_count=10,
        ))
    _db.session.commit()


@pytest.fixture()
def client(app):
    return app.test_client()


# ── User fixtures ──────────────────────────────────────────────────────────

@pytest.fixture()
def free_user(app):
    with app.app_context():
        # Delete any leftover from a previous interrupted run, then create fresh
        _db.session.query(User).filter_by(email="free@test.com").delete()
        _db.session.commit()
        u = User(email="free@test.com", full_name="Free User", tier="free")
        u.set_password("password123")
        _db.session.add(u)
        _db.session.commit()
        yield u
        _db.session.query(User).filter_by(email="free@test.com").delete()
        _db.session.commit()


@pytest.fixture()
def pro_user(app):
    with app.app_context():
        # Delete any leftover from a previous interrupted run, then create fresh
        _db.session.query(User).filter_by(email="pro@test.com").delete()
        _db.session.commit()
        u = User(email="pro@test.com", full_name="Pro User", tier="pro")
        u.set_password("password123")
        _db.session.add(u)
        _db.session.commit()
        yield u
        _db.session.query(User).filter_by(email="pro@test.com").delete()
        _db.session.commit()


# ── Helpers (importable from tests) ───────────────────────────────────────

def login(client, email, password="password123"):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    return res.get_json()["access_token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}
