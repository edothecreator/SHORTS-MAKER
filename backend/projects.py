"""Project History & Management API for Shorts Engine Studio.

Production Task 13: Complete project management system with CRUD operations,
search, favorites, and storage usage tracking.

Sub-tasks covered:
  13.1  Save processing job as a "project" in database
  13.3  Re-open completed project (view results, get download URLs)
  13.4  Re-process with different settings
  13.5  Delete project (remove from DB + trigger storage cleanup)
  13.6  Search projects by title/date with pagination
  13.7  Favorite/star projects
  13.8  Show storage usage per user (X GB of Y GB used)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ProjectStatus(str, Enum):
    """Status of a project throughout its lifecycle."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REPROCESSING = "reprocessing"


class SortOption(str, Enum):
    """Sort options for project listing."""
    NEWEST = "newest"
    OLDEST = "oldest"
    FAVORITES = "favorites"
    TITLE_ASC = "title_asc"
    TITLE_DESC = "title_desc"


# ---------------------------------------------------------------------------
# Pydantic Models — Request Schemas
# ---------------------------------------------------------------------------


class ProjectCreateRequest(BaseModel):
    """Request body for creating a new project (13.1)."""
    title: str = Field(..., min_length=1, max_length=200, description="Project title")
    config: dict = Field(default_factory=dict, description="Processing configuration JSON")
    video_filename: Optional[str] = Field(None, description="Original uploaded video filename")
    video_url: Optional[str] = Field(None, description="Source video URL (if from URL input)")


class ProjectReprocessRequest(BaseModel):
    """Request body for re-processing a project with different settings (13.4)."""
    config: dict = Field(..., description="New processing configuration")
    subtitle_style: Optional[str] = Field(None, description="New subtitle style template")
    clip_count: Optional[int] = Field(None, ge=1, le=20, description="Number of clips to generate")
    resolution: Optional[str] = Field(None, description="Target resolution (720p, 1080p, 4K)")


# ---------------------------------------------------------------------------
# Pydantic Models — Response Schemas
# ---------------------------------------------------------------------------


class RenderResult(BaseModel):
    """A single rendered clip result within a project."""
    id: str
    segment_index: int
    title: str
    hook: Optional[str] = None
    start_sec: float
    end_sec: float
    output_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    virality_score: Optional[int] = None
    created_at: str


class ProjectResponse(BaseModel):
    """Full project detail response (13.3)."""
    id: str
    user_id: str
    title: str
    video_filename: Optional[str] = None
    config: dict = Field(default_factory=dict)
    status: str
    is_favorite: bool = False
    storage_bytes: int = 0
    created_at: str
    updated_at: str
    renders: List[RenderResult] = Field(default_factory=list)


class ProjectSummary(BaseModel):
    """Lightweight project info for list views (13.2, 13.6)."""
    id: str
    title: str
    status: str
    is_favorite: bool = False
    thumbnail_url: Optional[str] = None
    clip_count: int = 0
    created_at: str
    updated_at: str


class ProjectListResponse(BaseModel):
    """Paginated list of projects (13.6)."""
    projects: List[ProjectSummary]
    total: int
    page: int
    page_size: int
    has_next: bool


class StorageUsageResponse(BaseModel):
    """Storage usage info per user (13.8)."""
    used_bytes: int
    used_gb: float
    total_bytes: int
    total_gb: float
    percentage: float
    project_count: int
    render_count: int


class FavoriteResponse(BaseModel):
    """Response after toggling favorite status (13.7)."""
    id: str
    is_favorite: bool


class DeleteResponse(BaseModel):
    """Response after deleting a project (13.5)."""
    id: str
    deleted: bool
    storage_freed_bytes: int


# ---------------------------------------------------------------------------
# Database Helpers (placeholder — same pattern as billing.py and auth.py)
# ---------------------------------------------------------------------------


async def _db_create_project(
    user_id: str, title: str, config: dict,
    video_filename: Optional[str] = None, video_url: Optional[str] = None
) -> dict:
    """Insert a new project record into the database.

    Real query:
        INSERT INTO projects (id, user_id, title, config_json, video_filename,
                              video_url, status, is_favorite, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, 'pending', false, NOW(), NOW())
        RETURNING *
    """
    # TODO: Replace with real asyncpg query
    # from backend.db.connection import get_pool
    # pool = await get_pool()
    # async with pool.acquire() as conn:
    #     row = await conn.fetchrow(query, project_id, user_id, title, ...)
    #     return dict(row)
    project_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    logger.info("Created project %s for user %s", project_id, user_id)
    return {
        "id": project_id,
        "user_id": user_id,
        "title": title,
        "video_filename": video_filename,
        "config": config,
        "status": ProjectStatus.PENDING.value,
        "is_favorite": False,
        "storage_bytes": 0,
        "created_at": now,
        "updated_at": now,
        "renders": [],
    }


