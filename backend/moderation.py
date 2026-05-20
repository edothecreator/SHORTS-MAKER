"""Content Safety & Moderation system for Shorts Engine Studio.

Production Task 19: Implements NSFW scanning, content blocking, DMCA
takedown workflow, content reporting, abuse logging, auto-ban, and
terms acceptance verification.

Integration Options (documented per sub-task):
  - Google Cloud Vision SafeSearch
  - AWS Rekognition Content Moderation
  - Open-source NSFW classifier (e.g., nsfw_detector / NudeNet)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/moderation", tags=["moderation"])



# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Task 19.7: Users MUST accept terms before using the service.
TERMS_ACCEPTANCE_REQUIRED = True

# Auto-ban threshold (Task 19.6)
MAX_VIOLATIONS_BEFORE_BAN = 3


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ModerationCategory(str, Enum):
    """Categories of content that may be flagged during moderation."""
    NSFW = "nsfw"
    VIOLENCE = "violence"
    HATE_SPEECH = "hate_speech"
    SPAM = "spam"
    COPYRIGHT = "copyright"



# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class ModerationResult(BaseModel):
    """Result of scanning content for policy violations (Task 19.1)."""
    is_safe: bool = Field(..., description="True if content passed moderation checks")
    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Confidence level of the detection (0.0–1.0)"
    )
    categories_detected: List[ModerationCategory] = Field(
        default_factory=list,
        description="List of flagged categories (empty if safe)"
    )
    provider: str = Field(
        default="placeholder",
        description="Which scanning provider was used"
    )
    details: Optional[str] = Field(
        default=None,
        description="Human-readable details about the detection"
    )


class DMCARequest(BaseModel):
    """DMCA takedown request submitted by a copyright holder (Task 19.3)."""
    reporter_name: str = Field(..., description="Full legal name of the reporter")
    reporter_email: str = Field(..., description="Contact email of the reporter")
    content_url: str = Field(..., description="URL of the infringing content")
    original_work_url: Optional[str] = Field(
        default=None,
        description="URL to the original copyrighted work"
    )
    description: str = Field(
        ...,
        description="Detailed description of the infringement"
    )
    sworn_statement: bool = Field(
        ...,
        description="Reporter affirms under penalty of perjury that the "
        "information is accurate and they are authorized to act"
    )



class DMCAResponse(BaseModel):
    """Response after a DMCA request is submitted."""
    request_id: str = Field(..., description="Unique ID for tracking the request")
    status: str = Field(default="received", description="Current status of the request")
    message: str = Field(..., description="Confirmation message")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContentReport(BaseModel):
    """Report submitted by a user flagging inappropriate content (Task 19.4)."""
    reporter_id: str = Field(..., description="User ID of the person reporting")
    content_id: str = Field(..., description="ID of the content being reported")
    reason: ModerationCategory = Field(
        ..., description="Category/reason for the report"
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional additional context from the reporter"
    )


class AbuseLogEntry(BaseModel):
    """Single entry in a user's abuse/violation log (Task 19.5)."""
    log_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    violation_type: ModerationCategory
    details: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    auto_action_taken: Optional[str] = Field(
        default=None,
        description="e.g., 'warned', 'content_removed', 'banned'"
    )



class ViolationRecord(BaseModel):
    """Summary of a user's violation history (Task 19.5/19.6)."""
    user_id: str
    total_violations: int = 0
    is_banned: bool = False
    violations: List[AbuseLogEntry] = Field(default_factory=list)
    banned_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Task 19.1: NSFW Content Scanning
# ---------------------------------------------------------------------------

def scan_upload_for_nsfw(video_path_or_url: str) -> ModerationResult:
    """Scan uploaded content for NSFW / policy-violating material.

    This is a PLACEHOLDER implementation. In production, integrate one of:

    Option A — Google Cloud Vision SafeSearch:
        from google.cloud import vision
        client = vision.ImageAnnotatorClient()
        response = client.safe_search_detection(image=image)
        # Check: LIKELY or VERY_LIKELY for adult, violence, racy

    Option B — AWS Rekognition Content Moderation:
        import boto3
        client = boto3.client('rekognition')
        response = client.detect_moderation_labels(
            Video={'S3Object': {'Bucket': bucket, 'Name': key}}
        )
        # Parse ModerationLabels for confidence > 80%

    Option C — Open-source NSFW classifier (nsfw_detector / NudeNet):
        from nsfw_detector import predict
        results = predict.classify(model, video_path_or_url)
        # Check 'porn', 'hentai', 'sexy' scores > 0.7

    For video content, sample frames at 1-second intervals and aggregate
    results. Flag if ANY frame exceeds the confidence threshold.

    Args:
        video_path_or_url: Local file path or remote URL of the upload.

    Returns:
        ModerationResult indicating whether the content is safe.
    """
    logger.info("Scanning content for NSFW: %s", video_path_or_url)

    # --- Placeholder: always returns safe ---
    # In production, replace with actual API call to chosen provider.
    return ModerationResult(
        is_safe=True,
        confidence=0.99,
        categories_detected=[],
        provider="placeholder",
        details="Placeholder scan — no real detection performed. "
        "Integrate a production provider before launch.",
    )



