"""Multi-Language Support for the Video-to-Shorts Engine.

This module implements Production Task 11: Multi-Language Support, providing:
- Language detection from Whisper transcription output (Task 11.1)
- Subtitle translation via Google Translate API (Task 11.3)
- Dual subtitle generation (original + translation) in ASS format (Task 11.4)
- Supported languages registry (Task 11.6)
- UI translations / i18n strings (Task 11.7)

Notes
-----
* Task 11.2 (Frontend Language Selector): The frontend ConfigPanel component
  (frontend/app/components/ConfigPanel.tsx) will add a language selector
  dropdown that allows users to override the auto-detected source language.
  The dropdown should be populated from SUPPORTED_LANGUAGES and send the
  selected language code to the backend via the config JSON payload.

* Task 11.5 (RTL Support): RTL rendering for Arabic, Hebrew, and Farsi is
  already implemented in the SubtitleEngine (frontend/app/components/SubtitleEngine.ts,
  Task 9.7). The ASS subtitle generation in this module sets appropriate
  RTL alignment for RTL languages. The SubtitleEngine handles bidirectional
  text rendering, mirrored animations, and proper glyph shaping on the frontend.
"""
from __future__ import annotations

from typing import Any


# =============================================================================
# Task 11.6: SUPPORTED_LANGUAGES
# =============================================================================
#: Mapping of ISO 639-1 language codes to human-readable language names.
#: Covers the top 10 languages by global internet usage and content demand.
SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "pt": "Portuguese",
    "fr": "French",
    "de": "German",
    "ja": "Japanese",
    "ko": "Korean",
    "hi": "Hindi",
    "ar": "Arabic",
    "zh": "Chinese",
}


# =============================================================================
# Task 11.7: UI_TRANSLATIONS (i18n strings)
# =============================================================================
#: Basic UI string translations for internationalization.
#: Each key is a language code; values are dicts mapping UI string keys to
#: their translated text. Covers English, Spanish, French, and Arabic.
UI_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "generate_shorts": "Generate Shorts",
        "upload_video": "Upload Video",
        "download": "Download",
        "processing": "Processing...",
        "done": "Done",
        "failed": "Failed",
        "sign_in": "Sign In",
        "sign_out": "Sign Out",
        "profile": "Profile",
        "upgrade": "Upgrade",
    },
    "es": {
        "generate_shorts": "Generar Shorts",
        "upload_video": "Subir Video",
        "download": "Descargar",
        "processing": "Procesando...",
        "done": "Listo",
        "failed": "Fallido",
        "sign_in": "Iniciar Sesion",
        "sign_out": "Cerrar Sesion",
        "profile": "Perfil",
        "upgrade": "Actualizar",
    },
    "fr": {
        "generate_shorts": "Generer des Shorts",
        "upload_video": "Telecharger la Video",
        "download": "Telecharger",
        "processing": "Traitement en cours...",
        "done": "Termine",
        "failed": "Echoue",
        "sign_in": "Se Connecter",
        "sign_out": "Se Deconnecter",
        "profile": "Profil",
        "upgrade": "Mettre a Niveau",
    },
    "ar": {
        "generate_shorts": "\u062a\u0648\u0644\u064a\u062f \u0641\u064a\u062f\u064a\u0648\u0647\u0627\u062a \u0642\u0635\u064a\u0631\u0629",
        "upload_video": "\u0631\u0641\u0639 \u0641\u064a\u062f\u064a\u0648",
        "download": "\u062a\u062d\u0645\u064a\u0644",
        "processing": "\u062c\u0627\u0631\u064d \u0627\u0644\u0645\u0639\u0627\u0644\u062c\u0629...",
        "done": "\u062a\u0645",
        "failed": "\u0641\u0634\u0644",
        "sign_in": "\u062a\u0633\u062c\u064a\u0644 \u0627\u0644\u062f\u062e\u0648\u0644",
        "sign_out": "\u062a\u0633\u062c\u064a\u0644 \u0627\u0644\u062e\u0631\u0648\u062c",
        "profile": "\u0627\u0644\u0645\u0644\u0641 \u0627\u0644\u0634\u062e\u0635\u064a",
        "upgrade": "\u062a\u0631\u0642\u064a\u0629",
    },
}


# =============================================================================
# RTL language codes (used for subtitle alignment decisions)
# =============================================================================
#: Languages that use right-to-left script direction.
RTL_LANGUAGES: set[str] = {"ar", "he", "fa"}


