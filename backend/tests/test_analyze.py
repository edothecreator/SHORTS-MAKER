"""Unit tests for ``backend.analyze``.

Covers Requirements 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 5.12, 5.13, 2.11.

The tests exercise three layers of the analyzer in isolation, all offline:

1. ``_build_prompt`` and the embedded style profile block (Requirements 5.4 -
   5.10).
2. ``_validate_result`` post-parse invariants (Requirement 5.13).
3. ``_call_gemini`` parse-failure handling with a fake response object
   (Requirements 2.11, 5.12).
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from backend.analyze import (
    _STYLE_PROFILES,
    _build_prompt,
    _call_gemini,
    _validate_result,
    ShortSegment,
    ShortsAnalysisResult,
    WordTimestamp,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tiny_transcript() -> dict[str, Any]:
    """Return a minimal Whisper-style transcript with two words."""

    return {
        "segments": [
            {
                "words": [
                    {"word": "Hello", "start": 0.0, "end": 0.5},
                    {"word": "world", "start": 0.5, "end": 1.0},
                ]
            }
        ]
    }


def _make_segment(start: float, end: float) -> ShortSegment:
    """Build a minimal valid ``ShortSegment`` covering ``[start, end]``."""

    return ShortSegment(
        start_sec=start,
        end_sec=end,
        title="t",
        hook="h",
        reason="r",
        words=[WordTimestamp(word="w", start=start, end=end if end > start else start + 0.001)],
    )


def _make_result(*intervals: tuple[float, float]) -> ShortsAnalysisResult:
    return ShortsAnalysisResult(segments=[_make_segment(s, e) for s, e in intervals])


# ---------------------------------------------------------------------------
# A) Prompt builder tests (Requirements 5.4 - 5.10)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tone",
    ["Funny", "Educational", "Motivational", "Highlights", "Story-driven"],
)
def test_build_prompt_embeds_builtin_style_profile(tone: str) -> None:
    """Each of the five built-in tones embeds its profile verbatim. (Req 5.9)"""

    prompt = _build_prompt(_tiny_transcript(), tone, shorts_count=3, duration_per_short=30)

    assert f"STYLE / TONE: {tone}" in prompt
    assert _STYLE_PROFILES[tone] in prompt
    # Sanity: the Custom-branch marker phrase must NOT appear when a built-in
    # tone is used.
    assert "verbatim from user" not in prompt


def test_build_prompt_custom_truncates_to_1000_chars() -> None:
    """Custom tone literal is embedded but truncated at 1000 chars. (Req 5.9)"""

    prefix = "A" * 1000
    suffix = "B" * 500
    custom = prefix + suffix  # 1500 chars
    assert len(custom) == 1500

    prompt = _build_prompt(
        _tiny_transcript(), custom, shorts_count=2, duration_per_short=15
    )

    # Custom-branch header is present and selection criterion line is the
    # verbatim-from-user variant, not a built-in profile.
    assert "STYLE / TONE: Custom" in prompt
    assert "verbatim from user" in prompt

    # First 1000 chars are kept...
    assert prefix in prompt
    # ... and the trailing 500 chars are dropped entirely. Check the run of
    # B's specifically rather than the bare letter, since the hard-rules
    # section legitimately contains a single 'B' (e.g. "A and B").
    assert suffix not in prompt
    assert "BB" not in prompt
    assert custom not in prompt

    # And no built-in profile text leaked in.
    for profile_text in _STYLE_PROFILES.values():
        assert profile_text not in prompt


def test_build_prompt_literal_custom_string_uses_custom_branch() -> None:
    """Passing the literal string ``"Custom"`` falls through to the Custom branch.

    `_STYLE_PROFILES` does not contain the key ``"Custom"`` so the function
    must treat it as free-form text and embed it verbatim under the Custom
    selection criterion, not under any built-in profile. (Req 5.9)
    """

    prompt = _build_prompt(
        _tiny_transcript(), "Custom", shorts_count=1, duration_per_short=30
    )

    assert "STYLE / TONE: Custom" in prompt
    assert "verbatim from user" in prompt
    for profile_text in _STYLE_PROFILES.values():
        assert profile_text not in prompt


def test_build_prompt_includes_hard_rule_clauses() -> None:
    """Spot-check the hard-rule wording covering Reqs 5.4, 5.5, 5.6, 5.7, 5.8, 5.10."""

    shorts_count = 4
    duration = 45
    prompt = _build_prompt(
        _tiny_transcript(), "Funny", shorts_count=shorts_count, duration_per_short=duration
    )

    # Req 5.10 - exact-count phrasing.
    assert f"exactly {shorts_count} segment" in prompt

    # Req 5.4 - duration upper bound referencing the user's target.
    assert f"end_sec - start_sec <= {duration}" in prompt
    # Req 5.4 - strictly positive duration is also required.
    assert "strictly greater than 0 seconds" in prompt

    # Req 5.8 - no-overlap rule.
    assert "No two segments may overlap" in prompt

    # Req 5.5 - title length + no-`#`.
    assert "1..50 characters" in prompt
    assert "`#` character" in prompt

    # Req 5.6 - hook = first 5 whitespace-separated words.
    assert "first 5 whitespace-separated words" in prompt

    # Req 5.7 - words containment + ascending order.
    assert "ascending `start` order" in prompt


def test_build_prompt_compact_transcript_dump_uses_w_s_e_keys() -> None:
    """Compact JSON dump uses keys ``w``, ``s``, ``e`` with no inter-token spaces."""

    prompt = _build_prompt(_tiny_transcript(), "Funny", shorts_count=1, duration_per_short=30)

    # ``json.dumps`` with ``separators=(",", ":")`` produces no whitespace.
    assert '{"w":"Hello","s":0.0,"e":0.5}' in prompt
    assert '{"w":"world","s":0.5,"e":1.0}' in prompt


# ---------------------------------------------------------------------------
# B) _validate_result tests (Requirement 5.13)
# ---------------------------------------------------------------------------


def test_validate_result_accepts_valid_result_returns_none() -> None:
    """Happy path: a valid result is accepted and returns ``None``."""

    result = _make_result((0.0, 5.0), (10.0, 15.0))
    assert _validate_result(result, count=2, max_dur=10) is None


def test_validate_result_rejects_count_mismatch() -> None:
    result = _make_result((0.0, 5.0), (10.0, 15.0))
    with pytest.raises(ValueError) as exc_info:
        _validate_result(result, count=3, max_dur=10)
    msg = str(exc_info.value)
    # Message must mention both the actual and expected count.
    assert "2" in msg
    assert "3" in msg


def test_validate_result_rejects_overlapping_segments() -> None:
    result = _make_result((0.0, 10.0), (5.0, 12.0))
    with pytest.raises(ValueError) as exc_info:
        _validate_result(result, count=2, max_dur=15)
    assert "overlap" in str(exc_info.value).lower()


def test_validate_result_rejects_duration_overrun() -> None:
    # Single segment whose duration (20s) exceeds the configured max (15s).
    result = _make_result((0.0, 20.0))
    with pytest.raises(ValueError) as exc_info:
        _validate_result(result, count=1, max_dur=15)
    assert "exceeds duration" in str(exc_info.value)


def test_validate_result_rejects_non_positive_duration() -> None:
    """``end_sec == start_sec`` is allowed by the schema but rejected here."""

    # `start_sec=5.0, end_sec=5.0` passes Pydantic (`end_sec > 0`,
    # `start_sec >= 0`) but has zero duration.
    result = _make_result((5.0, 5.0))
    with pytest.raises(ValueError) as exc_info:
        _validate_result(result, count=1, max_dur=15)
    assert "non-positive duration" in str(exc_info.value)


# ---------------------------------------------------------------------------
# C) _call_gemini parse-failure (Requirements 2.11, 5.12)
# ---------------------------------------------------------------------------


class _FakeResponse:
    """Minimal stand-in for ``google.genai`` response objects."""

    def __init__(self, parsed: Any, text: str) -> None:
        self.parsed = parsed
        self.text = text


class _FakeModels:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.calls = 0

    def generate_content(self, **_kwargs: Any) -> _FakeResponse:
        self.calls += 1
        return self._response


class _FakeClient:
    def __init__(self, response: _FakeResponse) -> None:
        self.models = _FakeModels(response)


def test_call_gemini_parse_failure_raises_with_raw_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``response.parsed is None``, ``_call_gemini`` raises ``ValueError``
    that surfaces both the parse-failure prefix and the raw response text.

    After three retries `_call_with_retry` re-raises a ``ValueError`` whose
    message wraps the original (`"Gemini API failure: Gemini parse failed: 'not json'"`).
    Validates Requirements 2.11 and 5.12.
    """

    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    fake_response = _FakeResponse(parsed=None, text="not json")
    fake_client = _FakeClient(fake_response)

    # Patch the symbol used inside ``backend.analyze`` so no real network call
    # is attempted. ``genai.Client(api_key=...)`` returns our fake.
    def _client_factory(*_args: Any, **_kwargs: Any) -> _FakeClient:
        return fake_client

    monkeypatch.setattr("backend.analyze.genai.Client", _client_factory)
    # Skip the 2.0s backoff so the test runs in milliseconds even though the
    # retry helper attempts the call three times before giving up.
    monkeypatch.setattr("backend.analyze.time.sleep", lambda _s: None)

    with pytest.raises(ValueError) as exc_info:
        _call_gemini("ignored prompt")

    msg = str(exc_info.value)
    # Retry wrapper prefix + original parse-failure prefix + raw response text.
    assert "Gemini API failure" in msg
    assert "Gemini parse failed" in msg
    assert "'not json'" in msg

    # All three retry attempts were made.
    assert fake_client.models.calls == 3
