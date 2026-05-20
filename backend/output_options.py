"""
Production Task 14: Better Output Options
==========================================
Comprehensive output configuration for the Shorts Engine Studio.
Handles aspect ratios, resolutions, background music, transitions,
intro/outro templates, watermarks, and CTA overlays.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# =============================================================================
# Task 14.1: Aspect Ratios
# =============================================================================

ASPECT_RATIOS: dict[str, tuple[int, int]] = {
    "9:16": (9, 16),     # Vertical shorts (TikTok, Reels, Shorts) - default
    "1:1": (1, 1),       # Square (Instagram feed)
    "16:9": (16, 9),     # Landscape (YouTube)
    "4:5": (4, 5),       # Portrait (Facebook/Instagram feed)
}

DEFAULT_ASPECT_RATIO = "9:16"


def compute_crop_dimensions(
    source_width: int,
    source_height: int,
    target_aspect: str,
) -> tuple[int, int, int, int]:
    """
    Compute crop dimensions to achieve target aspect ratio from source dimensions.

    Returns:
        (crop_w, crop_h, crop_x, crop_y) - width, height, x-offset, y-offset
        for the crop operation.
    """
    if target_aspect not in ASPECT_RATIOS:
        raise ValueError(
            f"Unknown aspect ratio '{target_aspect}'. "
            f"Valid options: {list(ASPECT_RATIOS.keys())}"
        )

    w_ratio, h_ratio = ASPECT_RATIOS[target_aspect]
    target_ratio = w_ratio / h_ratio
    source_ratio = source_width / source_height

    if source_ratio > target_ratio:
        # Source is wider than target: crop width (pillarbox)
        crop_h = source_height
        crop_w = int(source_height * target_ratio)
    else:
        # Source is taller than target: crop height (letterbox)
        crop_w = source_width
        crop_h = int(source_width / target_ratio)

    # Ensure even dimensions for FFmpeg compatibility
    crop_w = crop_w - (crop_w % 2)
    crop_h = crop_h - (crop_h % 2)

    # Center the crop
    crop_x = (source_width - crop_w) // 2
    crop_y = (source_height - crop_h) // 2

    return (crop_w, crop_h, crop_x, crop_y)


# =============================================================================
# Task 14.2: Resolutions
# =============================================================================

RESOLUTIONS: dict[str, dict[str, tuple[int, int]]] = {
    "720p": {
        "9:16": (720, 1280),
        "16:9": (1280, 720),
        "1:1": (720, 720),
        "4:5": (720, 900),
    },
    "1080p": {
        "9:16": (1080, 1920),
        "16:9": (1920, 1080),
        "1:1": (1080, 1080),
        "4:5": (1080, 1350),
    },
    "4K": {
        "9:16": (2160, 3840),
        "16:9": (3840, 2160),
        "1:1": (2160, 2160),
        "4:5": (2160, 2700),
    },
}

PLAN_RESOLUTION_MAP: dict[str, str] = {
    "free": "720p",
    "pro": "1080p",
    "business": "4K",
}


def get_output_dimensions(
    aspect_ratio: str,
    resolution: str,
) -> tuple[int, int]:
    """
    Get the output dimensions (width, height) for a given aspect ratio and resolution.

    Returns:
        (width, height) tuple in pixels.
    """
    if resolution not in RESOLUTIONS:
        raise ValueError(
            f"Unknown resolution '{resolution}'. "
            f"Valid options: {list(RESOLUTIONS.keys())}"
        )
    if aspect_ratio not in RESOLUTIONS[resolution]:
        raise ValueError(
            f"Unknown aspect ratio '{aspect_ratio}'. "
            f"Valid options: {list(RESOLUTIONS[resolution].keys())}"
        )
    return RESOLUTIONS[resolution][aspect_ratio]


def get_resolution_for_plan(plan: str) -> str:
    """
    Get the maximum resolution allowed for a subscription plan.

    Args:
        plan: One of 'free', 'pro', 'business'.

    Returns:
        Resolution preset string (e.g., '720p', '1080p', '4K').
    """
    if plan not in PLAN_RESOLUTION_MAP:
        raise ValueError(
            f"Unknown plan '{plan}'. Valid plans: {list(PLAN_RESOLUTION_MAP.keys())}"
        )
    return PLAN_RESOLUTION_MAP[plan]


# =============================================================================
# Task 14.3 + 14.4: Background Music Library
# =============================================================================

@dataclass
class MusicTrack:
    """Metadata for a royalty-free background music track."""
    name: str
    genre: str
    energy_level: str  # "low", "medium", "high"
    bpm: int
    duration: float  # seconds
    file_key: str  # storage key for the audio file


MUSIC_LIBRARY: list[MusicTrack] = [
    MusicTrack(
        name="Chill Lo-Fi Beats",
        genre="lo-fi",
        energy_level="low",
        bpm=75,
        duration=180.0,
        file_key="music/chill-lofi-beats.mp3",
    ),
    MusicTrack(
        name="Ambient Dreams",
        genre="ambient",
        energy_level="low",
        bpm=60,
        duration=240.0,
        file_key="music/ambient-dreams.mp3",
    ),
    MusicTrack(
        name="Soft Piano",
        genre="classical",
        energy_level="low",
        bpm=70,
        duration=200.0,
        file_key="music/soft-piano.mp3",
    ),
    MusicTrack(
        name="Upbeat Pop",
        genre="pop",
        energy_level="medium",
        bpm=110,
        duration=180.0,
        file_key="music/upbeat-pop.mp3",
    ),
    MusicTrack(
        name="Funky Groove",
        genre="funk",
        energy_level="medium",
        bpm=100,
        duration=150.0,
        file_key="music/funky-groove.mp3",
    ),
    MusicTrack(
        name="Corporate Inspiration",
        genre="corporate",
        energy_level="medium",
        bpm=120,
        duration=160.0,
        file_key="music/corporate-inspiration.mp3",
    ),
    MusicTrack(
        name="Indie Acoustic",
        genre="acoustic",
        energy_level="medium",
        bpm=95,
        duration=210.0,
        file_key="music/indie-acoustic.mp3",
    ),
    MusicTrack(
        name="Electronic Pulse",
        genre="electronic",
        energy_level="high",
        bpm=140,
        duration=180.0,
        file_key="music/electronic-pulse.mp3",
    ),
    MusicTrack(
        name="Hip Hop Energy",
        genre="hip-hop",
        energy_level="high",
        bpm=130,
        duration=170.0,
        file_key="music/hip-hop-energy.mp3",
    ),
    MusicTrack(
        name="Rock Drive",
        genre="rock",
        energy_level="high",
        bpm=150,
        duration=190.0,
        file_key="music/rock-drive.mp3",
    ),
]

ENERGY_LEVEL_ORDER = {"low": 0, "medium": 1, "high": 2}


def select_background_music(
    energy_level: str,
    duration: float,
) -> MusicTrack:
    """
    Select the best-matching background music track based on energy level
    and required duration.

    Prioritizes:
    1. Matching energy level
    2. Track duration >= required duration (to avoid looping)
    3. Closest BPM within energy level

    Args:
        energy_level: Desired energy level ("low", "medium", "high").
        duration: Required minimum duration in seconds.

    Returns:
        Best matching MusicTrack.
    """
    if energy_level not in ENERGY_LEVEL_ORDER:
        energy_level = "medium"

    # Filter tracks by energy level
    matching_tracks = [
        t for t in MUSIC_LIBRARY if t.energy_level == energy_level
    ]

    # If no exact match, fall back to all tracks
    if not matching_tracks:
        matching_tracks = MUSIC_LIBRARY

    # Prefer tracks that are long enough (no looping needed)
    long_enough = [t for t in matching_tracks if t.duration >= duration]
    if long_enough:
        # Return the one with the shortest duration that still fits
        # (minimize wasted audio)
        return min(long_enough, key=lambda t: t.duration)

    # If all tracks are too short, return the longest one
    return max(matching_tracks, key=lambda t: t.duration)


def generate_music_mix_filter(
    music_path: str,
    video_duration: float,
    volume: float = 0.15,
) -> str:
    """
    Generate FFmpeg filter string to mix background music at low volume
    under the main video audio.

    Args:
        music_path: Path to the background music file.
        video_duration: Duration of the video in seconds.
        volume: Background music volume level (0.0 to 1.0). Default 0.15.

    Returns:
        FFmpeg filter_complex string for audio mixing.
    """
    # Fade out the music in the last 2 seconds
    fade_start = max(0, video_duration - 2.0)
    return (
        f"[1:a]aloop=loop=-1:size=2e+09,atrim=0:{video_duration},"
        f"volume={volume},afade=t=out:st={fade_start}:d=2.0[music];"
        f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )


# =============================================================================
# Task 14.5: Transition Effects
# =============================================================================

TRANSITION_EFFECTS: dict[str, str] = {
    "fade": "xfade=transition=fade",
    "slide": "xfade=transition=slideleft",
    "zoom": "zoompan=z='min(zoom+0.0015,1.5)':d=25:s=1080x1920",
    "none": "",
}

DEFAULT_TRANSITION = "fade"


def generate_transition_filter(
    effect: str,
    duration: float = 0.5,
) -> str:
    """
    Generate FFmpeg filter string for a transition effect between segments.

    Args:
        effect: Transition effect name (fade, slide, zoom, none).
        duration: Transition duration in seconds. Default 0.5.

    Returns:
        FFmpeg filter string. Empty string for 'none'.
    """
    if effect not in TRANSITION_EFFECTS:
        raise ValueError(
            f"Unknown transition effect '{effect}'. "
            f"Valid options: {list(TRANSITION_EFFECTS.keys())}"
        )

    if effect == "none":
        return ""

    base_filter = TRANSITION_EFFECTS[effect]

    if effect in ("fade", "slide"):
        # xfade transitions use duration and offset parameters
        return f"{base_filter}:duration={duration}"
    elif effect == "zoom":
        # Zoom/pan effect is applied to individual clips, not between them
        return TRANSITION_EFFECTS["zoom"]

    return base_filter


# =============================================================================
# Task 14.6: Intro/Outro Templates
# =============================================================================

@dataclass
class IntroOutroConfig:
    """Configuration for intro/outro overlays."""
    brand_color: str = "#FFFFFF"  # Hex color for brand/text
    logo_path: Optional[str] = None  # Path to logo image (optional)
    text: str = ""  # Text to display (channel name, tagline, etc.)
    duration: float = 3.0  # Duration in seconds


def generate_intro_filter(config: IntroOutroConfig) -> str:
    """
    Generate FFmpeg filter string for an intro overlay.

    Creates a branded intro with optional logo and text that fades in
    at the beginning of the video.

    Args:
        config: IntroOutroConfig with brand settings.

    Returns:
        FFmpeg filter string for the intro effect.
    """
    filters = []

    # Background color overlay that fades out
    filters.append(
        f"color=c={config.brand_color}:s=1080x1920:d={config.duration}"
        f"[intro_bg]"
    )

    # Fade the intro background out
    filters.append(
        f"[intro_bg]format=yuva420p,"
        f"fade=t=out:st={config.duration - 0.5}:d=0.5:alpha=1[intro_fade]"
    )

    # Add text if provided
    if config.text:
        escaped_text = config.text.replace("'", "\\'").replace(":", "\\:")
        filters.append(
            f"[intro_fade]drawtext="
            f"text='{escaped_text}':"
            f"fontcolor=white:fontsize=64:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:"
            f"font=Arial:bold=1:"
            f"fade_in=0:0.5[intro_text]"
        )
        final_label = "intro_text"
    else:
        final_label = "intro_fade"

    # Add logo overlay if provided
    if config.logo_path:
        filters.append(
            f"[{final_label}][logo]overlay="
            f"x=(W-w)/2:y=(H-h)/2-100:"
            f"enable='between(t,0,{config.duration})'[intro_out]"
        )
        final_label = "intro_out"

    return ";".join(filters)


def generate_outro_filter(config: IntroOutroConfig) -> str:
    """
    Generate FFmpeg filter string for an outro overlay.

    Creates a branded outro with optional logo and text that fades in
    at the end of the video.

    Args:
        config: IntroOutroConfig with brand settings.

    Returns:
        FFmpeg filter string for the outro effect.
    """
    filters = []

    # Background color overlay that fades in
    filters.append(
        f"color=c={config.brand_color}:s=1080x1920:d={config.duration}"
        f"[outro_bg]"
    )

    # Fade the outro background in
    filters.append(
        f"[outro_bg]format=yuva420p,"
        f"fade=t=in:st=0:d=0.5:alpha=1[outro_fade]"
    )

    # Add text if provided
    if config.text:
        escaped_text = config.text.replace("'", "\\'").replace(":", "\\:")
        filters.append(
            f"[outro_fade]drawtext="
            f"text='{escaped_text}':"
            f"fontcolor=white:fontsize=64:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:"
            f"font=Arial:bold=1[outro_text]"
        )
        final_label = "outro_text"
    else:
        final_label = "outro_fade"

    # Add logo overlay if provided
    if config.logo_path:
        filters.append(
            f"[{final_label}][logo]overlay="
            f"x=(W-w)/2:y=(H-h)/2-100[outro_out]"
        )
        final_label = "outro_out"

    return ";".join(filters)


# =============================================================================
# Task 14.7 + 14.8: Watermark
# =============================================================================

WATERMARK_POSITIONS: dict[str, str] = {
    "top-left": "x=10:y=10",
    "top-right": "x=W-w-10:y=10",
    "bottom-left": "x=10:y=H-h-10",
    "bottom-right": "x=W-w-10:y=H-h-10",
    "center": "x=(W-w)/2:y=(H-h)/2",
}


def generate_watermark_filter(
    logo_path: str,
    position: str = "bottom-right",
    opacity: float = 0.5,
) -> str:
    """
    Generate FFmpeg filter string for a watermark overlay.

    Args:
        logo_path: Path to the watermark/logo image file.
        position: Position on the video. One of:
            'top-left', 'top-right', 'bottom-left', 'bottom-right', 'center'.
        opacity: Opacity of the watermark (0.0 to 1.0). Default 0.5.

    Returns:
        FFmpeg filter string for the watermark overlay.
    """
    if position not in WATERMARK_POSITIONS:
        raise ValueError(
            f"Unknown watermark position '{position}'. "
            f"Valid options: {list(WATERMARK_POSITIONS.keys())}"
        )

    pos_coords = WATERMARK_POSITIONS[position]

    # Scale watermark to reasonable size and apply opacity
    return (
        f"[1:v]format=rgba,colorchannelmixer=aa={opacity},"
        f"scale=iw*0.15:-1[wm];"
        f"[0:v][wm]overlay={pos_coords}[vout]"
    )


def should_add_watermark(plan: str) -> bool:
    """
    Determine if a watermark should be added based on the user's plan.

    Free users get a watermark; paid users (pro/business) do not.

    Args:
        plan: User's subscription plan ('free', 'pro', 'business').

    Returns:
        True if watermark should be added, False otherwise.
    """
    return plan.lower() == "free"


# =============================================================================
# Task 14.9: CTA (Call-to-Action) Overlay
# =============================================================================

CTA_POSITIONS: dict[str, str] = {
    "top": "x=(w-text_w)/2:y=50",
    "center": "x=(w-text_w)/2:y=(h-text_h)/2",
    "bottom": "x=(w-text_w)/2:y=h-text_h-80",
}


def generate_cta_overlay(
    text: str,
    url: str,
    position: str = "bottom",
    start_time: float = 0.0,
    duration: float = 5.0,
) -> str:
    """
    Generate FFmpeg drawtext filter for a CTA (Call-to-Action) overlay.

    Displays a text CTA (e.g., "Subscribe!", "Link in bio") with optional
    URL text during a specific time window in the video.

    Args:
        text: CTA text to display (e.g., "Subscribe Now!").
        url: URL or additional text (e.g., "@channelname" or "link.to/page").
        position: Position on the video ('top', 'center', 'bottom').
        start_time: When to show the CTA (seconds from start).
        duration: How long to display the CTA (seconds).

    Returns:
        FFmpeg drawtext filter string.
    """
    if position not in CTA_POSITIONS:
        raise ValueError(
            f"Unknown CTA position '{position}'. "
            f"Valid options: {list(CTA_POSITIONS.keys())}"
        )

    end_time = start_time + duration
    pos_coords = CTA_POSITIONS[position]

    # Escape special characters for FFmpeg drawtext
    escaped_text = text.replace("'", "\\'").replace(":", "\\:")
    escaped_url = url.replace("'", "\\'").replace(":", "\\:")

    # Main CTA text (larger, bold)
    cta_filter = (
        f"drawtext="
        f"text='{escaped_text}':"
        f"fontcolor=white:fontsize=48:"
        f"{pos_coords}:"
        f"font=Arial:bold=1:"
        f"borderw=2:bordercolor=black:"
        f"enable='between(t,{start_time},{end_time})'"
    )

    # URL/secondary text (smaller, below the main text)
    if url:
        # Adjust y position for URL line below main text
        if position == "bottom":
            url_pos = "x=(w-text_w)/2:y=h-text_h-30"
        elif position == "top":
            url_pos = "x=(w-text_w)/2:y=110"
        else:
            url_pos = "x=(w-text_w)/2:y=(h-text_h)/2+60"

        url_filter = (
            f"drawtext="
            f"text='{escaped_url}':"
            f"fontcolor=#AAAAFF:fontsize=32:"
            f"{url_pos}:"
            f"font=Arial:"
            f"borderw=1:bordercolor=black:"
            f"enable='between(t,{start_time},{end_time})'"
        )
        return f"{cta_filter},{url_filter}"

    return cta_filter


# =============================================================================
# Master Output Configuration & FFmpeg Argument Builder
# =============================================================================

@dataclass
class OutputConfig:
    """
    Master output configuration combining all output options.
    Passed to build_output_ffmpeg_args() to generate the complete
    FFmpeg command argument list.
    """
    # Source video info
    source_width: int = 1920
    source_height: int = 1080
    source_path: str = "input.mp4"
    output_path: str = "output.mp4"

    # Aspect ratio and resolution
    aspect_ratio: str = "9:16"
    resolution: str = "1080p"

    # Background music
    music_enabled: bool = False
    music_path: Optional[str] = None
    music_volume: float = 0.15
    video_duration: float = 60.0

    # Transitions
    transition_effect: str = "none"
    transition_duration: float = 0.5

    # Intro/Outro
    intro_config: Optional[IntroOutroConfig] = None
    outro_config: Optional[IntroOutroConfig] = None

    # Watermark
    watermark_enabled: bool = False
    watermark_logo_path: Optional[str] = None
    watermark_position: str = "bottom-right"
    watermark_opacity: float = 0.5

    # CTA overlay
    cta_enabled: bool = False
    cta_text: str = ""
    cta_url: str = ""
    cta_position: str = "bottom"
    cta_start_time: float = 0.0
    cta_duration: float = 5.0

    # User plan (affects watermark, resolution limits)
    plan: str = "free"


def build_output_ffmpeg_args(config: OutputConfig) -> list[str]:
    """
    Master function that combines all output options into a single FFmpeg
    command argument list.

    This builds the complete set of FFmpeg arguments needed to render a
    short with the specified output configuration (crop, scale, music,
    transitions, watermark, CTA, etc.).

    Args:
        config: OutputConfig with all rendering parameters.

    Returns:
        List of FFmpeg command arguments (excluding 'ffmpeg' itself).
    """
    args: list[str] = []
    video_filters: list[str] = []
    audio_filters: list[str] = []
    input_files: list[str] = ["-i", config.source_path]
    filter_complex_parts: list[str] = []

    # --- Input files ---
    # Add music input if enabled
    if config.music_enabled and config.music_path:
        input_files.extend(["-i", config.music_path])

    # Add watermark input if enabled
    if config.watermark_enabled and config.watermark_logo_path:
        input_files.extend(["-i", config.watermark_logo_path])

    # --- Video filters ---

    # 1. Crop to target aspect ratio
    crop_w, crop_h, crop_x, crop_y = compute_crop_dimensions(
        config.source_width,
        config.source_height,
        config.aspect_ratio,
    )
    video_filters.append(f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}")

    # 2. Scale to target resolution
    out_w, out_h = get_output_dimensions(config.aspect_ratio, config.resolution)
    video_filters.append(f"scale={out_w}:{out_h}")

    # 3. Transition effect (applied as video filter if zoom-type)
    if config.transition_effect == "zoom":
        transition_filter = generate_transition_filter("zoom")
        if transition_filter:
            video_filters.append(transition_filter)

    # 4. CTA overlay (drawtext filter)
    if config.cta_enabled and config.cta_text:
        cta_filter = generate_cta_overlay(
            text=config.cta_text,
            url=config.cta_url,
            position=config.cta_position,
            start_time=config.cta_start_time,
            duration=config.cta_duration,
        )
        video_filters.append(cta_filter)

    # --- Build filter_complex or simple -vf ---

    if config.watermark_enabled and config.watermark_logo_path:
        # Watermark requires filter_complex for multi-input overlay
        wm_filter = generate_watermark_filter(
            logo_path=config.watermark_logo_path,
            position=config.watermark_position,
            opacity=config.watermark_opacity,
        )
        # Prepend video filters to the main stream before overlay
        if video_filters:
            vf_chain = ",".join(video_filters)
            filter_complex_parts.append(f"[0:v]{vf_chain}[v_processed]")
            # Replace [0:v] in watermark filter with processed video
            wm_adjusted = wm_filter.replace("[0:v]", "[v_processed]")
            filter_complex_parts.append(wm_adjusted)
        else:
            filter_complex_parts.append(wm_filter)
    elif video_filters:
        # Simple video filter chain (no multi-input needed)
        vf_chain = ",".join(video_filters)
        filter_complex_parts.append(f"[0:v]{vf_chain}[vout]")

    # --- Audio processing ---

    if config.music_enabled and config.music_path:
        music_mix = generate_music_mix_filter(
            music_path=config.music_path,
            video_duration=config.video_duration,
            volume=config.music_volume,
        )
        filter_complex_parts.append(music_mix)

    # --- Assemble final args ---

    args.extend(input_files)

    if filter_complex_parts:
        full_filter = ";".join(filter_complex_parts)
        args.extend(["-filter_complex", full_filter])

        # Map the output streams
        if config.watermark_enabled and config.watermark_logo_path:
            args.extend(["-map", "[vout]"])
        elif video_filters:
            args.extend(["-map", "[vout]"])

        if config.music_enabled and config.music_path:
            args.extend(["-map", "[aout]"])
        else:
            args.extend(["-map", "0:a?"])
    else:
        # No filters at all - just copy
        args.extend(["-c", "copy"])

    # --- Encoding settings ---
    if filter_complex_parts:
        args.extend([
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
        ])

    # --- Transition between segments (for concat operations) ---
    if config.transition_effect in ("fade", "slide") and config.transition_effect != "none":
        transition_filter = generate_transition_filter(
            config.transition_effect,
            config.transition_duration,
        )
        # Store as metadata — applied during segment concatenation
        args.extend(["-metadata", f"transition={transition_filter}"])

    # --- Output ---
    args.extend([
        "-movflags", "+faststart",
        "-y",
        config.output_path,
    ])

    return args