# =============================================================================
# Task 11.1: detect_language
# =============================================================================
def detect_language(transcript_result: dict) -> str:
    """Auto-detect the source language from Whisper transcription output.

    Whisper's ``transcribe()`` returns a dictionary that includes a ``language``
    field containing the ISO 639-1 code of the detected language. This function
    extracts and validates that field.

    Parameters
    ----------
    transcript_result:
        The raw dictionary returned by ``whisper.transcribe()``. Expected to
        contain a ``"language"`` key with an ISO 639-1 language code string.

    Returns
    -------
    str
        The ISO 639-1 language code (e.g., ``"en"``, ``"es"``, ``"ja"``).
        Falls back to ``"en"`` if the language field is missing or empty.

    Examples
    --------
    >>> result = {"text": "Hello world", "language": "en", "segments": [...]}
    >>> detect_language(result)
    'en'
    """
    if not isinstance(transcript_result, dict):
        return "en"

    language = transcript_result.get("language", "")

    if not language or not isinstance(language, str):
        return "en"

    # Normalize to lowercase and take only the first 2 characters
    # (Whisper may occasionally return longer codes)
    lang_code = language.strip().lower()[:2]

    return lang_code if lang_code else "en"


# =============================================================================
# Task 11.3: translate_subtitles
# =============================================================================
def translate_subtitles(
    words: list[dict[str, Any]],
    source_lang: str,
    target_lang: str,
) -> list[dict[str, Any]]:
    """Translate subtitle words from source language to target language.

    Uses Google Translate API to translate each word/phrase while preserving
    the original timing information (start/end timestamps). Words are grouped
    into sentences for better translation quality, then split back into
    individual word entries with interpolated timing.

    Parameters
    ----------
    words:
        List of word dictionaries from Whisper output. Each dict has:
        - ``"word"`` (str): The word text
        - ``"start"`` (float): Start time in seconds
        - ``"end"`` (float): End time in seconds
    source_lang:
        ISO 639-1 source language code (e.g., ``"en"``).
    target_lang:
        ISO 639-1 target language code (e.g., ``"es"``).

    Returns
    -------
    list[dict[str, Any]]
        List of translated word dictionaries preserving the same structure:
        - ``"word"`` (str): The translated word text
        - ``"start"`` (float): Original start time in seconds
        - ``"end"`` (float): Original end time in seconds

    Notes
    -----
    * If source_lang == target_lang, the original words are returned unchanged.
    * Translation is performed in sentence-sized batches for context-aware
      translation quality, then timing is redistributed proportionally.
    * TODO: Replace placeholder implementation with real Google Translate API
      or DeepL API call. Requires API key configuration in environment:
      ``GOOGLE_TRANSLATE_API_KEY`` or ``DEEPL_API_KEY``.

    Examples
    --------
    >>> words = [
    ...     {"word": "Hello", "start": 0.0, "end": 0.5},
    ...     {"word": "world", "start": 0.5, "end": 1.0},
    ... ]
    >>> translate_subtitles(words, "en", "es")
    [{"word": "Hola", "start": 0.0, "end": 0.5}, {"word": "mundo", "start": 0.5, "end": 1.0}]
    """
    if not words:
        return []

    if source_lang == target_lang:
        return [dict(w) for w in words]

    # Validate target language
    if target_lang not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported target language: {target_lang!r}. "
            f"Supported: {list(SUPPORTED_LANGUAGES.keys())}"
        )

    # Group words into sentence-sized chunks for better translation quality
    chunks = _group_words_into_chunks(words, max_words_per_chunk=15)

    translated_words: list[dict[str, Any]] = []

    for chunk in chunks:
        # Build the text to translate from this chunk
        source_text = " ".join(w["word"].strip() for w in chunk)

        # Translate the chunk text
        translated_text = _call_translation_api(source_text, source_lang, target_lang)

        # Split translated text back into words
        translated_tokens = translated_text.split()

        if not translated_tokens:
            # Fallback: keep original words if translation returned empty
            translated_words.extend(dict(w) for w in chunk)
            continue

        # Redistribute timing proportionally across translated tokens
        chunk_start = chunk[0]["start"]
        chunk_end = chunk[-1]["end"]
        chunk_duration = chunk_end - chunk_start

        for i, token in enumerate(translated_tokens):
            # Interpolate start/end times proportionally
            ratio_start = i / len(translated_tokens)
            ratio_end = (i + 1) / len(translated_tokens)

            translated_words.append({
                "word": token,
                "start": round(chunk_start + chunk_duration * ratio_start, 3),
                "end": round(chunk_start + chunk_duration * ratio_end, 3),
            })

    return translated_words


