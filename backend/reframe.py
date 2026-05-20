"""
Smart Reframing & Face Tracking Module
=======================================

Production Task 8: Implements intelligent video reframing using MediaPipe
face detection to track speakers and dynamically crop video for vertical
(9:16) short-form content.

Features:
- MediaPipe face detection integration (Task 8.1)
- Per-frame face position sampling (Task 8.2)
- Dynamic crop window computation (Task 8.3)
- Smooth crop trajectory with EMA (Task 8.4)
- Active speaker detection via audio energy (Task 8.5)
- Fallback center crop (Task 8.6)
- User preference mode selection (Task 8.7)
- Split-screen crop for 2-person content (Task 8.8)
- FFmpeg filter generation for crop keyframes
- Audio energy extraction helper
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# MediaPipe import with graceful fallback
try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    mp = None  # type: ignore
    MEDIAPIPE_AVAILABLE = False

logger = logging.getLogger(__name__)



# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class FacePosition:
    """Represents a detected face position in a single frame.

    Attributes:
        x: Left edge of face bounding box (pixels from left)
        y: Top edge of face bounding box (pixels from top)
        width: Width of face bounding box in pixels
        height: Height of face bounding box in pixels
        confidence: Detection confidence score (0.0 to 1.0)
        frame_index: Index of the frame this detection belongs to
        timestamp: Timestamp in seconds within the video
    """
    x: float
    y: float
    width: float
    height: float
    confidence: float
    frame_index: int = 0
    timestamp: float = 0.0

    @property
    def center_x(self) -> float:
        """Horizontal center of the face bounding box."""
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        """Vertical center of the face bounding box."""
        return self.y + self.height / 2

    @property
    def area(self) -> float:
        """Area of the face bounding box."""
        return self.width * self.height



@dataclass
class CropWindow:
    """Represents a crop window applied to a video frame.

    Attributes:
        x: Left edge of crop area (pixels from left)
        y: Top edge of crop area (pixels from top)
        width: Width of crop area in pixels
        height: Height of crop area in pixels
        timestamp: Timestamp in seconds this crop applies to
    """
    x: float
    y: float
    width: float
    height: float
    timestamp: float = 0.0

    def to_ffmpeg_crop(self) -> str:
        """Convert to FFmpeg crop filter parameter string.

        Returns:
            String in format 'crop=w:h:x:y' suitable for FFmpeg -vf filter.
        """
        return f"crop={int(self.width)}:{int(self.height)}:{int(self.x)}:{int(self.y)}"

    def clamp_to_frame(self, frame_width: int, frame_height: int) -> "CropWindow":
        """Ensure crop window stays within frame boundaries.

        Args:
            frame_width: Total width of the video frame.
            frame_height: Total height of the video frame.

        Returns:
            New CropWindow clamped to valid frame coordinates.
        """
        clamped_x = max(0, min(self.x, frame_width - self.width))
        clamped_y = max(0, min(self.y, frame_height - self.height))
        clamped_w = min(self.width, frame_width)
        clamped_h = min(self.height, frame_height)
        return CropWindow(
            x=clamped_x,
            y=clamped_y,
            width=clamped_w,
            height=clamped_h,
            timestamp=self.timestamp,
        )



@dataclass
class SplitScreenCrop:
    """Represents a split-screen layout with two crop windows.

    Used for 2-person podcast/interview content where both speakers
    are shown simultaneously in a side-by-side or top-bottom layout.

    Attributes:
        top_crop: Crop window for the top (or left) speaker.
        bottom_crop: Crop window for the bottom (or right) speaker.
        layout: Either 'vertical_split' (top/bottom) or 'horizontal_split'.
    """
    top_crop: CropWindow
    bottom_crop: CropWindow
    layout: str = "vertical_split"


@dataclass
class AudioEnergyFrame:
    """Audio energy measurement for a single time window.

    Attributes:
        timestamp: Start time of the measurement window in seconds.
        energy: RMS energy level (0.0 to 1.0 normalized).
        duration: Duration of the measurement window in seconds.
    """
    timestamp: float
    energy: float
    duration: float = 0.5



# =============================================================================
# Task 8.1: MediaPipe Face Detection Integration
# =============================================================================


def _create_face_detector() -> Any:
    """Create and configure a MediaPipe Face Detection instance.

    Uses MediaPipe's short-range face detection model optimized for
    faces within 2 meters of the camera (typical for talking-head content).

    Returns:
        Configured MediaPipe FaceDetection object, or None if unavailable.

    Raises:
        RuntimeError: If MediaPipe is not installed.
    """
    if not MEDIAPIPE_AVAILABLE:
        raise RuntimeError(
            "MediaPipe is not installed. Install with: pip install mediapipe"
        )

    mp_face_detection = mp.solutions.face_detection
    detector = mp_face_detection.FaceDetection(
        model_selection=1,  # 1 = full-range model (better for varied distances)
        min_detection_confidence=0.5,
    )
    return detector


def _extract_face_positions_from_frame(
    detector: Any,
    frame: "np.ndarray",
    frame_index: int,
    timestamp: float,
) -> List[FacePosition]:
    """Extract face positions from a single video frame using MediaPipe.

    Args:
        detector: MediaPipe FaceDetection instance.
        frame: BGR image as numpy array (H, W, 3).
        frame_index: Sequential index of this frame.
        timestamp: Timestamp in seconds for this frame.

    Returns:
        List of FacePosition objects for all detected faces.
    """
    import cv2

    # MediaPipe expects RGB
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = detector.process(rgb_frame)

    faces: List[FacePosition] = []
    if results.detections:
        h, w, _ = frame.shape
        for detection in results.detections:
            bbox = detection.location_data.relative_bounding_box
            faces.append(
                FacePosition(
                    x=bbox.xmin * w,
                    y=bbox.ymin * h,
                    width=bbox.width * w,
                    height=bbox.height * h,
                    confidence=detection.score[0],
                    frame_index=frame_index,
                    timestamp=timestamp,
                )
            )

    return faces



# =============================================================================
# Task 8.2: Detect Faces in Video (sample every 0.5s)
# =============================================================================


def detect_faces_in_video(
    video_path: str,
    sample_interval: float = 0.5,
) -> List[List[FacePosition]]:
    """Sample frames from a video and detect faces in each.

    Processes the video by extracting frames at regular intervals and
    running MediaPipe face detection on each sampled frame.

    Args:
        video_path: Path to the input video file.
        sample_interval: Time between sampled frames in seconds.
            Default is 0.5s (2 frames per second of video).

    Returns:
        List of lists: outer list is per-sample, inner list contains
        all FacePosition detections for that sample. Returns empty
        inner lists for samples with no detected faces.

    Raises:
        FileNotFoundError: If video_path does not exist.
        RuntimeError: If MediaPipe or OpenCV is not available.

    Example:
        >>> faces = detect_faces_in_video("interview.mp4", sample_interval=0.5)
        >>> len(faces)  # one entry per 0.5s of video
        120
        >>> faces[0]  # faces detected in first sample
        [FacePosition(x=100, y=50, width=200, height=200, ...)]
    """
    import cv2

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    detector = _create_face_detector()
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0  # fallback assumption

    frame_skip = max(1, int(fps * sample_interval))
    all_faces: List[List[FacePosition]] = []
    frame_index = 0
    sample_index = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_index % frame_skip == 0:
                timestamp = frame_index / fps
                faces = _extract_face_positions_from_frame(
                    detector, frame, sample_index, timestamp
                )
                all_faces.append(faces)
                sample_index += 1

            frame_index += 1
    finally:
        cap.release()
        if hasattr(detector, "close"):
            detector.close()

    logger.info(
        f"Face detection complete: {sample_index} samples from "
        f"{frame_index} frames ({frame_index / fps:.1f}s video)"
    )
    return all_faces



# =============================================================================
# Task 8.3: Compute Dynamic Crop Window
# =============================================================================


def compute_dynamic_crop(
    face_positions: List[List[FacePosition]],
    frame_width: int,
    frame_height: int,
    target_aspect: float = 9 / 16,
) -> List[CropWindow]:
    """Compute a dynamic crop window that follows the primary speaker.

    For each sampled frame, determines the optimal crop rectangle that:
    1. Centers on the largest/most-confident face
    2. Maintains the target aspect ratio (default 9:16 for shorts)
    3. Provides adequate padding around the face
    4. Stays within frame boundaries

    Args:
        face_positions: Per-sample face detection results from
            detect_faces_in_video().
        frame_width: Width of the source video in pixels.
        frame_height: Height of the source video in pixels.
        target_aspect: Width-to-height ratio of output crop.
            Default 9/16 = 0.5625 for vertical shorts.

    Returns:
        List of CropWindow objects, one per sample. Falls back to
        center crop for samples with no detected faces.

    Example:
        >>> crops = compute_dynamic_crop(faces, 1920, 1080)
        >>> crops[0].width, crops[0].height
        (607, 1080)  # 9:16 aspect within 1080p frame
    """
    # Calculate crop dimensions to fill frame height
    crop_height = frame_height
    crop_width = int(crop_height * target_aspect)

    # Ensure crop width doesn't exceed frame width
    if crop_width > frame_width:
        crop_width = frame_width
        crop_height = int(crop_width / target_aspect)

    crop_windows: List[CropWindow] = []

    for sample_idx, faces in enumerate(face_positions):
        if not faces:
            # No face detected — use center crop
            crop = fallback_center_crop(frame_width, frame_height, target_aspect)
            crop.timestamp = sample_idx * 0.5  # approximate
            crop_windows.append(crop)
            continue

        # Select primary face: largest area with high confidence
        primary_face = max(
            faces,
            key=lambda f: f.area * f.confidence,
        )

        # Center crop on face with vertical bias (keep face in upper third)
        target_center_x = primary_face.center_x
        target_center_y = primary_face.center_y - (crop_height * 0.05)

        # Compute crop origin
        crop_x = target_center_x - crop_width / 2
        crop_y = target_center_y - crop_height / 3  # Face in upper third

        # Clamp to frame boundaries
        crop_x = max(0, min(crop_x, frame_width - crop_width))
        crop_y = max(0, min(crop_y, frame_height - crop_height))

        crop_windows.append(
            CropWindow(
                x=crop_x,
                y=crop_y,
                width=crop_width,
                height=crop_height,
                timestamp=sample_idx * 0.5,
            )
        )

    return crop_windows



# =============================================================================
# Task 8.4: Smooth Crop Trajectory (Exponential Moving Average)
# =============================================================================


def smooth_crop_trajectory(
    crop_windows: List[CropWindow],
    smoothing_factor: float = 0.85,
) -> List[CropWindow]:
    """Apply exponential moving average to crop trajectory to prevent jitter.

    Smooths the x and y positions of crop windows using EMA, ensuring
    camera movement appears natural and cinematic rather than jittery.
    Higher smoothing_factor means smoother (slower) camera movement.

    The formula for each position:
        smoothed[i] = smoothing_factor * smoothed[i-1] + (1 - smoothing_factor) * raw[i]

    Args:
        crop_windows: Raw crop windows from compute_dynamic_crop().
        smoothing_factor: EMA coefficient between 0 and 1.
            - 0.0 = no smoothing (raw positions)
            - 0.85 = moderate smoothing (default, good for most content)
            - 0.95 = very smooth (slow, cinematic panning)
            Values outside [0, 1] are clamped.

    Returns:
        New list of CropWindow objects with smoothed x/y positions.
        Width and height remain unchanged.

    Example:
        >>> smoothed = smooth_crop_trajectory(raw_crops, smoothing_factor=0.85)
        >>> # Smoothed positions change gradually even if face jumps
    """
    if not crop_windows:
        return []

    # Clamp smoothing factor to valid range
    alpha = max(0.0, min(1.0, smoothing_factor))

    smoothed: List[CropWindow] = []

    # Initialize with first window
    prev_x = crop_windows[0].x
    prev_y = crop_windows[0].y
    smoothed.append(
        CropWindow(
            x=prev_x,
            y=prev_y,
            width=crop_windows[0].width,
            height=crop_windows[0].height,
            timestamp=crop_windows[0].timestamp,
        )
    )

    for i in range(1, len(crop_windows)):
        raw = crop_windows[i]
        # EMA: new_pos = alpha * prev + (1 - alpha) * current
        smooth_x = alpha * prev_x + (1 - alpha) * raw.x
        smooth_y = alpha * prev_y + (1 - alpha) * raw.y

        smoothed.append(
            CropWindow(
                x=smooth_x,
                y=smooth_y,
                width=raw.width,
                height=raw.height,
                timestamp=raw.timestamp,
            )
        )

        prev_x = smooth_x
        prev_y = smooth_y

    return smoothed



# =============================================================================
# Task 8.5: Detect Active Speaker (Audio Energy Correlation)
# =============================================================================


def detect_active_speaker(
    face_positions: List[List[FacePosition]],
    audio_energy: List[AudioEnergyFrame],
) -> List[Optional[int]]:
    """Determine which face is the active speaker per time window.

    When multiple faces are detected, correlates face positions with
    audio energy levels to identify the speaker. The assumption is that
    the speaker's face position will be more spatially consistent during
    high-energy audio windows.

    Strategy:
    1. For each time window, if only one face → that's the speaker.
    2. If multiple faces, compute spatial stability during high audio energy.
    3. The face closest to the audio-energy-weighted centroid is the speaker.

    Args:
        face_positions: Per-sample face detection results.
        audio_energy: Audio energy measurements per time window
            (from extract_audio_energy()).

    Returns:
        List of face indices (0-based within each sample's face list).
        None for samples with no faces detected.

    Example:
        >>> speaker_indices = detect_active_speaker(faces, audio)
        >>> speaker_indices[5]  # Index of speaking face at sample 5
        0  # First detected face is speaking
    """
    if not face_positions:
        return []

    # Build a time-indexed energy lookup
    energy_by_time: Dict[float, float] = {}
    for ae in audio_energy:
        # Round to nearest 0.5s to align with face samples
        key = round(ae.timestamp * 2) / 2
        energy_by_time[key] = ae.energy

    speaker_indices: List[Optional[int]] = []

    # Track cumulative evidence for each face position cluster
    # We use spatial clustering to identify consistent face positions
    face_history: List[Tuple[float, float]] = []  # (center_x, center_y) running avg

    for sample_idx, faces in enumerate(face_positions):
        if not faces:
            speaker_indices.append(None)
            continue

        if len(faces) == 1:
            speaker_indices.append(0)
            continue

        # Multiple faces detected — use audio energy to choose
        timestamp = faces[0].timestamp if faces else sample_idx * 0.5
        energy_key = round(timestamp * 2) / 2
        current_energy = energy_by_time.get(energy_key, 0.0)

        if current_energy < 0.1:
            # Low audio energy — no clear speaker, pick largest face
            largest_idx = max(range(len(faces)), key=lambda i: faces[i].area)
            speaker_indices.append(largest_idx)
            continue

        # High audio energy — pick face with best correlation to recent activity
        # Heuristic: the speaker tends to be more centered and larger
        best_idx = 0
        best_score = -1.0

        for idx, face in enumerate(faces):
            # Score based on: size (larger = closer = speaker), confidence,
            # and vertical position (speakers tend to be at consistent height)
            size_score = face.area / (faces[0].area + 1e-8)
            conf_score = face.confidence
            # Prefer faces that are more centered horizontally
            center_score = 1.0 - abs(face.center_x - (face.width * 2)) / (face.width * 4 + 1e-8)

            score = (0.4 * size_score + 0.4 * conf_score + 0.2 * center_score) * current_energy
            if score > best_score:
                best_score = score
                best_idx = idx

        speaker_indices.append(best_idx)

    return speaker_indices



# =============================================================================
# Task 8.6: Fallback Center Crop
# =============================================================================


def fallback_center_crop(
    frame_width: int,
    frame_height: int,
    target_aspect: float = 9 / 16,
) -> CropWindow:
    """Generate a center crop when no face is detected.

    Computes the largest possible crop area centered in the frame
    that matches the target aspect ratio.

    Args:
        frame_width: Width of the source video frame in pixels.
        frame_height: Height of the source video frame in pixels.
        target_aspect: Width-to-height ratio for the crop.
            Default 9/16 for vertical shorts.

    Returns:
        CropWindow centered in the frame with the specified aspect ratio.

    Example:
        >>> crop = fallback_center_crop(1920, 1080, target_aspect=9/16)
        >>> crop.width, crop.height
        (607, 1080)
        >>> crop.x, crop.y
        (656, 0)  # centered horizontally
    """
    # Calculate crop dimensions to maximize frame usage
    crop_height = frame_height
    crop_width = int(crop_height * target_aspect)

    if crop_width > frame_width:
        crop_width = frame_width
        crop_height = int(crop_width / target_aspect)

    # Center the crop
    crop_x = (frame_width - crop_width) / 2
    crop_y = (frame_height - crop_height) / 2

    return CropWindow(
        x=crop_x,
        y=crop_y,
        width=crop_width,
        height=crop_height,
        timestamp=0.0,
    )



# =============================================================================
# Task 8.7: Get Reframe Mode from Config
# =============================================================================


def get_reframe_mode(config: Dict[str, Any]) -> str:
    """Read user preference for reframing mode from configuration.

    Supported modes:
    - "smart_reframe": Uses face tracking to dynamically crop (default)
    - "center_crop": Simple centered crop without face tracking
    - "split_screen": Side-by-side layout for 2-person content

    Args:
        config: Configuration dictionary, typically from project settings.
            Expected key: 'reframe_mode' with one of the supported values.

    Returns:
        One of: "smart_reframe", "center_crop", or "split_screen".
        Defaults to "smart_reframe" if key is missing or invalid.

    Example:
        >>> mode = get_reframe_mode({"reframe_mode": "center_crop"})
        >>> mode
        'center_crop'
        >>> mode = get_reframe_mode({})
        >>> mode
        'smart_reframe'
    """
    valid_modes = {"smart_reframe", "center_crop", "split_screen"}
    mode = config.get("reframe_mode", "smart_reframe")

    if mode not in valid_modes:
        logger.warning(
            f"Invalid reframe mode '{mode}', falling back to 'smart_reframe'. "
            f"Valid modes: {valid_modes}"
        )
        return "smart_reframe"

    return mode



# =============================================================================
# Task 8.8: Generate Split-Screen Crop (2-person podcasts)
# =============================================================================


def generate_split_screen_crop(
    face_positions: List[List[FacePosition]],
    frame_width: int,
    frame_height: int,
) -> List[SplitScreenCrop]:
    """Generate split-screen crop windows for 2-person podcast content.

    Creates a vertical layout with two crop regions:
    - Top half: focused on the left/first speaker
    - Bottom half: focused on the right/second speaker

    Each half maintains a 9:16 aspect ratio within its allocated space.
    Falls back to single center crops if fewer than 2 faces are detected.

    Args:
        face_positions: Per-sample face detection results.
        frame_width: Width of the source video in pixels.
        frame_height: Height of the source video in pixels.

    Returns:
        List of SplitScreenCrop objects, one per sample.

    Example:
        >>> splits = generate_split_screen_crop(faces, 1920, 1080)
        >>> splits[0].top_crop  # First speaker's crop
        CropWindow(x=100, y=0, width=540, height=540, ...)
        >>> splits[0].bottom_crop  # Second speaker's crop
        CropWindow(x=800, y=0, width=540, height=540, ...)
    """
    # For split screen, each panel is half the target height
    # Final output: 9:16 with two 9:8 panels stacked
    target_aspect = 9 / 16
    panel_height = frame_height  # Each panel crops full height, resized later
    panel_width = int(panel_height * target_aspect)

    if panel_width > frame_width:
        panel_width = frame_width
        panel_height = int(panel_width / target_aspect)

    split_crops: List[SplitScreenCrop] = []

    for sample_idx, faces in enumerate(face_positions):
        timestamp = sample_idx * 0.5

        if len(faces) < 2:
            # Not enough faces for split screen — duplicate center crop
            center = fallback_center_crop(frame_width, frame_height, target_aspect)
            center.timestamp = timestamp
            split_crops.append(
                SplitScreenCrop(
                    top_crop=CropWindow(
                        x=center.x, y=center.y,
                        width=center.width, height=center.height,
                        timestamp=timestamp,
                    ),
                    bottom_crop=CropWindow(
                        x=center.x, y=center.y,
                        width=center.width, height=center.height,
                        timestamp=timestamp,
                    ),
                    layout="vertical_split",
                )
            )
            continue

        # Sort faces by horizontal position (left to right)
        sorted_faces = sorted(faces, key=lambda f: f.center_x)
        left_face = sorted_faces[0]
        right_face = sorted_faces[1]

        # Create crop for left/top speaker
        top_x = left_face.center_x - panel_width / 2
        top_y = left_face.center_y - panel_height / 3
        top_x = max(0, min(top_x, frame_width - panel_width))
        top_y = max(0, min(top_y, frame_height - panel_height))

        # Create crop for right/bottom speaker
        bot_x = right_face.center_x - panel_width / 2
        bot_y = right_face.center_y - panel_height / 3
        bot_x = max(0, min(bot_x, frame_width - panel_width))
        bot_y = max(0, min(bot_y, frame_height - panel_height))

        split_crops.append(
            SplitScreenCrop(
                top_crop=CropWindow(
                    x=top_x, y=top_y,
                    width=panel_width, height=panel_height,
                    timestamp=timestamp,
                ),
                bottom_crop=CropWindow(
                    x=bot_x, y=bot_y,
                    width=panel_width, height=panel_height,
                    timestamp=timestamp,
                ),
                layout="vertical_split",
            )
        )

    return split_crops



# =============================================================================
# Audio Energy Extraction Helper
# =============================================================================


async def extract_audio_energy(
    video_path: str,
    window_duration: float = 0.5,
) -> List[AudioEnergyFrame]:
    """Extract audio energy levels per time window using FFmpeg.

    Uses FFmpeg's astats filter to compute RMS energy for each time
    window without requiring external audio libraries like librosa.

    Args:
        video_path: Path to the input video file.
        window_duration: Duration of each measurement window in seconds.
            Should match the face detection sample_interval.

    Returns:
        List of AudioEnergyFrame objects with normalized energy levels.

    Raises:
        FileNotFoundError: If video_path does not exist.
        RuntimeError: If FFmpeg command fails.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    # Use FFmpeg to extract audio volume levels
    # -af astats outputs per-frame audio statistics
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-af", f"asegment=timestamps=0,astats=metadata=1:reset={int(1/window_duration)}",
        "-f", "null",
        "-v", "info",
        "-stats",
        "-"
    ]

    # Alternative simpler approach: use volumedetect per segment
    # We'll use the ebur128 filter which gives loudness per time interval
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-af", f"aresample=8000,asetnsamples=n={int(8000 * window_duration)},"
               f"astats=metadata=1:reset=1",
        "-f", "null",
        "-v", "info",
        "-"
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr_data = await process.communicate()
        stderr_output = stderr_data.decode("utf-8", errors="replace")
    except FileNotFoundError:
        raise RuntimeError("FFmpeg not found. Please install FFmpeg.")

    # Parse RMS levels from FFmpeg output
    energy_frames: List[AudioEnergyFrame] = []
    rms_values: List[float] = []

    for line in stderr_output.split("\n"):
        if "RMS level" in line or "rms_level" in line.lower():
            try:
                # Extract dB value and convert to linear
                parts = line.split(":")
                if len(parts) >= 2:
                    db_str = parts[-1].strip().replace("dB", "").strip()
                    db_val = float(db_str)
                    # Convert dB to linear (0-1 range)
                    linear = 10 ** (db_val / 20) if db_val > -100 else 0.0
                    rms_values.append(min(1.0, linear))
            except (ValueError, IndexError):
                continue

    # If parsing failed, estimate from video duration with flat energy
    if not rms_values:
        logger.warning("Could not parse audio energy from FFmpeg output, using estimation")
        duration = await _get_video_duration(video_path)
        num_windows = int(duration / window_duration)
        rms_values = [0.5] * max(1, num_windows)  # Default moderate energy

    # Build AudioEnergyFrame list
    for i, energy in enumerate(rms_values):
        energy_frames.append(
            AudioEnergyFrame(
                timestamp=i * window_duration,
                energy=energy,
                duration=window_duration,
            )
        )

    return energy_frames



