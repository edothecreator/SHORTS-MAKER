"""Team & Collaboration System for Shorts Engine Studio.

Production Task 17: Complete team management with workspaces, invites,
role-based access, brand kits, approval workflows, and activity logging.

Sub-tasks covered:
  17.1  Team/workspace system (one team = one billing account)
  17.2  Invite team members by email (token-based)
  17.3  Role-based access: Owner, Admin, Editor, Viewer
  17.4  Shared project library (team members see all team projects)
  17.5  Brand kit: upload logo, set brand colors, default fonts
  17.6  Apply brand kit automatically to renders
  17.7  Approval workflow (editor submits -> admin approves -> publish)
  17.8  Activity log (who did what, when)
  17.9  Per-seat billing ($10/mo per additional team member) via Stripe

Per-seat billing note (17.9):
  Each team beyond the owner incurs $10/month per additional seat.
  Integration with Stripe uses metered billing or quantity-based subscriptions:
    - STRIPE_PRICE_TEAM_SEAT = price ID for $10/mo per-seat line item
    - On member add: stripe.SubscriptionItem.modify(quantity=new_count)
    - On member remove: stripe.SubscriptionItem.modify(quantity=new_count)
    - Stripe invoice automatically adjusts proration.
  TODO: Wire up real Stripe calls in _update_seat_billing() below.
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from enum import IntEnum
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, EmailStr

from backend.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/teams", tags=["teams"])



# ---------------------------------------------------------------------------
# 17.3 — Role-Based Access Enum (hierarchy: OWNER > ADMIN > EDITOR > VIEWER)
# ---------------------------------------------------------------------------


class TeamRole(IntEnum):
    """Team member roles with numeric hierarchy for permission checks.

    Higher value = more permissions. Use require_role() dependency to
    enforce minimum role level on endpoints.
    """
    VIEWER = 10
    EDITOR = 20
    ADMIN = 30
    OWNER = 40


# Human-readable descriptions for each role
ROLE_DESCRIPTIONS = {
    TeamRole.VIEWER: "Can view team projects and activity log (read-only)",
    TeamRole.EDITOR: "Can create/edit projects and submit for approval",
    TeamRole.ADMIN: "Can manage members, approve content, manage brand kit",
    TeamRole.OWNER: "Full control including billing, team deletion, ownership transfer",
}



# ---------------------------------------------------------------------------
# Pydantic Models — Core Entities
# ---------------------------------------------------------------------------


class Team(BaseModel):
    """Team/workspace entity (17.1). One team = one billing account."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., min_length=1, max_length=100, description="Team display name")
    slug: str = Field(..., min_length=1, max_length=50, description="URL-safe team identifier")
    owner_id: str = Field(..., description="User ID of the team owner")
    stripe_customer_id: Optional[str] = Field(None, description="Stripe customer for team billing")
    plan: str = Field(default="business", description="Team plan tier (must be business)")
    max_seats: int = Field(default=5, description="Maximum allowed team members")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TeamMembership(BaseModel):
    """Association between a user and a team (17.1, 17.3)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_id: str = Field(..., description="ID of the team")
    user_id: str = Field(..., description="ID of the member user")
    role: TeamRole = Field(..., description="Member's role in the team")
    invited_by: Optional[str] = Field(None, description="User ID of who invited this member")
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))



class TeamInvite(BaseModel):
    """Pending team invitation (17.2)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_id: str = Field(..., description="ID of the team")
    email: str = Field(..., description="Invitee email address")
    role: TeamRole = Field(default=TeamRole.EDITOR, description="Role to assign on acceptance")
    token: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    invited_by: str = Field(..., description="User ID of inviter")
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=7)
    )
    accepted: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BrandKit(BaseModel):
    """Team brand kit configuration (17.5)."""
    team_id: str = Field(..., description="ID of the team this brand kit belongs to")
    logo_url: Optional[str] = Field(None, description="URL to uploaded logo image")
    primary_color: str = Field(default="#6366f1", description="Primary brand color (hex)")
    secondary_color: str = Field(default="#8b5cf6", description="Secondary brand color (hex)")
    accent_color: str = Field(default="#f59e0b", description="Accent color (hex)")
    background_color: str = Field(default="#000000", description="Background color (hex)")
    default_font: str = Field(default="Inter", description="Default subtitle font family")
    heading_font: Optional[str] = Field(None, description="Font for titles/headings")
    watermark_url: Optional[str] = Field(None, description="Custom watermark image URL")
    watermark_position: str = Field(default="bottom-right", description="Watermark placement")
    watermark_opacity: float = Field(default=0.7, ge=0.0, le=1.0)
    intro_template_id: Optional[str] = Field(None, description="Default intro template")
    outro_template_id: Optional[str] = Field(None, description="Default outro template")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))



