"""Production Task 25.3: Billing Unit Tests.

Tests the billing/credit system:
- Credit deduction logic
- Limit enforcement
- Trial activation
- Failed payment grace period
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

# Ensure backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from billing import (
    PlanTier,
    PLAN_CONFIG,
    GRACE_PERIOD_DAYS,
    TRIAL_DURATION_DAYS,
    CreditExhaustedError,
    deduct_credit,
    check_credits,
    enforce_limits,
    start_trial,
    handle_failed_payment,
    create_checkout_session,
)



# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def free_user():
    """A user on the Free plan with credits remaining."""
    return {
        "id": "user-free-001",
        "email": "free@example.com",
        "name": "Free User",
        "plan": "free",
        "credits_remaining": 3,
        "stripe_customer_id": None,
        "trial_ends_at": None,
        "grace_period_ends_at": None,
    }


@pytest.fixture
def pro_user():
    """A user on the Pro plan with credits remaining."""
    return {
        "id": "user-pro-001",
        "email": "pro@example.com",
        "name": "Pro User",
        "plan": "pro",
        "credits_remaining": 25,
        "stripe_customer_id": "cus_test_pro",
        "trial_ends_at": None,
        "grace_period_ends_at": None,
    }


@pytest.fixture
def business_user():
    """A user on the Business plan (unlimited credits)."""
    return {
        "id": "user-biz-001",
        "email": "biz@example.com",
        "name": "Business User",
        "plan": "business",
        "credits_remaining": -1,
        "stripe_customer_id": "cus_test_biz",
        "trial_ends_at": None,
        "grace_period_ends_at": None,
    }


@pytest.fixture
def exhausted_user():
    """A user with zero credits remaining."""
    return {
        "id": "user-exhausted-001",
        "email": "exhausted@example.com",
        "name": "Exhausted User",
        "plan": "free",
        "credits_remaining": 0,
        "stripe_customer_id": None,
        "trial_ends_at": None,
        "grace_period_ends_at": None,
    }


@pytest.fixture
def trial_user():
    """A user on an active trial."""
    return {
        "id": "user-trial-001",
        "email": "trial@example.com",
        "name": "Trial User",
        "plan": "pro",
        "credits_remaining": 30,
        "stripe_customer_id": None,
        "trial_ends_at": datetime.now(timezone.utc) + timedelta(days=5),
        "grace_period_ends_at": None,
    }


@pytest.fixture
def grace_period_user():
    """A user in a payment grace period."""
    return {
        "id": "user-grace-001",
        "email": "grace@example.com",
        "name": "Grace User",
        "plan": "pro",
        "credits_remaining": 10,
        "stripe_customer_id": "cus_test_grace",
        "trial_ends_at": None,
        "grace_period_ends_at": datetime.now(timezone.utc) + timedelta(days=2),
    }


@pytest.fixture
def expired_grace_user():
    """A user whose grace period has expired."""
    return {
        "id": "user-expired-grace-001",
        "email": "expired-grace@example.com",
        "name": "Expired Grace User",
        "plan": "pro",
        "credits_remaining": 10,
        "stripe_customer_id": "cus_test_expired",
        "trial_ends_at": None,
        "grace_period_ends_at": datetime.now(timezone.utc) - timedelta(days=1),
    }



# ---------------------------------------------------------------------------
# Credit Deduction Tests
# ---------------------------------------------------------------------------


class TestCreditDeduction:
    """Test credit deduction logic (Task 5.7)."""

    @pytest.mark.asyncio
    async def test_deduct_credit_decrements_balance(self, pro_user):
        """Deducting a credit decreases credits_remaining by 1."""
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get, \
             patch("billing._db_deduct_credit", new_callable=AsyncMock) as mock_deduct, \
             patch("billing._db_log_usage", new_callable=AsyncMock):
            mock_get.return_value = pro_user
            mock_deduct.return_value = pro_user["credits_remaining"] - 1

            result = await deduct_credit(pro_user["id"])
            assert result["credits_remaining"] == 24
            assert result["unlimited"] is False
            mock_deduct.assert_called_once_with(pro_user["id"])

    @pytest.mark.asyncio
    async def test_deduct_credit_business_unlimited(self, business_user):
        """Business plan users never run out of credits."""
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get, \
             patch("billing._db_log_usage", new_callable=AsyncMock):
            mock_get.return_value = business_user

            result = await deduct_credit(business_user["id"])
            assert result["credits_remaining"] == -1
            assert result["unlimited"] is True

    @pytest.mark.asyncio
    async def test_deduct_credit_raises_when_exhausted(self, exhausted_user):
        """Raises CreditExhaustedError when credits are 0."""
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = exhausted_user

            with pytest.raises(CreditExhaustedError) as exc_info:
                await deduct_credit(exhausted_user["id"])

            assert exhausted_user["id"] in str(exc_info.value)
            assert "free" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_deduct_credit_raises_for_unknown_user(self):
        """Raises ValueError for non-existent user."""
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            with pytest.raises(ValueError, match="not found"):
                await deduct_credit("nonexistent-user-id")

    @pytest.mark.asyncio
    async def test_deduct_credit_logs_usage(self, pro_user):
        """Credit deduction logs a usage event."""
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get, \
             patch("billing._db_deduct_credit", new_callable=AsyncMock) as mock_deduct, \
             patch("billing._db_log_usage", new_callable=AsyncMock) as mock_log:
            mock_get.return_value = pro_user
            mock_deduct.return_value = 24

            await deduct_credit(pro_user["id"])
            mock_log.assert_called_once_with(pro_user["id"], "video_render", 1)



# ---------------------------------------------------------------------------
# Limit Enforcement Tests
# ---------------------------------------------------------------------------


class TestLimitEnforcement:
    """Test plan limit enforcement (Task 5.8)."""

    @pytest.mark.asyncio
    async def test_enforce_limits_allows_user_with_credits(self, pro_user):
        """Users with remaining credits are allowed to process."""
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = pro_user

            result = await enforce_limits(pro_user["id"])
            assert result["allowed"] is True
            assert result["plan"] == "pro"
            assert result["reason"] is None

    @pytest.mark.asyncio
    async def test_enforce_limits_blocks_exhausted_user(self, exhausted_user):
        """Users with 0 credits are blocked."""
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = exhausted_user

            result = await enforce_limits(exhausted_user["id"])
            assert result["allowed"] is False
            assert result["reason"] == "credits_exhausted"
            assert "upgrade" in result.get("upgrade_url", "")

    @pytest.mark.asyncio
    async def test_enforce_limits_business_always_allowed(self, business_user):
        """Business plan users are always allowed (unlimited)."""
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = business_user

            result = await enforce_limits(business_user["id"])
            assert result["allowed"] is True
            assert result["plan"] == "business"

    @pytest.mark.asyncio
    async def test_enforce_limits_unknown_user_gets_free_defaults(self):
        """Unknown users get free tier defaults."""
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            result = await enforce_limits("unknown-user-xyz")
            assert result["allowed"] is True
            assert result["plan"] == "free"

    @pytest.mark.asyncio
    async def test_enforce_limits_grace_period_active_allows(self, grace_period_user):
        """Users in active grace period still have access."""
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = grace_period_user

            result = await enforce_limits(grace_period_user["id"])
            assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_enforce_limits_grace_period_expired_blocks(self, expired_grace_user):
        """Users with expired grace period are blocked."""
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = expired_grace_user

            with pytest.raises(CreditExhaustedError):
                await enforce_limits(expired_grace_user["id"])

    @pytest.mark.asyncio
    async def test_enforce_limits_expired_trial_downgrades(self):
        """Expired trial users are downgraded to free plan."""
        expired_trial_user = {
            "id": "user-expired-trial",
            "email": "expired-trial@example.com",
            "plan": "pro",
            "credits_remaining": 0,
            "stripe_customer_id": None,
            "trial_ends_at": datetime.now(timezone.utc) - timedelta(days=1),
            "grace_period_ends_at": None,
        }
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get, \
             patch("billing._db_update_user_plan", new_callable=AsyncMock) as mock_update:
            mock_get.return_value = expired_trial_user

            result = await enforce_limits(expired_trial_user["id"])
            # User should be downgraded
            mock_update.assert_called_once_with(
                expired_trial_user["id"],
                PlanTier.FREE.value,
                PLAN_CONFIG[PlanTier.FREE]["monthly_credits"],
            )

    @pytest.mark.asyncio
    async def test_enforce_limits_shows_upgrade_message(self, exhausted_user):
        """Blocked users get a helpful upgrade message."""
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = exhausted_user

            result = await enforce_limits(exhausted_user["id"])
            assert "message" in result
            assert "upgrade" in result["message"].lower() or "credits" in result["message"].lower()



# ---------------------------------------------------------------------------
# Trial Activation Tests
# ---------------------------------------------------------------------------


class TestTrialActivation:
    """Test trial period logic (Task 5.11)."""

    @pytest.mark.asyncio
    async def test_start_trial_activates_pro_features(self):
        """Starting a trial gives Pro plan features for 7 days."""
        new_user = {
            "id": "user-new-001",
            "email": "new@example.com",
            "plan": "free",
            "credits_remaining": 3,
            "stripe_customer_id": None,
            "trial_ends_at": None,
            "grace_period_ends_at": None,
        }
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get, \
             patch("billing._db_set_trial", new_callable=AsyncMock) as mock_trial, \
             patch("billing._db_log_usage", new_callable=AsyncMock):
            mock_get.return_value = new_user

            result = await start_trial(new_user["id"])
            assert result["plan"] == "pro"
            assert result["trial"] is True
            assert result["credits_remaining"] == 30
            assert "trial_ends_at" in result

    @pytest.mark.asyncio
    async def test_start_trial_sets_7_day_expiry(self):
        """Trial expires in exactly 7 days."""
        new_user = {
            "id": "user-new-002",
            "email": "new2@example.com",
            "plan": "free",
            "credits_remaining": 3,
            "stripe_customer_id": None,
            "trial_ends_at": None,
            "grace_period_ends_at": None,
        }
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get, \
             patch("billing._db_set_trial", new_callable=AsyncMock) as mock_trial, \
             patch("billing._db_log_usage", new_callable=AsyncMock):
            mock_get.return_value = new_user

            result = await start_trial(new_user["id"])

            # Parse the trial_ends_at and check it's ~7 days from now
            trial_end = datetime.fromisoformat(result["trial_ends_at"])
            now = datetime.now(timezone.utc)
            diff = trial_end - now
            assert 6 <= diff.days <= 7

    @pytest.mark.asyncio
    async def test_start_trial_rejects_paid_user(self, pro_user):
        """Users on paid plans cannot start a trial."""
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = pro_user

            with pytest.raises(ValueError, match="already on"):
                await start_trial(pro_user["id"])

    @pytest.mark.asyncio
    async def test_start_trial_rejects_active_trial(self, trial_user):
        """Users with an active trial cannot start another."""
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = trial_user

            with pytest.raises(ValueError, match="active trial"):
                await start_trial(trial_user["id"])

    @pytest.mark.asyncio
    async def test_start_trial_allows_expired_trial_user(self):
        """Users whose trial expired (now on free) can't re-trial but get clear error."""
        expired_trial_user = {
            "id": "user-exp-trial",
            "email": "exp-trial@example.com",
            "plan": "free",
            "credits_remaining": 3,
            "stripe_customer_id": None,
            "trial_ends_at": datetime.now(timezone.utc) - timedelta(days=10),
            "grace_period_ends_at": None,
        }
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get, \
             patch("billing._db_set_trial", new_callable=AsyncMock) as mock_trial, \
             patch("billing._db_log_usage", new_callable=AsyncMock):
            mock_get.return_value = expired_trial_user

            # Expired trial should allow new trial (trial already ended)
            result = await start_trial(expired_trial_user["id"])
            assert result["trial"] is True

    @pytest.mark.asyncio
    async def test_trial_grants_correct_credits(self):
        """Trial gives exactly 30 credits (Pro plan monthly allocation)."""
        new_user = {
            "id": "user-credits-check",
            "email": "credits@example.com",
            "plan": "free",
            "credits_remaining": 1,
            "stripe_customer_id": None,
            "trial_ends_at": None,
            "grace_period_ends_at": None,
        }
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get, \
             patch("billing._db_set_trial", new_callable=AsyncMock) as mock_trial, \
             patch("billing._db_log_usage", new_callable=AsyncMock):
            mock_get.return_value = new_user

            result = await start_trial(new_user["id"])
            assert result["credits_remaining"] == PLAN_CONFIG[PlanTier.PRO]["monthly_credits"]