# =============================================================================
# FFmpeg Filter Generation
# =============================================================================


def generate_ffmpeg_crop_filter(
    crop_windows: List[CropWindow],
    frame_rate: float = 30.0,
) -> str:
    """Convert crop trajectory into an FFmpeg -vf crop filter with keyframes.

    Generates an FFmpeg crop filter string that animates the crop position
    over time using sendcmd/zmq or the crop filter with expressions.

    For smooth animated crops, we use FFmpeg's expression-based crop filter
    with interpolated keyframes via the 'if(between(t,...))' expression syntax.

    Args:
        crop_windows: Smoothed crop windows from smooth_crop_trajectory().
        frame_rate: Video frame rate for time-to-frame conversion.

    Returns:
        FFmpeg filter string suitable for use with -vf flag.
        Format: "crop=w:h:x_expr:y_expr" with time-based expressions.

    Example:
        >>> filter_str = generate_ffmpeg_crop_filter(smoothed_crops)
        >>> # Use in FFmpeg: ffmpeg -i input.mp4 -vf "{filter_str}" output.mp4
    """
    if not crop_windows:
        return "crop=iw:ih:0:0"

    # For simple cases (all same position), use static crop
    if len(crop_windows) == 1 or _is_static_trajectory(crop_windows):
        cw = crop_windows[0]
        return f"crop={int(cw.width)}:{int(cw.height)}:{int(cw.x)}:{int(cw.y)}"

    # Build time-based expression for animated crop
    # Use FFmpeg's expression language with linear interpolation between keyframes
    w = int(crop_windows[0].width)
    h = int(crop_windows[0].height)

    x_expr = _build_interpolated_expression(
        [(cw.timestamp, cw.x) for cw in crop_windows]
    )
    y_expr = _build_interpolated_expression(
        [(cw.timestamp, cw.y) for cw in crop_windows]
    )

    return f"crop={w}:{h}:{x_expr}:{y_expr}"


