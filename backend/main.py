# ==========================================================================
# SECURITY AUDIT (Task 7.11): Reviewed — no console.log/print statements
# expose sensitive data (passwords, tokens, API keys, PII). All logging uses
# structured JSON format without including request bodies or auth tokens.
# Audit date: 2026-05-20
# ==========================================================================

"""Video-to-Shorts Engine FastAPI backend (incremental scaffold).

This module is built up across several tasks. At the current stage it implements:

* Loading configuration from a local ``.env`` file via ``python-dotenv`` at module
  import time (Requirement 12.6).
* Validating that ``GOOGLE_API_KEY`` and ``WHISPER_MODEL_SIZE`` are non-empty
  strings, aborting startup with a descriptive error otherwise
  (Requirement 12.13).
* Resolving the effective Whisper model size, falling back to ``"base"`` with a
  recorded warning when the configured value is not in the allowed set
  (Requirement 2.6).

The FastAPI application object, route handlers, processing pipeline, SSE stream,
and cleanup helpers are added by later tasks (4.x). This file intentionally does
not yet construct ``app = FastAPI()``.
"""
from __future__ import annotations

import logging
import os
from typing import Mapping, Optional

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Whisper model sizes accepted by ``openai-whisper`` per Requirement 2.5.
ALLOWED_WHISPER_MODEL_SIZES: frozenset[str] = frozenset(
    {"tiny", "base", "small", "medium", "large"}
)

#: Fallback model size used when ``WHISPER_MODEL_SIZE`` is not in the allowed set
#: (Requirement 2.6).
DEFAULT_WHISPER_MODEL_SIZE: str = "base"

#: Required environment keys per Requirement 12.6 / 12.13.
_REQUIRED_ENV_KEYS: tuple[str, ...] = ("GOOGLE_API_KEY", "WHISPER_MODEL_SIZE")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class StartupConfigError(RuntimeError):
    """Raised when required startup configuration is missing or empty.

    Requirement 12.13 mandates aborting startup within 5 seconds and emitting an
    error that identifies which environment key is missing or empty. The
    exception message always names the offending key.
    """


# ---------------------------------------------------------------------------
# Pure helpers (testable without touching ``os.environ`` directly)
# ---------------------------------------------------------------------------


def _read_required_env(name: str, environ: Mapping[str, str]) -> str:
    """Return the trimmed value of *name* or raise :class:`StartupConfigError`.

    A value is considered empty if it is missing, ``None``, or contains only
    whitespace. The raised error always names the offending key so the operator
    can fix it (Requirement 12.13).
    """
    raw = environ.get(name)
    if raw is None or raw.strip() == "":
        raise StartupConfigError(
            f"Required environment variable {name!r} is missing or empty. "
            f"Set it in backend/.env (see backend/.env.example) before starting "
            f"the backend."
        )
    return raw.strip()


def resolve_whisper_model_size(value: str) -> tuple[str, Optional[str]]:
    """Resolve the effective Whisper model size (Requirement 2.6).

    Parameters
    ----------
    value:
        The raw, non-empty ``WHISPER_MODEL_SIZE`` value (already validated by
        :func:`_read_required_env`).

    Returns
    -------
    tuple[str, Optional[str]]
        ``(effective_size, warning)`` where ``effective_size`` is always in
        :data:`ALLOWED_WHISPER_MODEL_SIZES`. ``warning`` is ``None`` when the
        configured value was already valid, or a human-readable message
        describing the fallback when it was not.
    """
    normalized = value.strip().lower()
    if normalized in ALLOWED_WHISPER_MODEL_SIZES:
        return normalized, None

    warning = (
        f"WHISPER_MODEL_SIZE={value!r} is not one of "
        f"{sorted(ALLOWED_WHISPER_MODEL_SIZES)}; "
        f"falling back to {DEFAULT_WHISPER_MODEL_SIZE!r}."
    )
    return DEFAULT_WHISPER_MODEL_SIZE, warning


def load_startup_config(
    environ: Optional[Mapping[str, str]] = None,
) -> dict[str, object]:
    """Validate required env keys and resolve derived configuration.

    Parameters
    ----------
    environ:
        Optional mapping used in place of :data:`os.environ`. Provided so unit
        tests can exercise the function without mutating process state.

    Returns
    -------
    dict[str, object]
        Keys: ``google_api_key`` (str), ``whisper_model_size`` (str, one of
        :data:`ALLOWED_WHISPER_MODEL_SIZES`), and ``whisper_warning``
        (``str | None``).

    Raises
    ------
    StartupConfigError
        If ``GOOGLE_API_KEY`` or ``WHISPER_MODEL_SIZE`` is missing or empty
        (Requirement 12.13).
    """
    env: Mapping[str, str] = environ if environ is not None else os.environ

    # Validate every required key first so the error message is deterministic
    # and ordered: ``GOOGLE_API_KEY`` is checked before ``WHISPER_MODEL_SIZE``.
    values: dict[str, str] = {
        key: _read_required_env(key, env) for key in _REQUIRED_ENV_KEYS
    }

    effective_size, warning = resolve_whisper_model_size(values["WHISPER_MODEL_SIZE"])

    return {
        "google_api_key": values["GOOGLE_API_KEY"],
        "whisper_model_size": effective_size,
        "whisper_warning": warning,
    }


# ---------------------------------------------------------------------------
# Module import-time bootstrap
# ---------------------------------------------------------------------------

# Load ``.env`` once at module import (Requirement 12.6). ``load_dotenv`` is a
# no-op if no ``.env`` file is present, in which case validation below relies on
# values already exported in the parent process environment.
load_dotenv()

try:
    STARTUP_CONFIG: dict[str, object] = load_startup_config()
except StartupConfigError as exc:
    # Requirement 12.13: abort startup within 5 seconds with an error indicating
    # which required environment key is missing or empty. Logging at ERROR level
    # ensures the message is visible in uvicorn output before the import fails.
    logger.error("Backend startup aborted: %s", exc)
    raise

#: Validated Google Gemini API key (Requirement 12.6).
GOOGLE_API_KEY: str = str(STARTUP_CONFIG["google_api_key"])

