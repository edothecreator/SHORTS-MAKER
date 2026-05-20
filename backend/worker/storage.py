"""Object storage integration (S3-compatible: R2, S3, MinIO).

Production Tasks 3.6, 3.8, 3.12
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