class ApprovalStatus(BaseModel):
    """Project approval state (17.7)."""
    project_id: str = Field(..., description="ID of the project under review")
    team_id: str = Field(..., description="Team owning the project")
    submitted_by: str = Field(..., description="User ID of the editor who submitted")
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = Field(default="pending", description="pending | approved | rejected")
    reviewed_by: Optional[str] = Field(None, description="User ID of the reviewer")
    reviewed_at: Optional[datetime] = Field(None)
    review_notes: Optional[str] = Field(None, description="Reviewer comments")


class ActivityLogEntry(BaseModel):
    """Activity log entry for audit trail (17.8)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_id: str = Field(..., description="Team this activity belongs to")
    user_id: str = Field(..., description="User who performed the action")
    user_name: Optional[str] = Field(None, description="Display name at time of action")
    action: str = Field(..., description="Action type (e.g., 'member_invited', 'project_approved')")
    resource_type: Optional[str] = Field(None, description="Type of resource (project, member, brand_kit)")
    resource_id: Optional[str] = Field(None, description="ID of the affected resource")
    details: Optional[dict] = Field(None, description="Additional context as JSON")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))



# ---------------------------------------------------------------------------
# Pydantic Models — Request / Response Schemas
# ---------------------------------------------------------------------------


class CreateTeamRequest(BaseModel):
    """Request to create a new team/workspace (17.1)."""
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9\-]+$")


class CreateTeamResponse(BaseModel):
    """Response after creating a team."""
    team: Team
    membership: TeamMembership
    message: str = "Team created successfully"


class InviteMemberRequest(BaseModel):
    """Request to invite a team member (17.2)."""
    email: str = Field(..., description="Email address to invite")
    role: TeamRole = Field(default=TeamRole.EDITOR, description="Role to assign")


class InviteMemberResponse(BaseModel):
    """Response after sending an invite."""
    invite_id: str
    email: str
    role: TeamRole
    expires_at: str
    message: str = "Invitation sent successfully"


class UpdateBrandKitRequest(BaseModel):
    """Request to update brand kit (17.5)."""
    logo_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    secondary_color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    accent_color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    background_color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    default_font: Optional[str] = None
    heading_font: Optional[str] = None
    watermark_url: Optional[str] = None
    watermark_position: Optional[str] = None
    watermark_opacity: Optional[float] = Field(None, ge=0.0, le=1.0)
    intro_template_id: Optional[str] = None
    outro_template_id: Optional[str] = None


class ApplyBrandRequest(BaseModel):
    """Request to apply brand kit to a project (17.6)."""
    apply_colors: bool = Field(default=True, description="Apply brand colors to subtitles")
    apply_font: bool = Field(default=True, description="Apply default font")
    apply_watermark: bool = Field(default=True, description="Apply brand watermark")
    apply_intro_outro: bool = Field(default=False, description="Apply intro/outro templates")



class SubmitForApprovalRequest(BaseModel):
    """Request to submit a project for approval (17.7)."""
    notes: Optional[str] = Field(None, max_length=500, description="Notes for the reviewer")


class ApproveProjectRequest(BaseModel):
    """Request to approve/reject a submitted project (17.7)."""
    decision: str = Field(..., pattern=r"^(approved|rejected)$", description="approved or rejected")
    notes: Optional[str] = Field(None, max_length=500, description="Review notes")


class ActivityLogResponse(BaseModel):
    """Paginated activity log response (17.8)."""
    entries: List[ActivityLogEntry]
    total: int
    page: int
    per_page: int


class TeamProjectResponse(BaseModel):
    """A project visible within the team library (17.4)."""
    id: str
    title: str
    owner_id: str
    owner_name: Optional[str] = None
    status: str
    created_at: str
    updated_at: str
    thumbnail_url: Optional[str] = None
    approval_status: Optional[str] = None



# ---------------------------------------------------------------------------
# Permission Dependency — require_role (17.3)
# ---------------------------------------------------------------------------


def require_role(min_role: TeamRole):
    """FastAPI dependency factory that enforces minimum role level.

    Usage:
        @router.get("/api/teams/{team_id}/settings")
        async def get_settings(
            team_id: str,
            user: dict = Depends(get_current_user),
            _perm: None = Depends(require_role(TeamRole.ADMIN)),
        ):
            ...

    The dependency checks the requesting user's role in the specified team
    and raises 403 if their role is below the minimum required.

    Note: The team_id is extracted from the path parameter by convention.
    """

    async def _check_permission(
        team_id: str,
        user: dict = Depends(get_current_user),
    ) -> None:
        membership = await _db_get_membership(team_id, user["id"])

        if not membership:
            raise HTTPException(
                status_code=403,
                detail="You are not a member of this team.",
            )

        user_role = TeamRole(membership["role"])
        if user_role < min_role:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Insufficient permissions. Required: {min_role.name}, "
                    f"your role: {user_role.name}."
                ),
            )

    return _check_permission



# ---------------------------------------------------------------------------
# Database Helpers (placeholder — same pattern as billing.py, projects.py)
# ---------------------------------------------------------------------------


async def _db_create_team(team: Team) -> dict:
    """Insert a new team record.

    Real SQL:
        INSERT INTO teams (id, name, slug, owner_id, stripe_customer_id, plan,
                           max_seats, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING *
    """
    logger.info("Created team: id=%s name=%s owner=%s", team.id, team.name, team.owner_id)
    return team.model_dump()


async def _db_get_team(team_id: str) -> Optional[dict]:
    """Fetch team by ID.

    Real SQL:
        SELECT * FROM teams WHERE id = $1
    """
    logger.debug("_db_get_team called for team_id=%s", team_id)
    return None


async def _db_create_membership(membership: TeamMembership) -> dict:
    """Insert a team membership record.

    Real SQL:
        INSERT INTO team_memberships (id, team_id, user_id, role, invited_by, joined_at)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
    """
    logger.info(
        "Membership created: team=%s user=%s role=%s",
        membership.team_id, membership.user_id, membership.role.name,
    )
    return membership.model_dump()



async def _db_get_membership(team_id: str, user_id: str) -> Optional[dict]:
    """Fetch a user's membership in a team.

    Real SQL:
        SELECT * FROM team_memberships
        WHERE team_id = $1 AND user_id = $2
    """
    logger.debug("_db_get_membership: team=%s user=%s", team_id, user_id)
    return None


async def _db_get_team_members(team_id: str) -> List[dict]:
    """Fetch all members of a team.

    Real SQL:
        SELECT tm.*, u.name, u.email, u.avatar_url
        FROM team_memberships tm
        JOIN users u ON u.id = tm.user_id
        WHERE tm.team_id = $1
        ORDER BY tm.role DESC, tm.joined_at ASC
    """
    logger.debug("_db_get_team_members: team=%s", team_id)
    return []


async def _db_create_invite(invite: TeamInvite) -> dict:
    """Insert a team invite record.

    Real SQL:
        INSERT INTO team_invites (id, team_id, email, role, token, invited_by,
                                  expires_at, accepted, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING *
    """
    logger.info("Invite created: team=%s email=%s role=%s", invite.team_id, invite.email, invite.role.name)
    return invite.model_dump()


async def _db_get_invite_by_token(token: str) -> Optional[dict]:
    """Fetch invite by token.

    Real SQL:
        SELECT * FROM team_invites
        WHERE token = $1 AND accepted = false AND expires_at > NOW()
    """
    logger.debug("_db_get_invite_by_token: token=%s...", token[:8])
    return None



async def _db_get_brand_kit(team_id: str) -> Optional[dict]:
    """Fetch brand kit for a team.

    Real SQL:
        SELECT * FROM brand_kits WHERE team_id = $1
    """
    logger.debug("_db_get_brand_kit: team=%s", team_id)
    return None


async def _db_upsert_brand_kit(brand_kit: BrandKit) -> dict:
    """Insert or update brand kit for a team.

    Real SQL:
        INSERT INTO brand_kits (team_id, logo_url, primary_color, secondary_color,
                                accent_color, background_color, default_font,
                                heading_font, watermark_url, watermark_position,
                                watermark_opacity, intro_template_id, outro_template_id,
                                updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        ON CONFLICT (team_id)
        DO UPDATE SET logo_url = $2, primary_color = $3, secondary_color = $4,
                      accent_color = $5, background_color = $6, default_font = $7,
                      heading_font = $8, watermark_url = $9, watermark_position = $10,
                      watermark_opacity = $11, intro_template_id = $12,
                      outro_template_id = $13, updated_at = $14
        RETURNING *
    """
    logger.info("Brand kit upserted for team=%s", brand_kit.team_id)
    return brand_kit.model_dump()


async def _db_get_team_projects(team_id: str, page: int = 1, per_page: int = 20) -> tuple:
    """Fetch all projects belonging to team members (shared library).

    Real SQL:
        SELECT p.*, u.name AS owner_name,
               COALESCE(a.status, NULL) AS approval_status
        FROM projects p
        JOIN team_memberships tm ON tm.user_id = p.user_id
        LEFT JOIN project_approvals a ON a.project_id = p.id
        WHERE tm.team_id = $1
        ORDER BY p.updated_at DESC
        LIMIT $2 OFFSET $3

    Count query:
        SELECT COUNT(*) FROM projects p
        JOIN team_memberships tm ON tm.user_id = p.user_id
        WHERE tm.team_id = $1
    """
    logger.debug("_db_get_team_projects: team=%s page=%d", team_id, page)
    return ([], 0)



async def _db_submit_for_approval(approval: ApprovalStatus) -> dict:
    """Insert approval record for a project.

    Real SQL:
        INSERT INTO project_approvals (project_id, team_id, submitted_by,
                                       submitted_at, status)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (project_id)
        DO UPDATE SET submitted_by = $3, submitted_at = $4, status = 'pending',
                      reviewed_by = NULL, reviewed_at = NULL, review_notes = NULL
        RETURNING *
    """
    logger.info("Approval submitted: project=%s by=%s", approval.project_id, approval.submitted_by)
    return approval.model_dump()


async def _db_update_approval(
    project_id: str, status: str, reviewed_by: str, notes: Optional[str]
) -> dict:
    """Update approval decision.

    Real SQL:
        UPDATE project_approvals
        SET status = $2, reviewed_by = $3, reviewed_at = NOW(), review_notes = $4
        WHERE project_id = $1
        RETURNING *
    """
    logger.info("Approval updated: project=%s status=%s by=%s", project_id, status, reviewed_by)
    return {"project_id": project_id, "status": status, "reviewed_by": reviewed_by}


async def _db_get_approval(project_id: str) -> Optional[dict]:
    """Fetch approval status for a project.

    Real SQL:
        SELECT * FROM project_approvals WHERE project_id = $1
    """
    logger.debug("_db_get_approval: project=%s", project_id)
    return None


async def _db_log_activity(entry: ActivityLogEntry) -> dict:
    """Insert activity log entry.

    Real SQL:
        INSERT INTO team_activity_log (id, team_id, user_id, user_name, action,
                                       resource_type, resource_id, details, timestamp)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING *
    """
    logger.info("Activity logged: team=%s action=%s by=%s", entry.team_id, entry.action, entry.user_id)
    return entry.model_dump()



async def _db_get_activity_log(
    team_id: str, page: int = 1, per_page: int = 50
) -> tuple:
    """Fetch paginated activity log for a team.

    Real SQL:
        SELECT * FROM team_activity_log
        WHERE team_id = $1
        ORDER BY timestamp DESC
        LIMIT $2 OFFSET $3

    Count query:
        SELECT COUNT(*) FROM team_activity_log WHERE team_id = $1
    """
    logger.debug("_db_get_activity_log: team=%s page=%d", team_id, page)
    return ([], 0)


async def _db_get_member_count(team_id: str) -> int:
    """Get count of team members (for seat billing).

    Real SQL:
        SELECT COUNT(*) FROM team_memberships WHERE team_id = $1
    """
    logger.debug("_db_get_member_count: team=%s", team_id)
    return 0


async def _update_seat_billing(team_id: str, seat_count: int) -> None:
    """Update Stripe subscription quantity for per-seat billing (17.9).

    Per-seat pricing: $10/month per additional team member beyond the owner.
    Billable seats = total_members - 1 (owner is included in base plan).

    Real implementation:
        team = await _db_get_team(team_id)
        stripe.SubscriptionItem.modify(
            team["stripe_seat_subscription_item_id"],
            quantity=max(0, seat_count - 1),  # owner doesn't count
            proration_behavior="always_invoice",
        )

    Environment variable needed:
        STRIPE_PRICE_TEAM_SEAT — Stripe Price ID for $10/mo per-seat item

    TODO: Wire up real Stripe metered/quantity billing when Stripe is configured.
    """
    billable_seats = max(0, seat_count - 1)
    logger.info(
        "Seat billing updated: team=%s total_members=%d billable_seats=%d cost=$%d/mo",
        team_id, seat_count, billable_seats, billable_seats * 10,
    )



async def _send_invite_email(email: str, team_name: str, invite_token: str, inviter_name: str) -> None:
    """Send invitation email to prospective team member (17.2 placeholder).

    Real implementation would use SendGrid, Resend, or SES:
        await email_client.send(
            to=email,
            subject=f"You've been invited to join {team_name}",
            template="team_invite",
            context={
                "team_name": team_name,
                "inviter_name": inviter_name,
                "accept_url": f"{APP_BASE_URL}/teams/invite/accept?token={invite_token}",
                "expires_in": "7 days",
            }
        )

    TODO: Replace with real email sending (Resend/SendGrid/SES) in production.
    """
    import os
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:3000")
    accept_url = f"{APP_BASE_URL}/teams/invite/accept?token={invite_token}"
    logger.info(
        "INVITE EMAIL (placeholder): to=%s team=%s inviter=%s url=%s",
        email, team_name, inviter_name, accept_url,
    )



# ---------------------------------------------------------------------------
# 17.1 — Create Team/Workspace
# ---------------------------------------------------------------------------


@router.post("", response_model=CreateTeamResponse, status_code=201)
async def create_team(
    body: CreateTeamRequest,
    user: dict = Depends(get_current_user),
):
    """Create a new team/workspace.

    One team = one billing account. The creating user becomes the Owner.
    Teams require a Business plan for full team features.

    Args:
        body: Team name and slug.
        user: Authenticated user (becomes owner).

    Returns:
        Created team and owner membership.
    """
    team = Team(
        name=body.name,
        slug=body.slug,
        owner_id=user["id"],
    )

    # Persist team
    await _db_create_team(team)

    # Create owner membership
    membership = TeamMembership(
        team_id=team.id,
        user_id=user["id"],
        role=TeamRole.OWNER,
    )
    await _db_create_membership(membership)

    # Log activity
    await _db_log_activity(ActivityLogEntry(
        team_id=team.id,
        user_id=user["id"],
        user_name=user.get("name"),
        action="team_created",
        resource_type="team",
        resource_id=team.id,
        details={"team_name": team.name},
    ))

    logger.info("Team created: id=%s name=%s owner=%s", team.id, team.name, user["id"])

    return CreateTeamResponse(team=team, membership=membership)



# ---------------------------------------------------------------------------
# 17.2 — Invite Team Members by Email
# ---------------------------------------------------------------------------


@router.post("/{team_id}/invite", response_model=InviteMemberResponse)
async def invite_member(
    team_id: str,
    body: InviteMemberRequest,
    user: dict = Depends(get_current_user),
    _perm: None = Depends(require_role(TeamRole.ADMIN)),
):
    """Invite a new member to the team by email.

    Generates a unique invite token and sends an email (placeholder).
    Only Admins and Owners can invite new members. The invite expires
    after 7 days if not accepted.

    Args:
        team_id: Target team ID.
        body: Email and role for the invitee.
        user: Authenticated user (must be Admin+).

    Returns:
        Invite details including expiration.

    Raises:
        403: If user lacks Admin role.
        400: If inviting with a role higher than your own.
        404: If team not found.
    """
    # Cannot invite someone with a higher role than yourself
    inviter_membership = await _db_get_membership(team_id, user["id"])
    if inviter_membership:
        inviter_role = TeamRole(inviter_membership["role"])
        if body.role > inviter_role:
            raise HTTPException(
                status_code=400,
                detail="Cannot invite with a role higher than your own.",
            )

    # Cannot invite as OWNER (there can only be one)
    if body.role == TeamRole.OWNER:
        raise HTTPException(
            status_code=400,
            detail="Cannot invite as Owner. Use ownership transfer instead.",
        )

    # Create invite
    invite = TeamInvite(
        team_id=team_id,
        email=body.email,
        role=body.role,
        invited_by=user["id"],
    )
    await _db_create_invite(invite)

    # Send invitation email (placeholder)
    team = await _db_get_team(team_id)
    team_name = team["name"] if team else "Unknown Team"
    await _send_invite_email(body.email, team_name, invite.token, user.get("name", "A teammate"))

    # Log activity
    await _db_log_activity(ActivityLogEntry(
        team_id=team_id,
        user_id=user["id"],
        user_name=user.get("name"),
        action="member_invited",
        resource_type="invite",
        resource_id=invite.id,
        details={"email": body.email, "role": body.role.name},
    ))

    # Update seat billing (17.9)
    member_count = await _db_get_member_count(team_id)
    await _update_seat_billing(team_id, member_count + 1)

    return InviteMemberResponse(
        invite_id=invite.id,
        email=body.email,
        role=body.role,
        expires_at=invite.expires_at.isoformat(),
    )



# ---------------------------------------------------------------------------
# 17.4 — Shared Project Library
# ---------------------------------------------------------------------------


@router.get("/{team_id}/projects")
async def get_team_projects(
    team_id: str,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    _perm: None = Depends(require_role(TeamRole.VIEWER)),
):
    """Get shared project library for the team.

    All team members can view all team projects. Projects are collected
    from all members in the team workspace.

    Args:
        team_id: Team ID.
        page: Pagination page number.
        per_page: Items per page.
        user: Authenticated user (must be team member).

    Returns:
        Paginated list of team projects with approval status.
    """
    projects, total = await _db_get_team_projects(team_id, page, per_page)

    return {
        "projects": projects,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
    }



# ---------------------------------------------------------------------------
# 17.5 — Brand Kit: Upload Logo, Set Brand Colors, Default Fonts
# ---------------------------------------------------------------------------


@router.put("/{team_id}/brand-kit")
async def update_brand_kit(
    team_id: str,
    body: UpdateBrandKitRequest,
    user: dict = Depends(get_current_user),
    _perm: None = Depends(require_role(TeamRole.ADMIN)),
):
    """Update the team's brand kit.

    Brand kit includes logo, colors, fonts, watermark settings, and
    default intro/outro templates. Only Admins and Owners can modify.

    Args:
        team_id: Team ID.
        body: Brand kit fields to update (partial update supported).
        user: Authenticated user (must be Admin+).

    Returns:
        Updated brand kit.
    """
    # Fetch existing brand kit or create new
    existing = await _db_get_brand_kit(team_id)

    # Build brand kit, merging with existing values
    brand_kit_data = {
        "team_id": team_id,
        "updated_at": datetime.now(timezone.utc),
    }

    # Merge: use new value if provided, else keep existing
    fields = [
        "logo_url", "primary_color", "secondary_color", "accent_color",
        "background_color", "default_font", "heading_font", "watermark_url",
        "watermark_position", "watermark_opacity", "intro_template_id",
        "outro_template_id",
    ]
    for field in fields:
        new_val = getattr(body, field, None)
        if new_val is not None:
            brand_kit_data[field] = new_val
        elif existing and field in existing:
            brand_kit_data[field] = existing[field]

    brand_kit = BrandKit(**brand_kit_data)
    result = await _db_upsert_brand_kit(brand_kit)

    # Log activity
    await _db_log_activity(ActivityLogEntry(
        team_id=team_id,
        user_id=user["id"],
        user_name=user.get("name"),
        action="brand_kit_updated",
        resource_type="brand_kit",
        resource_id=team_id,
        details={"updated_fields": [f for f in fields if getattr(body, f, None) is not None]},
    ))

    return {"brand_kit": result, "message": "Brand kit updated successfully"}



# ---------------------------------------------------------------------------
# 17.6 — Apply Brand Kit Automatically to Renders
# ---------------------------------------------------------------------------


@router.post("/{team_id}/projects/{project_id}/apply-brand")
async def apply_brand_kit(
    team_id: str,
    project_id: str,
    body: ApplyBrandRequest,
    user: dict = Depends(get_current_user),
    _perm: None = Depends(require_role(TeamRole.EDITOR)),
):
    """Apply the team's brand kit to a specific project's renders.

    This updates the project's rendering configuration to use brand colors,
    fonts, watermark, and intro/outro templates from the team's brand kit.
    The next render will incorporate these brand elements.

    Args:
        team_id: Team ID.
        project_id: Target project ID.
        body: Which brand elements to apply.
        user: Authenticated user (must be Editor+).

    Returns:
        Updated project configuration showing applied brand elements.
    """
    brand_kit = await _db_get_brand_kit(team_id)
    if not brand_kit:
        raise HTTPException(
            status_code=404,
            detail="No brand kit configured for this team. Set one up first.",
        )

    # Build the brand overlay config to apply to the project
    applied = {}

    if body.apply_colors:
        applied["subtitle_color"] = brand_kit.get("primary_color", "#6366f1")
        applied["subtitle_highlight_color"] = brand_kit.get("accent_color", "#f59e0b")
        applied["background_color"] = brand_kit.get("background_color", "#000000")

    if body.apply_font:
        applied["font_family"] = brand_kit.get("default_font", "Inter")
        if brand_kit.get("heading_font"):
            applied["heading_font"] = brand_kit["heading_font"]

    if body.apply_watermark and brand_kit.get("watermark_url"):
        applied["watermark_url"] = brand_kit["watermark_url"]
        applied["watermark_position"] = brand_kit.get("watermark_position", "bottom-right")
        applied["watermark_opacity"] = brand_kit.get("watermark_opacity", 0.7)

    if body.apply_intro_outro:
        if brand_kit.get("intro_template_id"):
            applied["intro_template_id"] = brand_kit["intro_template_id"]
        if brand_kit.get("outro_template_id"):
            applied["outro_template_id"] = brand_kit["outro_template_id"]

    # TODO: In production, update project.config_json with applied brand settings:
    #   UPDATE projects SET config_json = config_json || $2, updated_at = NOW()
    #   WHERE id = $1

    # Log activity
    await _db_log_activity(ActivityLogEntry(
        team_id=team_id,
        user_id=user["id"],
        user_name=user.get("name"),
        action="brand_kit_applied",
        resource_type="project",
        resource_id=project_id,
        details={"applied_elements": applied},
    ))

    return {
        "project_id": project_id,
        "brand_applied": applied,
        "message": "Brand kit applied to project. Next render will use brand settings.",
    }



# ---------------------------------------------------------------------------
# 17.7 — Approval Workflow (Editor submits -> Admin approves -> Publish)
# ---------------------------------------------------------------------------


@router.post("/{team_id}/projects/{project_id}/submit-for-approval")
async def submit_for_approval(
    team_id: str,
    project_id: str,
    body: SubmitForApprovalRequest,
    user: dict = Depends(get_current_user),
    _perm: None = Depends(require_role(TeamRole.EDITOR)),
):
    """Submit a project for admin approval before publishing.

    Editors create content and submit for review. Admins/Owners review
    and approve or reject. Only approved projects can be published to
    connected social platforms.

    Args:
        team_id: Team ID.
        project_id: Project to submit.
        body: Optional notes for the reviewer.
        user: Authenticated user (must be Editor+).

    Returns:
        Approval submission confirmation.
    """
    approval = ApprovalStatus(
        project_id=project_id,
        team_id=team_id,
        submitted_by=user["id"],
        status="pending",
    )
    await _db_submit_for_approval(approval)

    # Log activity
    await _db_log_activity(ActivityLogEntry(
        team_id=team_id,
        user_id=user["id"],
        user_name=user.get("name"),
        action="project_submitted_for_approval",
        resource_type="project",
        resource_id=project_id,
        details={"notes": body.notes},
    ))

    return {
        "project_id": project_id,
        "status": "pending",
        "submitted_by": user["id"],
        "submitted_at": approval.submitted_at.isoformat(),
        "message": "Project submitted for approval. An admin will review it shortly.",
    }


@router.post("/{team_id}/projects/{project_id}/approve")
async def approve_project(
    team_id: str,
    project_id: str,
    body: ApproveProjectRequest,
    user: dict = Depends(get_current_user),
    _perm: None = Depends(require_role(TeamRole.ADMIN)),
):
    """Approve or reject a submitted project.

    Only Admins and Owners can approve/reject. Approved projects become
    eligible for publishing to connected social media platforms.

    Args:
        team_id: Team ID.
        project_id: Project to review.
        body: Decision (approved/rejected) and optional notes.
        user: Authenticated user (must be Admin+).

    Returns:
        Updated approval status.

    Raises:
        404: If no pending approval found for this project.
    """
    existing = await _db_get_approval(project_id)
    if not existing:
        raise HTTPException(
            status_code=404,
            detail="No pending approval found for this project.",
        )

    if existing.get("status") != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Project already {existing['status']}. Cannot review again.",
        )

    result = await _db_update_approval(
        project_id=project_id,
        status=body.decision,
        reviewed_by=user["id"],
        notes=body.notes,
    )

    # Log activity
    await _db_log_activity(ActivityLogEntry(
        team_id=team_id,
        user_id=user["id"],
        user_name=user.get("name"),
        action=f"project_{body.decision}",
        resource_type="project",
        resource_id=project_id,
        details={"notes": body.notes, "submitted_by": existing.get("submitted_by")},
    ))

    return {
        "project_id": project_id,
        "status": body.decision,
        "reviewed_by": user["id"],
        "notes": body.notes,
        "message": f"Project {body.decision}."
        + (" It can now be published." if body.decision == "approved" else ""),
    }



# ---------------------------------------------------------------------------
# 17.8 — Activity Log (who did what, when)
# ---------------------------------------------------------------------------


@router.get("/{team_id}/activity", response_model=ActivityLogResponse)
async def get_activity_log(
    team_id: str,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    user: dict = Depends(get_current_user),
    _perm: None = Depends(require_role(TeamRole.VIEWER)),
):
    """Get the team's activity log.

    Returns a chronological audit trail of all actions taken within
    the team workspace: member changes, project updates, approvals,
    brand kit modifications, etc.

    All team members can view the activity log.

    Args:
        team_id: Team ID.
        page: Pagination page number.
        per_page: Items per page (max 200).
        user: Authenticated user (must be team member).

    Returns:
        Paginated list of activity log entries.
    """
    entries, total = await _db_get_activity_log(team_id, page, per_page)

    # Convert raw dicts to ActivityLogEntry models
    log_entries = [ActivityLogEntry(**e) if isinstance(e, dict) else e for e in entries]

    return ActivityLogResponse(
        entries=log_entries,
        total=total,
        page=page,
        per_page=per_page,
    )



# ---------------------------------------------------------------------------
# 17.9 — Per-Seat Billing Integration Notes
# ---------------------------------------------------------------------------
#
# BILLING MODEL: $10/month per additional team member (beyond the owner).
#
# Implementation plan for Stripe integration:
#
# 1. Create a Stripe Price with usage_type="licensed" and unit_amount=1000
#    (=$10.00) for the team seat product.
#    Environment variable: STRIPE_PRICE_TEAM_SEAT
#
# 2. When a team is created, add a subscription item for team seats
#    with quantity=0 (owner is free).
#
# 3. On member invite acceptance:
#    - Increment quantity on the seat subscription item
#    - stripe.SubscriptionItem.modify(si_id, quantity=new_count)
#    - Stripe handles proration automatically
#
# 4. On member removal:
#    - Decrement quantity on the seat subscription item
#    - Stripe credits the prorated amount
#
# 5. Billing cycle:
#    - Seats are billed on the same cycle as the team's base plan
#    - Invoice shows: "Business Plan: $39/mo" + "Team Seats (3): $30/mo"
#    - Total: $69/mo for a team of 4 (1 owner + 3 members)
#
# 6. Seat limits by plan:
#    - Business plan: up to 50 seats
#    - Pro plan: up to 5 seats (limited team features)
#    - Free plan: no team features
#
# 7. The _update_seat_billing() function above is the integration point.
#    It should be called on every membership change.
#
# TODO: Implement real Stripe calls once STRIPE_PRICE_TEAM_SEAT is configured.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Accept Invite Endpoint (bonus — completes the invite flow)
# ---------------------------------------------------------------------------


@router.post("/invite/accept")
async def accept_invite(
    token: str = Query(..., description="Invite token from email link"),
    user: dict = Depends(get_current_user),
):
    """Accept a team invitation using the token from the invite email.

    Validates the token, checks expiration, creates the membership,
    and updates seat billing.

    Args:
        token: Invite token (from query parameter).
        user: Authenticated user accepting the invite.

    Returns:
        Membership details on success.

    Raises:
        404: If token is invalid or expired.
        400: If already a member.
    """
    invite = await _db_get_invite_by_token(token)

    if not invite:
        raise HTTPException(
            status_code=404,
            detail="Invalid or expired invitation token.",
        )

    # Check if already a member
    existing = await _db_get_membership(invite["team_id"], user["id"])
    if existing:
        raise HTTPException(
            status_code=400,
            detail="You are already a member of this team.",
        )

    # Create membership
    membership = TeamMembership(
        team_id=invite["team_id"],
        user_id=user["id"],
        role=TeamRole(invite["role"]),
        invited_by=invite["invited_by"],
    )
    await _db_create_membership(membership)

    # TODO: Mark invite as accepted in DB
    # UPDATE team_invites SET accepted = true WHERE id = $1

    # Update seat billing (17.9)
    member_count = await _db_get_member_count(invite["team_id"])
    await _update_seat_billing(invite["team_id"], member_count + 1)

    # Log activity
    await _db_log_activity(ActivityLogEntry(
        team_id=invite["team_id"],
        user_id=user["id"],
        user_name=user.get("name"),
        action="member_joined",
        resource_type="member",
        resource_id=user["id"],
        details={"role": membership.role.name, "invited_by": invite["invited_by"]},
    ))

    return {
        "team_id": invite["team_id"],
        "role": membership.role.name,
        "joined_at": membership.joined_at.isoformat(),
        "message": "Successfully joined the team!",
    }
