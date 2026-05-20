"""Gemini-based highlight analyzer for the Video-to-Shorts Engine.

This module defines the Pydantic schema used as the structured response schema
for Gemini 2.5 Flash, the prompt builder, and the Gemini client call with retry
plus per-call timeout. The `_validate_result` post-parse validator and the
`analyze_video_transcript` async entry point are added in task 3.4.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any, Callable, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, Field


class WordTimestamp(BaseModel):
    """A single transcribed word with its start/end timestamps in seconds.

    Field constraints map to Requirement 5.1:
      - word: 1..100 characters
      - start: float >= 0.0
      - end:   float >= 0.0
    """

    word: str = Field(min_length=1, max_length=100)
    start: float = Field(ge=0.0)
    end: float = Field(ge=0.0)


class ShortSegment(BaseModel):
    """A single selected short clip.

    Field constraints map to Requirement 5.2:
      - start_sec: float >= 0.0
      - end_sec:   float > 0.0
      - title:  str of length 1..50
      - hook:   str of length 1..200
      - reason: str of length 1..500
      - words:  list[WordTimestamp] of length 1..1000
    """

    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(gt=0.0)
    title: str = Field(min_length=1, max_length=50)
    hook: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=500)
    words: list[WordTimestamp] = Field(min_length=1, max_length=1000)


class ShortsAnalysisResult(BaseModel):
    """Root response object returned by Gemini.

    Field constraints map to Requirement 5.3:
      - segments: list[ShortSegment] of length 1..50
    """

    segments: list[ShortSegment] = Field(min_length=1, max_length=50)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

# Maximum length (in characters) of a free-form Custom style_tone embedded in
# the prompt. Maps to Requirement 5.9.
_CUSTOM_STYLE_MAX_CHARS = 1000


# Built-in style profiles. Each entry describes the selection criterion that
# Gemini should use when picking segments. Maps to Requirement 5.9.
_STYLE_PROFILES: dict[str, str] = {
    "Funny": (
        "Pick the funniest moments: punchlines, comedic timing, witty remarks, "
        "self-deprecation, surprising one-liners, and laugh-out-loud reactions. "
        "Avoid dry exposition; favor moments that land a clear joke."
    ),
    "Educational": (
        "Pick the most instructive moments: clear definitions, step-by-step "
        "explanations, surprising facts, key insights, and ah-ha realizations. "
        "Each clip should teach the viewer one concrete idea on its own."
    ),
    "Motivational": (
        "Pick the most inspiring moments: calls-to-action, mindset shifts, "
        "stories of perseverance, powerful affirmations, and lines that leave "
        "the viewer wanting to act. Avoid filler; each clip should hit hard."
    ),
    "Highlights": (
        "Pick the most engaging, memorable, share-worthy moments overall: "
        "peak emotional beats, surprising turns, quotable lines, and any "
        "passage a casual viewer would replay or send to a friend."
    ),
    "Story-driven": (
        "Pick moments that work as miniature stories: a clear setup, a turn "
        "or twist, and a resolution within the clip. Favor narrative arcs, "
        "personal anecdotes, and emotional beats that pay off on their own."
    ),
}


def _flatten_whisper_words(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every word entry across all Whisper segments, in input order.

    Skips entries that are missing `word`, `start`, or `end` so the dump never
    contains partial timestamps that Gemini cannot anchor against.
    """

    flat: list[dict[str, Any]] = []
    for segment in transcript.get("segments", []) or []:
        for w in segment.get("words", []) or []:
            word = w.get("word")
            start = w.get("start")
            end = w.get("end")
            if word is None or start is None or end is None:
                continue
            flat.append({"w": word, "s": start, "e": end})
    return flat


def _style_block(style_tone: str) -> str:
    """Render the style profile block for the given `style_tone`.

    Built-in tones (`Funny`, `Educational`, `Motivational`, `Highlights`,
    `Story-driven`) map to a fixed selection criterion. Anything else is
    treated as a free-form `Custom` tone whose literal text is embedded,
    truncated to `_CUSTOM_STYLE_MAX_CHARS` characters per Requirement 5.9.
    """

    profile = _STYLE_PROFILES.get(style_tone)
    if profile is not None:
        return f"STYLE / TONE: {style_tone}\nSelection criterion: {profile}"

    custom = (style_tone or "")[:_CUSTOM_STYLE_MAX_CHARS]
    return (
        "STYLE / TONE: Custom\n"
        "Selection criterion (verbatim from user, treat as the sole guide):\n"
        f"{custom}"
    )