async def _db_get_project(project_id: str, user_id: str) -> Optional[dict]:
    """Fetch a single project by ID, scoped to the user.

    Real query:
        SELECT p.*,
               COALESCE(json_agg(
                   json_build_object(
                       'id', r.id, 'segment_index', r.segment_index,
                       'title', r.title, 'hook', r.hook,
                       'start_sec', r.start_sec, 'end_sec', r.end_sec,
                       'output_url', r.output_url, 'thumbnail_url', r.thumbnail_url,
                       'virality_score', r.virality_score, 'created_at', r.created_at
                   )
               ) FILTER (WHERE r.id IS NOT NULL), '[]') AS renders
        FROM projects p
        LEFT JOIN renders r ON r.project_id = p.id
        WHERE p.id = $1 AND p.user_id = $2
        GROUP BY p.id
    """
    # TODO: Replace with real asyncpg query
    logger.debug("Fetching project %s for user %s", project_id, user_id)
    return None


async def _db_list_projects(
    user_id: str,
    search: Optional[str] = None,
    sort: SortOption = SortOption.NEWEST,
    page: int = 1,
    page_size: int = 12,
) -> tuple[list[dict], int]:
    """List projects for a user with search, sort, and pagination.

    Real query (dynamic based on params):
        SELECT p.id, p.title, p.status, p.is_favorite, p.created_at, p.updated_at,
               (SELECT r.thumbnail_url FROM renders r
                WHERE r.project_id = p.id ORDER BY r.segment_index LIMIT 1) AS thumbnail_url,
               (SELECT COUNT(*) FROM renders r WHERE r.project_id = p.id) AS clip_count
        FROM projects p
        WHERE p.user_id = $1
          AND ($2::text IS NULL OR p.title ILIKE '%' || $2 || '%')
        ORDER BY
          CASE WHEN $3 = 'newest' THEN p.created_at END DESC,
          CASE WHEN $3 = 'oldest' THEN p.created_at END ASC,
          CASE WHEN $3 = 'favorites' THEN p.is_favorite END DESC,
          CASE WHEN $3 = 'title_asc' THEN p.title END ASC,
          CASE WHEN $3 = 'title_desc' THEN p.title END DESC
        LIMIT $4 OFFSET $5

    Count query:
        SELECT COUNT(*) FROM projects p
        WHERE p.user_id = $1
          AND ($2::text IS NULL OR p.title ILIKE '%' || $2 || '%')
    """
    # TODO: Replace with real asyncpg query
    logger.debug(
        "Listing projects for user %s (search=%s, sort=%s, page=%d)",
        user_id, search, sort, page,
    )
    return [], 0


async def _db_delete_project(project_id: str, user_id: str) -> Optional[int]:
    """Delete a project and its associated renders from the database.

    Real queries (transaction):
        -- Get storage to free
        SELECT COALESCE(SUM(r.file_size_bytes), 0) + COALESCE(p.source_file_size, 0)
        FROM projects p
        LEFT JOIN renders r ON r.project_id = p.id
        WHERE p.id = $1 AND p.user_id = $2

        -- Delete renders
        DELETE FROM renders WHERE project_id = $1

        -- Delete project
        DELETE FROM projects WHERE id = $1 AND user_id = $2
    """
    # TODO: Replace with real asyncpg query (use transaction)
    logger.info("Deleted project %s for user %s", project_id, user_id)
    return 0


async def _db_toggle_favorite(project_id: str, user_id: str) -> Optional[bool]:
    """Toggle the is_favorite flag on a project.

    Real query:
        UPDATE projects
        SET is_favorite = NOT is_favorite, updated_at = NOW()
        WHERE id = $1 AND user_id = $2
        RETURNING is_favorite
    """
    # TODO: Replace with real asyncpg query
    logger.info("Toggled favorite on project %s for user %s", project_id, user_id)
    return True


