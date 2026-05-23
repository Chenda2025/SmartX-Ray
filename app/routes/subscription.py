import stripe
from flask import Blueprint, request, jsonify, current_app
from app.extensions import db
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.utils.auth_helpers import jwt_required_user, _get_current_user

subscription_bp = Blueprint("subscription", __name__)


def _stripe():
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    return stripe


# ── GET /api/subscription/status ─────────────────────────────────────────
@subscription_bp.route("/status", methods=["GET"])
@jwt_required_user
def status():
    user = _get_current_user()
    sub  = user.subscription
    return jsonify({
        "tier":         user.tier,
        "subscription": sub.to_dict() if sub else None,
    }), 200


# ── POST /api/subscription/checkout ──────────────────────────────────────
@subscription_bp.route("/checkout", methods=["POST"])
@jwt_required_user
def create_checkout():
    """Create a Stripe Checkout Session and return the session URL."""
    user = _get_current_user()
    data = request.get_json(silent=True) or {}
    plan = data.get("plan", "monthly")   # monthly | yearly

    s = _stripe()
    price_id = (
        current_app.config["STRIPE_PRICE_YEARLY"]
        if plan == "yearly"
        else current_app.config["STRIPE_PRICE_MONTHLY"]
    )

    # Reuse or create Stripe customer
    sub = user.subscription
    customer_id = sub.stripe_customer_id if sub else None
    if not customer_id:
        customer = s.Customer.create(email=user.email, name=user.full_name)
        customer_id = customer.id

    session = s.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{data.get('success_url', 'http://localhost:5000/dashboard')}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=data.get("cancel_url", "http://localhost:5000/pricing"),
        metadata={"user_id": user.id, "plan": plan},
    )

    return jsonify({"checkout_url": session.url, "session_id": session.id}), 200


# ── POST /api/subscription/cancel ────────────────────────────────────────
@subscription_bp.route("/cancel", methods=["POST"])
@jwt_required_user
def cancel():
    user = _get_current_user()
    sub  = user.subscription

    if not sub or not sub.stripe_subscription_id:
        return jsonify({"error": "No active subscription found."}), 404

    s = _stripe()
    s.Subscription.modify(
        sub.stripe_subscription_id,
        cancel_at_period_end=True,
    )

    sub.cancel_at_period_end = True
    db.session.commit()
    return jsonify({
        "message": "Subscription will cancel at the end of the current billing period.",
        "subscription": sub.to_dict(),
    }), 200


# ── POST /api/subscription/webhook ───────────────────────────────────────
@subscription_bp.route("/webhook", methods=["POST"])
def stripe_webhook():
    """Stripe sends events here. Verify signature, then update DB."""
    payload    = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")
    secret     = current_app.config["STRIPE_WEBHOOK_SECRET"]

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "Invalid signature."}), 400

    _handle_stripe_event(event)
    return jsonify({"received": True}), 200


def _handle_stripe_event(event: dict) -> None:
    from app.models.user import User
    from datetime import datetime, timezone

    etype = event["type"]
    obj   = event["data"]["object"]

    if etype == "checkout.session.completed":
        user_id = int(obj["metadata"].get("user_id", 0))
        plan    = obj["metadata"].get("plan", "monthly")
        user    = db.session.get(User, user_id)
        if not user:
            return

        sub = user.subscription or Subscription(user_id=user_id)
        sub.stripe_customer_id     = obj.get("customer")
        sub.stripe_subscription_id = obj.get("subscription")
        sub.plan                   = plan
        sub.status                 = "active"
        db.session.add(sub)
        user.tier = "pro"
        db.session.commit()

    elif etype in ("customer.subscription.updated", "customer.subscription.deleted"):
        stripe_sub_id = obj["id"]
        sub = Subscription.query.filter_by(stripe_subscription_id=stripe_sub_id).first()
        if not sub:
            return

        sub.status               = obj["status"]
        sub.current_period_start = datetime.fromtimestamp(obj["current_period_start"], tz=timezone.utc)
        sub.current_period_end   = datetime.fromtimestamp(obj["current_period_end"],   tz=timezone.utc)
        sub.cancel_at_period_end = obj.get("cancel_at_period_end", False)

        # Downgrade to free if canceled/past_due
        if obj["status"] in ("canceled", "unpaid"):
            sub.user.tier = "free"

        db.session.commit()

    elif etype == "invoice.payment_succeeded":
        txn = Transaction(
            user_id          = None,
            stripe_customer_id       = obj.get("customer"),
            stripe_invoice_id        = obj.get("id"),
            stripe_payment_intent_id = obj.get("payment_intent"),
            amount           = obj["amount_paid"] / 100,
            currency         = obj.get("currency", "usd"),
            product_type     = "subscription_monthly",
            status           = "succeeded",
            receipt_url      = obj.get("hosted_invoice_url"),
        )
        # Resolve user from customer id
        sub = Subscription.query.filter_by(stripe_customer_id=obj.get("customer")).first()
        if sub:
            txn.user_id = sub.user_id
            txn.plan    = sub.plan
            txn.product_type = f"subscription_{sub.plan}"
        db.session.add(txn)
        db.session.commit()

    elif etype == "invoice.payment_failed":
        sub = Subscription.query.filter_by(stripe_customer_id=obj.get("customer")).first()
        if sub:
            sub.status = "past_due"
            db.session.commit()