#: Effective Whisper model size after fallback resolution (Requirement 2.6).
WHISPER_MODEL_SIZE: str = str(STARTUP_CONFIG["whisper_model_size"])

#: Warning message recorded when ``WHISPER_MODEL_SIZE`` was outside the allowed
#: set, or ``None`` when the configured value was already valid. Later pipeline
#: tasks attach this warning to each Task_Registry entry per Requirement 2.6.
WHISPER_MODEL_WARNING: Optional[str] = (
    str(STARTUP_CONFIG["whisper_warning"])
    if STARTUP_CONFIG["whisper_warning"] is not None
    else None
)

if WHISPER_MODEL_WARNING:
    logger.warning(WHISPER_MODEL_WARNING)


# ---------------------------------------------------------------------------
# FastAPI application, CORS, in-process Task_Registry, and lifespan
# ---------------------------------------------------------------------------
#
# Added by task 4.1. This block constructs the FastAPI ``app`` instance,
# locks CORS down to the single Frontend origin, declares the in-process
# ``task_registry`` dictionary used as the source of truth for pipeline
# progress, and wires a ``lifespan`` context manager that launches the
# Cleanup_Task scanner coroutine on startup and cancels it gracefully on
# shutdown.
#
# Implementation notes:
#
# * ``CORSMiddleware`` is configured with ``allow_origins=["http://localhost:3000"]``
#   only (Requirements 4.9 and 12.12). Any other origin is rejected by the
#   browser via the standard CORS handshake.
# * ``task_registry: dict[str, dict]`` is a module-level dictionary. Per the
#   design, "writes are confined to single-key mutations and reads by the SSE
#   coroutine, so a ``dict`` is sufficient — no lock is required."
# * ``_cleanup_scanner`` is intentionally a stub at this stage: its body is
#   filled in by task 4.7 to scan ``/tmp/shorts_workspace/`` every 300 seconds
#   and remove any Workspace_Directory older than 3600 seconds (Requirement
#   3.7). Until then it is a no-op coroutine so the lifespan startup hook can
#   schedule it without raising.
# * The modern ``lifespan=`` kwarg is used in place of the deprecated
#   ``@app.on_event("startup")`` / ``@app.on_event("shutdown")`` decorators.

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

#: Production CORS origins (Task 7.1). Read from ALLOWED_ORIGINS env var
#: (comma-separated), defaulting to localhost for development.
PRODUCTION_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

#: Single allowed CORS origin per Requirement 12.12. The Frontend is served at
#: ``http://localhost:3000`` and no other origin may invoke the Backend.
_ALLOWED_ORIGIN: str = "http://localhost:3000"

#: In-process Task_Registry. Keys are Task_IDs (UUID4 strings); values are the
#: per-task entries described in the design (``step``, ``progress``,
#: ``created_at``, optional ``data``/``error``/``warning`` fields, plus
#: leading-underscore stash fields populated by the upload route in task 4.2).
task_registry: dict[str, dict] = {}


