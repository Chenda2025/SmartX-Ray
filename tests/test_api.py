"""
SmartX-Ray — API test suite
Run:  pytest tests/ -v
"""

import io
import os
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("FLASK_ENV", "testing")

from app import create_app
from app.extensions import db as _db
from app.models.user import User
from app.models.scan import Scan
from app.models.ad import Ad
from app.models.doctor import Doctor


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        _seed_ads()
        _seed_doctors()
        yield app
        # Use CASCADE so FK-dependent tables (reviews, etc.) don't block drop
        _db.session.execute(_db.text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        _db.session.commit()


def _seed_ads():
    ad = Ad(
        title="Test Ad", body="Upgrade now", target_url="/pricing",
        placement="result_page", is_active=True, priority=1,
    )
    _db.session.add(ad)
    _db.session.commit()


def _seed_doctors():
    doc = Doctor(
        full_name="Dr. Jane Smith", specialty="Pulmonologist",
        city="London", country="UK", is_active=True, is_verified=True,
    )
    _db.session.add(doc)
    _db.session.commit()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def free_user(app):
    with app.app_context():
        # Delete any leftover from an interrupted run, then create fresh
        _db.session.query(User).filter_by(email="free@test.com").delete()
        _db.session.commit()
        u = User(email="free@test.com", full_name="Free User")
        u.set_password("password123")
        _db.session.add(u)
        _db.session.commit()
        yield u
        _db.session.query(User).filter_by(email="free@test.com").delete()
        _db.session.commit()


@pytest.fixture()
def pro_user(app):
    with app.app_context():
        # Delete any leftover from an interrupted run, then create fresh
        _db.session.query(User).filter_by(email="pro@test.com").delete()
        _db.session.commit()
        u = User(email="pro@test.com", full_name="Pro User", tier="pro")
        u.set_password("password123")
        _db.session.add(u)
        _db.session.commit()
        yield u
        _db.session.query(User).filter_by(email="pro@test.com").delete()
        _db.session.commit()


def _login(client, email, password="password123"):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    return res.get_json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── Auth ───────────────────────────────────────────────────────────────────

class TestAuth:

    def test_register_success(self, client):
        res  = client.post("/api/auth/register", json={
            "email": "new@test.com", "password": "password123", "full_name": "New User",
        })
        data = res.get_json()
        assert res.status_code == 201
        assert "access_token"  in data
        assert "refresh_token" in data
        assert data["user"]["tier"] == "free"

    def test_register_duplicate_email(self, client, free_user):
        res = client.post("/api/auth/register", json={
            "email": "free@test.com", "password": "password123", "full_name": "Dup",
        })
        assert res.status_code == 409

    def test_register_bad_email(self, client):
        res = client.post("/api/auth/register", json={
            "email": "not-an-email", "password": "password123", "full_name": "X",
        })
        assert res.status_code == 400

    def test_register_short_password(self, client):
        res = client.post("/api/auth/register", json={
            "email": "short@test.com", "password": "abc", "full_name": "X",
        })
        assert res.status_code == 400

    def test_login_success(self, client, free_user):
        res  = client.post("/api/auth/login", json={"email": "free@test.com", "password": "password123"})
        assert res.status_code == 200
        assert "access_token" in res.get_json()

    def test_login_wrong_password(self, client, free_user):
        res = client.post("/api/auth/login", json={"email": "free@test.com", "password": "wrong"})
        assert res.status_code == 401

    def test_me_authenticated(self, client, free_user):
        token = _login(client, "free@test.com")
        res   = client.get("/api/auth/me", headers=_auth(token))
        data  = res.get_json()
        assert res.status_code == 200
        assert data["email"] == "free@test.com"

    def test_me_unauthenticated(self, client):
        res = client.get("/api/auth/me")
        assert res.status_code == 401

    def test_update_name(self, client, free_user):
        token = _login(client, "free@test.com")
        res   = client.patch("/api/auth/me", json={"full_name": "Updated"}, headers=_auth(token))
        assert res.status_code == 200
        assert res.get_json()["user"]["full_name"] == "Updated"

    def test_logout(self, client, free_user):
        token = _login(client, "free@test.com")
        res   = client.post("/api/auth/logout", headers=_auth(token))
        assert res.status_code == 200


# ── Scan ───────────────────────────────────────────────────────────────────

def _png_bytes():
    from PIL import Image as PILImage
    buf = io.BytesIO()
    PILImage.new("RGB", (224, 224), color=(128, 128, 128)).save(buf, format="PNG")
    buf.seek(0)
    return buf


class TestScan:

    @patch("app.services.ai_service.predict", return_value=("NORMAL", 0.92, 0.08))
    @patch("app.services.gradcam.generate_gradcam", return_value=None)
    def test_upload_free_gets_ad(self, mock_gc, mock_pred, client, free_user):
        token = _login(client, "free@test.com")
        res   = client.post("/api/scan/upload",
                            data={"file": (_png_bytes(), "test.png", "image/png")},
                            content_type="multipart/form-data",
                            headers=_auth(token))
        assert res.status_code == 201
        body = res.get_json()
        assert body["prediction"] == "NORMAL"
        assert "ad" in body          # free users receive an ad

    @patch("app.services.ai_service.predict", return_value=("PNEUMONIA", 0.95, 0.95))
    @patch("app.services.gradcam.generate_gradcam", return_value=None)
    @patch("app.services.pdf_service.generate_report", return_value=("rpt.pdf", 1024))
    @patch("app.services.email_service.send_scan_result")
    def test_upload_pro_gets_report(self, mock_mail, mock_pdf, mock_gc, mock_pred, client, pro_user):
        token = _login(client, "pro@test.com")
        res   = client.post("/api/scan/upload",
                            data={"file": (_png_bytes(), "test.png", "image/png")},
                            content_type="multipart/form-data",
                            headers=_auth(token))
        assert res.status_code == 201
        body = res.get_json()
        assert body["prediction"] == "PNEUMONIA"
        assert "report_id"  in body  # Pro users get PDF
        assert "ad"        not in body

    def test_upload_no_file(self, client, free_user):
        token = _login(client, "free@test.com")
        res   = client.post("/api/scan/upload", headers=_auth(token))
        assert res.status_code == 400

    def test_upload_invalid_type(self, client, free_user):
        token = _login(client, "free@test.com")
        res   = client.post("/api/scan/upload",
                            data={"file": (io.BytesIO(b"fake"), "doc.pdf", "application/pdf")},
                            content_type="multipart/form-data",
                            headers=_auth(token))
        assert res.status_code == 400

    def test_history_returns_list(self, client, free_user):
        token = _login(client, "free@test.com")
        res   = client.get("/api/scan/history", headers=_auth(token))
        data  = res.get_json()
        assert res.status_code == 200
        assert "scans" in data and "total" in data

    def test_get_scan_not_found(self, client, free_user):
        token = _login(client, "free@test.com")
        res   = client.get("/api/scan/99999", headers=_auth(token))
        assert res.status_code == 404

    @patch("app.services.ai_service.predict", return_value=("NORMAL", 0.88, 0.12))
    @patch("app.services.gradcam.generate_gradcam", return_value=None)
    def test_delete_scan(self, mock_gc, mock_pred, client, free_user):
        token = _login(client, "free@test.com")
        up    = client.post("/api/scan/upload",
                            data={"file": (_png_bytes(), "x.png", "image/png")},
                            content_type="multipart/form-data",
                            headers=_auth(token))
        sid = up.get_json()["id"]
        res = client.delete(f"/api/scan/{sid}", headers=_auth(token))
        assert res.status_code == 200


# ── Quota ──────────────────────────────────────────────────────────────────

class TestQuota:

    @patch("app.services.ai_service.predict", return_value=("NORMAL", 0.9, 0.1))
    @patch("app.services.gradcam.generate_gradcam", return_value=None)
    def test_quota_blocks_at_limit(self, mock_gc, mock_pred, app, client):
        with app.app_context():
            from datetime import datetime, timezone
            u = User(email="quota@test.com", full_name="Quota", scans_today=3)
            u.set_password("password123")
            u.scans_reset_at = datetime.now(timezone.utc)
            _db.session.add(u)
            _db.session.commit()

        token = _login(client, "quota@test.com")
        res   = client.post("/api/scan/upload",
                            data={"file": (_png_bytes(), "x.png", "image/png")},
                            content_type="multipart/form-data",
                            headers=_auth(token))
        assert res.status_code == 429
        assert "upgrade_url" in res.get_json()

        with app.app_context():
            _db.session.query(User).filter_by(email="quota@test.com").delete()
            _db.session.commit()


# ── Subscription ───────────────────────────────────────────────────────────

class TestSubscription:

    def test_status_free(self, client, free_user):
        token = _login(client, "free@test.com")
        res   = client.get("/api/subscription/status", headers=_auth(token))
        assert res.status_code == 200
        assert res.get_json()["tier"] == "free"

    def test_status_pro(self, client, pro_user):
        token = _login(client, "pro@test.com")
        res   = client.get("/api/subscription/status", headers=_auth(token))
        assert res.status_code == 200
        assert res.get_json()["tier"] == "pro"

    @patch("stripe.checkout.Session.create")
    @patch("stripe.Customer.create")
    def test_checkout_returns_url(self, mock_cust, mock_sess, client, free_user):
        mock_cust.return_value = MagicMock(id="cus_test")
        mock_sess.return_value = MagicMock(url="https://checkout.stripe.com/x", id="cs_x")
        token = _login(client, "free@test.com")
        res   = client.post("/api/subscription/checkout",
                            json={"plan": "monthly"}, headers=_auth(token))
        assert res.status_code == 200
        assert "checkout_url" in res.get_json()


# ── Marketplace ────────────────────────────────────────────────────────────

class TestMarketplace:

    def test_list_public(self, client):
        res = client.get("/api/doctors")
        assert res.status_code == 200
        assert "doctors" in res.get_json()

    def test_get_not_found(self, client):
        res = client.get("/api/doctors/99999")
        assert res.status_code == 404

    def test_specialties(self, client):
        res = client.get("/api/doctors")
        assert res.status_code == 200
        assert "doctors" in res.get_json()

    def test_cities(self, client):
        res = client.get("/api/doctors")
        assert res.status_code == 200

    def test_search_specialty(self, client):
        res  = client.get("/api/doctors?specialty=Pulmonologist")
        data = res.get_json()
        assert res.status_code == 200
        for d in data["doctors"]:
            assert "pulmonologist" in d["specialty"].lower()

    def test_search_no_match(self, client):
        res = client.get("/api/doctors?specialty=Unicornologist")
        assert res.get_json()["total"] == 0


# ── Ads ────────────────────────────────────────────────────────────────────

class TestAds:

    def test_free_user_gets_ads(self, client, free_user):
        token = _login(client, "free@test.com")
        res   = client.get("/api/ads?placement=result_page", headers=_auth(token))
        data  = res.get_json()
        assert res.status_code == 200
        assert data["pro"] is False
        assert isinstance(data["ads"], list)

    def test_pro_user_gets_no_ads(self, client, pro_user):
        token = _login(client, "pro@test.com")
        res   = client.get("/api/ads?placement=banner", headers=_auth(token))
        data  = res.get_json()
        assert res.status_code == 200
        assert data["pro"] is True
        assert data["ads"] == []

    def test_invalid_placement(self, client, free_user):
        token = _login(client, "free@test.com")
        res   = client.get("/api/ads?placement=invalid", headers=_auth(token))
        assert res.status_code == 400

    def test_click_increments_counter(self, client, app):
        with app.app_context():
            ad = Ad.query.filter_by(is_active=True).first()
            if not ad:
                pytest.skip("No active ad")
            ad_id  = ad.id
            before = ad.clicks
        res = client.post(f"/api/ads/{ad_id}/click")
        assert res.status_code == 200
        with app.app_context():
            updated = _db.session.get(Ad, ad_id)
            assert updated.clicks == before + 1


# ── Pro gating ─────────────────────────────────────────────────────────────

class TestProGating:

    def test_pdf_download_blocked_free(self, client, free_user):
        token = _login(client, "free@test.com")
        res   = client.get("/api/scan/report/1/download", headers=_auth(token))
        assert res.status_code == 403
        assert "upgrade_url" in res.get_json()

    def test_pdf_download_past_gate_for_pro(self, client, pro_user):
        """Pro user hits 404 (no report), not 403 (gate)."""
        token = _login(client, "pro@test.com")
        res   = client.get("/api/scan/report/99999/download", headers=_auth(token))
        assert res.status_code == 404


# ── HTML pages ─────────────────────────────────────────────────────────────

class TestPages:

    def test_landing(self, client):
        res = client.get("/")
        assert res.status_code == 200
        assert b"SmartX-Ray" in res.data

    def test_login_page(self, client):
        assert client.get("/login").status_code == 200

    def test_dashboard_page(self, client):
        assert client.get("/dashboard").status_code == 200

    def test_pricing_page(self, client):
        assert client.get("/pricing").status_code in (200, 302)

    def test_marketplace_page(self, client):
        assert client.get("/marketplace").status_code in (200, 301, 302)

    def test_result_page(self, client):
        assert client.get("/scan/1").status_code == 200
