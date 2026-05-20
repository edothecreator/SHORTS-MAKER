"""Stripe Payment & Billing System for Shorts Engine Studio.

Production Task 5: Complete payment and billing integration with Stripe.
Handles subscriptions, credits, trials, webhooks, and plan enforcement.

Sub-tasks covered:
  5.1  Stripe API key configuration
  5.2  Pricing tier definitions (Free, Pro, Business)
  5.3  Stripe Products and Prices
  5.4  Checkout session creation
  5.5  Customer Portal session
  5.6  Webhook handler (all events)
  5.7  Credit system (deduct per video)
  5.8  Enforce limits (block when exhausted)
  5.9  Upgrade prompt trigger
  5.10 Usage dashboard data
  5.11 Trial period (7 days Pro, no card)
  5.12 Annual billing (20% discount)
  5.13 Failed payment handling (3-day grace then downgrade)
"""
from __future__ import annotations

import os
import logging
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import stripe

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration — load from environment variables
# ---------------------------------------------------------------------------

# TODO: Set these in production environment (Stripe Dashboard → Developers → API Keys)
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# Stripe Price IDs — create these in Stripe Dashboard → Products
STRIPE_PRICE_PRO_MONTHLY = os.environ.get("STRIPE_PRICE_PRO_MONTHLY", "")
STRIPE_PRICE_PRO_ANNUAL = os.environ.get("STRIPE_PRICE_PRO_ANNUAL", "")
STRIPE_PRICE_BUSINESS_MONTHLY = os.environ.get("STRIPE_PRICE_BUSINESS_MONTHLY", "")
STRIPE_PRICE_BUSINESS_ANNUAL = os.environ.get("STRIPE_PRICE_BUSINESS_ANNUAL", "")

# Configure Stripe SDK
stripe.api_key = STRIPE_SECRET_KEY

# Base URL for redirects after checkout/portal
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:3000")



# ---------------------------------------------------------------------------
# 5.2 — Pricing Tier Definitions
# ---------------------------------------------------------------------------


class PlanTier(str, Enum):
    """Subscription plan tiers."""
    FREE = "free"
    PRO = "pro"
    BUSINESS = "business"


# Plan configuration: limits, features, and pricing
PLAN_CONFIG = {
    PlanTier.FREE: {
        "name": "Free",
        "monthly_credits": 3,          # 3 videos/month
        "max_resolution": "720p",
        "watermark": True,
        "priority_render": False,
        "api_access": False,
        "team_features": False,
        "price_monthly": 0,
        "price_annual": 0,
    },
    PlanTier.PRO: {
        "name": "Pro",
        "monthly_credits": 30,         # 30 videos/month
        "max_resolution": "1080p",
        "watermark": False,
        "priority_render": True,
        "api_access": False,
        "team_features": False,
        "price_monthly": 1500,         # $15.00 in cents
        "price_annual": 14400,         # $144.00/year (20% discount: $15*12*0.8)
    },
    PlanTier.BUSINESS: {
        "name": "Business",
        "monthly_credits": -1,         # -1 = unlimited
        "max_resolution": "4K",
        "watermark": False,
        "priority_render": True,
        "api_access": True,
        "team_features": True,
        "price_monthly": 3900,         # $39.00 in cents
        "price_annual": 37440,         # $374.40/year (20% discount: $39*12*0.8)
    },
}



# Map plan + billing period to Stripe Price IDs
PRICE_ID_MAP = {
    (PlanTier.PRO, "monthly"): STRIPE_PRICE_PRO_MONTHLY,
    (PlanTier.PRO, "annual"): STRIPE_PRICE_PRO_ANNUAL,
    (PlanTier.BUSINESS, "monthly"): STRIPE_PRICE_BUSINESS_MONTHLY,
    (PlanTier.BUSINESS, "annual"): STRIPE_PRICE_BUSINESS_ANNUAL,
}

# Grace period duration for failed payments (5.13)
GRACE_PERIOD_DAYS = 3

# Trial duration (5.11)
TRIAL_DURATION_DAYS = 7



# ---------------------------------------------------------------------------
# Database Helper (placeholder)
# ---------------------------------------------------------------------------
# In production, replace these with real asyncpg queries against PostgreSQL.
# The pattern follows auth.py — placeholder functions with comments showing
# what the real SQL would look like.


async def _db_get_user_subscription(user_id: str) -> Optional[dict]:
    """Fetch user's current subscription from database.

    Real query:
        SELECT s.*, u.credits_remaining, u.plan, u.trial_ends_at,
               u.grace_period_ends_at
        FROM subscriptions s
        JOIN users u ON u.id = s.user_id
        WHERE s.user_id = $1 AND s.status = 'active'
        ORDER BY s.created_at DESC LIMIT 1
    """
    # TODO: Replace with real database query using asyncpg connection pool
    # from backend.db.connection import get_pool
    # pool = await get_pool()
    # async with pool.acquire() as conn:
    #     row = await conn.fetchrow(query, user_id)
    #     return dict(row) if row else None
    logger.debug("_db_get_user_subscription called for user_id=%s", user_id)
    return None



