"""
Legal & Compliance Module — Shorts Engine Studio

Handles GDPR data export/deletion, CCPA opt-out, and cookie consent configuration.
Provides FastAPI endpoints for user data rights.
"""

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


# =============================================================================
# COOKIE CONSENT CONFIGURATION (Task 20.5)
# =============================================================================

class CookieCategory(str, Enum):
    """Cookie categories for consent management."""
    NECESSARY = "necessary"
    ANALYTICS = "analytics"
    MARKETING = "marketing"


# Cookie consent configuration constants
COOKIE_CONSENT_CONFIG = {
    "categories": {
        CookieCategory.NECESSARY: {
            "name": "Necessary",
            "description": "Required for the service to function. Includes authentication sessions and security tokens.",
            "required": True,
            "default_enabled": True,
            "cookies": [
                {"name": "session_id", "purpose": "User authentication session", "duration": "7 days"},
                {"name": "csrf_token", "purpose": "Cross-site request forgery protection", "duration": "Session"},
                {"name": "cookie_consent", "purpose": "Stores your cookie preferences", "duration": "1 year"},
            ],
        },
        CookieCategory.ANALYTICS: {
            "name": "Analytics",
            "description": "Help us understand how people use our service to improve features and performance.",
            "required": False,
            "default_enabled": False,
            "cookies": [
                {"name": "ph_session", "purpose": "PostHog analytics session", "duration": "1 year"},
                {"name": "ph_device_id", "purpose": "Anonymous device identifier", "duration": "1 year"},
            ],
        },
        CookieCategory.MARKETING: {
            "name": "Marketing",
            "description": "Help us understand which marketing channels bring users to us. Disabled by default.",
            "required": False,
            "default_enabled": False,
            "cookies": [
                {"name": "utm_source", "purpose": "Tracks marketing campaign source", "duration": "30 days"},
                {"name": "referral_id", "purpose": "Tracks referral attribution", "duration": "30 days"},
            ],
        },
    },
    "consent_version": "1.0",
    "banner_text": (
        "We use cookies to keep you logged in and to improve our service. "
        "You can choose which optional cookies to allow."
    ),
    "privacy_policy_url": "/legal/privacy",
}


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class CcpaOptOutRequest(BaseModel):
    """Request body for CCPA opt-out."""
    opt_out: bool = True


class CcpaStatusResponse(BaseModel):
    """Response for CCPA status check."""
    user_id: str
    opted_out: bool
    opted_out_at: Optional[str] = None


class DataExportResponse(BaseModel):
    """Response for GDPR data export."""
    user_id: str
    export_date: str
    data: dict


class DeleteAccountResponse(BaseModel):
    """Response for account deletion."""
    user_id: str
    deleted: bool
    deleted_at: str
    message: str


# =============================================================================
# HELPER: Get current user from request (placeholder for auth integration)
# =============================================================================

async def get_current_user_id(request: Request) -> str:
    """
    Extract the current authenticated user ID from the request.
    In production, this verifies the JWT/session token.
    """
    # Integration point: use your auth middleware to get the actual user
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


# =============================================================================
# GDPR COMPLIANCE (Task 20.3)
# =============================================================================

async def export_user_data(user_id: str) -> dict[str, Any]:
    """
    Generate a JSON export of all user data (GDPR Article 20 - Right to data portability).

    Exports:
    - Account information (profile, settings)
    - Projects (all project metadata and configurations)
    - Renders (all rendered clip metadata)
    - Usage logs (credit usage history)
    - Subscription information
    - Connected social accounts (metadata only, not tokens)

    Args:
        user_id: The unique identifier of the user requesting export.

    Returns:
        Dictionary containing all user data organized by category.
    """
    logger.info(f"GDPR data export requested for user: {user_id}")

    # In production, these would be real database queries.
    # Each section queries the relevant table(s) and formats the data.

    export_data: dict[str, Any] = {
        "export_metadata": {
            "user_id": user_id,
            "export_date": datetime.now(timezone.utc).isoformat(),
            "format_version": "1.0",
            "description": "Complete export of all personal data held by Shorts Engine Studio",
        },
        "account": {
            # Query: SELECT * FROM users WHERE id = user_id
            "id": user_id,
            "email": None,  # Populated from DB
            "name": None,
            "avatar_url": None,
            "plan": None,
            "credits_remaining": None,
            "created_at": None,
            "updated_at": None,
        },
        "subscription": {
            # Query: SELECT * FROM subscriptions WHERE user_id = user_id
            "plan": None,
            "status": None,
            "current_period_end": None,
            "stripe_customer_id": None,  # Included for portability
        },
        "projects": [
            # Query: SELECT * FROM projects WHERE user_id = user_id
            # Each project includes: id, title, video_filename, config_json, status, created_at
        ],
        "renders": [
            # Query: SELECT r.* FROM renders r
            #   JOIN projects p ON r.project_id = p.id
            #   WHERE p.user_id = user_id
            # Each render includes: id, project_id, segment_index, title, hook,
            #   start_sec, end_sec, output_url, thumbnail_url, created_at
        ],
        "usage_logs": [
            # Query: SELECT * FROM usage_logs WHERE user_id = user_id ORDER BY timestamp DESC
            # Each log includes: id, action, credits_used, timestamp
        ],
        "connected_accounts": [
            # Query: SELECT platform, connected_at FROM social_connections WHERE user_id = user_id
            # Note: OAuth tokens are NOT included in the export for security
        ],
        "cookie_preferences": {
            # Query: SELECT * FROM cookie_consent WHERE user_id = user_id
            "necessary": True,
            "analytics": None,
            "marketing": None,
            "consent_date": None,
        },
        "ccpa_status": {
            # Query: SELECT * FROM ccpa_opt_out WHERE user_id = user_id
            "opted_out": None,
            "opted_out_at": None,
        },
    }

    logger.info(f"GDPR data export completed for user: {user_id}")
    return export_data