# ---------------------------------------------------------------------------
# Task 19.2: Block Flagged Content
# ---------------------------------------------------------------------------

def block_flagged_content(scan_result: ModerationResult, user_id: str) -> dict:
    """If content is flagged, block processing and return error to user.

    Also logs the event for audit purposes and records a violation.

    Args:
        scan_result: The ModerationResult from scan_upload_for_nsfw().
        user_id: The ID of the user who uploaded the content.

    Returns:
        dict with 'allowed' (bool) and 'message' (str).
        If blocked, includes 'categories' that triggered the block.
    """
    if scan_result.is_safe:
        return {
            "allowed": True,
            "message": "Content passed moderation checks.",
        }

    # Content is flagged — block processing
    categories_str = ", ".join(c.value for c in scan_result.categories_detected)
    logger.warning(
        "BLOCKED content from user %s. Categories: %s (confidence: %.2f)",
        user_id,
        categories_str,
        scan_result.confidence,
    )

    # Record the violation
    violation_type = (
        scan_result.categories_detected[0]
        if scan_result.categories_detected
        else ModerationCategory.NSFW
    )
    record_violation(
        user_id=user_id,
        violation_type=violation_type,
        details=f"Upload blocked. Detected: {categories_str}. "
        f"Confidence: {scan_result.confidence:.2f}",
    )

    return {
        "allowed": False,
        "message": (
            "Your content has been flagged and cannot be processed. "
            f"Reason: {categories_str}. "
            "If you believe this is an error, please contact support."
        ),
        "categories": [c.value for c in scan_result.categories_detected],
    }



# ---------------------------------------------------------------------------
# Task 19.3: DMCA Takedown Process
# ---------------------------------------------------------------------------

def submit_dmca_takedown(request: DMCARequest) -> DMCAResponse:
    """Submit a DMCA takedown request.

    Validates the request, stores it in the database, and sends a
    notification email to the site admin for review.

    Placeholder DB query:
        INSERT INTO dmca_requests (
            id, reporter_name, reporter_email, content_url,
            original_work_url, description, sworn_statement,
            status, created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'received', NOW())

    Placeholder email notification:
        send_email(
            to="legal@shortsengine.studio",
            subject=f"DMCA Takedown Request: {request_id}",
            body=f"New DMCA request from {request.reporter_name}..."
        )

    Args:
        request: The DMCARequest with reporter info and infringement details.

    Returns:
        DMCAResponse confirming receipt.

    Raises:
        HTTPException 400 if sworn_statement is False.
    """
    if not request.sworn_statement:
        raise HTTPException(
            status_code=400,
            detail="You must affirm the sworn statement to submit a DMCA request.",
        )

    request_id = str(uuid.uuid4())

    # --- Placeholder: store in DB ---
    logger.info(
        "DMCA request %s from %s for content: %s",
        request_id,
        request.reporter_email,
        request.content_url,
    )

    # --- Placeholder: send notification email ---
    logger.info("Sending DMCA notification email to legal team for %s", request_id)

    return DMCAResponse(
        request_id=request_id,
        status="received",
        message=(
            "Your DMCA takedown request has been received. "
            f"Reference ID: {request_id}. "
            "Our legal team will review it within 48 hours."
        ),
    )



# ---------------------------------------------------------------------------
# Task 19.4: Content Reporting
# ---------------------------------------------------------------------------

def report_content(
    reporter_id: str, content_id: str, reason: ModerationCategory,
    description: Optional[str] = None,
) -> dict:
    """Allow users to flag inappropriate content for review.

    Stores the report in the database and adds it to the moderation
    review queue.

    Placeholder DB query:
        INSERT INTO content_reports (
            id, reporter_id, content_id, reason, description,
            status, created_at
        ) VALUES ($1, $2, $3, $4, $5, 'pending_review', NOW())

    Placeholder review queue trigger:
        enqueue_moderation_review(report_id, priority='normal')

    Args:
        reporter_id: User ID of the person submitting the report.
        content_id: ID of the content being reported.
        reason: Category of the violation.
        description: Optional extra context.

    Returns:
        dict confirming the report was submitted.
    """
    report_id = str(uuid.uuid4())

    logger.info(
        "Content report %s: user %s reported content %s for %s",
        report_id,
        reporter_id,
        content_id,
        reason.value,
    )

    # --- Placeholder: add to review queue ---
    logger.info("Added report %s to moderation review queue", report_id)

    return {
        "report_id": report_id,
        "status": "pending_review",
        "message": (
            "Thank you for your report. Our moderation team will review "
            "this content within 24 hours."
        ),
    }