async def _db_get_user(user_id: str) -> Optional[dict]:
    """Fetch user record from database.

    Real query:
        SELECT id, email, name, plan, credits_remaining, stripe_customer_id,
               trial_ends_at, grace_period_ends_at, created_at
        FROM users WHERE id = $1
    """
    # TODO: Replace with real database query
    logger.debug("_db_get_user called for user_id=%s", user_id)
    return None


async def _db_update_user_plan(
    user_id: str, plan: str, credits: int
) -> None:
    """Update user's plan and credit balance.

    Real query:
        UPDATE users
        SET plan = $2, credits_remaining = $3, updated_at = NOW()
        WHERE id = $1
    """
    # TODO: Replace with real database query
    logger.info("Updated user %s to plan=%s credits=%d", user_id, plan, credits)



async def _db_update_subscription(
    user_id: str,
    stripe_subscription_id: str,
    plan: str,
    status: str,
    current_period_end: Optional[datetime] = None,
) -> None:
    """Insert or update subscription record.

    Real query:
        INSERT INTO subscriptions (user_id, stripe_subscription_id, plan, status,
                                   current_period_end, created_at)
        VALUES ($1, $2, $3, $4, $5, NOW())
        ON CONFLICT (stripe_subscription_id)
        DO UPDATE SET plan = $3, status = $4, current_period_end = $5,
                      updated_at = NOW()
    """
    # TODO: Replace with real database query
    logger.info(
        "Subscription updated: user=%s sub_id=%s plan=%s status=%s",
        user_id, stripe_subscription_id, plan, status,
    )



async def _db_deduct_credit(user_id: str) -> int:
    """Deduct 1 credit from user and return remaining balance.

    Real query:
        UPDATE users
        SET credits_remaining = credits_remaining - 1, updated_at = NOW()
        WHERE id = $1 AND credits_remaining > 0
        RETURNING credits_remaining

    Also insert usage log:
        INSERT INTO usage_logs (user_id, action, credits_used, timestamp)
        VALUES ($1, 'video_render', 1, NOW())
    """
    # TODO: Replace with real database query (atomic decrement)
    logger.info("Deducted 1 credit for user %s", user_id)
    return 0


async def _db_get_credits(user_id: str) -> int:
    """Get remaining credits for user.

    Real query:
        SELECT credits_remaining FROM users WHERE id = $1
    """
    # TODO: Replace with real database query
    return 0



async def _db_set_grace_period(user_id: str, ends_at: datetime) -> None:
    """Set grace period end date for user with failed payment.

    Real query:
        UPDATE users
        SET grace_period_ends_at = $2, updated_at = NOW()
        WHERE id = $1
    """
    # TODO: Replace with real database query
    logger.info("Grace period set for user %s until %s", user_id, ends_at)


async def _db_set_trial(user_id: str, plan: str, ends_at: datetime, credits: int) -> None:
    """Activate trial for user.

    Real query:
        UPDATE users
        SET plan = $2, trial_ends_at = $3, credits_remaining = $4,
            updated_at = NOW()
        WHERE id = $1
    """
    # TODO: Replace with real database query
    logger.info("Trial started for user %s: plan=%s ends=%s", user_id, plan, ends_at)


async def _db_get_user_by_stripe_customer(customer_id: str) -> Optional[dict]:
    """Fetch user by their Stripe customer ID.

    Real query:
        SELECT * FROM users WHERE stripe_customer_id = $1
    """
    # TODO: Replace with real database query
    logger.debug("Looking up user by stripe_customer_id=%s", customer_id)
    return None



async def _db_set_stripe_customer_id(user_id: str, customer_id: str) -> None:
    """Store Stripe customer ID on user record.

    Real query:
        UPDATE users SET stripe_customer_id = $2, updated_at = NOW()
        WHERE id = $1
    """
    # TODO: Replace with real database query
    logger.info("Stored stripe_customer_id=%s for user %s", customer_id, user_id)


async def _db_log_usage(user_id: str, action: str, credits_used: int) -> None:
    """Log usage event for billing dashboard (5.10).

    Real query:
        INSERT INTO usage_logs (user_id, action, credits_used, timestamp)
        VALUES ($1, $2, $3, NOW())
    """
    # TODO: Replace with real database query
    logger.info("Usage log: user=%s action=%s credits=%d", user_id, action, credits_used)