def _is_static_trajectory(crop_windows: List[CropWindow], threshold: float = 2.0) -> bool:
    """Check if the crop trajectory is essentially static (no movement).

    Args:
        crop_windows: List of crop windows to check.
        threshold: Maximum pixel deviation to consider static.

    Returns:
        True if all crop positions are within threshold of each other.
    """
    if len(crop_windows) <= 1:
        return True

    ref_x = crop_windows[0].x
    ref_y = crop_windows[0].y

    for cw in crop_windows[1:]:
        if abs(cw.x - ref_x) > threshold or abs(cw.y - ref_y) > threshold:
            return False

    return True


def _build_interpolated_expression(
    keyframes: List[Tuple[float, float]],
) -> str:
    """Build FFmpeg expression for linear interpolation between keyframes.

    Creates a nested if(between(t,...)) expression that linearly
    interpolates the crop position between defined keyframe timestamps.

    Args:
        keyframes: List of (timestamp, value) tuples.

    Returns:
        FFmpeg expression string using 't' variable for time.
    """
    if not keyframes:
        return "0"

    if len(keyframes) == 1:
        return str(int(keyframes[0][1]))

    # Build piecewise linear expression
    # Format: if(lt(t,t1), v0 + (v1-v0)*(t-t0)/(t1-t0), if(lt(t,t2), ...))
    parts: List[str] = []

    for i in range(len(keyframes) - 1):
        t0, v0 = keyframes[i]
        t1, v1 = keyframes[i + 1]

        if abs(v1 - v0) < 1.0:
            # No significant movement in this segment
            segment_expr = str(int(v0))
        else:
            # Linear interpolation: v0 + (v1-v0) * (t-t0) / (t1-t0)
            dt = t1 - t0
            if dt > 0:
                slope = (v1 - v0) / dt
                segment_expr = f"{int(v0)}+{slope:.2f}*(t-{t0:.2f})"
            else:
                segment_expr = str(int(v0))

        parts.append((t1, segment_expr))

    # Build nested if expression
    if len(parts) == 1:
        return parts[0][1]

    # Construct from last to first
    expr = str(int(keyframes[-1][1]))  # final fallback value
    for i in range(len(parts) - 1, -1, -1):
        t_end = parts[i][0]
        segment = parts[i][1]
        expr = f"if(lt(t\\,{t_end:.2f})\\,{segment}\\,{expr})"

    return f"'{expr}'"