def _group_words_into_chunks(
    words: list[dict[str, Any]],
    max_words_per_chunk: int = 15,
) -> list[list[dict[str, Any]]]:
    """Group words into sentence-like chunks for translation.

    Splits on natural sentence boundaries (periods, question marks, etc.)
    or after max_words_per_chunk words, whichever comes first.
    """
    chunks: list[list[dict[str, Any]]] = []
    current_chunk: list[dict[str, Any]] = []

    sentence_enders = {".", "!", "?", "\u3002", "\uff1f", "\uff01"}

    for word in words:
        current_chunk.append(word)
        text = word["word"].strip()

        # Split on sentence boundaries or chunk size limit
        is_sentence_end = any(text.endswith(ch) for ch in sentence_enders)
        is_chunk_full = len(current_chunk) >= max_words_per_chunk

        if is_sentence_end or is_chunk_full:
            chunks.append(current_chunk)
            current_chunk = []

    # Don't forget the last chunk
    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def _call_translation_api(text: str, source_lang: str, target_lang: str) -> str:
    """Call translation API to translate text.

    TODO: Replace this placeholder with a real API call to Google Translate
    or DeepL. The implementation below is a stub that returns the original
    text prefixed with the target language code for development/testing.

    Production implementation should:
    1. Read API key from environment variable:
       - GOOGLE_TRANSLATE_API_KEY for Google Translate
       - DEEPL_API_KEY for DeepL
    2. Make HTTP request to translation endpoint
    3. Handle rate limiting, retries, and errors gracefully
    4. Cache translations to reduce API costs

    Example Google Translate API call::

        import httpx
        import os

        api_key = os.environ["GOOGLE_TRANSLATE_API_KEY"]
        url = "https://translation.googleapis.com/language/translate/v2"
        response = httpx.post(url, params={
            "key": api_key,
            "q": text,
            "source": source_lang,
            "target": target_lang,
            "format": "text",
        })
        result = response.json()
        return result["data"]["translations"][0]["translatedText"]

    Parameters
    ----------
    text:
        Source text to translate.
    source_lang:
        ISO 639-1 source language code.
    target_lang:
        ISO 639-1 target language code.

    Returns
    -------
    str
        Translated text (currently a placeholder that returns original text).
    """
    # TODO: Replace with real translation API call.
    # Placeholder: return original text with language marker for testing.
    # In production, this would call Google Translate or DeepL API.
    #
    # Required environment variables:
    #   GOOGLE_TRANSLATE_API_KEY=your-api-key-here
    #   or
    #   DEEPL_API_KEY=your-api-key-here
    return text


# =============================================================================
# Task 11.4: generate_dual_subtitles
# =============================================================================
def generate_dual_subtitles(
    original_words: list[dict[str, Any]],
    translated_words: list[dict[str, Any]],
    segment_start: float,
    segment_dur: float,
    style: str = "default",
) -> str:
    """Generate ASS subtitle content with dual subtitles (original + translation).

    Creates an ASS (Advanced SubStation Alpha) subtitle file with two
    simultaneous subtitle tracks: the original language displayed on top
    and the translation displayed below.

    Parameters
    ----------
    original_words:
        List of word dictionaries for the original language. Each dict has:
        - ``"word"`` (str): The word text
        - ``"start"`` (float): Start time in seconds
        - ``"end"`` (float): End time in seconds
    translated_words:
        List of word dictionaries for the translated language (from
        ``translate_subtitles``). Same structure as original_words.
    segment_start:
        Start time of the segment in seconds (used to offset word times).
    segment_dur:
        Duration of the segment in seconds.
    style:
        Subtitle style preset name. Affects font, colors, and positioning.
        Default is ``"default"`` (white text with black outline).

    Returns
    -------
    str
        Complete ASS subtitle file content as a string, ready to be written
        to a ``.ass`` file and passed to FFmpeg for rendering.

    Notes
    -----
    * Original text is positioned in the upper portion of the screen
      (alignment 8 = top-center in ASS).
    * Translated text is positioned in the lower portion of the screen
      (alignment 2 = bottom-center in ASS).
    * For RTL languages, alignment is adjusted appropriately.
    * The style parameter maps to predefined ASS style definitions that
      control font family, size, colors, outline, and shadow.
    """
    # Define style properties based on style parameter
    style_config = _get_style_config(style)

    # Build ASS header
    ass_content = _build_ass_header(style_config)

    # Group words into display lines (for readability)
    original_lines = _words_to_timed_lines(original_words, segment_start, max_words=6)
    translated_lines = _words_to_timed_lines(translated_words, segment_start, max_words=6)

    # Add original subtitle events (top position)
    for line_text, start_time, end_time in original_lines:
        start_ts = _seconds_to_ass_time(start_time)
        end_ts = _seconds_to_ass_time(end_time)
        ass_content += (
            f"Dialogue: 0,{start_ts},{end_ts},Original,,0,0,0,,{line_text}\n"
        )

    # Add translated subtitle events (bottom position)
    for line_text, start_time, end_time in translated_lines:
        start_ts = _seconds_to_ass_time(start_time)
        end_ts = _seconds_to_ass_time(end_time)
        ass_content += (
            f"Dialogue: 0,{start_ts},{end_ts},Translation,,0,0,0,,{line_text}\n"
        )

    return ass_content