# ---------------------------------------------------------------------------
# 5.4 — Create Checkout Session
# ---------------------------------------------------------------------------


async def create_checkout_session(
    user_id: str,
    plan: PlanTier,
    is_annual: bool = False,
) -> dict:
    """Create a Stripe Checkout session for subscribing to a plan.

    Args:
        user_id: Internal user ID.
        plan: Target plan tier (PRO or BUSINESS).
        is_annual: If True, use annual pricing (20% discount per 5.12).

    Returns:
        dict with 'checkout_url' for redirecting the user.

    Raises:
        ValueError: If plan is FREE or invalid.
        stripe.error.StripeError: On Stripe API failure.
    """
    if plan == PlanTier.FREE:
        raise ValueError("Cannot create checkout session for free plan.")

    billing_period = "annual" if is_annual else "monthly"
    price_id = PRICE_ID_MAP.get((plan, billing_period))

    if not price_id:
        raise ValueError(
            f"No Stripe Price ID configured for {plan.value}/{billing_period}. "
            "Set the corresponding environment variable."
        )

    # Get or create Stripe customer for this user
    user = await _db_get_user(user_id)
    customer_id = None
    if user and user.get("stripe_customer_id"):
        customer_id = user["stripe_customer_id"]


    # TODO: In production, this calls the real Stripe API
    # Create Stripe Checkout Session
    session_params = {
        "mode": "subscription",
        "payment_method_types": ["card"],
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": f"{APP_BASE_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{APP_BASE_URL}/billing/cancel",
        "metadata": {"user_id": user_id, "plan": plan.value},
        "subscription_data": {
            "metadata": {"user_id": user_id, "plan": plan.value},
        },
    }

    if customer_id:
        session_params["customer"] = customer_id
    else:
        # Let Stripe create a new customer; we'll store the ID via webhook
        session_params["customer_creation"] = "always"
        if user and user.get("email"):
            session_params["customer_email"] = user["email"]

    session = stripe.checkout.Session.create(**session_params)

    logger.info(
        "Checkout session created: user=%s plan=%s annual=%s session_id=%s",
        user_id, plan.value, is_annual, session.id,
    )

    return {
        "checkout_url": session.url,
        "session_id": session.id,
    }



# ---------------------------------------------------------------------------
# 5.5 — Customer Portal Session
# ---------------------------------------------------------------------------


async def create_customer_portal_session(user_id: str) -> dict:
    """Create a Stripe Customer Portal session for managing subscription.

    Allows users to:
      - Update payment method
      - Cancel subscription
      - View billing history
      - Change plan

    Args:
        user_id: Internal user ID.

    Returns:
        dict with 'portal_url' for redirecting the user.

    Raises:
        ValueError: If user has no Stripe customer ID.
        stripe.error.StripeError: On Stripe API failure.
    """
    user = await _db_get_user(user_id)

    if not user or not user.get("stripe_customer_id"):
        raise ValueError(
            "No Stripe customer found for this user. "
            "User must subscribe to a paid plan first."
        )

    # TODO: In production, this calls the real Stripe API
    session = stripe.billing_portal.Session.create(
        customer=user["stripe_customer_id"],
        return_url=f"{APP_BASE_URL}/billing",
    )

    logger.info("Portal session created for user %s", user_id)

    return {
        "portal_url": session.url,
        "session_id": session.id,
    }



# ---------------------------------------------------------------------------
# 5.6 — Webhook Handler
# ---------------------------------------------------------------------------


async def handle_webhook(payload: bytes, sig_header: str) -> dict:
    """Process incoming Stripe webhook events.

    Verifies the webhook signature, then dispatches to the appropriate
    handler based on event type.

    Handled events:
      - checkout.session.completed → activate subscription
      - invoice.paid → renew credits
      - invoice.payment_failed → notify user, set grace period
      - customer.subscription.deleted → downgrade to free

    Args:
        payload: Raw request body bytes from Stripe.
        sig_header: Value of the 'Stripe-Signature' header.

    Returns:
        dict with 'status' key indicating result.

    Raises:
        ValueError: If webhook signature verification fails.
    """
    if not STRIPE_WEBHOOK_SECRET:
        raise ValueError(
            "STRIPE_WEBHOOK_SECRET not configured. "
            "Cannot verify webhook signatures."
        )

    # Verify webhook signature to ensure it's from Stripe
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError as e:
        logger.error("Webhook signature verification failed: %s", e)
        raise ValueError("Invalid webhook signature") from e
    except Exception as e:
        logger.error("Webhook construction failed: %s", e)
        raise ValueError(f"Webhook error: {e}") from e


    event_type = event["type"]
    data = event["data"]["object"]

    logger.info("Webhook received: type=%s id=%s", event_type, event.get("id"))

    # Dispatch to appropriate handler
    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data)
    elif event_type == "invoice.paid":
        await _handle_invoice_paid(data)
    elif event_type == "invoice.payment_failed":
        await _handle_invoice_payment_failed(data)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(data)
    else:
        logger.debug("Unhandled webhook event type: %s", event_type)

    return {"status": "processed", "event_type": event_type}



