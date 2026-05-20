"""
Performance & Scalability System (Production Task 23)

Provides caching, upload optimization, rendering optimization,
horizontal scaling, job prioritization, request queuing, and
Whisper optimization configurations.
"""

import hashlib
import json
import time
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


# =============================================================================
# 23.1 — Caching Layer (Redis-backed)
# =============================================================================

class CacheTTL:
    """TTL constants for different cache categories."""
    SESSION_DATA = 1800       # 30 minutes
    RENDERED_VIDEO_URL = 3600 # 1 hour
    USER_PLAN_INFO = 300      # 5 minutes


class CacheManager:
    """
    Redis-backed caching layer for session data, rendered video URLs,
    and user plan info with configurable TTLs.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0", prefix: str = "shorts:cache"):
        self.redis_url = redis_url
        self.prefix = prefix
        self._client = None

    def _get_client(self):
        """Lazily connect to Redis."""
        if self._client is None:
            try:
                import redis
                self._client = redis.from_url(self.redis_url, decode_responses=True)
            except ImportError:
                raise RuntimeError("redis package required: pip install redis")
        return self._client

    def _make_key(self, namespace: str, key: str) -> str:
        """Create a namespaced cache key."""
        return f"{self.prefix}:{namespace}:{key}"


    def get(self, namespace: str, key: str) -> Optional[Any]:
        """
        Get a value from cache.

        Args:
            namespace: Cache category (e.g., 'session', 'video_url', 'plan')
            key: The cache key within the namespace

        Returns:
            Cached value or None if not found/expired
        """
        client = self._get_client()
        full_key = self._make_key(namespace, key)
        raw = client.get(full_key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    def set(self, namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set a value in cache with optional TTL.

        Args:
            namespace: Cache category
            key: The cache key
            value: Value to store (will be JSON serialized)
            ttl: Time-to-live in seconds. Uses default for namespace if not specified.

        Returns:
            True if successfully stored
        """
        if ttl is None:
            ttl = self._default_ttl(namespace)
        client = self._get_client()
        full_key = self._make_key(namespace, key)
        serialized = json.dumps(value) if not isinstance(value, str) else value
        return client.setex(full_key, ttl, serialized)

    def invalidate(self, namespace: str, key: str) -> bool:
        """
        Remove a key from cache.

        Args:
            namespace: Cache category
            key: The cache key to invalidate

        Returns:
            True if the key existed and was deleted
        """
        client = self._get_client()
        full_key = self._make_key(namespace, key)
        return client.delete(full_key) > 0


    def get_or_set(
        self, namespace: str, key: str, factory: Callable[[], Any], ttl: Optional[int] = None
    ) -> Any:
        """
        Get from cache or compute and store value.

        Args:
            namespace: Cache category
            key: The cache key
            factory: Callable that produces the value if not cached
            ttl: Time-to-live in seconds

        Returns:
            Cached or freshly-computed value
        """
        cached = self.get(namespace, key)
        if cached is not None:
            return cached
        value = factory()
        self.set(namespace, key, value, ttl)
        return value

    def _default_ttl(self, namespace: str) -> int:
        """Return default TTL based on namespace."""
        defaults = {
            "session": CacheTTL.SESSION_DATA,
            "video_url": CacheTTL.RENDERED_VIDEO_URL,
            "plan": CacheTTL.USER_PLAN_INFO,
        }
        return defaults.get(namespace, CacheTTL.SESSION_DATA)

    def invalidate_pattern(self, namespace: str, pattern: str = "*") -> int:
        """
        Invalidate all keys matching a pattern in a namespace.

        Args:
            namespace: Cache category
            pattern: Glob pattern to match keys

        Returns:
            Number of keys deleted
        """
        client = self._get_client()
        full_pattern = self._make_key(namespace, pattern)
        keys = client.keys(full_pattern)
        if keys:
            return client.delete(*keys)
        return 0

    def get_session(self, session_id: str) -> Optional[Dict]:
        """Shortcut: get session data."""
        return self.get("session", session_id)

    def set_session(self, session_id: str, data: Dict) -> bool:
        """Shortcut: cache session data (TTL 30 min)."""
        return self.set("session", session_id, data, CacheTTL.SESSION_DATA)

    def get_video_url(self, render_id: str) -> Optional[str]:
        """Shortcut: get cached rendered video URL."""
        return self.get("video_url", render_id)

    def set_video_url(self, render_id: str, url: str) -> bool:
        """Shortcut: cache rendered video URL (TTL 1 hr)."""
        return self.set("video_url", render_id, url, CacheTTL.RENDERED_VIDEO_URL)

    def get_user_plan(self, user_id: str) -> Optional[Dict]:
        """Shortcut: get cached user plan info."""
        return self.get("plan", user_id)

    def set_user_plan(self, user_id: str, plan_info: Dict) -> bool:
        """Shortcut: cache user plan info (TTL 5 min)."""
        return self.set("plan", user_id, plan_info, CacheTTL.USER_PLAN_INFO)