def generate_split_screen_filter(
    split_crops: List[SplitScreenCrop],
    frame_width: int,
    frame_height: int,
    output_width: int = 1080,
    output_height: int = 1920,
) -> str:
    """Generate FFmpeg complex filter for split-screen layout.

    Creates a filter that:
    1. Crops two regions from the source video (one per speaker)
    2. Scales each to half the output height
    3. Stacks them vertically

    Args:
        split_crops: Split screen crop data from generate_split_screen_crop().
        frame_width: Source video width.
        frame_height: Source video height.
        output_width: Output video width (default 1080 for vertical HD).
        output_height: Output video height (default 1920 for 9:16).

    Returns:
        FFmpeg complex filter string for use with -filter_complex.
    """
    if not split_crops:
        return f"scale={output_width}:{output_height}"

    # Use first crop positions (static split for simplicity)
    sc = split_crops[0]
    panel_h = output_height // 2

    top = sc.top_crop
    bot = sc.bottom_crop

    # Complex filter: crop each region, scale to panel size, stack vertically
    filter_str = (
        f"[0:v]split=2[top_in][bot_in];"
        f"[top_in]crop={int(top.width)}:{int(top.height)}:{int(top.x)}:{int(top.y)},"
        f"scale={output_width}:{panel_h}[top_out];"
        f"[bot_in]crop={int(bot.width)}:{int(bot.height)}:{int(bot.x)}:{int(bot.y)},"
        f"scale={output_width}:{panel_h}[bot_out];"
        f"[top_out][bot_out]vstack=inputs=2[out]"
    )

    return filter_str



