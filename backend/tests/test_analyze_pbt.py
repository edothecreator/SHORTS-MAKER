"""Property-based tests for ``backend.analyze._validate_result``.

Covers Property 3 from the design (Segment non-overlap), which validates
Requirements 5.8 and 5.13. The dispatcher property under test:

  ``_validate_result`` accepts a ``ShortsAnalysisResult`` *iff* the segments,
  once sorted by ``start_sec``, contain no overlapping adjacent pair (modulo
  the count and per-segment duration checks, which we hold fixed in these
  tests by passing a matching ``count`` and a generous ``max_dur``).

The strategies build segments with strictly positive durations so the
non-positive-duration check inside ``_validate_result`` never fires; that
isolates the overlap behaviour we want to exercise.
"""

from __future__ import annotations

from typing import List

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.analyze import (
    ShortSegment,
    ShortsAnalysisResult,
    WordTimestamp,
    _validate_result,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


def _segment(start: float, duration: float) -> ShortSegment:
    """Build a minimal valid ``ShortSegment`` covering ``[start, start+duration]``.

    A single placeholder ``WordTimestamp`` is included so the schema's
    ``min_length=1`` constraint on ``words`` is satisfied. The placeholder's
    timestamps mirror the segment bounds so the schema-level
    ``end >= start`` invariant on ``WordTimestamp`` always holds.
    """

    end = start + duration
    return ShortSegment(
        start_sec=start,
        end_sec=end,
        title="t",
        hook="h",
        reason="r",
        words=[WordTimestamp(word="w", start=start, end=end)],
    )


# Quantize bounds keep float arithmetic well-behaved (no NaN, no infinity, no
# subnormal jitter that could push ``end_sec`` below ``start_sec`` after a
# round-trip through Pydantic).
_START = st.floats(
    min_value=0.0,
    max_value=1000.0,
    allow_nan=False,
    allow_infinity=False,
    allow_subnormal=False,
)
_DURATION = st.floats(
    min_value=0.001,
    max_value=20.0,
    allow_nan=False,
    allow_infinity=False,
    allow_subnormal=False,
)


@st.composite
def segments_strategy(draw) -> List[ShortSegment]:
    """Strategy that yields 1..5 ``ShortSegment`` instances with arbitrary bounds.

    Segments may overlap, be disjoint, or any mix in between - that is the
    space we want ``_validate_result`` to dispatch over.
    """

    n = draw(st.integers(min_value=1, max_value=5))
    pairs = draw(
        st.lists(
            st.tuples(_START, _DURATION),
            min_size=n,
            max_size=n,
        )
    )
    return [_segment(start, duration) for start, duration in pairs]


# ---------------------------------------------------------------------------
# Property 3: Segment non-overlap
# ---------------------------------------------------------------------------


@given(segs=segments_strategy())
@settings(max_examples=200, deadline=None)
def test_validate_result_overlap_dispatches(segs: List[ShortSegment]) -> None:
    """**Validates: Requirements 5.8, 5.13**

    For every randomly generated ``ShortsAnalysisResult``:

      * If sorting by ``start_sec`` reveals any adjacent overlapping pair
        (``a.end_sec > b.start_sec``), ``_validate_result`` must raise
        ``ValueError`` whose message mentions ``"overlap"``.
      * Otherwise, ``_validate_result`` must return ``None`` and the sorted
        segments must satisfy ``segments[i].end_sec <= segments[i+1].start_sec``
        for every adjacent pair.

    The ``count`` argument is set to ``len(segs)`` and ``max_dur`` to a value
    far above any generated duration, so neither the count nor duration
    checks inside ``_validate_result`` can fire - isolating the overlap
    behaviour.
    """

    result = ShortsAnalysisResult(segments=segs)

    sorted_segs = sorted(segs, key=lambda s: s.start_sec)
    expected_overlap = any(
        a.end_sec > b.start_sec for a, b in zip(sorted_segs, sorted_segs[1:])
    )

    if expected_overlap:
        with pytest.raises(ValueError, match="overlap"):
            _validate_result(result, count=len(segs), max_dur=10000)
    else:
        assert _validate_result(result, count=len(segs), max_dur=10000) is None
        for a, b in zip(sorted_segs, sorted_segs[1:]):
            assert a.end_sec <= b.start_sec


# ---------------------------------------------------------------------------
# Sanity property: count mismatch always raises (Requirement 5.13 first check)
# ---------------------------------------------------------------------------


@st.composite
def _segments_and_wrong_count(draw):
    segs = draw(segments_strategy())
    wrong = draw(
        st.integers(min_value=1, max_value=20).filter(lambda c: c != len(segs))
    )
    return segs, wrong


@given(data=_segments_and_wrong_count())
@settings(max_examples=100, deadline=None)
def test_validate_result_count_mismatch_always_raises(data) -> None:
    """**Validates: Requirements 5.13**

    Whenever ``count`` does not match ``len(segments)``, ``_validate_result``
    must raise ``ValueError``. The message must mention both the actual and
    expected segment counts so callers can diagnose the mismatch.
    """

    segs, wrong_count = data
    result = ShortsAnalysisResult(segments=segs)

    with pytest.raises(ValueError) as exc_info:
        _validate_result(result, count=wrong_count, max_dur=10000)

    msg = str(exc_info.value)
    assert str(len(segs)) in msg
    assert str(wrong_count) in msg
