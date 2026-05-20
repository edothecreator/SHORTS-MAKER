"""
Production Task 12: YouTube URL Input — yt-dlp download module.

Provides video downloading from multiple platforms (YouTube, Vimeo, Twitter/X,
Instagram Reels, TikTok) with validation, caching, duration enforcement,
progress callbacks, and graceful error handling.
"""

import hashlib
import json
import os
import re
import time
from typing import Callable, Optional
from urllib.parse import urlparse

import redis
import yt_dlp

# ---------------------------------------------------------------------------
# Task 12.9: Copyright disclaimer constant
# ---------------------------------------------------------------------------

COPYRIGHT_DISCLAIMER = (
    "By providing a URL for processing, you confirm that:\n"
    "1. You own the content or have explicit permission from the copyright holder.\n"
    "2. You accept full responsibility for any copyright infringement claims.\n"
    "3. This service is intended for repurposing YOUR OWN content (podcasts, "
    "streams, vlogs, interviews you participated in).\n"
    "4. Downloading and re-uploading others' content without permission violates "
    "platform Terms of Service and may violate copyright law.\n"
    "5. We reserve the right to terminate accounts found violating these terms.\n\n"
    "By proceeding, you agree to these terms and accept all legal responsibility "
    "for the content you process through this service."
)

# ---------------------------------------------------------------------------
# Supported platform patterns
# ---------------------------------------------------------------------------

SUPPORTED_PLATFORMS = {
    "youtube": [
        r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/",
        r"(https?://)?(www\.)?youtube\.com/shorts/",
    ],
    "vimeo": [
        r"(https?://)?(www\.)?vimeo\.com/",
    ],
    "twitter": [
        r"(https?://)?(www\.)?(twitter\.com|x\.com)/",
    ],
    "instagram": [
        r"(https?://)?(www\.)?instagram\.com/(reel|reels|p)/",
    ],
    "tiktok": [
        r"(https?://)?(www\.|vm\.)?tiktok\.com/",
    ],
}

# ---------------------------------------------------------------------------
# Task 12.6: Duration limits per plan
# ---------------------------------------------------------------------------

DURATION_LIMITS = {
    "free": 60 * 60,       # 60 minutes in seconds
    "pro": 180 * 60,       # 180 minutes in seconds
    "paid": 180 * 60,      # alias for pro
    "business": 180 * 60,  # business plan same as pro
}

# ---------------------------------------------------------------------------
# Redis connection for caching (Task 12.8)
# ---------------------------------------------------------------------------

_redis_client: Optional[redis.Redis] = None

CACHE_TTL = 3600  # 1 hour in seconds