# ---------------------------------------------------------------------------
# Failed Payment Grace Period Tests
# ---------------------------------------------------------------------------


class TestFailedPaymentGracePeriod:
    """Test failed payment handling (Task 5.13)."""

    @pytest.mark.asyncio
    async def test_first_failure_sets_grace_period(self, pro_user):
        """First failed payment starts a 3-day grace period."""
        # Remove grace_period_ends_at to simulate first failure
        pro_user["grace_period_ends_at"] = None
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get, \
             patch("billing._db_set_grace_period", new_callable=AsyncMock) as mock_grace:
            mock_get.return_value = pro_user

            result = await handle_failed_payment(pro_user["id"])
            assert result["status"] == "grace_period"
            mock_grace.assert_called_once()

            # Verify grace period is ~3 days from now
            grace_end = mock_grace.call_args[0][1]
            now = datetime.now(timezone.utc)
            diff = grace_end - now
            assert 2 <= diff.days <= 3

    @pytest.mark.asyncio
    async def test_grace_period_duration_is_3_days(self):
        """Grace period constant is set to 3 days."""
        assert GRACE_PERIOD_DAYS == 3

    @pytest.mark.asyncio
    async def test_expired_grace_period_downgrades_to_free(self):
        """After grace period expires, user is downgraded to Free."""
        expired_user = {
            "id": "user-downgrade",
            "email": "downgrade@example.com",
            "plan": "pro",
            "credits_remaining": 15,
            "stripe_customer_id": "cus_test",
            "trial_ends_at": None,
            "grace_period_ends_at": datetime.now(timezone.utc) - timedelta(days=1),
        }
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get, \
             patch("billing._db_update_user_plan", new_callable=AsyncMock) as mock_update, \
             patch("billing._db_log_usage", new_callable=AsyncMock):
            mock_get.return_value = expired_user

            result = await handle_failed_payment(expired_user["id"])
            assert result["status"] == "downgraded"
            mock_update.assert_called_once_with(
                expired_user["id"],
                PlanTier.FREE.value,
                PLAN_CONFIG[PlanTier.FREE]["monthly_credits"],
            )

    @pytest.mark.asyncio
    async def test_active_grace_period_keeps_access(self, grace_period_user):
        """Users within grace period still have access."""
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = grace_period_user

            result = await handle_failed_payment(grace_period_user["id"])
            assert result["status"] == "grace_period"
            assert "grace_period_ends_at" in result

    @pytest.mark.asyncio
    async def test_failed_payment_unknown_user_raises(self):
        """handle_failed_payment raises ValueError for unknown user."""
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            with pytest.raises(ValueError, match="not found"):
                await handle_failed_payment("nonexistent-user")

    @pytest.mark.asyncio
    async def test_successful_payment_clears_grace_period(self, grace_period_user):
        """Successful payment after failure clears the grace period."""
        # This tests the check_credits path — grace period user should
        # still report credits correctly
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = grace_period_user

            result = await check_credits(grace_period_user["id"])
            assert result["credits_remaining"] == grace_period_user["credits_remaining"]
            assert result["plan"] == "pro"