# =============================================================================
# Helper Functions
# =============================================================================


async def _get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using FFprobe.

    Args:
        video_path: Path to the video file.

    Returns:
        Duration in seconds, or 0.0 if unable to determine.
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        video_path,
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_data, _ = await process.communicate()
        info = json.loads(stdout_data.decode("utf-8"))
        return float(info.get("format", {}).get("duration", 0.0))
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return 0.0


async def _get_video_dimensions(video_path: str) -> Tuple[int, int, float]:
    """Get video width, height, and frame rate using FFprobe.

    Args:
        video_path: Path to the video file.

    Returns:
        Tuple of (width, height, fps). Defaults to (1920, 1080, 30.0)
        if unable to determine.
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-select_streams", "v:0",
        video_path,
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_data, _ = await process.communicate()
        info = json.loads(stdout_data.decode("utf-8"))

        stream = info.get("streams", [{}])[0]
        width = int(stream.get("width", 1920))
        height = int(stream.get("height", 1080))

        # Parse frame rate (can be "30/1" or "29.97")
        r_frame_rate = stream.get("r_frame_rate", "30/1")
        if "/" in r_frame_rate:
            num, den = r_frame_rate.split("/")
            fps = float(num) / float(den)
        else:
            fps = float(r_frame_rate)

        return width, height, fps
    except (FileNotFoundError, json.JSONDecodeError, ValueError, IndexError):
        return 1920, 1080, 30.0



# =============================================================================
# Main Entry Point: reframe_video
# =============================================================================


async def reframe_video(
    video_path: str,
    output_path: str,
    mode: str = "smart_reframe",
    target_aspect: float = 9 / 16,
    smoothing_factor: float = 0.85,
    sample_interval: float = 0.5,
) -> str:
    """Main entry point for the smart reframing pipeline.

    Orchestrates the full face-tracking and reframing workflow:
    1. Detects video dimensions
    2. Based on mode, either:
       a) smart_reframe: detect faces → compute crops → smooth → apply
       b) center_crop: simple center crop with target aspect ratio
       c) split_screen: detect faces → generate split layout → apply
    3. Generates FFmpeg filter and applies it to produce output

    Args:
        video_path: Path to the input video file.
        output_path: Path for the reframed output video.
        mode: Reframing mode - "smart_reframe", "center_crop", or "split_screen".
        target_aspect: Width-to-height ratio for output (default 9/16).
        smoothing_factor: EMA smoothing for crop trajectory (0-1).
        sample_interval: Time between face detection samples in seconds.

    Returns:
        Path to the output video file.

    Raises:
        FileNotFoundError: If input video does not exist.
        RuntimeError: If FFmpeg processing fails.

    Example:
        >>> output = await reframe_video(
        ...     "podcast.mp4",
        ...     "podcast_reframed.mp4",
        ...     mode="smart_reframe",
        ... )
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Input video not found: {video_path}")

    logger.info(f"Starting reframe: mode={mode}, aspect={target_aspect}, input={video_path}")

    # Get video dimensions
    frame_width, frame_height, fps = await _get_video_dimensions(video_path)
    logger.info(f"Video dimensions: {frame_width}x{frame_height} @ {fps:.2f}fps")

    # Determine output dimensions
    output_height = frame_height
    output_width = int(output_height * target_aspect)
    if output_width > frame_width:
        output_width = frame_width
        output_height = int(output_width / target_aspect)

    # Route based on mode
    if mode == "center_crop":
        crop = fallback_center_crop(frame_width, frame_height, target_aspect)
        vf_filter = crop.to_ffmpeg_crop()
        await _apply_ffmpeg_crop(video_path, output_path, vf_filter)

    elif mode == "split_screen":
        await _process_split_screen(
            video_path, output_path,
            frame_width, frame_height,
            output_width, output_height,
            sample_interval,
        )

    else:  # smart_reframe (default)
        await _process_smart_reframe(
            video_path, output_path,
            frame_width, frame_height,
            fps, target_aspect,
            smoothing_factor, sample_interval,
        )

    logger.info(f"Reframe complete: {output_path}")
    return output_path