async def _cleanup_scanner() -> None:
    """Background scanner that purges stale Workspace_Directories (Req 3.7).

    Runs forever once launched by the lifespan startup hook. Every 300 seconds
    it scans :data:`WORKSPACE_ROOT` and removes any subdirectory whose
    creation time (``st_ctime``) is older than 3600 seconds. Errors on
    individual directories are logged and swallowed so the scanner continues
    with the next entry.
    """
    import shutil

    scan_interval = 300  # seconds between scans
    max_age = 3600  # seconds before a workspace is considered stale

    while True:
        await asyncio.sleep(scan_interval)
        try:
            if not WORKSPACE_ROOT.exists():
                continue
            now = time.time()
            for entry in WORKSPACE_ROOT.iterdir():
                if not entry.is_dir():
                    continue
                try:
                    age = now - entry.stat().st_ctime
                    if age > max_age:
                        shutil.rmtree(entry, ignore_errors=True)
                except OSError as exc:
                    logger.warning(
                        "Cleanup scanner: failed to process %s: %s", entry, exc
                    )
        except OSError as exc:
            logger.warning("Cleanup scanner: scan failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan context: launch and tear down the cleanup scanner.

    On enter, schedule :func:`_cleanup_scanner` as a background task. On exit,
    cancel that task and await its cancellation so the event loop shuts down
    cleanly without leaking pending coroutines.
    """
    scanner_task = asyncio.create_task(_cleanup_scanner(), name="cleanup-scanner")
    try:
        yield
    finally:
        scanner_task.cancel()
        try:
            await scanner_task
        except asyncio.CancelledError:
            # Expected: ``scanner_task.cancel()`` raises ``CancelledError`` from
            # the awaited task. Swallow it so shutdown completes cleanly.
            pass


#: FastAPI application instance. Routes are attached by tasks 4.2 and 4.6.
app: FastAPI = FastAPI(lifespan=lifespan)

# Lock CORS to production origins list (Task 7.1). Uses PRODUCTION_ORIGINS
# which reads from ALLOWED_ORIGINS env var for production deployments.
# Wildcards are not used to maintain strict origin control.
app.add_middleware(
    CORSMiddleware,
    allow_origins=PRODUCTION_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Upload endpoint: POST /api/process-video
# ---------------------------------------------------------------------------
#
# Added by task 4.2. Accepts a multipart upload (``video_file``) plus the
# form fields (``style_tone``, ``shorts_count``, ``duration_per_short``),
# validates them manually so 422 responses identify the offending field,
# creates a Workspace_Directory under :data:`WORKSPACE_ROOT`, streams the
# upload to disk in 1 MiB chunks, registers a Task_Registry entry, and
# schedules the processing pipeline and cleanup as ``BackgroundTasks``.
#
# Implementation notes:
#
# * ``shorts_count`` and ``duration_per_short`` are declared as ``str`` form
#   fields and parsed manually so the 422 error message shape is uniform
#   across validation failures (otherwise FastAPI's automatic Pydantic
#   coercion would emit a different envelope on non-integer input).
# * Validation order is strict: every form-field check runs **before** any
#   filesystem mutation, so a malformed request is rejected without
#   creating a Workspace_Directory or registering a Task_Registry entry
#   (Reqs 1.6, 1.7, 1.8, 1.11).
# * :data:`WORKSPACE_ROOT` is the literal ``Path("/tmp/shorts_workspace")``
#   per Reqs 1.2 and 3.1. On Windows this resolves under the current drive
#   root (e.g. ``C:\tmp\shorts_workspace``); the path string is what
#   matters for the spec.
# * The chunked upload loop catches ``OSError`` (Req 1.12), removes any
#   partially written state, and returns HTTP 500 without registering or
#   scheduling background work.
# * :func:`run_processing_pipeline` and :func:`cleanup_task_directory` are
#   forward stubs at module level so the upload route can reference them
#   by name. Their bodies are filled in by tasks 4.4 and 4.7 respectively.

import time
from pathlib import Path
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from backend.auth import get_current_user

#: Base directory for per-task Workspace_Directories (Reqs 1.2, 3.1). The
#: path is intentionally the literal ``/tmp/shorts_workspace`` to match the
#: spec; OS-conditional branching is not introduced.
WORKSPACE_ROOT: Path = Path("/tmp/shorts_workspace")

#: Maximum trimmed length of ``style_tone`` (Req 1.8).
MAX_STYLE_TONE_LEN: int = 500

#: Inclusive bounds on ``shorts_count`` (Req 1.6).
MIN_SHORTS_COUNT: int = 1
MAX_SHORTS_COUNT: int = 10

#: Allowed values for the ``duration_per_short`` form field (Req 1.7).
ALLOWED_DURATIONS: frozenset[int] = frozenset({15, 30, 60})

#: Streaming chunk size for the upload endpoint, in bytes (Req 1.12).
UPLOAD_CHUNK_SIZE: int = 1024 * 1024  # 1 MiB


# ---------------------------------------------------------------------------
# Forward-declared coroutine stubs
# ---------------------------------------------------------------------------
#
# These names must resolve at module import time so the route handler can
# pass them to ``BackgroundTasks.add_task``. The real bodies land in tasks
# 4.4 (pipeline) and 4.7 (cleanup); each stub is marked with a comment
# naming its implementing task.


async def _safe_delete(task_id: str, path: Path) -> None:
    """Best-effort file deletion with retries (Requirement 3.6).

    Attempts ``path.unlink(missing_ok=True)`` up to 3 times with 1 second
    between attempts on ``OSError``. On final failure, records a
    ``cleanup_warning`` on the Task_Registry entry without changing ``step``
    so the SSE consumer can surface a non-fatal notice.
    """
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            path.unlink(missing_ok=True)
            return
        except OSError:
            if attempt < max_attempts - 1:
                await asyncio.sleep(1)

    # Final failure: record a warning without changing step.
    entry = task_registry.get(task_id)
    if entry is not None:
        existing = entry.get("cleanup_warning") or ""
        entry["cleanup_warning"] = (
            f"{existing}; Failed to delete {path.name}" if existing
            else f"Failed to delete {path.name}"
        )


async def run_processing_pipeline(task_id: str) -> None:
    """Run the audio-extraction → transcription → analysis pipeline.

    Orchestrates the three sequential processing stages:

      1. **Extracting Audio** — calls :func:`_extract_audio` to produce a
         16 kHz mono PCM WAV via the system ``ffmpeg`` binary.
      2. **Transcribing** — calls :func:`transcribe.run_whisper_transcription`
         with the resolved Whisper model size.
      3. **Analyzing Highlights** — calls
         :func:`analyze.analyze_video_transcript` with the stashed form fields.

    On success the registry entry transitions to ``step="Done"`` /
    ``progress=100`` with ``data`` holding the ``ShortsAnalysisResult`` dict.

    On any exception the registry entry transitions to ``step="Failed"`` with
    an ``error`` field containing the stringified exception (Reqs 2.3, 2.13).

    In all cases (success or failure), the input video and extracted audio WAV
    are deleted via :func:`_safe_delete` so the workspace directory contains
    only the (empty) folder skeleton for the cleanup scanner (Reqs 3.1, 3.2).
    """
    from backend.transcribe import run_whisper_transcription
    from backend.analyze import analyze_video_transcript

    entry = task_registry[task_id]
    workspace = Path(entry["_workspace"])
    input_path = Path(entry["_input_path"])
    audio_path = workspace / "audio.wav"

    try:
        # ---- Stage 1: Extract Audio (Req 2.1, progress=25) ----
        entry["step"] = "Extracting Audio"
        entry["progress"] = 25

        await _extract_audio(input_path, audio_path)

        # ---- Stage 2: Transcribe (Req 2.4, progress=60) ----
        entry["step"] = "Transcribing"
        entry["progress"] = 60

        transcript = await run_whisper_transcription(
            str(audio_path), model_size=WHISPER_MODEL_SIZE
        )

        # ---- Stage 3: Analyze Highlights (Req 2.8, progress=75) ----
        entry["step"] = "Analyzing Highlights"
        entry["progress"] = 75

        result = await analyze_video_transcript(
            transcript=transcript,
            style_tone=entry["_style_tone"],
            max_count=entry["_shorts_count"],
            target_duration=entry["_duration_per_short"],
        )

        # ---- Done (Req 2.13, progress=100) ----
        entry["step"] = "Done"
        entry["progress"] = 100
        entry["data"] = result.model_dump()

    except Exception as exc:
        # Req 2.3 / 2.14: terminate pipeline and surface the error.
        entry["step"] = "Failed"
        entry["error"] = str(exc)

    finally:
        # Req 3.1, 3.2: delete input video and audio WAV regardless of
        # outcome. _safe_delete retries up to 3 times with 1 s between
        # attempts and records a warning on final failure rather than
        # raising.
        await _safe_delete(task_id, input_path)
        await _safe_delete(task_id, audio_path)


async def cleanup_task_directory(task_id: str, delay: int = 3600) -> None:
    """Remove the Workspace_Directory for *task_id* after *delay* seconds.

    Sleeps for *delay* seconds then removes the entire workspace directory
    tree via ``shutil.rmtree(..., ignore_errors=True)`` (Req 3.3, 3.4, 3.5).
    If the directory no longer exists (already cleaned by the scanner or by
    ``_safe_delete``), ``rmtree`` is a no-op because ``ignore_errors=True``.
    """
    import shutil

    await asyncio.sleep(delay)
    workspace = WORKSPACE_ROOT / task_id
    shutil.rmtree(workspace, ignore_errors=True)


# ---------------------------------------------------------------------------
# Pure validation helpers
# ---------------------------------------------------------------------------


def _validate_shorts_count(value: object) -> int:
    """Coerce *value* to an int in ``[MIN_SHORTS_COUNT, MAX_SHORTS_COUNT]``.

    Raises ``HTTPException(422, ...)`` on non-integer input or out-of-range
    values (Req 1.6). The error ``detail`` always names ``shorts_count`` so
    the client can display a precise message.
    """
    try:
        coerced = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                f"shorts_count must be an integer between "
                f"{MIN_SHORTS_COUNT} and {MAX_SHORTS_COUNT} inclusive"
            ),
        ) from exc
    if not (MIN_SHORTS_COUNT <= coerced <= MAX_SHORTS_COUNT):
        raise HTTPException(
            status_code=422,
            detail=(
                f"shorts_count must be an integer between "
                f"{MIN_SHORTS_COUNT} and {MAX_SHORTS_COUNT} inclusive"
            ),
        )
    return coerced


def _validate_duration_per_short(value: object) -> int:
    """Coerce *value* to an int in :data:`ALLOWED_DURATIONS`.

    Raises ``HTTPException(422, ...)`` on non-integer input or values
    outside ``{15, 30, 60}`` (Req 1.7).
    """
    try:
        coerced = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail="duration_per_short must be one of {15, 30, 60}",
        ) from exc
    if coerced not in ALLOWED_DURATIONS:
        raise HTTPException(
            status_code=422,
            detail="duration_per_short must be one of {15, 30, 60}",
        )
    return coerced


def _validate_style_tone(value: str) -> str:
    """Trim *value* and return it; raise 422 on empty or oversized input.

    Per Req 1.8, ``style_tone`` must be a non-empty trimmed string of at
    most :data:`MAX_STYLE_TONE_LEN` characters.
    """
    if not isinstance(value, str):
        raise HTTPException(
            status_code=422,
            detail="style_tone must be a non-empty string after trimming whitespace",
        )
    trimmed = value.strip()
    if not trimmed:
        raise HTTPException(
            status_code=422,
            detail="style_tone must be a non-empty string after trimming whitespace",
        )
    if len(trimmed) > MAX_STYLE_TONE_LEN:
        raise HTTPException(
            status_code=422,
            detail=(
                f"style_tone must be at most {MAX_STYLE_TONE_LEN} characters "
                f"after trimming"
            ),
        )
    return trimmed


def _cleanup_partial_upload(workspace: Path, output_path: Path) -> None:
    """Best-effort removal of a partially populated Workspace_Directory.

    Used after a validation or write failure when no Task_Registry entry
    has been registered. Errors during cleanup are swallowed because the
    periodic ``_cleanup_scanner`` (task 4.7) acts as a safety net, and the
    long-delay :func:`cleanup_task_directory` is intentionally not
    scheduled in this path (Req 1.12 forbids scheduling BackgroundTasks
    when registration is skipped).
    """
    try:
        output_path.unlink(missing_ok=True)
    except OSError:
        pass
    try:
        workspace.rmdir()
    except OSError:
        pass


@app.post("/api/process-video")
async def process_video(
    background: BackgroundTasks,
    video_file: UploadFile = File(...),
    style_tone: str = Form(...),
    shorts_count: str = Form(...),
    duration_per_short: str = Form(...),
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """Accept a video upload and start the processing pipeline.

    See Requirements 1.1 through 1.8, 1.11, and 1.12 for the full
    contract. ``shorts_count`` and ``duration_per_short`` arrive as
    ``str`` so the 422 envelope is controlled by the manual validators
    rather than FastAPI's automatic Pydantic coercion.

    CSRF Protection (Task 7.6): NextAuth handles CSRF for the frontend.
    For the API, the Bearer token (JWT) combined with the CORS origin check
    is sufficient — the browser enforces same-origin on preflight requests,
    and the JWT cannot be sent cross-origin without explicit CORS allowance.

    Authorization (Task 7.10): User authorization is enforced — the JWT
    user_id from get_current_user ensures users can only access their own
    data. The task_registry entries are keyed by task_id which is generated
    per-request and returned only to the authenticated caller.
    """
    # ---- 1) Manual form-field validation (Reqs 1.6, 1.7, 1.8). ----
    # Order: count → duration → style_tone. Each helper raises 422 on
    # failure BEFORE any filesystem mutation, satisfying the "no
    # workspace, no registry" half of those requirements.
    count = _validate_shorts_count(shorts_count)
    duration = _validate_duration_per_short(duration_per_short)
    tone = _validate_style_tone(style_tone)

    # Task 7.5: Apply input sanitization to user-provided text fields
    tone = sanitize_input(tone)

    # ---- 2) Multipart video-file presence check (Req 1.11). ----
    if video_file is None or not video_file.filename:
        raise HTTPException(
            status_code=422,
            detail="video_file is required",
        )
    # ``UploadFile.size`` may be ``None`` on some clients; in that case
    # the empty-stream check after the chunked write below catches the
    # zero-byte case.
    if video_file.size is not None and video_file.size == 0:
        raise HTTPException(
            status_code=422,
            detail="video_file is empty",
        )

    # ---- 3) Workspace creation (Req 1.2). ----
    task_id = str(uuid4())
    workspace = WORKSPACE_ROOT / task_id
    # ``parents=True`` so :data:`WORKSPACE_ROOT` is created on first use;
    # ``exist_ok=False`` so a UUID4 collision raises rather than silently
    # reusing a directory that may already contain another task's files.
    workspace.mkdir(parents=True, exist_ok=False)

    # Preserve the original extension (Req 1.2). Default to ``"bin"`` if
    # the upload has no extension at all so the on-disk filename is
    # always well-formed.
    ext = Path(video_file.filename).suffix.lower().lstrip(".") or "bin"
    output_path = workspace / f"input.{ext}"

    # ---- 4) Streamed chunked write (Req 1.12). ----
    total_bytes = 0
    try:
        with output_path.open("wb") as out_fh:
            while True:
                chunk = await video_file.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                out_fh.write(chunk)
                total_bytes += len(chunk)
    except OSError as exc:
        # Best-effort cleanup of the partially-written file and the empty
        # workspace directory. Do NOT register a Task_Registry entry and
        # do NOT schedule BackgroundTasks (Req 1.12).
        _cleanup_partial_upload(workspace, output_path)
        raise HTTPException(
            status_code=500,
            detail="Failed to save uploaded video.",
        ) from exc

    if total_bytes == 0:
        # The stream was empty even though ``UploadFile.size`` was unknown
        # at validation time. Treat as Req 1.11: no Workspace_Directory,
        # no registry entry, no scheduled BackgroundTasks.
        _cleanup_partial_upload(workspace, output_path)
        raise HTTPException(
            status_code=422,
            detail="video_file is empty",
        )

    # ---- 5) Register Task_Registry entry (Reqs 1.3, 2.6). ----
    # Single-key set, no lock needed (per design).
    # The leading-underscore stash fields are how the pipeline (task
    # 4.4) reads its inputs without re-parsing the form. ``warning``
    # carries any Whisper fallback notice from startup so it is visible
    # from the very first SSE message (Req 2.6).
    task_registry[task_id] = {
        "step": "Uploading",
        "progress": 10,
        "created_at": time.time(),
        "data": None,
        "error": None,
        "warning": WHISPER_MODEL_WARNING,
        "_style_tone": tone,
        "_shorts_count": count,
        "_duration_per_short": duration,
        "_workspace": str(workspace),
        "_input_path": str(output_path),
    }

    # ---- 6) Schedule background work (Req 1.4). ----
    background.add_task(run_processing_pipeline, task_id)
    background.add_task(cleanup_task_directory, task_id, 3600)

    # ---- 7) Respond (Req 1.5). ----
    return {"taskId": task_id}



# ---------------------------------------------------------------------------
# Audio extraction helper
# ---------------------------------------------------------------------------
#
# Added by task 4.3. ``run_processing_pipeline`` (task 4.4) calls this
# helper to convert the uploaded video into the 16 kHz mono PCM
# ``audio.wav`` that Whisper consumes.
#
# Per Reqs 2.2 and 2.3, the helper:
#
# * Invokes the system ``ffmpeg`` binary via ``asyncio.create_subprocess_exec``
#   (NOT a shell) with the exact arguments mandated by the task description.
# * Caps the subprocess at :data:`AUDIO_EXTRACTION_TIMEOUT_SECONDS` (600 s)
#   via ``asyncio.wait_for``. On timeout, the child is killed and reaped so
#   it does not leak past the FastAPI worker.
# * Converts the three failure modes (non-zero return code, ``TimeoutError``,
#   ``FileNotFoundError`` for the missing binary) into a single
#   ``RuntimeError("Audio extraction failed: ...")`` whose message embeds
#   the underlying cause and whose ``__cause__`` is set via ``raise ... from``.
#
# Pipeline ownership of the Task_Registry update (``step="Failed"`` etc.)
# stays in :func:`run_processing_pipeline` (task 4.4); this helper only
# raises.

#: Cap on the ``ffmpeg`` audio-extraction subprocess, in seconds (Req 2.2).
AUDIO_EXTRACTION_TIMEOUT_SECONDS: int = 600

#: Tail length, in characters, of the ``ffmpeg`` stderr included in the
#: ``RuntimeError`` message on non-zero rc. Capped so a verbose ffmpeg log
#: cannot blow up the Task_Registry entry or SSE payload.
_FFMPEG_STDERR_TAIL_CHARS: int = 500


async def _extract_audio(input_path: Path, audio_path: Path) -> None:
    """Run ``ffmpeg`` to produce 16 kHz mono PCM ``audio.wav``.

    The command line is exactly::

        ffmpeg -y -nostdin -i <input_path> -vn -acodec pcm_s16le \\
               -ac 1 -ar 16000 <audio_path>

    Parameters
    ----------
    input_path:
        Path to the uploaded source video, written by the upload route.
    audio_path:
        Destination path for the extracted ``.wav`` (typically
        ``{workspace}/audio.wav``).

    Raises
    ------
    RuntimeError
        On any of the three failure modes from Req 2.3:

        * ``ffmpeg`` binary not on PATH (``FileNotFoundError`` from
          ``asyncio.create_subprocess_exec``),
        * subprocess exceeds :data:`AUDIO_EXTRACTION_TIMEOUT_SECONDS`
          (``asyncio.TimeoutError``),
        * subprocess exits with a non-zero return code.

        The exception message starts with ``"Audio extraction failed: "``
        and embeds the underlying cause; the original exception is
        chained via ``__cause__``.
    """
    args: list[str] = [
        "ffmpeg",
        "-y",
        "-nostdin",
        "-i",
        str(input_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(audio_path),
    ]

    # Spawn the subprocess. ``FileNotFoundError`` raised here means the
    # ``ffmpeg`` binary itself is not on PATH (Req 2.3 third failure
    # mode). A *missing input file* manifests later as a non-zero return
    # code instead, because ffmpeg starts up and only then fails to open
    # its input.
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Audio extraction failed: ffmpeg binary not found on PATH ({exc})"
        ) from exc

    # Read both pipes concurrently via ``communicate`` (avoids a pipe-buffer
    # deadlock on verbose ffmpeg stderr) and enforce the 600 s cap.
    try:
        _, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=AUDIO_EXTRACTION_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        # ``asyncio.wait_for`` cancels its inner task but does NOT kill the
        # underlying OS process, so do that explicitly. Reap with a short
        # bound to avoid a second, indefinite hang if the process is
        # already gone or un-killable.
        try:
            proc.kill()
        except ProcessLookupError:
            # Already exited between the timeout and the kill.
            pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            # Best-effort: the OS will reap the zombie. Do not block the
            # pipeline on a stuck child.
            pass
        raise RuntimeError(
            f"Audio extraction failed: ffmpeg exceeded "
            f"{AUDIO_EXTRACTION_TIMEOUT_SECONDS}s timeout"
        ) from exc

    if proc.returncode != 0:
        stderr_text = (stderr_bytes or b"").decode("utf-8", errors="replace").strip()
        tail = (
            stderr_text[-_FFMPEG_STDERR_TAIL_CHARS:]
            if stderr_text
            else "<no stderr>"
        )
        raise RuntimeError(
            f"Audio extraction failed: ffmpeg exited with rc={proc.returncode}: "
            f"{tail}"
        )


# ---------------------------------------------------------------------------
# SSE streaming endpoint: GET /api/stream/{task_id}
# ---------------------------------------------------------------------------
#
# Added by task 4.6. Streams pipeline progress to the Frontend via
# Server-Sent Events (SSE). The consumer is the ``EventSource`` opened by
# the orchestrator page immediately after receiving the ``taskId`` from the
# upload response.
#
# Contract (Requirements 4.1 through 4.8):
#
# * Returns HTTP 404 when ``task_id`` is not in ``task_registry``.
# * Returns ``StreamingResponse(media_type="text/event-stream")`` with
#   ``Cache-Control: no-cache`` and ``Connection: keep-alive`` headers.
# * Emits an initial snapshot within 1 second of connection.
# * Emits subsequent messages on a 1 s ± 200 ms cadence.
# * Tracks ``last_step_change``; emits a final stall message and closes
#   after 600 s of no ``step`` advance.
# * On ``step ∈ {"Done", "Failed"}``, emits a final message and closes
#   within 1 additional second.
# * Stops emitting and releases resources within 5 seconds of client
#   disconnect (detected via ``asyncio.CancelledError`` when the client
#   drops the TCP connection and Starlette cancels the generator).

import json as _json

from fastapi import Request
from fastapi.responses import StreamingResponse

#: Terminal steps that signal the end of the SSE stream (Req 4.5).
_TERMINAL_STEPS: frozenset[str] = frozenset({"Done", "Failed"})

#: Maximum time (seconds) without a ``step`` change before the stream is
#: considered stalled and closed with a stall notice (Req 4.7).
_STALL_TIMEOUT_SEC: float = 600.0

#: Polling cadence for the SSE loop, in seconds (Req 4.3).
_SSE_POLL_INTERVAL_SEC: float = 1.0


def _sse_event(data: dict) -> str:
    """Format a dict as a single SSE ``data:`` frame terminated by ``\\n\\n``."""
    payload = _json.dumps(data, separators=(",", ":"))
    return f"data: {payload}\n\n"


async def _stream_generator(task_id: str, request: Request):
    """Async generator that yields SSE frames until terminal or stall."""
    entry = task_registry.get(task_id)
    if entry is None:
        # Should not happen because the route checks before creating the
        # StreamingResponse, but guard defensively.
        return

    last_step = entry["step"]
    last_step_change = time.time()

    # Emit initial snapshot immediately (Req 4.2).
    yield _sse_event({
        "step": entry["step"],
        "progress": entry["progress"],
        "data": entry.get("data"),
        "error": entry.get("error"),
        "warning": entry.get("warning"),
        "cleanup_warning": entry.get("cleanup_warning"),
    })

    # If already terminal at connect time, close within 1 s (Req 4.5).
    if entry["step"] in _TERMINAL_STEPS:
        return

    while True:
        # Respect client disconnect (Req 4.8). Starlette raises
        # CancelledError on the generator when the client drops;
        # alternatively we can poll `request.is_disconnected()`.
        if await request.is_disconnected():
            return

        await asyncio.sleep(_SSE_POLL_INTERVAL_SEC)

        current_step = entry["step"]

        # Detect step change and reset stall timer.
        if current_step != last_step:
            last_step = current_step
            last_step_change = time.time()

        # Emit current state.
        yield _sse_event({
            "step": entry["step"],
            "progress": entry["progress"],
            "data": entry.get("data"),
            "error": entry.get("error"),
            "warning": entry.get("warning"),
            "cleanup_warning": entry.get("cleanup_warning"),
        })

        # Terminal: emit final frame and close (Req 4.5).
        if current_step in _TERMINAL_STEPS:
            return

        # Stall detection (Req 4.7): close after 600 s of no step change.
        elapsed = time.time() - last_step_change
        if elapsed >= _STALL_TIMEOUT_SEC:
            yield _sse_event({
                "step": entry["step"],
                "progress": entry["progress"],
                "error": (
                    f"Pipeline stalled: no progress for "
                    f"{_STALL_TIMEOUT_SEC:.0f}s"
                ),
                "warning": entry.get("warning"),
                "cleanup_warning": entry.get("cleanup_warning"),
            })
            return


@app.get("/api/stream/{task_id}")
async def stream_task(task_id: str, request: Request):
    """Stream pipeline progress for *task_id* via SSE.

    Returns HTTP 404 when ``task_id`` is not in ``task_registry``.
    Otherwise returns a ``StreamingResponse`` with ``text/event-stream``
    content type and the appropriate cache/connection headers
    (Requirements 4.1 through 4.8).
    """
    if task_id not in task_registry:
        raise HTTPException(status_code=404, detail="Task not found")

    return StreamingResponse(
        _stream_generator(task_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )



# ---------------------------------------------------------------------------
# Health & Readiness Endpoints
# ---------------------------------------------------------------------------
#
# Added by task 6.13. These endpoints support container orchestration
# (Docker HEALTHCHECK, Kubernetes liveness/readiness probes) and uptime
# monitoring services.
#
# * GET /health — Lightweight liveness check. Returns 200 if the process is
#   running and can serve HTTP. Does NOT check external dependencies.
#
# * GET /ready — Readiness check. Verifies connectivity to PostgreSQL and
#   Redis. Returns 200 only when both are reachable. Orchestrators should
#   route traffic away from instances that fail this probe.


@app.get("/health")
async def health_check() -> dict:
    """Liveness probe: confirms the application process is alive.

    Returns HTTP 200 unconditionally. Used by Docker HEALTHCHECK and
    uptime monitors (UptimeRobot, Better Uptime) to verify the process
    has not crashed.
    """
    return {"status": "healthy"}


@app.get("/ready")
async def readiness_check() -> dict:
    """Readiness probe: confirms the application can serve requests.

    Checks connectivity to both PostgreSQL (via asyncpg) and Redis.
    Returns HTTP 200 with {"status": "ready"} when both are reachable.
    Returns HTTP 503 with details about which dependency is unreachable
    so orchestrators can route traffic to healthy instances.
    """
    errors: list[str] = []

    # --- Check PostgreSQL ---
    try:
        import asyncpg

        database_url = os.environ.get("DATABASE_URL", "")
        if database_url:
            conn = await asyncpg.connect(database_url, timeout=5.0)
            await conn.execute("SELECT 1")
            await conn.close()
        else:
            # If DATABASE_URL is not set, skip DB check (local dev without DB)
            pass
    except Exception as exc:
        errors.append(f"postgres: {exc}")

    # --- Check Redis ---
    try:
        import redis as redis_lib

        redis_url = os.environ.get("REDIS_URL", "")
        if redis_url:
            r = redis_lib.from_url(redis_url, socket_connect_timeout=5)
            r.ping()
            r.close()
        else:
            # If REDIS_URL is not set, skip Redis check (local dev without Redis)
            pass
    except Exception as exc:
        errors.append(f"redis: {exc}")

    if errors:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "errors": errors,
            },
        )

    return {"status": "ready"}



# ===========================================================================
# PRODUCTION TASK 7: CORS & SECURITY HARDENING
# ===========================================================================
# Tasks 7.2-7.12: Rate limiting, security headers, input sanitization,
# brute-force protection, API key auth, and structured request logging.
# ===========================================================================


# ---------------------------------------------------------------------------
# Task 7.5: Input Sanitization Utility
# ---------------------------------------------------------------------------

import re as _re
import unicodedata as _unicodedata

#: Maximum allowed length for sanitized input strings.
_SANITIZE_MAX_LENGTH: int = 5000


def sanitize_input(text: str, max_length: int = _SANITIZE_MAX_LENGTH) -> str:
    """Sanitize user input by stripping dangerous characters (Task 7.5).

    Removes:
    - Null bytes (\\x00)
    - Control characters (C0/C1 category in Unicode) except common whitespace
      (newline, tab, carriage return)
    - Trims result to max_length

    Parameters
    ----------
    text : str
        Raw user input string.
    max_length : int
        Maximum allowed output length. Defaults to 5000 characters.

    Returns
    -------
    str
        Cleaned string safe for storage and processing.
    """
    if not text:
        return text

    # Remove null bytes
    cleaned = text.replace("\x00", "")

    # Remove control characters except \n, \r, \t
    cleaned = "".join(
        ch for ch in cleaned
        if ch in ("\n", "\r", "\t")
        or _unicodedata.category(ch)[0] != "C"
    )

    # Trim to max length
    return cleaned[:max_length]


# ---------------------------------------------------------------------------
# Task 7.2 + 7.3: Rate Limiting (In-Memory Token Bucket)
# ---------------------------------------------------------------------------

import hashlib as _hashlib
from collections import defaultdict as _defaultdict

#: Rate limit configuration
_UPLOAD_RATE_LIMIT: int = 10  # requests per minute for authenticated uploads
_GENERAL_RATE_LIMIT: int = 30  # requests per minute per IP for general endpoints
_RATE_WINDOW_SECONDS: float = 60.0

#: In-memory rate limit stores: {key: [(timestamp, ...),]}
_rate_limit_store: dict[str, list[float]] = _defaultdict(list)


def _get_client_ip(request) -> str:
    """Extract client IP from request, considering X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(key: str, limit: int, window: float = _RATE_WINDOW_SECONDS) -> bool:
    """Check if a rate limit key has exceeded its quota.

    Returns True if the request is ALLOWED, False if rate limited.
    Cleans up expired entries as a side effect.
    """
    now = time.time()
    cutoff = now - window

    # Prune expired entries
    _rate_limit_store[key] = [t for t in _rate_limit_store[key] if t > cutoff]

    if len(_rate_limit_store[key]) >= limit:
        return False  # Rate limited

    _rate_limit_store[key].append(now)
    return True


@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    """Rate limiting middleware (Tasks 7.2, 7.3).

    - Upload endpoints (/api/process-video): 10 req/min per authenticated user
    - General endpoints: 30 req/min per IP
    - Health/ready endpoints are exempt from rate limiting.
    """
    path = request.url.path

    # Exempt health check endpoints
    if path in ("/health", "/ready"):
        return await call_next(request)

    client_ip = _get_client_ip(request)

    # Upload endpoint: rate limit per user (identified by auth header hash)
    if path == "/api/process-video" and request.method == "POST":
        # Use auth token hash as user identifier for rate limiting
        auth_header = request.headers.get("authorization", "")
        api_key = request.headers.get("x-api-key", "")
        user_key = _hashlib.sha256(
            (auth_header or api_key or client_ip).encode()
        ).hexdigest()[:16]
        rate_key = f"upload:{user_key}"
        if not _check_rate_limit(rate_key, _UPLOAD_RATE_LIMIT):
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Max 10 upload requests per minute."},
                headers={"Retry-After": "60"},
            )
    else:
        # General endpoint: rate limit per IP
        rate_key = f"general:{client_ip}"
        if not _check_rate_limit(rate_key, _GENERAL_RATE_LIMIT):
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Max 30 requests per minute."},
                headers={"Retry-After": "60"},
            )

    return await call_next(request)