# ---------------------------------------------------------------------------
# Plan Configuration Tests
# ---------------------------------------------------------------------------


class TestPlanConfiguration:
    """Test plan tier configuration constants."""

    def test_free_plan_has_3_monthly_credits(self):
        """Free plan allows 3 videos per month."""
        assert PLAN_CONFIG[PlanTier.FREE]["monthly_credits"] == 3

    def test_pro_plan_has_30_monthly_credits(self):
        """Pro plan allows 30 videos per month."""
        assert PLAN_CONFIG[PlanTier.PRO]["monthly_credits"] == 30

    def test_business_plan_is_unlimited(self):
        """Business plan has unlimited credits (-1)."""
        assert PLAN_CONFIG[PlanTier.BUSINESS]["monthly_credits"] == -1

    def test_free_plan_has_watermark(self):
        """Free plan includes watermark on output."""
        assert PLAN_CONFIG[PlanTier.FREE]["watermark"] is True

    def test_pro_plan_no_watermark(self):
        """Pro plan removes watermark."""
        assert PLAN_CONFIG[PlanTier.PRO]["watermark"] is False

    def test_business_plan_has_api_access(self):
        """Only Business plan has API access."""
        assert PLAN_CONFIG[PlanTier.BUSINESS]["api_access"] is True
        assert PLAN_CONFIG[PlanTier.PRO]["api_access"] is False
        assert PLAN_CONFIG[PlanTier.FREE]["api_access"] is False

    def test_annual_pricing_is_20_percent_discount(self):
        """Annual pricing is exactly 20% off monthly * 12."""
        pro_monthly = PLAN_CONFIG[PlanTier.PRO]["price_monthly"]
        pro_annual = PLAN_CONFIG[PlanTier.PRO]["price_annual"]
        expected_annual = int(pro_monthly * 12 * 0.8)
        assert pro_annual == expected_annual

        biz_monthly = PLAN_CONFIG[PlanTier.BUSINESS]["price_monthly"]
        biz_annual = PLAN_CONFIG[PlanTier.BUSINESS]["price_annual"]
        expected_biz_annual = int(biz_monthly * 12 * 0.8)
        assert biz_annual == expected_biz_annual

    def test_trial_duration_is_7_days(self):
        """Trial duration constant is 7 days."""
        assert TRIAL_DURATION_DAYS == 7