async def _process_smart_reframe(
    video_path: str,
    output_path: str,
    frame_width: int,
    frame_height: int,
    fps: float,
    target_aspect: float,
    smoothing_factor: float,
    sample_interval: float,
) -> None:
    """Process video with smart face-tracking reframe.

    Internal helper that runs the full smart reframe pipeline:
    face detection → audio energy → speaker selection → crop → smooth → FFmpeg.

    Args:
        video_path: Input video path.
        output_path: Output video path.
        frame_width: Source video width.
        frame_height: Source video height.
        fps: Source video frame rate.
        target_aspect: Target aspect ratio.
        smoothing_factor: EMA smoothing coefficient.
        sample_interval: Face detection sample interval.
    """
    # Step 1: Detect faces
    try:
        face_positions = detect_faces_in_video(video_path, sample_interval)
    except RuntimeError as e:
        logger.warning(f"Face detection failed ({e}), falling back to center crop")
        crop = fallback_center_crop(frame_width, frame_height, target_aspect)
        await _apply_ffmpeg_crop(video_path, output_path, crop.to_ffmpeg_crop())
        return

    # Step 2: Extract audio energy for speaker detection
    audio_energy = await extract_audio_energy(video_path, sample_interval)

    # Step 3: Detect active speaker (for multi-face scenarios)
    speaker_indices = detect_active_speaker(face_positions, audio_energy)

    # Step 4: Filter face positions to focus on active speaker
    focused_faces: List[List[FacePosition]] = []
    for i, (faces, speaker_idx) in enumerate(
        zip(face_positions, speaker_indices)
    ):
        if speaker_idx is not None and faces:
            # Keep only the active speaker's face for crop computation
            focused_faces.append([faces[min(speaker_idx, len(faces) - 1)]])
        else:
            focused_faces.append(faces)

    # Step 5: Compute dynamic crop windows
    crop_windows = compute_dynamic_crop(
        focused_faces, frame_width, frame_height, target_aspect
    )

    # Step 6: Smooth the trajectory
    smoothed_crops = smooth_crop_trajectory(crop_windows, smoothing_factor)

    # Step 7: Generate FFmpeg filter and apply
    vf_filter = generate_ffmpeg_crop_filter(smoothed_crops, fps)
    await _apply_ffmpeg_crop(video_path, output_path, vf_filter)