def _build_prompt(
    transcript: dict[str, Any],
    style_tone: str,
    shorts_count: int,
    duration_per_short: int,
) -> str:
    """Build the full Gemini prompt for highlight selection.

    The returned string concatenates four sections:

      1. Role + task framing (viral short-form strategist).
      2. Hard rules covering duration bound (req 5.4), title rules (req 5.5),
         hook = first 5 words (req 5.6), `words` containment + ascending
         order (req 5.7), no-overlap (req 5.8), and exact segment count
         (req 5.10).
      3. Style profile block (req 5.9), with a `Custom` branch that embeds
         the user's literal text truncated to 1000 characters.
      4. Compact JSON dump of every Whisper word with keys `w`, `s`, `e`,
         flattened across all whisper segments to keep prompt tokens tight.

    Args:
        transcript: Raw Whisper output dict whose ``segments[*].words[*]``
            entries carry ``word``, ``start``, and ``end`` fields.
        style_tone: One of the five built-in tones or any `Custom` text.
        shorts_count: Exact number of segments Gemini must return (1..50).
        duration_per_short: Maximum allowed ``end_sec - start_sec`` in seconds.

    Returns:
        The fully composed prompt string ready to send to Gemini.
    """

    role = (
        "ROLE: You are a viral short-form video strategist. Given a full "
        "word-level transcript of a long-form video, your job is to select "
        "the strongest non-overlapping segments to clip into vertical shorts."
    )

    task = (
        f"TASK: Return exactly {shorts_count} short segment(s). "
        f"Each segment must be at most {duration_per_short} seconds long "
        "(i.e. end_sec - start_sec <= "
        f"{duration_per_short}) and strictly greater than 0 seconds."
    )

    hard_rules = (
        "HARD RULES (every rule is mandatory; violating any rule means the "
        "response is invalid):\n"
        f"  1. Return exactly {shorts_count} segment(s) in the `segments` "
        "array - no more, no fewer.\n"
        f"  2. For every segment: 0 < end_sec - start_sec <= "
        f"{duration_per_short}.\n"
        "  3. No two segments may overlap. For any two segments A and B, "
        "either A.end_sec <= B.start_sec or B.end_sec <= A.start_sec.\n"
        "  4. `title` must be 1..50 characters inclusive and must NOT contain "
        "the `#` character.\n"
        "  5. `hook` must be exactly the first 5 whitespace-separated words "
        "of the segment's spoken content, joined by single spaces.\n"
        "  6. `words` must contain every transcript word whose `start` is "
        ">= the segment's `start_sec` AND whose `end` is <= the segment's "
        "`end_sec`. Include them in ascending `start` order. Preserve the "
        "`word`, `start`, and `end` values exactly as given in the "
        "transcript below - do not round, re-time, or rephrase.\n"
        "  7. `reason` must be 1..500 characters explaining why this segment "
        "fits the requested style/tone."
    )

    style = _style_block(style_tone)

    word_dump = _flatten_whisper_words(transcript)
    transcript_json = json.dumps(word_dump, separators=(",", ":"))
    transcript_block = (
        "TRANSCRIPT (compact JSON, one entry per word; "
        "`w`=word, `s`=start_sec, `e`=end_sec):\n"
        f"{transcript_json}"
    )

    closing = (
        f"Now produce exactly {shorts_count} segment(s) that obey every rule "
        "above. Output JSON only, matching the response schema."
    )

    return "\n\n".join([role, task, hard_rules, style, transcript_block, closing])


# ---------------------------------------------------------------------------
# Gemini call with retry + per-call timeout
# ---------------------------------------------------------------------------

# Gemini model identifier used by the analyzer (Requirement 2.9).
_GEMINI_MODEL = "gemini-2.5-flash"

# Per-call timeout for `models.generate_content` in seconds (Requirement 2.9).
_GEMINI_CALL_TIMEOUT_SEC = 120.0


T = TypeVar("T")


