"""
run.py — development convenience runner.

Usage:  python run.py
Equivalent to: FLASK_ENV=development flask run
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