# =============================================================================
# 23.2 — Upload Optimization (Resumable/Multipart Uploads)
# =============================================================================

DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB


@dataclass
class ResumableUploadConfig:
    """
    Configuration for multipart/resumable upload strategy.

    Strategy:
    - Files < 10MB: single PUT upload via presigned URL
    - Files 10MB-5GB: multipart upload with 5MB chunks
    - Files > 5GB: rejected (max file size exceeded)

    Frontend uploads directly to object storage using presigned URLs.
    Backend provides upload_id and per-part presigned URLs.
    On completion, backend triggers multipart completion API.
    """
    chunk_size: int = DEFAULT_CHUNK_SIZE  # 5 MB per chunk
    max_file_size: int = 5 * 1024 * 1024 * 1024  # 5 GB max
    single_upload_threshold: int = 10 * 1024 * 1024  # 10 MB
    max_concurrent_chunks: int = 4  # parallel chunk uploads
    retry_attempts: int = 3  # retries per failed chunk
    retry_delay_seconds: float = 1.0  # backoff base delay
    timeout_per_chunk_seconds: int = 60  # timeout for each chunk upload
    content_types_allowed: List[str] = field(default_factory=lambda: [
        "video/mp4", "video/webm", "video/quicktime",
        "video/x-msvideo", "video/x-matroska"
    ])


@dataclass
class UploadChunk:
    """Represents a single chunk in a multipart upload."""
    part_number: int
    offset: int
    size: int
    end_offset: int


def generate_upload_chunks(file_size: int, chunk_size: int = DEFAULT_CHUNK_SIZE) -> List[UploadChunk]:
    """
    Generate chunk definitions for a multipart upload.

    Args:
        file_size: Total file size in bytes
        chunk_size: Size of each chunk in bytes (default 5MB)

    Returns:
        List of UploadChunk objects defining each part
    """
    if file_size <= 0:
        return []
    chunks = []
    part_number = 1
    offset = 0
    while offset < file_size:
        size = min(chunk_size, file_size - offset)
        chunks.append(UploadChunk(
            part_number=part_number,
            offset=offset,
            size=size,
            end_offset=offset + size - 1,
        ))
        offset += size
        part_number += 1
    return chunks