def _categorize_error(exc: BaseException) -> str:
    """Return a short category label for the given exception.

    Categories map exception types and message hints to one of `timeout`,
    `network`, or `unknown`. Used to prefix the final error message when
    `_call_with_retry` exhausts its attempts (Requirements 2.12, 5.14).
    """

    if isinstance(exc, (FuturesTimeoutError, asyncio.TimeoutError, TimeoutError)):
        return "timeout"
    if isinstance(exc, (ConnectionError, socket.gaierror, socket.herror, socket.timeout)):
        return "network"

    msg = str(exc).lower()
    if "timeout" in msg or "timed out" in msg:
        return "timeout"
    if (
        "connection" in msg
        or "network" in msg
        or "dns" in msg
        or "unreachable" in msg
        or "reset" in msg
    ):
        return "network"
    return "unknown"


def _call_with_retry(
    fn: Callable[[], T],
    attempts: int = 3,
    backoff: float = 2.0,
) -> T:
    """Call ``fn`` up to ``attempts`` times with ``backoff`` seconds between tries.

    Sleeps at least ``backoff`` seconds between attempts on failure. On final
    failure, re-raises the last exception with a categorized message prefix
    (e.g. ``"Gemini API failure (timeout): ..."``).

    Only ``Exception`` is caught - ``BaseException`` subclasses such as
    ``KeyboardInterrupt`` and ``SystemExit`` propagate immediately.

    Maps to Requirements 2.12 and 5.14.
    """

    if attempts < 1:
        raise ValueError("attempts must be >= 1")

    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - intentionally broad
            last_exc = exc
            if i < attempts - 1:
                time.sleep(backoff)

    assert last_exc is not None  # for type-checkers; loop guarantees this
    category = _categorize_error(last_exc)
    if category == "unknown":
        prefix = "Gemini API failure"
    else:
        prefix = f"Gemini API failure ({category})"
    message = f"{prefix}: {last_exc}"
    # Try to preserve the original exception type so callers can pattern-match
    # (e.g. on `TimeoutError`). Fall back to `RuntimeError` for exception
    # types whose constructors do not accept a single string argument.
    try:
        new_exc: Exception = type(last_exc)(message)
    except Exception:
        new_exc = RuntimeError(message)
    raise new_exc from last_exc


def _call_gemini(prompt: str) -> ShortsAnalysisResult:
    """Send ``prompt`` to Gemini and return the parsed `ShortsAnalysisResult`.

    Uses ``response_mime_type="application/json"`` and
    ``response_schema=ShortsAnalysisResult`` so the SDK populates
    ``response.parsed`` directly. Each attempt is wrapped in a 120 second
    timeout via a worker thread (the SDK's ``generate_content`` is
    synchronous and offers no native timeout knob, so we surface a hung
    call as ``TimeoutError`` through ``concurrent.futures``).

    The whole call is retried up to three times with at least two seconds
    between attempts (Requirements 2.9, 2.12, 5.14). When the response
    cannot be parsed, raises ``ValueError(f"Gemini parse failed: ...")``
    (Requirements 2.11, 5.12).

    `GOOGLE_API_KEY` is read from the environment at call-time so the
    FastAPI startup hook in `backend/main.py` owns the precondition.
    """

    def _attempt() -> ShortsAnalysisResult:
        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

        def _do_call():
            return client.models.generate_content(
                model=_GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ShortsAnalysisResult,
                ),
            )

        # Use a fresh single-worker executor per attempt. We cannot kill a
        # running Python thread, so on timeout we abandon the worker via
        # `shutdown(wait=False)` and surface a `TimeoutError` immediately
        # rather than blocking on the hung call.
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(_do_call)
            try:
                response = future.result(timeout=_GEMINI_CALL_TIMEOUT_SEC)
            except FuturesTimeoutError as exc:
                # Surface a standard TimeoutError so `_categorize_error`
                # tags this as a `timeout` failure on the final attempt.
                future.cancel()
                raise TimeoutError(
                    f"Gemini call exceeded {_GEMINI_CALL_TIMEOUT_SEC:.0f}s timeout"
                ) from exc
        finally:
            executor.shutdown(wait=False)

        parsed: Any = getattr(response, "parsed", None)
        if parsed is None:
            text = getattr(response, "text", None)
            raise ValueError(f"Gemini parse failed: {text!r}")

        if not isinstance(parsed, ShortsAnalysisResult):
            # Defensive: SDK should already return the schema instance.
            parsed = ShortsAnalysisResult.model_validate(parsed)

        return parsed

    return _call_with_retry(_attempt, attempts=3, backoff=2.0)


