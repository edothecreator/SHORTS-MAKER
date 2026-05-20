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

#: Single allowed CORS origin per Requirement 12.12. The Frontend is served at
#: ``http://localhost:3000`` and no other origin may invoke the Backend.
_ALLOWED_ORIGIN: str = "http://localhost:3000"

#: In-process Task_Registry. Keys are Task_IDs (UUID4 strings); values are the
#: per-task entries described in the design (``step``, ``progress``,
#: ``created_at``, optional ``data``/``error``/``warning`` fields, plus
#: leading-underscore stash fields populated by the upload route in task 4.2).
task_registry: dict[str, dict] = {}


async def _cleanup_scanner() -> None:
    """Background scanner that purges stale Workspace_Directories.

    The full implementation lands in task 4.7 — it will loop forever, sleeping
    300 seconds between scans and removing any subdirectory of
    ``/tmp/shorts_workspace/`` whose creation time is older than 3600 seconds
    (Requirement 3.7). Until then this is a no-op coroutine so the lifespan
    startup hook can schedule it without raising.
    """
    # Placeholder body. Task 4.7 will replace this with the real scan loop.
    return None


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

# Lock CORS to the Frontend origin only (Requirements 4.9, 12.12). Note that
# ``allow_origins`` accepts an exact list — wildcards would violate
# Requirement 12.12 and are not used here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_ALLOWED_ORIGIN],
    allow_credentials=False,
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

from fastapi import BackgroundTasks, File, Form, HTTPException, UploadFile

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

    Forward stub. Body filled in by task 4.7.
    """
    # Body filled in by task 4.7.
    return None


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
) -> dict[str, str]:
    """Accept a video upload and start the processing pipeline.

    See Requirements 1.1 through 1.8, 1.11, and 1.12 for the full
    contract. ``shorts_count`` and ``duration_per_short`` arrive as
    ``str`` so the 422 envelope is controlled by the manual validators
    rather than FastAPI's automatic Pydantic coercion.
    """
    # ---- 1) Manual form-field validation (Reqs 1.6, 1.7, 1.8). ----
    # Order: count → duration → style_tone. Each helper raises 422 on
    # failure BEFORE any filesystem mutation, satisfying the "no
    # workspace, no registry" half of those requirements.
    count = _validate_shorts_count(shorts_count)
    duration = _validate_duration_per_short(duration_per_short)
    tone = _validate_style_tone(style_tone)

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