def estimate_upload_progress(
    chunks_completed: int,
    total_chunks: int,
    current_chunk_bytes_sent: int = 0,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Dict[str, Any]:
    """
    Estimate upload progress and remaining time.

    Args:
        chunks_completed: Number of fully uploaded chunks
        total_chunks: Total number of chunks
        current_chunk_bytes_sent: Bytes sent in the current in-progress chunk
        chunk_size: Size of each chunk

    Returns:
        Dict with percentage, bytes_sent, bytes_total, estimated fields
    """
    if total_chunks <= 0:
        return {"percentage": 100.0, "bytes_sent": 0, "bytes_total": 0}

    total_bytes = total_chunks * chunk_size
    bytes_sent = (chunks_completed * chunk_size) + current_chunk_bytes_sent
    percentage = min(100.0, (bytes_sent / total_bytes) * 100.0)

    return {
        "percentage": round(percentage, 2),
        "bytes_sent": bytes_sent,
        "bytes_total": total_bytes,
        "chunks_completed": chunks_completed,
        "chunks_total": total_chunks,
    }


# =============================================================================
# 23.3 — Rendering Optimization
# =============================================================================

class HardwareEncoder(Enum):
    """Supported hardware encoders."""
    NONE = "software"       # libx264 (CPU)
    NVENC = "nvenc"         # NVIDIA GPU encoding
    VAAPI = "vaapi"         # Intel/AMD GPU encoding (Linux)
    VIDEOTOOLBOX = "vtb"   # macOS hardware encoding


@dataclass
class RenderOptimizationConfig:
    """
    Configuration for rendering performance optimization.

    Strategies:
    - Hardware encoding: detect NVENC (NVIDIA) or VAAPI (Intel/AMD)
      for 3-5x encoding speedup over libx264
    - Parallel subtitle generation: generate ASS subtitle files
      concurrently while main video encodes
    - FFmpeg process pre-warming: maintain a pool of FFmpeg processes
      ready to accept work, avoiding cold-start overhead (~200ms savings)
    """
    # Hardware encoding detection
    preferred_encoder: HardwareEncoder = HardwareEncoder.NONE
    fallback_encoder: HardwareEncoder = HardwareEncoder.NONE
    detect_hardware_on_start: bool = True

    # NVENC settings
    nvenc_preset: str = "p4"              # balance of speed/quality
    nvenc_tune: str = "hq"               # high quality tuning
    nvenc_max_concurrent: int = 3        # max concurrent NVENC sessions

    # VAAPI settings
    vaapi_device: str = "/dev/dri/renderD128"
    vaapi_profile: str = "high"

    # Parallel subtitle generation
    parallel_subtitle_generation: bool = True
    subtitle_thread_pool_size: int = 4

    # FFmpeg process pre-warming pool
    prewarm_pool_enabled: bool = True
    prewarm_pool_size: int = 2           # pre-warmed FFmpeg processes
    prewarm_idle_timeout: int = 300      # kill idle processes after 5 min
    max_render_time_seconds: int = 300   # 5 min max per segment


    def get_ffmpeg_encoder_args(self) -> List[str]:
        """
        Get FFmpeg encoder arguments based on detected hardware.

        Returns:
            List of FFmpeg CLI arguments for the encoder
        """
        encoder = self.preferred_encoder
        if encoder == HardwareEncoder.NVENC:
            return [
                "-c:v", "h264_nvenc",
                "-preset", self.nvenc_preset,
                "-tune", self.nvenc_tune,
                "-b:v", "5M",
                "-maxrate", "8M",
                "-bufsize", "10M",
            ]
        elif encoder == HardwareEncoder.VAAPI:
            return [
                "-vaapi_device", self.vaapi_device,
                "-c:v", "h264_vaapi",
                "-vf", "format=nv12,hwupload",
                "-b:v", "5M",
            ]
        elif encoder == HardwareEncoder.VIDEOTOOLBOX:
            return [
                "-c:v", "h264_videotoolbox",
                "-b:v", "5M",
            ]
        else:
            # Software fallback (libx264)
            return [
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
            ]


def detect_hardware_encoder() -> HardwareEncoder:
    """
    Detect available hardware encoder on the system.

    Checks in order of preference: NVENC > VAAPI > VideoToolbox > Software

    Returns:
        The best available HardwareEncoder
    """
    import subprocess
    import platform

    # Check for NVIDIA GPU (NVENC)
    try:
        result = subprocess.run(
            ["nvidia-smi"], capture_output=True, timeout=5
        )
        if result.returncode == 0:
            # Verify ffmpeg supports nvenc
            ffmpeg_check = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True, text=True, timeout=5
            )
            if "h264_nvenc" in ffmpeg_check.stdout:
                return HardwareEncoder.NVENC
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Check for VAAPI (Linux Intel/AMD)
    if platform.system() == "Linux":
        try:
            import os
            if os.path.exists("/dev/dri/renderD128"):
                ffmpeg_check = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-encoders"],
                    capture_output=True, text=True, timeout=5
                )
                if "h264_vaapi" in ffmpeg_check.stdout:
                    return HardwareEncoder.VAAPI
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Check for VideoToolbox (macOS)
    if platform.system() == "Darwin":
        try:
            ffmpeg_check = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True, text=True, timeout=5
            )
            if "h264_videotoolbox" in ffmpeg_check.stdout:
                return HardwareEncoder.VIDEOTOOLBOX
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return HardwareEncoder.NONE



# =============================================================================
# 23.4 — Horizontal Scaling
# =============================================================================