async def _db_get_storage_usage(user_id: str) -> dict:
    """Calculate total storage usage for a user.

    Real query:
        SELECT
            COALESCE(SUM(r.file_size_bytes), 0) AS render_bytes,
            COALESCE(SUM(p.source_file_size), 0) AS source_bytes,
            COUNT(DISTINCT p.id) AS project_count,
            COUNT(r.id) AS render_count
        FROM projects p
        LEFT JOIN renders r ON r.project_id = p.id
        WHERE p.user_id = $1
    """
    # TODO: Replace with real asyncpg query
    logger.debug("Getting storage usage for user %s", user_id)
    return {
        "render_bytes": 0,
        "source_bytes": 0,
        "project_count": 0,
        "render_count": 0,
    }


async def _db_update_project_for_reprocess(
    project_id: str, user_id: str, config: dict
) -> Optional[dict]:
    """Update project config and set status to reprocessing.

    Real query:
        UPDATE projects
        SET config_json = $3, status = 'reprocessing', updated_at = NOW()
        WHERE id = $1 AND user_id = $2
        RETURNING *
    """
    # TODO: Replace with real asyncpg query
    logger.info("Reprocessing project %s for user %s", project_id, user_id)
    return None


# ---------------------------------------------------------------------------
# Storage Cleanup Helper
# ---------------------------------------------------------------------------


async def _trigger_storage_cleanup(project_id: str, user_id: str) -> int:
    """Trigger deletion of stored files (source video + rendered clips) from
    object storage (S3/R2) when a project is deleted.

    In production, this would:
      1. List all objects with prefix: renders/{user_id}/{project_id}/
      2. List source video: sources/{user_id}/{project_id}/
      3. Delete all matching objects
      4. Return total bytes freed

    Real implementation:
        import boto3
        s3 = boto3.client('s3', ...)
        # Delete rendered clips
        objects = s3.list_objects_v2(
            Bucket=RENDER_BUCKET,
            Prefix=f"renders/{user_id}/{project_id}/"
        )
        if objects.get('Contents'):
            s3.delete_objects(Bucket=RENDER_BUCKET, Delete={
                'Objects': [{'Key': obj['Key']} for obj in objects['Contents']]
            })
        # Delete source video
        s3.delete_objects(Bucket=SOURCE_BUCKET, Delete={
            'Objects': [{'Key': f"sources/{user_id}/{project_id}/source.mp4"}]
        })
    """
    # TODO: Replace with real S3/R2 deletion
    logger.info(
        "Storage cleanup triggered for project %s (user %s)", project_id, user_id
    )
    return 0


# ---------------------------------------------------------------------------
# Storage Limits per Plan
# ---------------------------------------------------------------------------

# Storage quotas in bytes (per user)
STORAGE_LIMITS = {
    "free": 5 * 1024 * 1024 * 1024,         # 5 GB
    "pro": 50 * 1024 * 1024 * 1024,          # 50 GB
    "business": 500 * 1024 * 1024 * 1024,    # 500 GB
}


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreateRequest,
    user: dict = Depends(get_current_user),
):
    """13.1 — Save a processing job as a project in the database.

    Creates a new project record with the user's ID, title, processing config,
    and initial 'pending' status. This is called when a user starts a new
    video processing job.
    """
    user_id = user["id"]

    project = await _db_create_project(
        user_id=user_id,
        title=body.title,
        config=body.config,
        video_filename=body.video_filename,
        video_url=body.video_url,
    )

    logger.info("Project created: id=%s user=%s title=%s", project["id"], user_id, body.title)

    return ProjectResponse(**project)