async def _handle_checkout_completed(session: dict) -> None:
    """Handle checkout.session.completed — activate subscription.

    Called when a user successfully completes the Stripe Checkout flow.
    Creates/updates subscription record and grants plan credits.
    """
    user_id = session.get("metadata", {}).get("user_id")
    plan_value = session.get("metadata", {}).get("plan", "pro")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    if not user_id:
        logger.error("checkout.session.completed missing user_id in metadata")
        return

    plan = PlanTier(plan_value)
    credits = PLAN_CONFIG[plan]["monthly_credits"]

    # Store Stripe customer ID on user record
    if customer_id:
        await _db_set_stripe_customer_id(user_id, customer_id)

    # Activate the subscription
    await _db_update_user_plan(user_id, plan.value, credits)

    if subscription_id:
        await _db_update_subscription(
            user_id=user_id,
            stripe_subscription_id=subscription_id,
            plan=plan.value,
            status="active",
        )

    logger.info(
        "Subscription activated: user=%s plan=%s credits=%d",
        user_id, plan.value, credits,
    )



async def _handle_invoice_paid(invoice: dict) -> None:
    """Handle invoice.paid — renew monthly credits.

    Called on each successful billing cycle. Resets the user's credits
    to their plan's monthly allocation.
    """
    customer_id = invoice.get("customer")
    subscription_id = invoice.get("subscription")

    if not customer_id:
        logger.warning("invoice.paid missing customer ID")
        return

    user = await _db_get_user_by_stripe_customer(customer_id)
    if not user:
        logger.warning("invoice.paid: no user found for customer %s", customer_id)
        return

    user_id = user["id"]
    plan = PlanTier(user.get("plan", "pro"))
    credits = PLAN_CONFIG[plan]["monthly_credits"]

    # Reset credits to full monthly allocation
    await _db_update_user_plan(user_id, plan.value, credits)

    # Clear any grace period that was set
    await _db_set_grace_period(user_id, datetime.min.replace(tzinfo=timezone.utc))

    # Log the renewal
    await _db_log_usage(user_id, "credits_renewed", 0)

    logger.info(
        "Credits renewed: user=%s plan=%s credits=%d",
        user_id, plan.value, credits,
    )



async def _handle_invoice_payment_failed(invoice: dict) -> None:
    """Handle invoice.payment_failed — notify user and start grace period.

    Sets a 3-day grace period. If payment is not resolved within that
    window, the user will be downgraded to Free tier (handled by
    handle_failed_payment cron job or subsequent webhook).
    """
    customer_id = invoice.get("customer")

    if not customer_id:
        logger.warning("invoice.payment_failed missing customer ID")
        return

    user = await _db_get_user_by_stripe_customer(customer_id)
    if not user:
        logger.warning(
            "invoice.payment_failed: no user for customer %s", customer_id
        )
        return

    user_id = user["id"]
    grace_ends = datetime.now(timezone.utc) + timedelta(days=GRACE_PERIOD_DAYS)

    # Set grace period
    await _db_set_grace_period(user_id, grace_ends)

    # Log the failed payment event
    await _db_log_usage(user_id, "payment_failed", 0)

    # TODO: Send email notification to user about failed payment
    # await send_email(
    #     to=user["email"],
    #     subject="Payment failed — please update your card",
    #     template="payment_failed",
    #     context={"grace_period_end": grace_ends.isoformat(), "portal_url": ...}
    # )

    logger.warning(
        "Payment failed for user %s. Grace period until %s",
        user_id, grace_ends.isoformat(),
    )



async def _handle_subscription_deleted(subscription: dict) -> None:
    """Handle customer.subscription.deleted — downgrade to Free.

    Called when a subscription is canceled (either by user or due to
    repeated payment failures). Downgrades user to Free tier with
    limited credits.
    """
    customer_id = subscription.get("customer")
    subscription_id = subscription.get("id")

    if not customer_id:
        logger.warning("subscription.deleted missing customer ID")
        return

    user = await _db_get_user_by_stripe_customer(customer_id)
    if not user:
        logger.warning(
            "subscription.deleted: no user for customer %s", customer_id
        )
        return

    user_id = user["id"]
    free_credits = PLAN_CONFIG[PlanTier.FREE]["monthly_credits"]

    # Downgrade to free plan
    await _db_update_user_plan(user_id, PlanTier.FREE.value, free_credits)

    if subscription_id:
        await _db_update_subscription(
            user_id=user_id,
            stripe_subscription_id=subscription_id,
            plan=PlanTier.FREE.value,
            status="canceled",
        )

    # Log the downgrade
    await _db_log_usage(user_id, "subscription_canceled", 0)

    logger.info("User %s downgraded to Free tier", user_id)