@dataclass
class ScalingConfig:
    """
    Configuration for horizontal scaling strategy.

    Architecture:
    - Multiple render workers pulling from shared Redis queue
    - Auto-scale workers based on queue depth thresholds
    - PostgreSQL read replicas for query-heavy endpoints
    - Load balancer (nginx/HAProxy) distributing API requests

    Scaling triggers:
    - Queue depth > 10 jobs: spin up 1 additional worker
    - Queue depth > 25 jobs: spin up 2 additional workers
    - Queue depth > 50 jobs: spin up max workers
    - Queue depth < 5 for 10 min: scale down 1 worker
    """
    # Render workers
    min_workers: int = 1
    max_workers: int = 10
    scale_up_queue_threshold: int = 10
    scale_up_aggressive_threshold: int = 25
    scale_up_max_threshold: int = 50
    scale_down_queue_threshold: int = 5
    scale_down_cooldown_seconds: int = 600  # 10 min
    worker_health_check_interval: int = 30  # seconds

    # Database read replicas
    read_replica_enabled: bool = True
    read_replica_count: int = 2
    read_replica_hosts: List[str] = field(default_factory=lambda: [
        "db-replica-1.internal:5432",
        "db-replica-2.internal:5432",
    ])
    primary_host: str = "db-primary.internal:5432"

    # Load balancer
    load_balancer_strategy: str = "least_connections"  # round_robin, least_connections, ip_hash
    api_server_count: int = 2
    api_server_hosts: List[str] = field(default_factory=lambda: [
        "api-1.internal:8000",
        "api-2.internal:8000",
    ])
    health_check_path: str = "/health"
    health_check_interval_seconds: int = 10

    def get_desired_worker_count(self, current_queue_depth: int) -> int:
        """
        Calculate desired number of workers based on queue depth.

        Args:
            current_queue_depth: Number of jobs currently in queue

        Returns:
            Desired number of workers to run
        """
        if current_queue_depth >= self.scale_up_max_threshold:
            return self.max_workers
        elif current_queue_depth >= self.scale_up_aggressive_threshold:
            return min(self.max_workers, self.min_workers + 3)
        elif current_queue_depth >= self.scale_up_queue_threshold:
            return min(self.max_workers, self.min_workers + 1)
        elif current_queue_depth <= self.scale_down_queue_threshold:
            return self.min_workers
        else:
            return self.min_workers + 1



# =============================================================================
# 23.5 — Job Prioritization (Three-queue system)
# =============================================================================

class QueuePriority(Enum):
    """Job queue priority levels."""
    HIGH = "high"    # Paid users
    LOW = "low"      # Free users
    RETRY = "retry"  # Failed jobs being retried


@dataclass
class PriorityQueueConfig:
    """
    Configuration for priority-based job queue system.

    Three queues:
    - HIGH (paid users): processed first, 2x worker allocation
    - LOW (free users): processed when high queue is empty or after timeout
    - RETRY (failed jobs): processed with backoff, max 2 retries

    Workers check queues in order: HIGH → RETRY → LOW
    Starvation prevention: LOW queue jobs promoted after 5 min wait
    """
    high_queue_name: str = "render:queue:high"
    low_queue_name: str = "render:queue:low"
    retry_queue_name: str = "render:queue:retry"

    # Processing ratios
    high_priority_weight: int = 3  # process 3 high for every 1 low
    low_priority_weight: int = 1

    # Starvation prevention
    max_low_priority_wait_seconds: int = 300  # promote after 5 min
    promote_check_interval_seconds: int = 30

    # Retry configuration
    max_retries: int = 2
    retry_base_delay_seconds: int = 30
    retry_max_delay_seconds: int = 300  # 5 min max backoff

    # Queue limits
    max_high_queue_depth: int = 100
    max_low_queue_depth: int = 200
    max_retry_queue_depth: int = 50

    def get_retry_delay(self, attempt: int) -> int:
        """
        Calculate retry delay with exponential backoff.

        Args:
            attempt: Current retry attempt (1-based)

        Returns:
            Delay in seconds before next retry
        """
        delay = self.retry_base_delay_seconds * (2 ** (attempt - 1))
        return min(delay, self.retry_max_delay_seconds)


def get_queue_for_user(plan: str) -> str:
    """
    Determine which queue a user's job should go to based on their plan.

    Args:
        plan: User's subscription plan ('free', 'pro', 'business', 'enterprise')

    Returns:
        Queue name string for the appropriate priority queue
    """
    config = PriorityQueueConfig()
    paid_plans = {"pro", "business", "enterprise"}

    if plan.lower() in paid_plans:
        return config.high_queue_name
    else:
        return config.low_queue_name