@router.get("/storage-usage", response_model=StorageUsageResponse)
async def get_storage_usage(
    user: dict = Depends(get_current_user),
):
    """13.8 — Show storage usage per user (X GB of Y GB used).

    Returns the user's current storage consumption and their plan's quota.
    Includes breakdown by project count and render count.
    """
    user_id = user["id"]
    plan = user.get("plan", "free")

    usage = await _db_get_storage_usage(user_id)

    total_used = usage["render_bytes"] + usage["source_bytes"]
    total_limit = STORAGE_LIMITS.get(plan, STORAGE_LIMITS["free"])

    used_gb = round(total_used / (1024 * 1024 * 1024), 2)
    total_gb = round(total_limit / (1024 * 1024 * 1024), 2)
    percentage = round((total_used / total_limit) * 100, 1) if total_limit > 0 else 0.0

    return StorageUsageResponse(
        used_bytes=total_used,
        used_gb=used_gb,
        total_bytes=total_limit,
        total_gb=total_gb,
        percentage=percentage,
        project_count=usage["project_count"],
        render_count=usage["render_count"],
    )


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    search: Optional[str] = Query(None, max_length=100, description="Search by title"),
    sort: SortOption = Query(SortOption.NEWEST, description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(12, ge=1, le=50, description="Items per page"),
    user: dict = Depends(get_current_user),
):
    """13.6 — Search and list projects with pagination.

    Supports searching by title, sorting by date/favorites/title, and
    pagination. Returns lightweight project summaries for grid view.
    """
    user_id = user["id"]

    projects, total = await _db_list_projects(
        user_id=user_id,
        search=search,
        sort=sort,
        page=page,
        page_size=page_size,
    )

    summaries = [
        ProjectSummary(
            id=p["id"],
            title=p["title"],
            status=p["status"],
            is_favorite=p.get("is_favorite", False),
            thumbnail_url=p.get("thumbnail_url"),
            clip_count=p.get("clip_count", 0),
            created_at=p["created_at"],
            updated_at=p["updated_at"],
        )
        for p in projects
    ]

    has_next = (page * page_size) < total

    return ProjectListResponse(
        projects=summaries,
        total=total,
        page=page,
        page_size=page_size,
        has_next=has_next,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """13.3 — Re-open a completed project.

    Returns full project details including all rendered clips with their
    download URLs and thumbnails. Allows users to view results and
    re-download clips from a previously completed job.
    """
    user_id = user["id"]

    project = await _db_get_project(project_id, user_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectResponse(**project)


@router.post("/{project_id}/reprocess", response_model=ProjectResponse)
async def reprocess_project(
    project_id: str,
    body: ProjectReprocessRequest,
    user: dict = Depends(get_current_user),
):
    """13.4 — Re-process a project with different settings.

    Allows users to re-run the processing pipeline with new configuration
    (different subtitle style, clip count, resolution, etc.) without
    re-uploading the video. Sets status to 'reprocessing' and enqueues
    a new render job.
    """
    user_id = user["id"]

    # Verify project exists and belongs to user
    existing = await _db_get_project(project_id, user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Project not found")

    # Merge new config with existing config
    new_config = {**existing.get("config", {}), **body.config}
    if body.subtitle_style:
        new_config["subtitle_style"] = body.subtitle_style
    if body.clip_count:
        new_config["clip_count"] = body.clip_count
    if body.resolution:
        new_config["resolution"] = body.resolution

    # Update project in database
    updated = await _db_update_project_for_reprocess(project_id, user_id, new_config)

    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update project for reprocessing")

    # TODO: Enqueue new render job to the worker queue
    # from backend.worker.queue import enqueue_render_job
    # await enqueue_render_job(project_id=project_id, config=new_config, priority="normal")

    logger.info("Reprocess triggered: project=%s user=%s", project_id, user_id)

    return ProjectResponse(**updated)


@router.delete("/{project_id}", response_model=DeleteResponse)
async def delete_project(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """13.5 — Delete a project.

    Removes the project from the database and triggers cleanup of all
    associated files in object storage (source video + rendered clips).
    This operation is irreversible.
    """
    user_id = user["id"]

    # Verify project exists and belongs to user
    existing = await _db_get_project(project_id, user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Project not found")

    # Trigger storage cleanup (delete files from S3/R2)
    storage_freed = await _trigger_storage_cleanup(project_id, user_id)

    # Delete from database (cascades to renders)
    deleted_bytes = await _db_delete_project(project_id, user_id)

    total_freed = storage_freed + (deleted_bytes or 0)

    logger.info(
        "Project deleted: id=%s user=%s freed=%d bytes",
        project_id, user_id, total_freed,
    )

    return DeleteResponse(
        id=project_id,
        deleted=True,
        storage_freed_bytes=total_freed,
    )


@router.post("/{project_id}/favorite", response_model=FavoriteResponse)
async def toggle_favorite(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """13.7 — Toggle favorite/star on a project.

    Toggles the is_favorite boolean on a project. Favorited projects can
    be sorted to the top of the project list for quick access.
    """
    user_id = user["id"]

    new_status = await _db_toggle_favorite(project_id, user_id)

    if new_status is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return FavoriteResponse(id=project_id, is_favorite=new_status)
