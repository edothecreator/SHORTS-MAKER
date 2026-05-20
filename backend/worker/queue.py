"""Redis-based job queue for render tasks.

Production Tasks 3.1, 3.2, 3.13, 3.14:
- Job queue using Redis lists (LPUSH/BRPOP pattern)
- Priority queue: paid users go to high-priority queue
- Support for concurrent workers pulling from the same queue

Queue structure:
- render:queue:high   — paid users (pro/business)
- render:queue:low    — free users
- render:queue:retry  — failed jobs being retried
- render:job:{job_id} — job data hash
- render:progress:{job_id} — progress updates (pub/sub channel)
"""
from __future__ import annotations

import json
import time
import logging
from typing import Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

QUEUE_HIGH = "render:queue:high"
QUEUE_LOW = "render:queue:low"
QUEUE_RETRY = "render:queue:retry"

STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

MAX_RETRIES = 2
RENDER_TIMEOUT_SEC = 300  # 5 minutes per segment


@dataclass
class RenderJob:
    job_id: str
    project_id: str
    user_id: str
    user_plan: str
    segment_index: int
    start_sec: float
    end_sec: float
    title: str
    hook: str
    source_video_url: str
    subtitle_style: str
    words_json: str
    status: str = STATUS_PENDING
    attempt: int = 0
    max_retries: int = MAX_RETRIES
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    output_url: Optional[str] = None
    thumbnail_url: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "RenderJob":
        return cls(**json.loads(data))

    @property
    def queue_name(self) -> str:
        if self.status == STATUS_FAILED and self.attempt < self.max_retries:
            return QUEUE_RETRY
        if self.user_plan in ("pro", "business"):
            return QUEUE_HIGH
        return QUEUE_LOW


async def enqueue_job(redis, job: RenderJob) -> None:
    job.status = STATUS_PENDING
    queue = job.queue_name
    await redis.set(f"render:job:{job.job_id}", job.to_json(), ex=86400)
    await redis.lpush(queue, job.job_id)
    logger.info("Enqueued job %s (segment %d) to %s", job.job_id, job.segment_index, queue)


async def dequeue_job(redis, timeout: int = 5) -> Optional[RenderJob]:
    result = await redis.brpop([QUEUE_HIGH, QUEUE_RETRY, QUEUE_LOW], timeout=timeout)
    if result is None:
        return None
    queue_name, job_id = result
    job_data = await redis.get(f"render:job:{job_id}")
    if job_data is None:
        return None
    job = RenderJob.from_json(job_data)
    job.status = STATUS_PROCESSING
    job.started_at = time.time()
    job.attempt += 1
    await redis.set(f"render:job:{job.job_id}", job.to_json(), ex=86400)
    logger.info("Dequeued job %s from %s (attempt %d)", job.job_id, queue_name, job.attempt)
    return job


async def complete_job(redis, job: RenderJob, output_url: str, thumbnail_url: str) -> None:
    job.status = STATUS_COMPLETED
    job.completed_at = time.time()
    job.output_url = output_url
    job.thumbnail_url = thumbnail_url
    await redis.set(f"render:job:{job.job_id}", job.to_json(), ex=86400)
    await redis.publish(f"render:progress:{job.job_id}", json.dumps({"status": "completed", "output_url": output_url, "thumbnail_url": thumbnail_url}))


async def fail_job(redis, job: RenderJob, error: str) -> None:
    job.status = STATUS_FAILED
    job.error = error
    job.completed_at = time.time()
    await redis.set(f"render:job:{job.job_id}", job.to_json(), ex=86400)
    await redis.publish(f"render:progress:{job.job_id}", json.dumps({"status": "failed", "error": error}))
    if job.attempt < job.max_retries:
        job.status = STATUS_PENDING
        await redis.lpush(QUEUE_RETRY, job.job_id)
        logger.info("Job %s re-queued for retry", job.job_id)
    else:
        logger.error("Job %s permanently failed after %d attempts", job.job_id, job.attempt)


async def publish_progress(redis, job_id: str, progress: float, message: str = "") -> None:
    await redis.publish(f"render:progress:{job_id}", json.dumps({"status": "progress", "progress": progress, "message": message}))