# ---------------------------------------------------------------------------
# 5.7 — Credit System: Deduct Per Video
# ---------------------------------------------------------------------------


class CreditExhaustedError(Exception):
    """Raised when user has no credits remaining."""

    def __init__(self, user_id: str, plan: str):
        self.user_id = user_id
        self.plan = plan
        super().__init__(
            f"Credits exhausted for user {user_id} on {plan} plan. "
            "Please upgrade your plan or wait for monthly renewal."
        )


async def deduct_credit(user_id: str) -> dict:
    """Deduct 1 credit from user's balance for processing a video.

    This should be called when a video render job starts. It atomically
    decrements the credit count and raises if the user has none left.

    Args:
        user_id: Internal user ID.

    Returns:
        dict with 'credits_remaining' after deduction.

    Raises:
        CreditExhaustedError: If user has 0 credits remaining.
    """
    user = await _db_get_user(user_id)

    if not user:
        raise ValueError(f"User {user_id} not found")

    plan = PlanTier(user.get("plan", "free"))
    credits = user.get("credits_remaining", 0)

    # Business plan has unlimited credits (-1 means unlimited)
    if PLAN_CONFIG[plan]["monthly_credits"] == -1:
        await _db_log_usage(user_id, "video_render", 1)
        return {"credits_remaining": -1, "unlimited": True}

    if credits <= 0:
        raise CreditExhaustedError(user_id, plan.value)

    # Atomic deduction in database
    remaining = await _db_deduct_credit(user_id)
    await _db_log_usage(user_id, "video_render", 1)

    logger.info(
        "Credit deducted: user=%s remaining=%d plan=%s",
        user_id, remaining, plan.value,
    )

    return {"credits_remaining": remaining, "unlimited": False}



# ---------------------------------------------------------------------------
# 5.7 (cont) — Check Credits
# ---------------------------------------------------------------------------


async def check_credits(user_id: str) -> dict:
    """Return the user's current credit balance and plan info.

    Used by the frontend to display remaining credits and usage dashboard.

    Args:
        user_id: Internal user ID.

    Returns:
        dict with credit info: remaining, total, plan, unlimited flag.
    """
    user = await _db_get_user(user_id)

    if not user:
        # Default to free plan for unknown users
        return {
            "credits_remaining": PLAN_CONFIG[PlanTier.FREE]["monthly_credits"],
            "credits_total": PLAN_CONFIG[PlanTier.FREE]["monthly_credits"],
            "plan": PlanTier.FREE.value,
            "unlimited": False,
        }

    plan = PlanTier(user.get("plan", "free"))
    plan_config = PLAN_CONFIG[plan]
    is_unlimited = plan_config["monthly_credits"] == -1

    return {
        "credits_remaining": -1 if is_unlimited else user.get("credits_remaining", 0),
        "credits_total": plan_config["monthly_credits"],
        "plan": plan.value,
        "unlimited": is_unlimited,
        "max_resolution": plan_config["max_resolution"],
        "watermark": plan_config["watermark"],
        "priority_render": plan_config["priority_render"],
    }



# ---------------------------------------------------------------------------
# 5.8 — Enforce Limits: Block Processing When Credits Exhausted
# ---------------------------------------------------------------------------