async def _process_split_screen(
    video_path: str,
    output_path: str,
    frame_width: int,
    frame_height: int,
    output_width: int,
    output_height: int,
    sample_interval: float,
) -> None:
    """Process video with split-screen layout for 2-person content.

    Args:
        video_path: Input video path.
        output_path: Output video path.
        frame_width: Source video width.
        frame_height: Source video height.
        output_width: Target output width.
        output_height: Target output height.
        sample_interval: Face detection sample interval.
    """
    # Detect faces for split-screen layout
    try:
        face_positions = detect_faces_in_video(video_path, sample_interval)
    except RuntimeError as e:
        logger.warning(f"Face detection failed ({e}), using center split")
        face_positions = [[]]  # empty, will trigger fallback

    # Generate split-screen crops
    split_crops = generate_split_screen_crop(face_positions, frame_width, frame_height)

    # Generate complex filter
    filter_complex = generate_split_screen_filter(
        split_crops, frame_width, frame_height, output_width, output_height
    )

    # Apply with FFmpeg complex filter
    await _apply_ffmpeg_complex_filter(video_path, output_path, filter_complex)


async def _apply_ffmpeg_crop(
    input_path: str,
    output_path: str,
    vf_filter: str,
) -> None:
    """Apply an FFmpeg video filter (crop) to produce output.

    Args:
        input_path: Input video file path.
        output_path: Output video file path.
        vf_filter: Video filter string (e.g., "crop=1080:1920:420:0").

    Raises:
        RuntimeError: If FFmpeg returns a non-zero exit code.
    """
    cmd = [
        "ffmpeg",
        "-y",  # overwrite output
        "-i", input_path,
        "-vf", vf_filter,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path,
    ]

    logger.info(f"Running FFmpeg crop: {' '.join(cmd)}")

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr_data = await process.communicate()

    if process.returncode != 0:
        error_msg = stderr_data.decode("utf-8", errors="replace")[-500:]
        raise RuntimeError(
            f"FFmpeg crop failed (exit code {process.returncode}): {error_msg}"
        )