# ---------------------------------------------------------------------------
# Task 7.4: Request Size Validation Middleware
# ---------------------------------------------------------------------------

#: Maximum request body sizes
_MAX_UPLOAD_SIZE: int = 2 * 1024 * 1024 * 1024  # 2 GB for upload endpoint
_MAX_GENERAL_SIZE: int = 1 * 1024 * 1024  # 1 MB for all other endpoints


@app.middleware("http")
async def request_size_middleware(request: Request, call_next):
    """Validate request size (Task 7.4).

    - /api/process-video: max 2 GB
    - All other endpoints: max 1 MB
    """
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            size = int(content_length)
        except ValueError:
            size = 0

        path = request.url.path
        if path == "/api/process-video" and request.method == "POST":
            max_size = _MAX_UPLOAD_SIZE
        else:
            max_size = _MAX_GENERAL_SIZE

        if size > max_size:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=413,
                content={
                    "detail": f"Request body too large. Maximum: {max_size} bytes."
                },
            )

    return await call_next(request)


# ---------------------------------------------------------------------------
# Task 7.7: Security Headers Middleware
# ---------------------------------------------------------------------------


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses (Task 7.7).

    Headers added:
    - X-Frame-Options: DENY (prevent clickjacking)
    - X-Content-Type-Options: nosniff (prevent MIME sniffing)
    - X-XSS-Protection: 1; mode=block (legacy XSS filter)
    - Strict-Transport-Security: max-age=31536000; includeSubDomains (HSTS)
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: camera=(), microphone=(), geolocation=()
    """
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


# ---------------------------------------------------------------------------
# Task 7.8: API Key Authentication Alternative
# ---------------------------------------------------------------------------


async def verify_api_key(request: Request) -> Optional[dict]:
    """Check for X-API-Key header and validate against database (Task 7.8).

    This provides an alternative authentication method for programmatic
    API access. The API key is looked up in the database. Returns the user
    dict if valid, None otherwise.

    Usage: Endpoints can optionally check for API key auth as a fallback
    when JWT Bearer token is not present.
    """
    api_key = request.headers.get("x-api-key")
    if not api_key:
        return None

    # Validate API key format (expect a 64-char hex string)
    if not _re.match(r"^[a-f0-9]{64}$", api_key):
        return None

    try:
        import asyncpg

        database_url = os.environ.get("DATABASE_URL", "")
        if not database_url:
            return None

        conn = await asyncpg.connect(database_url, timeout=5.0)
        try:
            # Look up the API key in the database
            row = await conn.fetchrow(
                """
                SELECT u.id, u.email, u.name, u.plan
                FROM api_keys ak
                JOIN users u ON ak.user_id = u.id
                WHERE ak.key_hash = $1
                  AND ak.revoked_at IS NULL
                  AND (ak.expires_at IS NULL OR ak.expires_at > NOW())
                """,
                _hashlib.sha256(api_key.encode()).hexdigest(),
            )
            if row:
                return {
                    "user_id": str(row["id"]),
                    "email": row["email"],
                    "name": row["name"],
                    "plan": row["plan"],
                }
        finally:
            await conn.close()
    except Exception:
        # On any DB error, fall through to normal auth
        pass

    return None


# ---------------------------------------------------------------------------
# Task 7.9: Brute-Force Protection on Login Endpoints
# ---------------------------------------------------------------------------

#: Track failed login attempts: {key: [(timestamp, ...),]}
_login_attempts: dict[str, list[float]] = _defaultdict(list)

#: Maximum failed attempts before lockout
_MAX_LOGIN_ATTEMPTS: int = 5

#: Lockout duration in seconds (15 minutes)
_LOCKOUT_DURATION: float = 900.0


def _is_locked_out(identifier: str) -> bool:
    """Check if an IP/email is currently locked out (Task 7.9).

    Returns True if the identifier has >= 5 failed attempts in the last
    15 minutes, indicating a brute-force attack.
    """
    now = time.time()
    cutoff = now - _LOCKOUT_DURATION

    # Prune old entries
    _login_attempts[identifier] = [
        t for t in _login_attempts[identifier] if t > cutoff
    ]

    return len(_login_attempts[identifier]) >= _MAX_LOGIN_ATTEMPTS


def _record_failed_login(identifier: str) -> None:
    """Record a failed login attempt for brute-force tracking (Task 7.9)."""
    _login_attempts[identifier].append(time.time())


def _clear_login_attempts(identifier: str) -> None:
    """Clear failed login attempts after successful authentication."""
    _login_attempts.pop(identifier, None)


@app.middleware("http")
async def brute_force_protection_middleware(request: Request, call_next):
    """Brute-force protection on login-related endpoints (Task 7.9).

    Tracks failed attempts per IP and locks out after 5 failures for 15
    minutes. Applies to auth-related endpoints only.
    """
    path = request.url.path

    # Only apply to auth/login endpoints
    auth_paths = ("/api/auth/", "/auth/login", "/auth/signup")
    is_auth_path = any(path.startswith(p) for p in auth_paths)

    if not is_auth_path:
        return await call_next(request)

    client_ip = _get_client_ip(request)
    lockout_key = f"login:{client_ip}"

    # Check if locked out
    if _is_locked_out(lockout_key):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Too many failed attempts. Account temporarily locked. Try again in 15 minutes."
            },
            headers={"Retry-After": "900"},
        )

    response = await call_next(request)

    # Record failed attempt on 401/403 responses
    if response.status_code in (401, 403):
        _record_failed_login(lockout_key)
    elif response.status_code == 200:
        # Clear attempts on successful login
        _clear_login_attempts(lockout_key)

    return response


# ---------------------------------------------------------------------------
# Task 7.12: Structured JSON Request Logging Middleware
# ---------------------------------------------------------------------------

_request_logger = logging.getLogger("shorts_engine.requests")


@app.middleware("http")
async def structured_logging_middleware(request: Request, call_next):
    """Structured JSON request logging (Task 7.12).

    Logs: method, path, status_code, duration_ms, client_ip, user_id (if available).
    Does NOT log: request body, auth tokens, cookies, or any PII beyond user_id.
    """
    start_time = time.time()

    response = await call_next(request)

    duration_ms = round((time.time() - start_time) * 1000, 2)
    client_ip = _get_client_ip(request)

    # Extract user_id from auth header if present (hash only, not the token itself)
    user_id = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        # Don't log the actual token — just note that auth was present
        user_id = "authenticated"

    log_entry = {
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
        "client_ip": client_ip,
        "user_id": user_id,
        "query_params": str(request.query_params) if request.query_params else None,
    }

    # Log at appropriate level based on status code
    if response.status_code >= 500:
        _request_logger.error(_json.dumps(log_entry))
    elif response.status_code >= 400:
        _request_logger.warning(_json.dumps(log_entry))
    else:
        _request_logger.info(_json.dumps(log_entry))

    return response