async def enforce_limits(user_id: str) -> dict:
    """Check if user can process a video, enforcing plan limits.

    This is a gate function called before starting any render job.
    It checks credits, grace periods, and trial status.

    Args:
        user_id: Internal user ID.

    Returns:
        dict with 'allowed' bool and reason if blocked.

    Raises:
        CreditExhaustedError: If user cannot process (for hard enforcement).
    """
    user = await _db_get_user(user_id)

    if not user:
        # Unknown user gets free tier defaults
        return {
            "allowed": True,
            "plan": PlanTier.FREE.value,
            "reason": None,
        }

    plan = PlanTier(user.get("plan", "free"))
    plan_config = PLAN_CONFIG[plan]

    # Business plan: unlimited, always allowed
    if plan_config["monthly_credits"] == -1:
        return {"allowed": True, "plan": plan.value, "reason": None}

    # Check if in grace period (failed payment but still has access)
    grace_ends = user.get("grace_period_ends_at")
    if grace_ends and isinstance(grace_ends, datetime):
        if datetime.now(timezone.utc) > grace_ends:
            # Grace period expired — block access
            raise CreditExhaustedError(user_id, plan.value)


    # Check if trial has expired
    trial_ends = user.get("trial_ends_at")
    if trial_ends and isinstance(trial_ends, datetime):
        if datetime.now(timezone.utc) > trial_ends:
            # Trial expired and user hasn't subscribed — downgrade to free
            free_credits = PLAN_CONFIG[PlanTier.FREE]["monthly_credits"]
            await _db_update_user_plan(user_id, PlanTier.FREE.value, free_credits)
            plan = PlanTier.FREE
            plan_config = PLAN_CONFIG[plan]

    # Check credit balance
    credits = user.get("credits_remaining", 0)
    if credits <= 0:
        return {
            "allowed": False,
            "plan": plan.value,
            "reason": "credits_exhausted",
            "upgrade_url": f"{APP_BASE_URL}/billing/upgrade",
            "message": (
                f"You've used all {plan_config['monthly_credits']} videos "
                f"for this month on the {plan_config['name']} plan. "
                "Upgrade for more credits or wait for monthly renewal."
            ),
        }

    return {
        "allowed": True,
        "plan": plan.value,
        "credits_remaining": credits,
        "reason": None,
    }



# ---------------------------------------------------------------------------
# 5.11 — Trial Period (7 days Pro free, no card required)
# ---------------------------------------------------------------------------


async def start_trial(user_id: str) -> dict:
    """Start a 7-day Pro trial for a new user (no card required).

    Grants Pro-level features and credits for 7 days. After trial ends,
    user is automatically downgraded to Free unless they subscribe.

    Args:
        user_id: Internal user ID.

    Returns:
        dict with trial info (plan, credits, expiry).

    Raises:
        ValueError: If user already has an active subscription or trial.
    """
    user = await _db_get_user(user_id)

    # Check if user already has a paid plan or active trial
    if user:
        current_plan = user.get("plan", "free")
        trial_ends = user.get("trial_ends_at")

        if current_plan != "free":
            raise ValueError(
                f"User already on {current_plan} plan. Trial not applicable."
            )

        if trial_ends and isinstance(trial_ends, datetime):
            if datetime.now(timezone.utc) < trial_ends:
                raise ValueError("User already has an active trial.")

    trial_end = datetime.now(timezone.utc) + timedelta(days=TRIAL_DURATION_DAYS)
    trial_credits = PLAN_CONFIG[PlanTier.PRO]["monthly_credits"]

    # Activate trial
    await _db_set_trial(user_id, PlanTier.PRO.value, trial_end, trial_credits)

    # Log trial start
    await _db_log_usage(user_id, "trial_started", 0)

    logger.info(
        "Trial started: user=%s plan=Pro expires=%s credits=%d",
        user_id, trial_end.isoformat(), trial_credits,
    )

    return {
        "plan": PlanTier.PRO.value,
        "trial": True,
        "trial_ends_at": trial_end.isoformat(),
        "credits_remaining": trial_credits,
        "features": PLAN_CONFIG[PlanTier.PRO],
    }



# ---------------------------------------------------------------------------
# 5.13 — Handle Failed Payments (3-day grace then downgrade)
# ---------------------------------------------------------------------------


async def handle_failed_payment(user_id: str) -> dict:
    """Handle failed payment with 3-day grace period then downgrade.

    This function manages the full failed payment lifecycle:
    1. First call: sets a 3-day grace period (user keeps access)
    2. After grace period expires: downgrades to Free tier

    Should be called by:
    - The webhook handler (on invoice.payment_failed)
    - A scheduled cron job that checks for expired grace periods

    Args:
        user_id: Internal user ID.

    Returns:
        dict with current status (grace_period or downgraded).
    """
    user = await _db_get_user(user_id)

    if not user:
        raise ValueError(f"User {user_id} not found")

    grace_ends = user.get("grace_period_ends_at")

    # If no grace period set yet, start one
    if not grace_ends or not isinstance(grace_ends, datetime):
        grace_end = datetime.now(timezone.utc) + timedelta(days=GRACE_PERIOD_DAYS)
        await _db_set_grace_period(user_id, grace_end)

        logger.info(
            "Grace period started for user %s (ends %s)",
            user_id, grace_end.isoformat(),
        )

        return {
            "status": "grace_period",
            "grace_period_ends_at": grace_end.isoformat(),
            "days_remaining": GRACE_PERIOD_DAYS,
            "message": (
                "Your payment failed. Please update your payment method "
                f"within {GRACE_PERIOD_DAYS} days to keep your plan."
            ),
        }


    # Grace period exists — check if expired
    if datetime.now(timezone.utc) > grace_ends:
        # Grace period expired: downgrade to free
        free_credits = PLAN_CONFIG[PlanTier.FREE]["monthly_credits"]
        await _db_update_user_plan(user_id, PlanTier.FREE.value, free_credits)

        # Clear grace period
        await _db_set_grace_period(
            user_id, datetime.min.replace(tzinfo=timezone.utc)
        )

        # Log the downgrade
        await _db_log_usage(user_id, "downgraded_payment_failed", 0)

        logger.warning(
            "User %s downgraded to Free: grace period expired after payment failure",
            user_id,
        )

        return {
            "status": "downgraded",
            "plan": PlanTier.FREE.value,
            "credits_remaining": free_credits,
            "message": (
                "Your subscription has been canceled due to payment failure. "
                "You've been downgraded to the Free plan. "
                "Subscribe again to restore your plan."
            ),
        }

    # Grace period still active
    days_remaining = (grace_ends - datetime.now(timezone.utc)).days
    return {
        "status": "grace_period",
        "grace_period_ends_at": grace_ends.isoformat(),
        "days_remaining": max(0, days_remaining),
        "message": (
            f"Payment failed. {max(0, days_remaining)} days remaining "
            "to update your payment method before downgrade."
        ),
    }