# ---------------------------------------------------------------------------
# Post-parse validation + async public entry point
# ---------------------------------------------------------------------------


def _validate_result(
    result: ShortsAnalysisResult,
    count: int,
    max_dur: int,
) -> None:
    """Validate Gemini's parsed result against the request invariants.

    Raises ``ValueError`` whose message identifies which constraint was
    violated (Requirement 5.13). The four checks performed, in order:

      1. ``len(result.segments) == count``.
      2. After sorting by ``start_sec`` ascending, no adjacent pair overlaps
         (i.e. ``a.end_sec <= b.start_sec``). The ascending sort makes a
         single linear scan sufficient: any two segments that overlap will
         do so as adjacent neighbours in the sorted order.
      3. Every segment has a strictly positive duration
         (``end_sec > start_sec``). The Pydantic schema already enforces
         ``end_sec > 0`` and ``start_sec >= 0``, but allows ``end_sec ==
         start_sec`` for non-zero ``start_sec``; this check closes that gap.
      4. Every segment satisfies ``end_sec - start_sec <= max_dur``.

    Args:
        result: The parsed ``ShortsAnalysisResult`` from Gemini.
        count: The exact number of segments the request asked for.
        max_dur: The maximum allowed segment duration in seconds.

    Returns:
        None on success. Raises ``ValueError`` on any violation.
    """

    if len(result.segments) != count:
        raise ValueError(
            f"Gemini returned {len(result.segments)} segments, expected {count}"
        )

    sorted_segs = sorted(result.segments, key=lambda s: s.start_sec)
    for a, b in zip(sorted_segs, sorted_segs[1:]):
        if a.end_sec > b.start_sec:
            raise ValueError(
                "Segments overlap: "
                f"[{a.start_sec},{a.end_sec}] and [{b.start_sec},{b.end_sec}]"
            )

    for s in result.segments:
        if s.end_sec <= s.start_sec:
            raise ValueError(
                f"Segment {s.start_sec}-{s.end_sec} has non-positive duration"
            )
        if s.end_sec - s.start_sec > max_dur:
            raise ValueError(
                f"Segment {s.start_sec}-{s.end_sec} exceeds duration {max_dur}"
            )


async def analyze_video_transcript(
    transcript: dict[str, Any],
    style_tone: str,
    max_count: int,
    target_duration: int,
) -> ShortsAnalysisResult:
    """Analyze a Whisper transcript and return a validated `ShortsAnalysisResult`.

    Composes the full analyzer flow:

      1. Build the strategist prompt via ``_build_prompt``.
      2. Run the synchronous Gemini call (with retry + per-call timeout)
         on the default thread executor via ``loop.run_in_executor`` so the
         FastAPI event loop is not blocked while Gemini is in flight.
      3. Apply ``_validate_result`` to enforce count, no-overlap,
         positive-duration, and duration-bound invariants.

    Args:
        transcript: Raw Whisper output dict whose ``segments[*].words[*]``
            entries carry ``word``, ``start``, and ``end`` fields.
        style_tone: One of the five built-in tones or any free-form
            ``Custom`` text (truncated to 1000 chars in the prompt).
        max_count: Exact number of segments to return (1..50).
        target_duration: Maximum allowed ``end_sec - start_sec`` in seconds.

    Returns:
        The validated ``ShortsAnalysisResult`` ready for ``model_dump()``.

    Raises:
        ValueError: If Gemini's response cannot be parsed (Requirement 5.12)
            or any post-parse invariant is violated (Requirement 5.13).
        Exception: If the Gemini API call fails after all retry attempts
            (Requirements 2.12, 5.14). The category (``timeout`` /
            ``network`` / ``unknown``) is included in the message prefix.
    """

    prompt = _build_prompt(transcript, style_tone, max_count, target_duration)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _call_gemini, prompt)

    _validate_result(result, max_count, target_duration)
    return result