async def _apply_ffmpeg_complex_filter(
    input_path: str,
    output_path: str,
    filter_complex: str,
) -> None:
    """Apply an FFmpeg complex filter (split-screen) to produce output.

    Args:
        input_path: Input video file path.
        output_path: Output video file path.
        filter_complex: Complex filter graph string.

    Raises:
        RuntimeError: If FFmpeg returns a non-zero exit code.
    """
    cmd = [
        "ffmpeg",
        "-y",  # overwrite output
        "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-map", "0:a?",  # include audio if present
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path,
    ]

    logger.info(f"Running FFmpeg complex filter: {' '.join(cmd)}")

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr_data = await process.communicate()

    if process.returncode != 0:
        error_msg = stderr_data.decode("utf-8", errors="replace")[-500:]
        raise RuntimeError(
            f"FFmpeg complex filter failed (exit code {process.returncode}): {error_msg}"
        )


# =============================================================================
# Module-level convenience
# =============================================================================


__all__ = [
    "FacePosition",
    "CropWindow",
    "SplitScreenCrop",
    "AudioEnergyFrame",
    "detect_faces_in_video",
    "compute_dynamic_crop",
    "smooth_crop_trajectory",
    "detect_active_speaker",
    "fallback_center_crop",
    "get_reframe_mode",
    "generate_split_screen_crop",
    "extract_audio_energy",
    "generate_ffmpeg_crop_filter",
    "generate_split_screen_filter",
    "reframe_video",
]
