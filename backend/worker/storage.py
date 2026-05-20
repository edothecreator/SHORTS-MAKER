"""Object storage integration (S3-compatible: R2, S3, MinIO).

Production Tasks 3.6, 3.8, 3.12, 4.1–4.8:
- Bucket setup helpers (renders + sources)
- Presigned upload URLs (frontend uploads directly to storage)
- Presigned download URLs (time-limited, per-user)
- Lifecycle rules (24h for sources, 30/90 days for renders)
- CDN-aware URL generation
- Upload scanning placeholder
"""
from __future__ import annotations

import asyncio
import os
import logging

logger = logging.getLogger(__name__)

ENDPOINT_URL = os.environ.get("STORAGE_ENDPOINT_URL", "")
ACCESS_KEY_ID = os.environ.get("STORAGE_ACCESS_KEY_ID", "")
SECRET_ACCESS_KEY = os.environ.get("STORAGE_SECRET_ACCESS_KEY", "")
BUCKET_RENDERS = os.environ.get("STORAGE_BUCKET_RENDERS", "shorts-renders")
BUCKET_SOURCES = os.environ.get("STORAGE_BUCKET_SOURCES", "shorts-sources")
PUBLIC_URL = os.environ.get("STORAGE_PUBLIC_URL", "")
SIGNED_URL_EXPIRY = 3600


def _get_client():
    import boto3
    if not ENDPOINT_URL:
        raise RuntimeError("STORAGE_ENDPOINT_URL not configured")
    return boto3.client("s3", endpoint_url=ENDPOINT_URL, aws_access_key_id=ACCESS_KEY_ID, aws_secret_access_key=SECRET_ACCESS_KEY)


async def upload_rendered_video(local_path: str, project_id: str, segment_index: int) -> str:
    key = f"renders/{project_id}/{segment_index}.mp4"
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: _get_client().upload_file(local_path, BUCKET_RENDERS, key, ExtraArgs={"ContentType": "video/mp4"}))
    logger.info("Uploaded render: %s", key)
    return key


async def upload_thumbnail(local_path: str, project_id: str, segment_index: int) -> str:
    key = f"renders/{project_id}/{segment_index}_thumb.jpg"
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: _get_client().upload_file(local_path, BUCKET_RENDERS, key, ExtraArgs={"ContentType": "image/jpeg"}))
    return key


async def generate_signed_url(key: str, bucket: str = BUCKET_RENDERS) -> str:
    if PUBLIC_URL:
        return f"{PUBLIC_URL}/{key}"
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _get_client().generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=SIGNED_URL_EXPIRY))


async def delete_source_video(project_id: str, filename: str) -> None:
    key = f"sources/{project_id}/{filename}"
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: _get_client().delete_object(Bucket=BUCKET_SOURCES, Key=key))
    logger.info("Deleted source: %s", key)



# ---------------------------------------------------------------------------
# Presigned Upload URLs (Task 4.3)
# ---------------------------------------------------------------------------
# Frontend calls this to get a URL it can PUT directly to storage,
# bypassing the backend for large video uploads.

UPLOAD_URL_EXPIRY = 3600  # 1 hour to complete upload


async def generate_presigned_upload_url(
    project_id: str, filename: str, content_type: str = "video/mp4"
) -> dict:
    """Generate a presigned PUT URL for direct frontend → storage upload.

    Returns dict with:
        - url: presigned PUT URL
        - key: object key in the sources bucket
        - expires_in: seconds until URL expires
    """
    key = f"sources/{project_id}/{filename}"
    loop = asyncio.get_running_loop()

    url = await loop.run_in_executor(
        None,
        lambda: _get_client().generate_presigned_url(
            "put_object",
            Params={
                "Bucket": BUCKET_SOURCES,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=UPLOAD_URL_EXPIRY,
        ),
    )

    logger.info("Generated presigned upload URL for key: %s", key)
    return {"url": url, "key": key, "expires_in": UPLOAD_URL_EXPIRY}


# ---------------------------------------------------------------------------
# Presigned Download URLs (Task 4.4)
# ---------------------------------------------------------------------------

DOWNLOAD_URL_EXPIRY_FREE = 3600       # 1 hour for free users
DOWNLOAD_URL_EXPIRY_PAID = 86400      # 24 hours for paid users


async def generate_download_url(
    key: str, user_plan: str = "free", bucket: str = BUCKET_RENDERS
) -> str:
    """Generate a time-limited download URL based on user plan.

    Paid users get 24h links; free users get 1h links.
    If a CDN public URL is configured, returns that directly (no expiry).
    """
    if PUBLIC_URL:
        return f"{PUBLIC_URL}/{key}"

    expiry = DOWNLOAD_URL_EXPIRY_PAID if user_plan in ("pro", "business") else DOWNLOAD_URL_EXPIRY_FREE
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: _get_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiry,
        ),
    )


