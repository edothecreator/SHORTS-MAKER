"""Virality Scoring Module for the Video-to-Shorts Engine.

Production Task 10: Implements heuristic-based virality scoring for generated
short segments. Each clip is scored 0-100 based on multiple factors that
correlate with viral short-form content performance.

Frontend Integration (Tasks 10.3 & 10.4):
    The frontend ResultsGrid component (frontend/app/components/ResultsGrid.tsx)
    will display the virality score (0-100) on each clip card and sort clips
    by virality score (highest first). The scoring API returns segments
    pre-sorted by score descending so the frontend can render them directly.

TODO (Task 10.6): Real performance tracking requires social account OAuth
    integration to pull actual engagement metrics (views, likes, shares,
    comments). This is Phase 3, Task 15 (Multi-Platform Publishing).
    Until then, scores are purely heuristic-based predictions.

TODO (Task 10.7 — Feedback Loop):
    To improve scoring accuracy over time, implement the following feedback loop:
    1. Track which clips users actually export/publish (implicit positive signal).
    2. Once social OAuth is connected (Phase 3, Task 15), pull real engagement
       metrics (views, likes, shares, watch-through rate) for published clips.
    3. Build a dataset: (clip_features, actual_engagement_score) pairs.
    4. Periodically retrain/adjust heuristic weights using regression on real data.
    5. A/B test new weights against the current model to validate improvements.
    6. Consider upgrading from heuristics to a lightweight ML model (e.g.,
       gradient-boosted trees) once sufficient labeled data is collected
       (~1000+ clips with engagement data).
    The current heuristic weights (hook: 30%, pacing: 25%, emotional: 25%,
    completeness: 20%) are initial estimates based on content creation best
    practices and should be treated as a starting baseline to be refined.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Sentiment word lists (simple keyword-based approach)
# ---------------------------------------------------------------------------

POSITIVE_WORDS: set[str] = {
    "amazing", "awesome", "beautiful", "best", "brilliant", "celebrate",
    "confident", "creative", "delightful", "easy", "excellent", "excited",
    "fantastic", "free", "fun", "genius", "good", "great", "growth", "happy",
    "helpful", "hilarious", "hope", "important", "impressive", "incredible",
    "innovative", "inspire", "inspiring", "interesting", "joy", "key",
    "laugh", "legendary", "life-changing", "love", "lucky", "magic",
    "massive", "mind-blowing", "motivate", "outstanding", "passion",
    "perfect", "phenomenal", "positive", "powerful", "remarkable", "secret",
    "shocking", "simple", "smart", "special", "strong", "success",
    "superb", "surprise", "terrific", "thrilling", "top", "transform",
    "ultimate", "unbelievable", "unique", "valuable", "victory", "viral",
    "win", "winner", "wonderful", "wow",
}

NEGATIVE_WORDS: set[str] = {
    "angry", "annoying", "awful", "bad", "boring", "broken", "cheap",
    "confusing", "crazy", "dangerous", "dead", "destroy", "difficult",
    "disappointing", "disaster", "disgusting", "dumb", "embarrassing",
    "evil", "fail", "failure", "fake", "fear", "fool", "frustrating",
    "hate", "horrible", "hurt", "idiot", "impossible", "insane", "jealous",
    "kill", "lazy", "lie", "loser", "lost", "mad", "mess", "mistake",
    "nasty", "negative", "never", "nightmare", "pain", "pathetic", "poor",
    "problem", "regret", "reject", "ruin", "sad", "scam", "scary", "sick",
    "slow", "stop", "struggle", "stupid", "suffer", "terrible", "threat",
    "toxic", "trash", "trouble", "ugly", "unfair", "useless", "victim",
    "waste", "weak", "weird", "worry", "worst", "wrong",
}

# Words that indicate high emotional intensity (amplifiers)
INTENSITY_WORDS: set[str] = {
    "absolutely", "actually", "always", "believe", "completely", "critical",
    "crucial", "definitely", "essential", "every", "exactly", "extremely",
    "finally", "forever", "honestly", "literally", "must", "need", "never",
    "nobody", "nothing", "only", "realize", "really", "remember",
    "seriously", "should", "single", "suddenly", "totally", "truly",
    "understand", "very",
}


# ---------------------------------------------------------------------------
# Task 10.1: Scoring Heuristic Functions
# ---------------------------------------------------------------------------


def score_hook_strength(
    words: list[dict[str, Any]],
    segment_start: float,
    segment_end: float,
) -> float:
    """Score the first 3 seconds of a segment for engagement potential (0-100).

    A strong hook in the first 3 seconds is the #1 factor for viewer retention
    on short-form platforms (TikTok, Reels, Shorts). This heuristic evaluates:
      - Word density in first 3s (more words = more engaging opening)
      - Presence of emotional/power words in the opening
      - Whether the hook starts immediately (no dead air)

    Args:
        words: List of word dicts with 'word', 'start', 'end' keys.
        segment_start: Start time of the segment in seconds.
        segment_end: End time of the segment in seconds.

    Returns:
        Score from 0.0 to 100.0.
    """
    if not words:
        return 0.0

    hook_end = segment_start + 3.0
    hook_words = [
        w for w in words
        if w.get("start", 0) >= segment_start and w.get("end", 0) <= min(hook_end, segment_end)
    ]

    if not hook_words:
        return 10.0  # No words in first 3s = weak hook (but not zero since visual may carry)

    score = 0.0

    # Factor 1: Word density in first 3 seconds (max 40 points)
    # Ideal: 8-12 words in 3 seconds (natural speaking pace with energy)
    word_count = len(hook_words)
    if word_count >= 8:
        density_score = 40.0
    elif word_count >= 5:
        density_score = 25.0 + (word_count - 5) * 5.0
    else:
        density_score = word_count * 5.0
    score += density_score

    # Factor 2: Emotional/power words in the hook (max 35 points)
    hook_text = [w.get("word", "").lower().strip(".,!?;:'\"") for w in hook_words]
    emotional_count = sum(
        1 for word in hook_text
        if word in POSITIVE_WORDS or word in NEGATIVE_WORDS or word in INTENSITY_WORDS
    )
    emotional_ratio = emotional_count / max(len(hook_text), 1)
    score += min(emotional_ratio * 100.0, 35.0)

    # Factor 3: Immediate start — no dead air (max 25 points)
    # How quickly does speech begin after segment start?
    first_word_start = hook_words[0].get("start", segment_start)
    delay = first_word_start - segment_start
    if delay <= 0.3:
        score += 25.0  # Speech starts immediately
    elif delay <= 0.8:
        score += 18.0  # Short pause, acceptable
    elif delay <= 1.5:
        score += 10.0  # Notable delay
    else:
        score += 3.0   # Long dead air = poor hook

    return min(max(score, 0.0), 100.0)


def score_pacing(words: list[dict[str, Any]], duration: float) -> float:
    """Score the pacing and energy of a segment (0-100).

    Good pacing for viral shorts means:
      - Appropriate words per minute (120-180 WPM is the sweet spot)
      - Minimal long pauses (keeps attention)
      - Energy variation (not monotone)

    Args:
        words: List of word dicts with 'word', 'start', 'end' keys.
        duration: Total duration of the segment in seconds.

    Returns:
        Score from 0.0 to 100.0.
    """
    if not words or duration <= 0:
        return 0.0

    score = 0.0

    # Factor 1: Words per minute (max 40 points)
    # Sweet spot for viral content: 140-180 WPM
    wpm = (len(words) / duration) * 60.0
    if 140 <= wpm <= 180:
        wpm_score = 40.0
    elif 120 <= wpm < 140 or 180 < wpm <= 200:
        wpm_score = 30.0
    elif 100 <= wpm < 120 or 200 < wpm <= 220:
        wpm_score = 20.0
    elif 80 <= wpm < 100:
        wpm_score = 12.0
    else:
        wpm_score = 5.0
    score += wpm_score

    # Factor 2: Pause analysis (max 35 points)
    # Fewer long pauses = better pacing for shorts
    pauses: list[float] = []
    sorted_words = sorted(words, key=lambda w: w.get("start", 0))
    for i in range(1, len(sorted_words)):
        prev_end = sorted_words[i - 1].get("end", 0)
        curr_start = sorted_words[i].get("start", 0)
        gap = curr_start - prev_end
        if gap > 0.3:  # Gaps > 300ms are noticeable pauses
            pauses.append(gap)

    long_pauses = [p for p in pauses if p > 1.0]
    if not long_pauses:
        pause_score = 35.0  # No long pauses = great pacing
    elif len(long_pauses) == 1:
        pause_score = 25.0  # One dramatic pause can be intentional
    elif len(long_pauses) <= 3:
        pause_score = 15.0  # A few pauses
    else:
        pause_score = 5.0   # Too many pauses = disengaging
    score += pause_score

    # Factor 3: Energy variation — word length variation as proxy (max 25 points)
    # Variation in word lengths suggests emphasis changes and dynamic delivery
    word_lengths = [len(w.get("word", "")) for w in words]
    if len(word_lengths) >= 3:
        avg_len = sum(word_lengths) / len(word_lengths)
        variance = sum((l - avg_len) ** 2 for l in word_lengths) / len(word_lengths)
        # Moderate variance is best (mix of short punchy and longer words)
        if 3.0 <= variance <= 12.0:
            energy_score = 25.0
        elif 1.5 <= variance < 3.0 or 12.0 < variance <= 20.0:
            energy_score = 18.0
        else:
            energy_score = 10.0
    else:
        energy_score = 10.0
    score += energy_score

    return min(max(score, 0.0), 100.0)


def score_emotional_peaks(words: list[dict[str, Any]]) -> float:
    """Score emotional intensity of the segment via sentiment analysis (0-100).

    Viral content tends to have strong emotional signals — either very positive
    (inspiring, funny, surprising) or very negative (outrage, shock, fear).
    Neutral content rarely goes viral. This heuristic measures:
      - Ratio of emotional words (positive + negative)
      - Intensity amplifier presence
      - Emotional polarity strength (strongly positive or negative > mixed)

    Args:
        words: List of word dicts with 'word', 'start', 'end' keys.

    Returns:
        Score from 0.0 to 100.0.
    """
    if not words:
        return 0.0

    cleaned_words = [w.get("word", "").lower().strip(".,!?;:'\"") for w in words]
    total = len(cleaned_words)
    if total == 0:
        return 0.0

    positive_count = sum(1 for w in cleaned_words if w in POSITIVE_WORDS)
    negative_count = sum(1 for w in cleaned_words if w in NEGATIVE_WORDS)
    intensity_count = sum(1 for w in cleaned_words if w in INTENSITY_WORDS)

    score = 0.0

    # Factor 1: Emotional word density (max 45 points)
    emotional_total = positive_count + negative_count
    emotional_ratio = emotional_total / total
    # 10-25% emotional words is the sweet spot for engaging content
    if 0.10 <= emotional_ratio <= 0.25:
        score += 45.0
    elif 0.05 <= emotional_ratio < 0.10 or 0.25 < emotional_ratio <= 0.35:
        score += 32.0
    elif emotional_ratio > 0.35:
        score += 20.0  # Oversaturated can feel forced
    elif emotional_ratio > 0:
        score += emotional_ratio * 200.0  # Scale up from 0
    # else: 0 emotional words = 0 points

    # Factor 2: Intensity amplifiers (max 30 points)
    intensity_ratio = intensity_count / total
    if intensity_ratio >= 0.08:
        score += 30.0
    elif intensity_ratio >= 0.04:
        score += 20.0
    elif intensity_ratio > 0:
        score += 10.0

    # Factor 3: Emotional polarity (max 25 points)
    # Strong polarity (mostly positive OR mostly negative) > mixed
    if emotional_total > 0:
        polarity = abs(positive_count - negative_count) / emotional_total
        if polarity >= 0.7:
            score += 25.0  # Strong direction = clear emotional narrative
        elif polarity >= 0.4:
            score += 18.0  # Moderate direction
        else:
            score += 12.0  # Mixed emotions — can still work for drama/conflict
    else:
        score += 0.0

    return min(max(score, 0.0), 100.0)


def score_clip_completeness(segment: dict[str, Any]) -> float:
    """Score whether a segment tells a complete story (0-100).

    Complete clips (beginning/middle/end) perform better than abrupt cuts.
    This heuristic evaluates:
      - Duration (too short = incomplete, too long = loses attention)
      - Has a title and hook (indicates clear start)
      - Has a reason/explanation (indicates clear purpose)
      - Word count (enough content to form a narrative)

    Args:
        segment: A segment dict with keys like 'start_sec', 'end_sec',
                 'title', 'hook', 'reason', 'words'.

    Returns:
        Score from 0.0 to 100.0.
    """
    score = 0.0

    # Factor 1: Duration sweet spot (max 35 points)
    # Optimal short duration: 30-60 seconds for most platforms
    start = segment.get("start_sec", 0)
    end = segment.get("end_sec", 0)
    duration = end - start

    if duration <= 0:
        return 0.0

    if 30 <= duration <= 60:
        score += 35.0  # Sweet spot
    elif 20 <= duration < 30 or 60 < duration <= 90:
        score += 28.0  # Good range
    elif 15 <= duration < 20 or 90 < duration <= 120:
        score += 18.0  # Acceptable
    elif 10 <= duration < 15:
        score += 12.0  # Might be too short for a full story
    else:
        score += 5.0   # Either too short or too long

    # Factor 2: Has strong metadata — title + hook (max 25 points)
    title = segment.get("title", "")
    hook = segment.get("hook", "")
    if title and len(title) >= 5:
        score += 12.0  # Has a descriptive title
    if hook and len(hook) >= 10:
        score += 13.0  # Has a substantial hook

    # Factor 3: Word count indicates complete narrative (max 25 points)
    words = segment.get("words", [])
    word_count = len(words) if isinstance(words, list) else 0
    # 40-120 words is ideal for a short (roughly 20-60 seconds of speech)
    if 40 <= word_count <= 120:
        score += 25.0
    elif 25 <= word_count < 40 or 120 < word_count <= 180:
        score += 18.0
    elif 15 <= word_count < 25:
        score += 10.0
    elif word_count > 0:
        score += 5.0

    # Factor 4: Has a stated reason/purpose (max 15 points)
    reason = segment.get("reason", "")
    if reason and len(reason) >= 20:
        score += 15.0
    elif reason:
        score += 8.0

    return min(max(score, 0.0), 100.0)


# ---------------------------------------------------------------------------
# Task 10.2: Weighted Virality Score Calculation
# ---------------------------------------------------------------------------

# Scoring weights — these are initial estimates based on content creation
# best practices. See the feedback loop TODO at module top for improvement plan.
WEIGHT_HOOK_STRENGTH = 0.30
WEIGHT_PACING = 0.25
WEIGHT_EMOTIONAL_PEAKS = 0.25
WEIGHT_CLIP_COMPLETENESS = 0.20


def calculate_virality_score(
    segment: dict[str, Any],
    words: list[dict[str, Any]],
) -> dict[str, Any]:
    """Calculate the overall virality score as a weighted combination of heuristics.

    Weights:
      - hook_strength:      30% (first impressions are critical on feed-based platforms)
      - pacing:             25% (keeps viewers watching past the hook)
      - emotional_peaks:    25% (emotional content gets shared more)
      - clip_completeness:  20% (complete stories get replayed and commented on)

    Args:
        segment: A segment dict with 'start_sec', 'end_sec', 'title', 'hook',
                 'reason', 'words' keys.
        words: List of word dicts with 'word', 'start', 'end' keys for this segment.

    Returns:
        Dict with:
          - 'score': float 0-100 (overall virality score)
          - 'breakdown': dict of individual heuristic scores
          - 'explanation': human-readable explanation string
    """
    start_sec = segment.get("start_sec", 0)
    end_sec = segment.get("end_sec", 0)
    duration = end_sec - start_sec

    # Calculate individual heuristic scores
    hook = score_hook_strength(words, start_sec, end_sec)
    pacing = score_pacing(words, duration)
    emotional = score_emotional_peaks(words)
    completeness = score_clip_completeness(segment)

    # Weighted combination
    overall = (
        hook * WEIGHT_HOOK_STRENGTH
        + pacing * WEIGHT_PACING
        + emotional * WEIGHT_EMOTIONAL_PEAKS
        + completeness * WEIGHT_CLIP_COMPLETENESS
    )

    # Round to 1 decimal place for cleaner display
    overall = round(min(max(overall, 0.0), 100.0), 1)

    breakdown = {
        "hook_strength": round(hook, 1),
        "pacing": round(pacing, 1),
        "emotional_peaks": round(emotional, 1),
        "clip_completeness": round(completeness, 1),
    }

    explanation = explain_score(breakdown)

    return {
        "score": overall,
        "breakdown": breakdown,
        "explanation": explanation,
    }


# ---------------------------------------------------------------------------
# Task 10.5: Score Explanation
# ---------------------------------------------------------------------------


def _describe_level(score: float) -> str:
    """Convert a numeric score to a qualitative descriptor."""
    if score >= 80:
        return "excellent"
    elif score >= 60:
        return "good"
    elif score >= 40:
        return "moderate"
    elif score >= 20:
        return "weak"
    else:
        return "poor"


def explain_score(scores_breakdown: dict[str, float]) -> str:
    """Return a human-readable explanation of why the virality score is what it is.

    Analyzes the breakdown of individual heuristic scores and constructs a
    narrative explanation highlighting strengths and areas for improvement.

    Args:
        scores_breakdown: Dict with keys 'hook_strength', 'pacing',
                         'emotional_peaks', 'clip_completeness' and float values.

    Returns:
        A human-readable explanation string suitable for display in a tooltip
        or detail panel.
    """
    hook = scores_breakdown.get("hook_strength", 0)
    pacing = scores_breakdown.get("pacing", 0)
    emotional = scores_breakdown.get("emotional_peaks", 0)
    completeness = scores_breakdown.get("clip_completeness", 0)

    parts: list[str] = []

    # Overall assessment
    weighted_total = (
        hook * WEIGHT_HOOK_STRENGTH
        + pacing * WEIGHT_PACING
        + emotional * WEIGHT_EMOTIONAL_PEAKS
        + completeness * WEIGHT_CLIP_COMPLETENESS
    )
    overall_level = _describe_level(weighted_total)
    parts.append(f"Overall virality potential is {overall_level}.")

    # Strengths (scores >= 60)
    strengths: list[str] = []
    if hook >= 60:
        strengths.append("a strong opening hook")
    if pacing >= 60:
        strengths.append("engaging pacing")
    if emotional >= 60:
        strengths.append("high emotional impact")
    if completeness >= 60:
        strengths.append("a complete narrative arc")

    if strengths:
        parts.append(f"Strengths: {', '.join(strengths)}.")

    # Weaknesses (scores < 40)
    weaknesses: list[str] = []
    if hook < 40:
        weaknesses.append("the opening hook could be stronger (try starting with a question or bold statement)")
    if pacing < 40:
        weaknesses.append("pacing feels uneven (consider tighter editing to remove dead air)")
    if emotional < 40:
        weaknesses.append("emotional engagement is low (add more expressive language or reactions)")
    if completeness < 40:
        weaknesses.append("the clip feels incomplete (ensure it tells a full mini-story)")

    if weaknesses:
        parts.append(f"Areas to improve: {'; '.join(weaknesses)}.")

    # If no clear strengths or weaknesses, give a balanced assessment
    if not strengths and not weaknesses:
        parts.append(
            "All scoring factors are in the moderate range. "
            "The clip is decent but may need a stronger hook or "
            "more emotional moments to stand out in crowded feeds."
        )

    return " ".join(parts)