# ---------------------------------------------------------------------------
# 5.10 — Usage Dashboard Data
# ---------------------------------------------------------------------------


async def get_usage_dashboard(user_id: str) -> dict:
    """Get usage data for the billing/usage dashboard.

    Returns current credits, plan info, usage history this month,
    and subscription status. Used by the frontend to render the
    usage dashboard (task 5.10).

    Args:
        user_id: Internal user ID.

    Returns:
        dict with comprehensive usage and billing information.
    """
    credit_info = await check_credits(user_id)
    user = await _db_get_user(user_id)

    # Calculate usage percentage
    total = credit_info["credits_total"]
    remaining = credit_info["credits_remaining"]
    if credit_info["unlimited"]:
        usage_percent = 0
    elif total > 0:
        used = total - remaining
        usage_percent = round((used / total) * 100, 1)
    else:
        usage_percent = 100

    dashboard = {
        "plan": credit_info["plan"],
        "plan_name": PLAN_CONFIG[PlanTier(credit_info["plan"])]["name"],
        "credits_remaining": remaining,
        "credits_total": total,
        "unlimited": credit_info["unlimited"],
        "usage_percent": usage_percent,
        "max_resolution": credit_info.get("max_resolution", "720p"),
        "watermark": credit_info.get("watermark", True),
        "priority_render": credit_info.get("priority_render", False),
        # TODO: Add usage history from usage_logs table
        # "usage_history": await _db_get_usage_history(user_id, days=30),
        "usage_history": [],
    }

    # Add subscription info if user exists
    if user:
        dashboard["trial_active"] = bool(
            user.get("trial_ends_at")
            and isinstance(user.get("trial_ends_at"), datetime)
            and datetime.now(timezone.utc) < user["trial_ends_at"]
        )
        dashboard["grace_period_active"] = bool(
            user.get("grace_period_ends_at")
            and isinstance(user.get("grace_period_ends_at"), datetime)
            and datetime.now(timezone.utc) < user["grace_period_ends_at"]
        )
    else:
        dashboard["trial_active"] = False
        dashboard["grace_period_active"] = False

    return dashboard



# ---------------------------------------------------------------------------
# 5.9 — Upgrade Prompt (helper for frontend)
# ---------------------------------------------------------------------------


def get_upgrade_prompt(current_plan: str) -> dict:
    """Generate upgrade prompt data when user hits free tier limit.

    Used by the frontend to show an upgrade modal/banner (task 5.9).

    Args:
        current_plan: User's current plan tier string.

    Returns:
        dict with upgrade options and messaging.
    """
    plan = PlanTier(current_plan)

    if plan == PlanTier.BUSINESS:
        return {"show_upgrade": False, "message": "You're on the top plan!"}

    if plan == PlanTier.PRO:
        target = PlanTier.BUSINESS
        return {
            "show_upgrade": True,
            "target_plan": target.value,
            "target_name": PLAN_CONFIG[target]["name"],
            "price_monthly": PLAN_CONFIG[target]["price_monthly"] / 100,
            "price_annual_monthly": round(
                PLAN_CONFIG[target]["price_annual"] / 12 / 100, 2
            ),
            "features": [
                "Unlimited videos per month",
                "4K resolution output",
                "API access for automation",
                "Team collaboration features",
            ],
            "message": "Upgrade to Business for unlimited videos and 4K output.",
        }

    # Free plan — suggest Pro
    target = PlanTier.PRO
    return {
        "show_upgrade": True,
        "target_plan": target.value,
        "target_name": PLAN_CONFIG[target]["name"],
        "price_monthly": PLAN_CONFIG[target]["price_monthly"] / 100,
        "price_annual_monthly": round(
            PLAN_CONFIG[target]["price_annual"] / 12 / 100, 2
        ),
        "annual_discount_percent": 20,
        "features": [
            "30 videos per month (10x more)",
            "1080p HD resolution",
            "No watermark on output",
            "Priority rendering queue",
        ],
        "message": (
            "You've used all your free credits this month! "
            "Upgrade to Pro for 30 videos/month and HD quality."
        ),
    }