# ---------------------------------------------------------------------------
# Task 19.5: Abuse Log
# ---------------------------------------------------------------------------

def get_abuse_log(user_id: str) -> ViolationRecord:
    """Retrieve the abuse/violation log for a specific user.

    Placeholder DB query:
        SELECT id, user_id, violation_type, details, timestamp, auto_action_taken
        FROM abuse_log
        WHERE user_id = $1
        ORDER BY timestamp DESC

    Placeholder ban check:
        SELECT is_banned, banned_at
        FROM users
        WHERE id = $1

    Args:
        user_id: The user whose abuse log to retrieve.

    Returns:
        ViolationRecord with complete violation history.
    """
    logger.info("Fetching abuse log for user %s", user_id)

    # --- Placeholder: query DB for violations ---
    # In production, this fetches real records from the abuse_log table.
    return ViolationRecord(
        user_id=user_id,
        total_violations=0,
        is_banned=False,
        violations=[],
        banned_at=None,
    )


def record_violation(
    user_id: str,
    violation_type: ModerationCategory,
    details: str,
) -> AbuseLogEntry:
    """Record a new violation in the user's abuse log.

    Placeholder DB query:
        INSERT INTO abuse_log (
            id, user_id, violation_type, details, timestamp, auto_action_taken
        ) VALUES ($1, $2, $3, $4, NOW(), $5)

    After recording, checks if auto-ban threshold is reached.

    Args:
        user_id: The user who committed the violation.
        violation_type: Category of the violation.
        details: Description of what happened.

    Returns:
        The newly created AbuseLogEntry.
    """
    entry = AbuseLogEntry(
        user_id=user_id,
        violation_type=violation_type,
        details=details,
    )

    logger.warning(
        "Violation recorded for user %s: %s — %s",
        user_id,
        violation_type.value,
        details,
    )

    # Check if user should be auto-banned
    ban_result = check_auto_ban(user_id)
    if ban_result["is_banned"]:
        entry.auto_action_taken = "banned"
        logger.warning("User %s has been AUTO-BANNED", user_id)
    else:
        entry.auto_action_taken = "warned"

    return entry



# ---------------------------------------------------------------------------
# Task 19.6: Auto-Ban After 3 Violations
# ---------------------------------------------------------------------------

def check_auto_ban(user_id: str) -> dict:
    """Check if a user should be auto-banned based on violation count.

    Auto-ban is triggered when a user accumulates MAX_VIOLATIONS_BEFORE_BAN
    (default: 3) violations.

    Placeholder DB query (count violations):
        SELECT COUNT(*) as violation_count
        FROM abuse_log
        WHERE user_id = $1

    Placeholder DB query (apply ban):
        UPDATE users
        SET is_banned = TRUE, banned_at = NOW()
        WHERE id = $1

    Args:
        user_id: The user to check.

    Returns:
        dict with 'is_banned' (bool), 'violation_count' (int),
        and 'message' (str).
    """
    # --- Placeholder: count violations from DB ---
    # In production, query the actual abuse_log table.
    violation_count = 0  # Placeholder: would come from DB

    logger.info(
        "Auto-ban check for user %s: %d violations (threshold: %d)",
        user_id,
        violation_count,
        MAX_VIOLATIONS_BEFORE_BAN,
    )

    is_banned = violation_count >= MAX_VIOLATIONS_BEFORE_BAN

    if is_banned:
        # --- Placeholder: update user record in DB ---
        logger.warning(
            "User %s BANNED: %d violations reached threshold of %d",
            user_id,
            violation_count,
            MAX_VIOLATIONS_BEFORE_BAN,
        )

    return {
        "is_banned": is_banned,
        "violation_count": violation_count,
        "message": (
            "Your account has been suspended due to repeated policy violations. "
            "You can no longer access this service. Contact support to appeal."
            if is_banned
            else "Account in good standing."
        ),
    }



# ---------------------------------------------------------------------------
# Task 19.7: Terms Acceptance Verification
# ---------------------------------------------------------------------------