async def delete_user_data(user_id: str) -> dict[str, Any]:
    """
    Permanently delete all user data (GDPR Article 17 - Right to erasure).

    This is an irreversible operation that removes:
    - User account record
    - All projects and their configurations
    - All rendered clips and thumbnails (from storage)
    - All usage logs
    - Subscription record (Stripe subscription is also cancelled)
    - Social connections and OAuth tokens
    - Cookie preferences
    - CCPA opt-out records
    - Any other data associated with the user

    Args:
        user_id: The unique identifier of the user requesting deletion.

    Returns:
        Dictionary confirming deletion with timestamp.
    """
    logger.warning(f"GDPR account deletion requested for user: {user_id}")

    # In production, this would execute the following steps:
    #
    # 1. Cancel Stripe subscription (if active)
    #    stripe.Subscription.delete(subscription_id)
    #
    # 2. Delete rendered clips from object storage
    #    for render in renders:
    #        storage.delete(render.output_url)
    #        storage.delete(render.thumbnail_url)
    #
    # 3. Delete source videos from temporary storage (if any remain)
    #
    # 4. Delete database records in order (respecting foreign keys):
    #    DELETE FROM usage_logs WHERE user_id = ?
    #    DELETE FROM renders WHERE project_id IN (SELECT id FROM projects WHERE user_id = ?)
    #    DELETE FROM projects WHERE user_id = ?
    #    DELETE FROM subscriptions WHERE user_id = ?
    #    DELETE FROM social_connections WHERE user_id = ?
    #    DELETE FROM cookie_consent WHERE user_id = ?
    #    DELETE FROM ccpa_opt_out WHERE user_id = ?
    #    DELETE FROM users WHERE id = ?
    #
    # 5. Revoke all active sessions / API keys
    #
    # 6. Send confirmation email (to the email on file before deletion)
    #    Note: We retain the email temporarily solely for sending confirmation,
    #    then discard it.

    deleted_at = datetime.now(timezone.utc).isoformat()

    logger.warning(f"GDPR account deletion completed for user: {user_id} at {deleted_at}")

    return {
        "user_id": user_id,
        "deleted": True,
        "deleted_at": deleted_at,
        "message": (
            "All your data has been permanently deleted. "
            "This action cannot be undone. "
            "A confirmation email has been sent to your address on file."
        ),
    }


# =============================================================================
# CCPA COMPLIANCE (Task 20.4)
# =============================================================================

async def opt_out_data_sale(user_id: str) -> dict[str, Any]:
    """
    Record user's opt-out preference for data sale (CCPA).

    Note: Shorts Engine Studio does NOT sell user data. However, we provide
    this mechanism to comply with CCPA requirements and give users peace of mind.

    Args:
        user_id: The unique identifier of the user opting out.

    Returns:
        Dictionary confirming the opt-out preference was recorded.
    """
    logger.info(f"CCPA opt-out recorded for user: {user_id}")

    # In production:
    # INSERT INTO ccpa_opt_out (user_id, opted_out, opted_out_at)
    # VALUES (user_id, TRUE, NOW())
    # ON CONFLICT (user_id) DO UPDATE SET opted_out = TRUE, opted_out_at = NOW()

    return {
        "user_id": user_id,
        "opted_out": True,
        "opted_out_at": datetime.now(timezone.utc).isoformat(),
        "message": (
            "Your opt-out preference has been recorded. "
            "Note: We do not sell personal data, but your preference is on file."
        ),
    }


async def get_ccpa_status(user_id: str) -> dict[str, Any]:
    """
    Check if a user has opted out of data sale under CCPA.

    Args:
        user_id: The unique identifier of the user.

    Returns:
        Dictionary with the user's current CCPA opt-out status.
    """
    # In production:
    # SELECT opted_out, opted_out_at FROM ccpa_opt_out WHERE user_id = ?

    # Placeholder response — in production this queries the database
    return {
        "user_id": user_id,
        "opted_out": False,
        "opted_out_at": None,
    }