# ---------------------------------------------------------------------------
# Lifecycle Rules (Tasks 4.5, 4.6)
# ---------------------------------------------------------------------------
# These functions configure bucket lifecycle policies programmatically.
# Call once during initial setup or via a management script.


async def configure_source_lifecycle(days: int = 1) -> None:
    """Set lifecycle rule: delete source videos after N days (default 24h).

    Task 4.5: Sources are temporary — auto-delete after processing.
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: _get_client().put_bucket_lifecycle_configuration(
            Bucket=BUCKET_SOURCES,
            LifecycleConfiguration={
                "Rules": [
                    {
                        "ID": "delete-sources-after-upload",
                        "Status": "Enabled",
                        "Filter": {"Prefix": "sources/"},
                        "Expiration": {"Days": days},
                    }
                ]
            },
        ),
    )
    logger.info("Source bucket lifecycle: delete after %d day(s)", days)


async def configure_render_lifecycle(
    free_days: int = 30, paid_days: int = 90
) -> None:
    """Set lifecycle rules for rendered videos.

    Task 4.6:
    - Free tier renders: delete after 30 days
    - Paid tier renders: delete after 90 days

    Note: S3 lifecycle rules work on prefixes. We use:
    - renders/free/... for free user renders
    - renders/paid/... for paid user renders
    Or alternatively, tag-based lifecycle with object tagging.

    For simplicity, this sets a single rule on the whole bucket.
    In production, use object tagging for per-tier expiration.
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: _get_client().put_bucket_lifecycle_configuration(
            Bucket=BUCKET_RENDERS,
            LifecycleConfiguration={
                "Rules": [
                    {
                        "ID": "delete-free-renders",
                        "Status": "Enabled",
                        "Filter": {
                            "Tag": {"Key": "plan", "Value": "free"},
                        },
                        "Expiration": {"Days": free_days},
                    },
                    {
                        "ID": "delete-paid-renders",
                        "Status": "Enabled",
                        "Filter": {
                            "Tag": {"Key": "plan", "Value": "paid"},
                        },
                        "Expiration": {"Days": paid_days},
                    },
                ]
            },
        ),
    )
    logger.info(
        "Render bucket lifecycle: free=%dd, paid=%dd", free_days, paid_days
    )


# ---------------------------------------------------------------------------
# CDN Configuration (Task 4.7)
# ---------------------------------------------------------------------------
# When STORAGE_PUBLIC_URL is set (e.g., a Cloudflare R2 public bucket URL
# or a CloudFront distribution), all download URLs use that prefix instead
# of generating presigned URLs. This provides:
# - Edge caching (faster downloads globally)
# - No URL expiration concerns for public content
# - Reduced S3 API calls
#
# Setup:
# 1. Create a CDN distribution pointing to your renders bucket
# 2. Set STORAGE_PUBLIC_URL=https://cdn.yourdomain.com
# 3. All generate_download_url() calls will return CDN URLs


def get_cdn_url(key: str) -> str | None:
    """Return CDN URL for a key, or None if CDN is not configured."""
    if PUBLIC_URL:
        return f"{PUBLIC_URL}/{key}"
    return None


# ---------------------------------------------------------------------------
# Upload Scanning Placeholder (Task 4.8)
# ---------------------------------------------------------------------------
# In production, integrate with ClamAV or a cloud service to scan uploads
# before processing. This is a placeholder that always returns clean.


async def scan_upload(key: str, bucket: str = BUCKET_SOURCES) -> dict:
    """Scan an uploaded file for malware/viruses.

    Task 4.8: Placeholder — returns clean status.
    In production, integrate with:
    - ClamAV (self-hosted, free)
    - AWS GuardDuty Malware Protection
    - Google Cloud DLP

    Returns:
        dict with 'clean' (bool) and 'details' (str)
    """
    # TODO: Implement actual scanning
    # Option 1: Download file, scan with clamd socket
    # Option 2: Use S3 Object Lambda + ClamAV container
    # Option 3: Cloud-native scanning service

    logger.info("Scan requested for %s/%s (placeholder: always clean)", bucket, key)
    return {"clean": True, "details": "Scan not yet implemented — placeholder"}