def get_queue_for_retry() -> str:
    """Get the retry queue name."""
    return PriorityQueueConfig().retry_queue_name



# =============================================================================
# 23.6 — Request Queuing (Burst Traffic Handling)
# =============================================================================

class QueueOverflowError(Exception):
    """Raised when request queue is full and cannot accept more requests."""
    pass


class RequestQueue:
    """
    Request queue for handling burst traffic.

    Buffers incoming requests when the system is under heavy load.
    Rejects requests with HTTP 503 when queue is full (back-pressure).

    Usage:
        queue = RequestQueue(max_depth=100)
        if queue.can_accept():
            queue.enqueue(request_data)
        else:
            raise QueueOverflowError("Service overloaded")
    """

    def __init__(
        self,
        max_depth: int = 100,
        overflow_status_code: int = 503,
        overflow_message: str = "Service temporarily overloaded. Please retry in a few seconds.",
        drain_rate_per_second: float = 10.0,
    ):
        """
        Initialize request queue.

        Args:
            max_depth: Maximum number of queued requests before rejection
            overflow_status_code: HTTP status code returned on overflow (503)
            overflow_message: Error message returned when queue is full
            drain_rate_per_second: Expected processing rate for ETA estimation
        """
        self.max_depth = max_depth
        self.overflow_status_code = overflow_status_code
        self.overflow_message = overflow_message
        self.drain_rate_per_second = drain_rate_per_second
        self._queue: List[Dict[str, Any]] = []
        self._total_enqueued: int = 0
        self._total_rejected: int = 0
        self._total_processed: int = 0

    @property
    def current_depth(self) -> int:
        """Current number of requests in queue."""
        return len(self._queue)

    @property
    def is_full(self) -> bool:
        """Check if queue has reached max depth."""
        return self.current_depth >= self.max_depth

    def can_accept(self) -> bool:
        """Check if queue can accept a new request."""
        return not self.is_full

    def enqueue(self, request_data: Dict[str, Any]) -> int:
        """
        Add a request to the queue.

        Args:
            request_data: Dict containing the request payload

        Returns:
            Position in queue (1-based)

        Raises:
            QueueOverflowError: If queue is full
        """
        if self.is_full:
            self._total_rejected += 1
            raise QueueOverflowError(self.overflow_message)

        entry = {
            "data": request_data,
            "enqueued_at": time.time(),
            "position": self.current_depth + 1,
        }
        self._queue.append(entry)
        self._total_enqueued += 1
        return entry["position"]


    def dequeue(self) -> Optional[Dict[str, Any]]:
        """
        Remove and return the next request from the queue.

        Returns:
            Request data dict, or None if queue is empty
        """
        if not self._queue:
            return None
        entry = self._queue.pop(0)
        self._total_processed += 1
        return entry["data"]

    def get_estimated_wait_time(self) -> float:
        """
        Estimate wait time for a new request entering the queue.

        Returns:
            Estimated wait time in seconds
        """
        if self.drain_rate_per_second <= 0:
            return float("inf")
        return self.current_depth / self.drain_rate_per_second

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            "current_depth": self.current_depth,
            "max_depth": self.max_depth,
            "utilization_percent": round(
                (self.current_depth / self.max_depth) * 100, 1
            ) if self.max_depth > 0 else 0,
            "total_enqueued": self._total_enqueued,
            "total_rejected": self._total_rejected,
            "total_processed": self._total_processed,
            "estimated_wait_seconds": round(self.get_estimated_wait_time(), 1),
        }

    def reject_response(self) -> Dict[str, Any]:
        """
        Generate a rejection response when queue is full.

        Returns:
            Dict suitable for HTTP response body
        """
        return {
            "error": "service_overloaded",
            "message": self.overflow_message,
            "status_code": self.overflow_status_code,
            "retry_after_seconds": math.ceil(self.get_estimated_wait_time()),
            "queue_depth": self.current_depth,
        }


# =============================================================================
# 23.7 — Whisper Optimization (faster-whisper / CTranslate2)
# =============================================================================