def verify_terms_accepted(user_id: str) -> dict:
    """Verify that a user has accepted the Terms of Service.

    Must be checked before allowing any content processing. The terms
    acceptance checkbox is presented on signup and stored in the users table.

    Placeholder DB query:
        SELECT terms_accepted, terms_accepted_at
        FROM users
        WHERE id = $1

    Args:
        user_id: The user to check.

    Returns:
        dict with 'accepted' (bool), 'accepted_at' (datetime or None),
        and 'message' (str).

    Raises:
        HTTPException 403 if terms have not been accepted.
    """
    logger.info("Checking terms acceptance for user %s", user_id)

    # --- Placeholder: query DB ---
    # In production, check the users.terms_accepted column.
    terms_accepted = True  # Placeholder
    accepted_at = datetime.now(timezone.utc)  # Placeholder

    if TERMS_ACCEPTANCE_REQUIRED and not terms_accepted:
        raise HTTPException(
            status_code=403,
            detail=(
                "You must accept the Terms of Service before using this service. "
                "Please visit your account settings to review and accept the terms."
            ),
        )

    return {
        "accepted": terms_accepted,
        "accepted_at": accepted_at.isoformat() if accepted_at else None,
        "message": "Terms of Service accepted.",
    }



# ---------------------------------------------------------------------------
# FastAPI Endpoints
# ---------------------------------------------------------------------------

class DMCASubmitRequest(BaseModel):
    """API request body for DMCA submission endpoint."""
    reporter_name: str
    reporter_email: str
    content_url: str
    original_work_url: Optional[str] = None
    description: str
    sworn_statement: bool


class ContentReportRequest(BaseModel):
    """API request body for content reporting endpoint."""
    content_id: str
    reason: ModerationCategory
    description: Optional[str] = None


@router.post("/dmca", response_model=DMCAResponse)
async def api_submit_dmca(body: DMCASubmitRequest) -> DMCAResponse:
    """Submit a DMCA takedown request.

    Accepts reporter information, content URL, infringement description,
    and a sworn statement. Returns a tracking reference ID.
    """
    dmca_request = DMCARequest(
        reporter_name=body.reporter_name,
        reporter_email=body.reporter_email,
        content_url=body.content_url,
        original_work_url=body.original_work_url,
        description=body.description,
        sworn_statement=body.sworn_statement,
    )
    return submit_dmca_takedown(dmca_request)


@router.post("/report")
async def api_report_content(body: ContentReportRequest) -> dict:
    """Report inappropriate content for moderation review.

    Requires authentication. The reporter_id is extracted from the
    current session (placeholder: uses a hardcoded dev ID).
    """
    # In production, extract reporter_id from authenticated session:
    #   user = await get_current_user(request)
    #   reporter_id = user["id"]
    reporter_id = "authenticated-user-placeholder"

    return report_content(
        reporter_id=reporter_id,
        content_id=body.content_id,
        reason=body.reason,
        description=body.description,
    )



@router.get("/abuse-log/{user_id}")
async def api_get_abuse_log(user_id: str) -> dict:
    """Get the abuse/violation log for a user (admin only in production).

    In production, this endpoint should be restricted to admin users only.
    """
    record = get_abuse_log(user_id)
    return record.model_dump()


@router.get("/ban-status/{user_id}")
async def api_get_ban_status(user_id: str) -> dict:
    """Check if a user is banned.

    In production, this is used by the auth middleware to reject
    requests from banned users before processing.
    """
    return check_auto_ban(user_id)


@router.get("/terms-status/{user_id}")
async def api_get_terms_status(user_id: str) -> dict:
    """Check if a user has accepted Terms of Service."""
    return verify_terms_accepted(user_id)


# ---------------------------------------------------------------------------
# Database Schema (for reference — add to migrations)
# ---------------------------------------------------------------------------

MODERATION_SCHEMA_SQL = """
-- Content moderation tables for Task 19

CREATE TABLE IF NOT EXISTS dmca_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reporter_name TEXT NOT NULL,
    reporter_email TEXT NOT NULL,
    content_url TEXT NOT NULL,
    original_work_url TEXT,
    description TEXT NOT NULL,
    sworn_statement BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'received',
    reviewer_notes TEXT,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS content_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reporter_id UUID NOT NULL REFERENCES users(id),
    content_id UUID NOT NULL,
    reason TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'pending_review',
    reviewer_id UUID REFERENCES users(id),
    resolution TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS abuse_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    violation_type TEXT NOT NULL,
    details TEXT NOT NULL,
    auto_action_taken TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_abuse_log_user_id ON abuse_log(user_id);
CREATE INDEX idx_content_reports_content_id ON content_reports(content_id);
CREATE INDEX idx_content_reports_status ON content_reports(status);
CREATE INDEX idx_dmca_requests_status ON dmca_requests(status);

-- Add columns to users table for moderation:
-- ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE;
-- ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_at TIMESTAMPTZ;
-- ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_accepted BOOLEAN DEFAULT FALSE;
-- ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMPTZ;
"""
