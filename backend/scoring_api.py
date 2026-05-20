"""FastAPI endpoints for the Virality Scoring system.

Production Task 10: Provides REST API access to the scoring engine so the
frontend can request virality scores for generated segments.

Endpoints:
    POST /api/score-segments — Accept segments + words, return scored segments
                               sorted by virality score (highest first).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .scoring import calculate_virality_score

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------


class WordInput(BaseModel):
    """A single word with timestamps."""

    word: str
    start: float = Field(ge=0.0)
    end: float = Field(ge=0.0)


class SegmentInput(BaseModel):
    """A segment to be scored."""

    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(gt=0.0)
    title: str = ""
    hook: str = ""
    reason: str = ""
    words: list[WordInput] = Field(default_factory=list)


class ScoreSegmentsRequest(BaseModel):
    """Request body for POST /api/score-segments."""

    segments: list[SegmentInput] = Field(min_length=1, max_length=100)


class ScoreBreakdown(BaseModel):
    """Breakdown of individual scoring heuristics."""

    hook_strength: float
    pacing: float
    emotional_peaks: float
    clip_completeness: float


class ScoredSegment(BaseModel):
    """A segment with its virality score, breakdown, and explanation."""

    start_sec: float
    end_sec: float
    title: str
    hook: str
    reason: str
    score: float = Field(ge=0.0, le=100.0, description="Overall virality score 0-100")
    breakdown: ScoreBreakdown
    explanation: str


class ScoreSegmentsResponse(BaseModel):
    """Response body for POST /api/score-segments.

    Segments are returned sorted by score descending (highest first).
    """

    scored_segments: list[ScoredSegment]
    count: int


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/api/score-segments", response_model=ScoreSegmentsResponse)
async def score_segments(request: ScoreSegmentsRequest) -> ScoreSegmentsResponse:
    """Score segments by virality potential and return sorted results.

    Accepts a list of segments (each with words/timestamps) and returns them
    scored and sorted by virality score (highest first). Each segment includes:
      - score: 0-100 overall virality score
      - breakdown: individual heuristic scores (hook, pacing, emotional, completeness)
      - explanation: human-readable reason for the score

    This endpoint is designed to be called after the Gemini analysis pipeline
    returns candidate segments, allowing the frontend to display and sort
    clips by their predicted viral potential.
    """
    if not request.segments:
        raise HTTPException(status_code=400, detail="At least one segment is required")

    scored: list[dict[str, Any]] = []

    for seg in request.segments:
        # Convert Pydantic models to dicts for the scoring functions
        segment_dict: dict[str, Any] = {
            "start_sec": seg.start_sec,
            "end_sec": seg.end_sec,
            "title": seg.title,
            "hook": seg.hook,
            "reason": seg.reason,
            "words": [w.model_dump() for w in seg.words],
        }
        words_list = [w.model_dump() for w in seg.words]

        # Calculate virality score
        result = calculate_virality_score(segment_dict, words_list)

        scored.append({
            "start_sec": seg.start_sec,
            "end_sec": seg.end_sec,
            "title": seg.title,
            "hook": seg.hook,
            "reason": seg.reason,
            "score": result["score"],
            "breakdown": result["breakdown"],
            "explanation": result["explanation"],
        })

    # Sort by score descending (highest virality first)
    scored.sort(key=lambda x: x["score"], reverse=True)

    return ScoreSegmentsResponse(
        scored_segments=[ScoredSegment(**s) for s in scored],
        count=len(scored),
    )
