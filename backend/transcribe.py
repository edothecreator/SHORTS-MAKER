"""Local Whisper transcription wrapper for the Video-to-Shorts Engine.

This module provides an async wrapper around the locally executed
``openai-whisper`` model. Inference is dispatched to the default thread-pool
executor via ``loop.run_in_executor`` so the FastAPI event loop is never blocked
while the (CPU-bound) transcription runs (Requirement 2.5).

A module-level ``_model_cache`` retains every loaded Whisper model keyed by its
size. The first pipeline run for a given size pays the disk-load cost; every
subsequent run in the same process reuses the cached weights.

Notes
-----
* All transcription happens locally — this module never issues any HTTP call to
  OpenAI or any other remote transcription service (Requirement 12.11).
* Whisper's ``transcribe`` returns a dict whose ``segments`` list contains
  per-segment ``words`` lists; each word is a dict with ``word``, ``start``, and
  ``end`` keys when ``word_timestamps=True`` is set. The raw dict is returned
  unchanged so downstream code (the analyzer in ``analyze.py``) can shape the
  data however it needs (Requirement 2.7).
* The caller (``backend/main.py``) is responsible for resolving the effective
  model size via :func:`backend.main.resolve_whisper_model_size` before invoking
  :func:`run_whisper_transcription`. This module trusts whatever ``model_size``
  it receives and forwards it to ``whisper.load_model``.
"""
from __future__ import annotations

import asyncio
from typing import Any

import whisper

#: Cache of loaded Whisper models keyed by size (e.g. ``"base"``, ``"small"``).
#:
#: Module-level so the second pipeline run in the same process reuses the
#: previously loaded weights rather than reloading from disk. Mutated only by
#: :func:`_load_model`, which is invoked from the executor thread; CPython's
#: dict single-key set/get is atomic so no explicit lock is required.
_model_cache: dict[str, Any] = {}


def _load_model(size: str) -> Any:
    """Return a Whisper model of the requested *size*, loading on first use.

    Parameters
    ----------
    size:
        A Whisper model size string (one of ``tiny``, ``base``, ``small``,
        ``medium``, ``large``). Validation of the value lives upstream in
        :func:`backend.main.resolve_whisper_model_size`; this helper performs no
        validation and forwards the value verbatim to ``whisper.load_model``.

    Returns
    -------
    Any
        The loaded Whisper model instance, suitable for calling ``.transcribe``.
    """
    if size not in _model_cache:
        _model_cache[size] = whisper.load_model(size)
    return _model_cache[size]


async def run_whisper_transcription(
    audio_file_path: str,
    model_size: str = "base",
) -> dict:
    """Transcribe *audio_file_path* with word-level timestamps off the event loop.

    The blocking ``whisper.transcribe`` call is dispatched to the default thread
    pool executor via ``loop.run_in_executor`` so the FastAPI event loop is free
    to keep streaming SSE updates while inference runs (Requirement 2.5).

    The returned dictionary is the raw output produced by ``whisper.transcribe``
    with ``word_timestamps=True``. In particular, ``result["segments"]`` is a
    list whose entries each carry a ``words`` list; every word entry is a dict
    with ``word`` (``str``), ``start`` (``float`` seconds), and ``end``
    (``float`` seconds) (Requirement 2.7).

    Parameters
    ----------
    audio_file_path:
        Filesystem path to the audio file to transcribe (typically the
        16 kHz mono PCM WAV produced by the audio-extraction step of the
        pipeline).
    model_size:
        Whisper model size to use. Defaults to ``"base"``. Callers should pass
        the value already resolved by
        :func:`backend.main.resolve_whisper_model_size` so an invalid
        ``WHISPER_MODEL_SIZE`` falls back to ``"base"`` upstream
        (Requirement 2.6).

    Returns
    -------
    dict
        The raw ``whisper.transcribe`` result dict.
    """
    loop = asyncio.get_running_loop()

    def _inference() -> dict:
        model = _load_model(model_size)
        return model.transcribe(audio_file_path, word_timestamps=True)

    return await loop.run_in_executor(None, _inference)