def _get_redis() -> Optional[redis.Redis]:
    """Get or create Redis connection for video caching."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        _redis_client = redis.from_url(redis_url, decode_responses=True)
        _redis_client.ping()
        return _redis_client
    except (redis.ConnectionError, redis.RedisError):
        # Redis not available — caching disabled, download will still work
        _redis_client = None
        return None


def _cache_key(url: str) -> str:
    """Generate a deterministic cache key for a URL."""
    normalized = url.strip().lower()
    url_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    return f"video_cache:{url_hash}"


# ---------------------------------------------------------------------------
# Task 12.8: Caching functions
# ---------------------------------------------------------------------------


def get_cached_video(url: str) -> Optional[str]:
    """
    Check if a video for the given URL is already cached.

    Returns the local file path if cached and file still exists,
    otherwise returns None.
    """
    r = _get_redis()
    if r is None:
        return None
    try:
        cached = r.get(_cache_key(url))
        if cached is None:
            return None
        data = json.loads(cached)
        path = data.get("path")
        if path and os.path.isfile(path):
            return path
        # File was deleted — remove stale cache entry
        r.delete(_cache_key(url))
        return None
    except (redis.RedisError, json.JSONDecodeError):
        return None


def cache_video(url: str, path: str) -> bool:
    """
    Cache a downloaded video path for 1 hour.

    Returns True if caching succeeded, False otherwise.
    """
    r = _get_redis()
    if r is None:
        return False
    try:
        data = json.dumps({"path": path, "cached_at": time.time()})
        r.setex(_cache_key(url), CACHE_TTL, data)
        return True
    except redis.RedisError:
        return False


# ---------------------------------------------------------------------------
# Task 12.5: URL validation
# ---------------------------------------------------------------------------


def _identify_platform(url: str) -> Optional[str]:
    """Identify which platform a URL belongs to."""
    for platform, patterns in SUPPORTED_PLATFORMS.items():
        for pattern in patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return platform
    return None


def validate_url(url: str) -> dict:
    """
    Validate a video URL without downloading.

    Checks:
    - URL format is valid
    - Platform is supported
    - Video exists and is accessible
    - Retrieves metadata (title, duration)

    Returns:
        dict with keys:
        - valid (bool): Whether the URL is valid and accessible
        - platform (str|None): Identified platform name
        - title (str|None): Video title
        - duration (float|None): Duration in seconds
        - error (str|None): Error message if not valid
    """
    result = {
        "valid": False,
        "platform": None,
        "title": None,
        "duration": None,
        "error": None,
    }

    # Basic URL format check
    if not url or not isinstance(url, str):
        result["error"] = "URL must be a non-empty string."
        return result

    url = url.strip()
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "https://" + url
        parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        result["error"] = "URL must use http or https protocol."
        return result

    if not parsed.netloc:
        result["error"] = "Invalid URL format."
        return result

    # Platform check
    platform = _identify_platform(url)
    if platform is None:
        result["error"] = (
            "Unsupported platform. Supported platforms: "
            "YouTube, Vimeo, Twitter/X, Instagram Reels, TikTok."
        )
        return result
    result["platform"] = platform

    # Attempt to extract metadata without downloading
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "socket_timeout": 15,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                result["error"] = "Could not retrieve video information."
                return result

            result["title"] = info.get("title")
            result["duration"] = info.get("duration")
            result["valid"] = True
            return result

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e).lower()
        if "private" in error_msg or "not available" in error_msg:
            result["error"] = (
                "This video is private or unavailable. "
                "Please check the URL and ensure the video is publicly accessible."
            )
        elif "age" in error_msg or "sign in" in error_msg or "login" in error_msg:
            result["error"] = (
                "This video is age-restricted and cannot be downloaded. "
                "Age-restricted content requires authentication which is not supported."
            )
        elif "removed" in error_msg or "deleted" in error_msg:
            result["error"] = "This video has been removed or deleted."
        elif "copyright" in error_msg:
            result["error"] = (
                "This video is blocked due to a copyright claim and cannot be downloaded."
            )
        elif "geo" in error_msg or "country" in error_msg:
            result["error"] = (
                "This video is not available in the server's region (geo-restricted)."
            )
        else:
            result["error"] = f"Could not access video: {str(e)[:200]}"
        return result

    except Exception as e:
        result["error"] = f"Unexpected error validating URL: {str(e)[:200]}"
        return result


# ---------------------------------------------------------------------------
# Task 12.6: Duration limit enforcement
# ---------------------------------------------------------------------------


def enforce_duration_limit(duration: Optional[float], user_plan: str) -> dict:
    """
    Check if a video duration is within the user's plan limit.

    Args:
        duration: Video duration in seconds (None if unknown)
        user_plan: User's plan name ('free', 'pro', 'paid', 'business')

    Returns:
        dict with keys:
        - allowed (bool): Whether the duration is within limits
        - max_seconds (int): Maximum allowed duration for this plan
        - error (str|None): Error message if not allowed
    """
    plan_key = user_plan.lower().strip() if user_plan else "free"
    max_seconds = DURATION_LIMITS.get(plan_key, DURATION_LIMITS["free"])

    result = {
        "allowed": True,
        "max_seconds": max_seconds,
        "error": None,
    }

    if duration is None:
        # If duration is unknown, allow download but it will be checked after
        return result

    if duration > max_seconds:
        max_minutes = max_seconds // 60
        video_minutes = int(duration // 60)
        result["allowed"] = False
        result["error"] = (
            f"Video duration ({video_minutes} min) exceeds your plan's limit "
            f"of {max_minutes} minutes. "
        )
        if plan_key == "free":
            result["error"] += (
                "Upgrade to Pro or Business to process videos up to 180 minutes."
            )
        else:
            result["error"] += "Please provide a shorter video."
        return result

    return result


# ---------------------------------------------------------------------------
# Task 12.7: Error classification
# ---------------------------------------------------------------------------


class DownloadError(Exception):
    """Base exception for download errors."""

    def __init__(self, message: str, error_type: str = "unknown"):
        super().__init__(message)
        self.error_type = error_type


class VideoUnavailableError(DownloadError):
    """Video is unavailable (private, deleted, etc.)."""

    def __init__(self, message: str):
        super().__init__(message, error_type="unavailable")


class AgeRestrictedError(DownloadError):
    """Video is age-restricted."""

    def __init__(self, message: str):
        super().__init__(message, error_type="age_restricted")


class DurationExceededError(DownloadError):
    """Video exceeds duration limit for user's plan."""

    def __init__(self, message: str):
        super().__init__(message, error_type="duration_exceeded")