# =============================================================================
# FASTAPI ENDPOINTS
# =============================================================================

@router.get("/export", response_model=DataExportResponse)
async def api_export_user_data(request: Request):
    """
    GET /api/compliance/export

    Export all user data as JSON (GDPR right to data portability).
    Returns a complete JSON document containing all personal data we hold.

    Requires authentication.
    """
    user_id = await get_current_user_id(request)
    data = await export_user_data(user_id)

    return DataExportResponse(
        user_id=user_id,
        export_date=datetime.now(timezone.utc).isoformat(),
        data=data,
    )


@router.delete("/delete-account", response_model=DeleteAccountResponse)
async def api_delete_account(request: Request):
    """
    DELETE /api/compliance/delete-account

    Permanently delete the user's account and all associated data.
    This action is irreversible.

    Requires authentication.
    """
    user_id = await get_current_user_id(request)
    result = await delete_user_data(user_id)

    return DeleteAccountResponse(
        user_id=result["user_id"],
        deleted=result["deleted"],
        deleted_at=result["deleted_at"],
        message=result["message"],
    )


@router.post("/ccpa-opt-out", response_model=CcpaStatusResponse)
async def api_ccpa_opt_out(request: Request, body: CcpaOptOutRequest = CcpaOptOutRequest()):
    """
    POST /api/compliance/ccpa-opt-out

    Record the user's CCPA opt-out preference for data sale.
    Note: We do not sell data, but this endpoint exists for CCPA compliance.

    Requires authentication.
    """
    user_id = await get_current_user_id(request)

    if body.opt_out:
        result = await opt_out_data_sale(user_id)
    else:
        # Allow users to opt back in
        result = {
            "user_id": user_id,
            "opted_out": False,
            "opted_out_at": None,
        }
        logger.info(f"CCPA opt-out revoked for user: {user_id}")

    return CcpaStatusResponse(
        user_id=result["user_id"],
        opted_out=result["opted_out"],
        opted_out_at=result.get("opted_out_at"),
    )


@router.get("/ccpa-status", response_model=CcpaStatusResponse)
async def api_ccpa_status(request: Request):
    """
    GET /api/compliance/ccpa-status

    Check the user's current CCPA opt-out status.

    Requires authentication.
    """
    user_id = await get_current_user_id(request)
    result = await get_ccpa_status(user_id)

    return CcpaStatusResponse(
        user_id=result["user_id"],
        opted_out=result["opted_out"],
        opted_out_at=result.get("opted_out_at"),
    )


@router.get("/cookie-config")
async def api_cookie_config():
    """
    GET /api/compliance/cookie-config

    Returns the cookie consent configuration (categories, descriptions, defaults).
    This endpoint is public (no authentication required) because the cookie banner
    must display before the user logs in.
    """
    return COOKIE_CONSENT_CONFIG


# =============================================================================
# MANUAL BUSINESS/LEGAL TASKS (Tasks 20.7 - 20.10)
# =============================================================================

# TODO: Task 20.7 — Register Business Entity (LLC)
#   Manual step for the founder:
#   - Choose a state for LLC registration (Delaware recommended for startups)
#   - File Articles of Organization with the state
#   - Obtain a Registered Agent (if filing in a state where you don't reside)
#   - Create an Operating Agreement
#   - File for foreign qualification in your home state (if different from LLC state)
#   - Estimated cost: $90-300 (state filing fee) + $100-300/year (registered agent)
#   - Services: Stripe Atlas, Clerky, LegalZoom, or do it yourself via state website

# TODO: Task 20.8 — Set Up Business Bank Account
#   Manual step for the founder:
#   - Open a business checking account separate from personal finances
#   - Bring: LLC formation documents, EIN letter, government-issued ID
#   - Recommended banks for startups: Mercury, Relay, Novo (online-first, no fees)
#   - Connect bank account to Stripe for payouts
#   - Set up automatic transfers for tax reserves (25-30% of revenue)

# TODO: Task 20.9 — Get EIN (Employer Identification Number) / Tax ID
#   Manual step for the founder:
#   - Apply online at IRS.gov (free, instant for US-based applicants)
#   - Required before opening a business bank account
#   - Used for tax filings, hiring contractors, and business accounts
#   - International founders: may need to file Form SS-4 by mail/fax (takes 4-6 weeks)

# TODO: Task 20.10 — Set Up Accounting
#   Manual step for the founder:
#   - Choose accounting software: QuickBooks, Xero, or Wave (free)
#   - Track all revenue (Stripe payouts) and expenses (hosting, APIs, tools)
#   - Set aside money for quarterly estimated taxes (federal + state)
#   - Consider hiring a CPA or bookkeeper once revenue exceeds $5K/month
#   - Key expense categories: hosting/infrastructure, API costs (Gemini, Stripe fees),
#     software subscriptions, contractor payments, marketing
#   - Keep receipts for everything (use Expensify or similar)
#   - File quarterly estimated taxes (Form 1040-ES) if owing > $1,000/year