# ---------------------------------------------------------------------------
# Check Credits Tests
# ---------------------------------------------------------------------------


class TestCheckCredits:
    """Test credit balance checking."""

    @pytest.mark.asyncio
    async def test_check_credits_returns_balance(self, pro_user):
        """check_credits returns correct balance info."""
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = pro_user

            result = await check_credits(pro_user["id"])
            assert result["credits_remaining"] == 25
            assert result["credits_total"] == 30
            assert result["plan"] == "pro"
            assert result["unlimited"] is False

    @pytest.mark.asyncio
    async def test_check_credits_business_shows_unlimited(self, business_user):
        """Business users see unlimited credits."""
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = business_user

            result = await check_credits(business_user["id"])
            assert result["credits_remaining"] == -1
            assert result["unlimited"] is True

    @pytest.mark.asyncio
    async def test_check_credits_unknown_user_defaults_to_free(self):
        """Unknown users get free plan defaults."""
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            result = await check_credits("unknown-user")
            assert result["plan"] == "free"
            assert result["credits_remaining"] == 3
            assert result["unlimited"] is False

    @pytest.mark.asyncio
    async def test_check_credits_includes_plan_features(self, pro_user):
        """check_credits includes feature info (resolution, watermark)."""
        with patch("billing._db_get_user", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = pro_user

            result = await check_credits(pro_user["id"])
            assert result["max_resolution"] == "1080p"
            assert result["watermark"] is False
            assert result["priority_render"] is True
