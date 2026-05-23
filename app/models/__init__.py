# Import all models here so Flask-Migrate / SQLAlchemy picks them up.
from app.models.user import User
from app.models.scan import Scan
from app.models.subscription import Subscription
from app.models.ad import Ad
from app.models.doctor import Doctor
from app.models.report import Report
from app.models.transaction import Transaction
from app.models.system_log import SystemLog

__all__ = [
    "User", "Scan", "Subscription", "Ad",
    "Doctor", "Report", "Transaction", "SystemLog",
]