@dataclass
class WhisperOptimizationConfig:
    """
    Configuration for Whisper transcription optimization.

    faster-whisper uses CTranslate2 backend which provides:
    - 4x faster transcription than openai-whisper
    - 2-3x less memory usage
    - Same accuracy as original Whisper
    - INT8 quantization support for additional 2x speedup

    Benchmarks (1-minute audio, NVIDIA T4 GPU):
    - openai-whisper large-v2: ~45 seconds
    - faster-whisper large-v2 FP16: ~12 seconds (3.75x faster)
    - faster-whisper large-v2 INT8: ~8 seconds (5.6x faster)
    - faster-whisper medium INT8: ~4 seconds (11x faster)

    Benchmarks (1-minute audio, CPU only, 8 cores):
    - openai-whisper base: ~30 seconds
    - faster-whisper base INT8: ~8 seconds (3.75x faster)
    - faster-whisper small INT8: ~15 seconds (2x faster than whisper base)
    """
    # Model selection
    model_size: str = "large-v2"  # tiny, base, small, medium, large-v2
    compute_type: str = "int8"    # float32, float16, int8, int8_float16
    device: str = "auto"          # auto, cpu, cuda

    # CTranslate2 settings
    cpu_threads: int = 4          # threads for CPU inference
    num_workers: int = 1          # concurrent transcription workers
    download_root: str = "/models/whisper"  # model cache directory

    # Performance tuning
    beam_size: int = 5
    best_of: int = 5
    patience: float = 1.0
    length_penalty: float = 1.0
    vad_filter: bool = True       # voice activity detection (skip silence)
    vad_min_silence_duration_ms: int = 500
    vad_min_speech_duration_ms: int = 250

    # Model preloading
    preload_on_start: bool = True
    keep_model_in_memory: bool = True
    max_model_memory_mb: int = 2048  # unload if exceeds this


    def get_model_load_args(self) -> Dict[str, Any]:
        """
        Get arguments for loading the faster-whisper model.

        Returns:
            Dict of kwargs for WhisperModel constructor
        """
        return {
            "model_size_or_path": self.model_size,
            "device": self.device,
            "compute_type": self.compute_type,
            "cpu_threads": self.cpu_threads,
            "num_workers": self.num_workers,
            "download_root": self.download_root,
        }

    def get_transcribe_args(self) -> Dict[str, Any]:
        """
        Get arguments for transcription call.

        Returns:
            Dict of kwargs for model.transcribe()
        """
        return {
            "beam_size": self.beam_size,
            "best_of": self.best_of,
            "patience": self.patience,
            "length_penalty": self.length_penalty,
            "vad_filter": self.vad_filter,
            "vad_parameters": {
                "min_silence_duration_ms": self.vad_min_silence_duration_ms,
                "min_speech_duration_ms": self.vad_min_speech_duration_ms,
            },
            "word_timestamps": True,  # needed for subtitle timing
        }

    def get_recommended_model(self, has_gpu: bool, memory_gb: float) -> str:
        """
        Recommend the best model size based on available hardware.

        Args:
            has_gpu: Whether a CUDA-capable GPU is available
            memory_gb: Available memory (VRAM if GPU, RAM if CPU)

        Returns:
            Recommended model size string
        """
        if has_gpu:
            if memory_gb >= 10:
                return "large-v2"
            elif memory_gb >= 5:
                return "medium"
            elif memory_gb >= 2:
                return "small"
            else:
                return "base"
        else:
            if memory_gb >= 8:
                return "medium"
            elif memory_gb >= 4:
                return "small"
            elif memory_gb >= 2:
                return "base"
            else:
                return "tiny"


# =============================================================================
# Factory / Initialization Helpers
# =============================================================================

def create_default_cache_manager(redis_url: Optional[str] = None) -> CacheManager:
    """Create a CacheManager with default settings."""
    import os
    url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    return CacheManager(redis_url=url)


def create_performance_config() -> Dict[str, Any]:
    """
    Create a complete performance configuration bundle.

    Returns:
        Dict with all performance config objects
    """
    return {
        "upload": ResumableUploadConfig(),
        "render": RenderOptimizationConfig(),
        "scaling": ScalingConfig(),
        "priority_queue": PriorityQueueConfig(),
        "request_queue": RequestQueue(),
        "whisper": WhisperOptimizationConfig(),
    }
