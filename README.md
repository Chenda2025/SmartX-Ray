# SmartX-Ray Web

[![CI](https://github.com/YOUR_USERNAME/SmartX-Ray/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/SmartX-Ray/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-39%2F39%20passing-brightgreen)](tests/)
[![Python](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**AI-Powered Chest X-Ray Pneumonia Detection**  
University Final Project — Python Flask + PostgreSQL + Hybrid CNN+ANN

---

## Model Performance

| Metric | Score |
|--------|-------|
| Validation Accuracy | **97.03%** |
| Test Accuracy | **83.01%** |
| Architecture | Hybrid CNN + ANN |
| Explainability | Grad-CAM heatmaps |

---

## Features

| Feature | Free | Pro ($9.99/mo) |
|---------|------|----------------|
| X-ray analysis | 3/day | Unlimited |
| Grad-CAM heatmaps | ✅ | ✅ |
| Scan history | ✅ | ✅ |
| PDF diagnostic report | ❌ | ✅ |
| Ad-free experience | ❌ | ✅ |
| Find a Doctor | ✅ | ✅ |

---

## Project Structure

```
SmartX-Ray/
├── app/
│   ├── __init__.py          # App factory
│   ├── extensions.py        # db, jwt, cors, mail
│   ├── models/              # 7 SQLAlchemy models
│   │   ├── user.py          # User + tier + quota
│   │   ├── scan.py          # X-ray scan records
│   │   ├── subscription.py  # Stripe subscription
│   │   ├── ad.py            # Advertisements
│   │   ├── doctor.py        # Marketplace doctors
│   │   ├── report.py        # PDF reports (Pro)
│   │   └── transaction.py   # Payment audit log
│   ├── routes/
│   │   ├── auth.py          # register, login, /me
│   │   ├── scan.py          # upload, history, download
│   │   ├── subscription.py  # Stripe checkout + webhook
│   │   ├── marketplace.py   # Doctor search & listing
│   │   ├── ads.py           # Ad serving + click tracking
│   │   └── pages.py         # HTML page routes
│   ├── services/
│   │   ├── ai_service.py    # Model singleton + predict()
│   │   ├── gradcam.py       # Grad-CAM heatmap generator
│   │   ├── pdf_service.py   # ReportLab PDF builder
│   │   └── email_service.py # Flask-Mail transactional emails
│   └── utils/
│       ├── auth_helpers.py  # @jwt_required_user, @pro_required
│       └── validators.py    # Email / password / file validators
├── models/
│   └── best_model.h5        # Trained Keras model (299 MB)
├── static/
│   ├── uploads/             # Uploaded X-rays
│   ├── heatmaps/            # Grad-CAM overlays
│   ├── reports/             # Generated PDFs
│   ├── css/main.css
│   └── js/api.js
├── templates/               # Jinja2 HTML pages
│   ├── base.html
│   ├── index.html           # Landing page
│   ├── auth.html            # Login / Register
│   ├── dashboard.html       # Upload + scan history
│   ├── result.html          # Prediction + heatmap
│   ├── pricing.html         # Subscription plans
│   └── marketplace.html     # Find a Doctor
├── migrations/
│   └── schema.sql           # Raw SQL reference schema
├── tests/
│   └── test_api.py          # Full pytest suite
├── config.py                # Dev / Test / Prod configs
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── app.py              # thin runner for `python app.py` (local only)
```

---

## Quick Start (Local)

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Redis (optional — only needed for Celery background jobs)

### 1. Clone & set up environment

```bash
git clone <your-repo-url>
cd SmartX-Ray
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/smartxray

# Optional — only needed for payment features
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_MONTHLY=price_...
STRIPE_PRICE_YEARLY=price_...

# Optional — only needed for email features
MAIL_USERNAME=you@gmail.com
MAIL_PASSWORD=your-app-password
```

### 3. Set up the database

```bash
createdb smartxray                         # or use psql
flask db init
flask db migrate -m "initial schema"
flask db upgrade
```

### 4. Place the AI model

Ensure `models/best_model.h5` exists (already committed or download separately).

### 5. Run the app

```bash
flask run
# or: python app.py
# or: gunicorn 'app:create_app()' --bind 0.0.0.0:5000 --workers 2 --timeout 120
```

Visit **http://localhost:5000**

---

## Docker Deployment

```bash
cp .env.example .env    # fill in production values

docker compose up --build -d
```

Services started:
- **web** → http://localhost:5000 (Flask via Gunicorn)
- **db** → PostgreSQL 16 (internal port 5432)
- **redis** → Redis 7 (internal port 6379)

Database migrations run automatically on container start.

---

## Running Tests

```bash
# Requires a running PostgreSQL instance (test DB is auto-created)
pytest tests/ -v

# With coverage
pip install pytest-cov
pytest tests/ --cov=app --cov-report=term-missing
```

---

## API Reference

### Auth — `/api/auth`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/register` | — | Create account |
| POST | `/login` | — | Returns JWT pair |
| POST | `/refresh` | refresh JWT | New access token |
| GET | `/me` | JWT | Profile + quota |
| PATCH | `/me` | JWT | Update name / password |
| POST | `/logout` | JWT | Invalidate session |

### Scan — `/api/scan`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/upload` | JWT | Upload X-ray → AI prediction |
| GET | `/history` | JWT | Paginated scan list |
| GET | `/<id>` | JWT | Single scan details |
| DELETE | `/<id>` | JWT | Delete scan |
| GET | `/report/<id>/download` | **Pro** JWT | Download PDF report |

### Subscription — `/api/subscription`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/status` | JWT | Tier + billing info |
| POST | `/checkout` | JWT | Stripe checkout session |
| POST | `/cancel` | JWT | Cancel at period end |
| POST | `/webhook` | Stripe sig | Stripe event handler |

### Marketplace — `/api/marketplace`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/doctors` | — | Search & filter doctors |
| GET | `/doctors/<id>` | — | Doctor profile |
| GET | `/specialties` | — | Distinct specialties |
| GET | `/cities` | — | Distinct cities |
| POST | `/doctors` | JWT | Add doctor listing |

### Ads — `/api/ads`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/?placement=` | JWT | Get ads (empty for Pro) |
| POST | `/<id>/click` | — | Track click |
| POST | `/` | JWT | Create ad |
| PATCH | `/<id>` | JWT | Update ad |

---

## Admin Dashboard

Available at **http://localhost:5000/admin/**

| Module | URL | Description |
|--------|-----|-------------|
| Dashboard | `/admin/` | KPI cards — total users, scans, revenue |
| User Management | `/admin/users` | Search, filter, toggle tier/admin flag |
| Ad Manager | `/admin/ads` | Create/edit/activate ads with placement |
| Subscriptions | `/admin/subscriptions` | Billing overview, cancel subscriptions |
| Marketplace | `/admin/marketplace` | Verify/unverify doctor listings |
| System Logs | `/admin/logs` | Audit trail of all admin actions |

**Default admin credentials** (created by `python seed.py`):
- Email: `admin@smartxray.com`
- Password: `admin123`

> 🔔 **Telegram alerts:** Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`
> to receive a Telegram message whenever a scan returns PNEUMONIA ≥ 80%.

---

## Business Models

| Model | Implementation |
|-------|---------------|
| **Advertising** | Free users receive ads on result page & dashboard |
| **Freemium** | PDF reports locked behind Pro tier (`@pro_required`) |
| **Subscription** | $9.99/month or $79.99/year via Stripe Checkout |
| **Marketplace** | Doctor directory with search & filter |
| **On-Demand Dashboard** | Unified scan history + stats + quick actions |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, Flask 3.0 |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 + Flask-Migrate |
| Auth | JWT (Flask-JWT-Extended) |
| AI Model | TensorFlow 2.16 / Keras 3 |
| Grad-CAM | GradientTape + OpenCV |
| PDF | ReportLab |
| Payments | Stripe |
| Email | Flask-Mail |
| Notifications | Telegram Bot API |
| Deployment | Gunicorn + Docker Compose |
| CI/CD | GitHub Actions (pytest + coverage) |

---

## Disclaimer

SmartX-Ray is a **university research project** for educational purposes only.
It is **not** a certified medical device and must not be used as a substitute
for professional medical advice, diagnosis, or treatment.