# ---------------------------------------------------------------------------
# 5.12 — Annual Billing (20% discount)
# ---------------------------------------------------------------------------


def get_pricing_table() -> dict:
    """Generate pricing table data for the frontend pricing page.

    Shows monthly and annual pricing for all plans, with the 20%
    annual discount clearly displayed.

    Returns:
        dict with all plan pricing and feature comparisons.
    """
    return {
        "plans": [
            {
                "id": PlanTier.FREE.value,
                "name": "Free",
                "description": "Get started with basic video shorts",
                "price_monthly": 0,
                "price_annual": 0,
                "price_annual_monthly_equivalent": 0,
                "annual_savings": 0,
                "features": {
                    "videos_per_month": 3,
                    "max_resolution": "720p",
                    "watermark": True,
                    "priority_render": False,
                    "api_access": False,
                    "team_features": False,
                },
                "cta": "Current Plan" if True else "Get Started",
            },
            {
                "id": PlanTier.PRO.value,
                "name": "Pro",
                "description": "For content creators who need more",
                "price_monthly": 15.00,
                "price_annual": 144.00,
                "price_annual_monthly_equivalent": 12.00,
                "annual_savings": 36.00,  # $15*12 - $144 = $36 saved
                "annual_discount_percent": 20,
                "features": {
                    "videos_per_month": 30,
                    "max_resolution": "1080p",
                    "watermark": False,
                    "priority_render": True,
                    "api_access": False,
                    "team_features": False,
                },
                "popular": True,
                "cta": "Start Free Trial",
            },
            {
                "id": PlanTier.BUSINESS.value,
                "name": "Business",
                "description": "For teams and agencies",
                "price_monthly": 39.00,
                "price_annual": 374.40,
                "price_annual_monthly_equivalent": 31.20,
                "annual_savings": 93.60,  # $39*12 - $374.40 = $93.60 saved
                "annual_discount_percent": 20,
                "features": {
                    "videos_per_month": "Unlimited",
                    "max_resolution": "4K",
                    "watermark": False,
                    "priority_render": True,
                    "api_access": True,
                    "team_features": True,
                },
                "cta": "Start Free Trial",
            },
        ],
        "faq": [
            {
                "q": "Can I switch plans anytime?",
                "a": "Yes! Upgrade or downgrade at any time. Changes take effect immediately.",
            },
            {
                "q": "What happens when I run out of credits?",
                "a": "You'll be prompted to upgrade. Credits reset monthly on your billing date.",
            },
            {
                "q": "Is there a free trial?",
                "a": "Yes! Get 7 days of Pro features free, no credit card required.",
            },
            {
                "q": "Can I cancel anytime?",
                "a": "Absolutely. Cancel from the billing portal and you'll keep access until the end of your billing period.",
            },
        ],
    }



# ---------------------------------------------------------------------------
# FastAPI Route Helpers
# ---------------------------------------------------------------------------
# These are meant to be integrated into main.py or a dedicated billing router.


def get_plan_features(plan: str) -> dict:
    """Get feature set for a given plan tier.

    Args:
        plan: Plan tier string ('free', 'pro', 'business').

    Returns:
        dict of plan features and limits.
    """
    try:
        tier = PlanTier(plan)
    except ValueError:
        tier = PlanTier.FREE

    return PLAN_CONFIG[tier]


def is_feature_allowed(plan: str, feature: str) -> bool:
    """Check if a specific feature is available on the user's plan.

    Args:
        plan: Plan tier string.
        feature: Feature key (e.g., 'api_access', 'priority_render').

    Returns:
        bool indicating if feature is available.
    """
    features = get_plan_features(plan)
    return bool(features.get(feature, False))


def get_max_resolution(plan: str) -> str:
    """Get maximum allowed resolution for a plan.

    Args:
        plan: Plan tier string.

    Returns:
        Resolution string ('720p', '1080p', or '4K').
    """
    features = get_plan_features(plan)
    return features.get("max_resolution", "720p")


def should_add_watermark(plan: str) -> bool:
    """Check if watermark should be applied for this plan.

    Args:
        plan: Plan tier string.

    Returns:
        True if watermark should be added (Free tier only).
    """
    features = get_plan_features(plan)
    return features.get("watermark", True)