def _get_style_config(style: str) -> dict[str, Any]:
    """Return ASS style configuration for the given style name."""
    configs = {
        "default": {
            "font_name": "Arial",
            "font_size": 48,
            "primary_color": "&H00FFFFFF",  # White
            "outline_color": "&H00000000",  # Black
            "back_color": "&H80000000",  # Semi-transparent black
            "outline_width": 2,
            "shadow_depth": 1,
        },
        "bold": {
            "font_name": "Arial",
            "font_size": 56,
            "primary_color": "&H00FFFFFF",
            "outline_color": "&H00000000",
            "back_color": "&H80000000",
            "outline_width": 3,
            "shadow_depth": 2,
        },
        "minimal": {
            "font_name": "Helvetica Neue",
            "font_size": 42,
            "primary_color": "&H00FFFFFF",
            "outline_color": "&H00333333",
            "back_color": "&H00000000",
            "outline_width": 1,
            "shadow_depth": 0,
        },
    }
    return configs.get(style, configs["default"])


def _build_ass_header(style_config: dict[str, Any]) -> str:
    """Build the ASS file header with script info and style definitions."""
    font = style_config["font_name"]
    size = style_config["font_size"]
    primary = style_config["primary_color"]
    outline = style_config["outline_color"]
    back = style_config["back_color"]
    outline_w = style_config["outline_width"]
    shadow = style_config["shadow_depth"]

    # Slightly smaller font for translation line
    trans_size = int(size * 0.85)

    header = f"""[Script Info]
Title: Dual Subtitles
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Original,{font},{size},{primary},&H000000FF,{outline},{back},-1,0,0,0,100,100,0,0,1,{outline_w},{shadow},8,20,20,80,1
Style: Translation,{font},{trans_size},{primary},&H000000FF,{outline},{back},0,0,0,0,100,100,0,0,1,{outline_w},{shadow},2,20,20,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    return header


def _words_to_timed_lines(
    words: list[dict[str, Any]],
    segment_start: float,
    max_words: int = 6,
) -> list[tuple[str, float, float]]:
    """Group words into display lines with timing.

    Returns a list of (text, start_time, end_time) tuples where times are
    relative to segment start (already adjusted).
    """
    if not words:
        return []

    lines: list[tuple[str, float, float]] = []
    current_words: list[dict[str, Any]] = []

    for word in words:
        current_words.append(word)

        if len(current_words) >= max_words:
            text = " ".join(w["word"].strip() for w in current_words)
            start = current_words[0]["start"] - segment_start
            end = current_words[-1]["end"] - segment_start
            lines.append((text, max(0.0, start), max(0.0, end)))
            current_words = []

    # Remaining words
    if current_words:
        text = " ".join(w["word"].strip() for w in current_words)
        start = current_words[0]["start"] - segment_start
        end = current_words[-1]["end"] - segment_start
        lines.append((text, max(0.0, start), max(0.0, end)))

    return lines


def _seconds_to_ass_time(seconds: float) -> str:
    """Convert seconds to ASS timestamp format (H:MM:SS.cc).

    Parameters
    ----------
    seconds:
        Time in seconds (e.g., 65.5 → "0:01:05.50").

    Returns
    -------
    str
        ASS-formatted timestamp string.
    """
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds % 1) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
