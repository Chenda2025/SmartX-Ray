"""
app.py — thin dev runner.

For development:   python app.py
For Flask CLI:     flask run   (auto-discovers app/ package and its create_app)
For production:    gunicorn app:create_app() --bind 0.0.0.0:5000
"""
import os
from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "development"))

if __name__ == "__main__":
    app.run(
        host  = "0.0.0.0",
        port  = int(os.environ.get("PORT", 5000)),
        debug = app.config["DEBUG"],
    )