# ---------------------------------------------------------------------------
# Task 12.2 + 12.3 + 12.4: Download function
# ---------------------------------------------------------------------------


def download_video_from_url(
    url: str,
    output_dir: str,
    max_duration: Optional[float] = None,
    on_progress: Optional[Callable[[dict], None]] = None,
) -> str:
    """
    Download a video from a supported URL using yt-dlp.

    Supports: YouTube, Vimeo, Twitter/X, Instagram Reels, TikTok.

    Args:
        url: The video URL to download.
        output_dir: Directory where the video file will be saved.
        max_duration: Optional maximum duration in seconds. If the video
                      exceeds this, a DurationExceededError is raised.
        on_progress: Optional callback function that receives progress info dict:
                     {
                         "status": "downloading" | "finished" | "error",
                         "downloaded_bytes": int,
                         "total_bytes": int | None,
                         "speed": float | None,  # bytes per second
                         "eta": float | None,    # seconds remaining
                         "percent": float,       # 0.0 to 100.0
                         "filename": str | None,
                     }

    Returns:
        str: Local file path to the downloaded video.

    Raises:
        DownloadError: Base error for download failures.
        VideoUnavailableError: Video is private, deleted, or region-blocked.
        AgeRestrictedError: Video requires age verification.
        DurationExceededError: Video exceeds max_duration.
        ValueError: Invalid URL or unsupported platform.
    """
    # Validate URL first
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string.")

    url = url.strip()
    if not urlparse(url).scheme:
        url = "https://" + url

    platform = _identify_platform(url)
    if platform is None:
        raise ValueError(
            "Unsupported platform. Supported: YouTube, Vimeo, Twitter/X, "
            "Instagram Reels, TikTok."
        )

    # Check cache first (Task 12.8)
    cached_path = get_cached_video(url)
    if cached_path:
        if on_progress:
            on_progress({
                "status": "finished",
                "downloaded_bytes": os.path.getsize(cached_path),
                "total_bytes": os.path.getsize(cached_path),
                "speed": None,
                "eta": 0,
                "percent": 100.0,
                "filename": cached_path,
            })
        return cached_path

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Build output template
    output_template = os.path.join(output_dir, "%(id)s.%(ext)s")

    # Progress hook for yt-dlp
    def _progress_hook(d: dict) -> None:
        if on_progress is None:
            return

        status = d.get("status", "downloading")
        total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")
        downloaded = d.get("downloaded_bytes", 0)

        percent = 0.0
        if total_bytes and total_bytes > 0:
            percent = min((downloaded / total_bytes) * 100.0, 100.0)

        progress_info = {
            "status": status,
            "downloaded_bytes": downloaded,
            "total_bytes": total_bytes,
            "speed": d.get("speed"),
            "eta": d.get("eta"),
            "percent": percent,
            "filename": d.get("filename"),
        }
        on_progress(progress_info)

    # yt-dlp options
    ydl_opts = {
        "outtmpl": output_template,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "progress_hooks": [_progress_hook],
        "noprogress": True,
        # Avoid downloading playlists
        "noplaylist": True,
        # Avoid geo-restrictions where possible
        "geo_bypass": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info first to check duration
            info = ydl.extract_info(url, download=False)
            if info is None:
                raise VideoUnavailableError(
                    "Could not retrieve video information. "
                    "The video may be unavailable or the URL may be incorrect."
                )

            # Check duration limit
            duration = info.get("duration")
            if max_duration is not None and duration is not None:
                if duration > max_duration:
                    max_min = int(max_duration // 60)
                    vid_min = int(duration // 60)
                    raise DurationExceededError(
                        f"Video duration ({vid_min} min) exceeds the maximum "
                        f"allowed duration of {max_min} minutes for your plan."
                    )

            # Download the video
            info = ydl.extract_info(url, download=True)
            if info is None:
                raise DownloadError(
                    "Download completed but no file information returned."
                )

            # Determine the output file path
            filepath = ydl.prepare_filename(info)

            # yt-dlp might merge to mp4, check both possibilities
            if not os.path.isfile(filepath):
                # Try with .mp4 extension
                base, _ = os.path.splitext(filepath)
                filepath_mp4 = base + ".mp4"
                if os.path.isfile(filepath_mp4):
                    filepath = filepath_mp4
                else:
                    # Search output_dir for any new file
                    video_id = info.get("id", "")
                    for fname in os.listdir(output_dir):
                        if video_id and video_id in fname:
                            filepath = os.path.join(output_dir, fname)
                            break
                    else:
                        raise DownloadError(
                            "Download appeared to succeed but output file not found."
                        )

            # Cache the result (Task 12.8)
            cache_video(url, filepath)

            # Send final progress
            if on_progress:
                on_progress({
                    "status": "finished",
                    "downloaded_bytes": os.path.getsize(filepath),
                    "total_bytes": os.path.getsize(filepath),
                    "speed": None,
                    "eta": 0,
                    "percent": 100.0,
                    "filename": filepath,
                })

            return filepath

    except (DurationExceededError, VideoUnavailableError, AgeRestrictedError):
        # Re-raise our own exceptions
        raise

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e).lower()

        # Task 12.7: Classify errors into user-friendly messages
        if "private" in error_msg or "not available" in error_msg:
            raise VideoUnavailableError(
                "This video is private or unavailable. "
                "Please check the URL and ensure the video is publicly accessible."
            ) from e
        elif "age" in error_msg or "sign in" in error_msg or "login" in error_msg:
            raise AgeRestrictedError(
                "This video is age-restricted and cannot be downloaded. "
                "Age-restricted content requires authentication which is "
                "not supported by this service."
            ) from e
        elif "removed" in error_msg or "deleted" in error_msg:
            raise VideoUnavailableError(
                "This video has been removed or deleted by the uploader."
            ) from e
        elif "copyright" in error_msg:
            raise VideoUnavailableError(
                "This video is blocked due to a copyright claim and cannot "
                "be downloaded."
            ) from e
        elif "geo" in error_msg or "country" in error_msg:
            raise VideoUnavailableError(
                "This video is not available in the server's region "
                "(geo-restricted)."
            ) from e
        elif "live" in error_msg:
            raise DownloadError(
                "Live streams cannot be downloaded. Please wait until the "
                "stream has ended and a recording is available."
            ) from e
        else:
            raise DownloadError(
                f"Failed to download video: {str(e)[:300]}"
            ) from e

    except ValueError:
        raise

    except Exception as e:
        if on_progress:
            on_progress({
                "status": "error",
                "downloaded_bytes": 0,
                "total_bytes": None,
                "speed": None,
                "eta": None,
                "percent": 0.0,
                "filename": None,
            })
        raise DownloadError(
            f"Unexpected error during download: {str(e)[:300]}"
        ) from e
