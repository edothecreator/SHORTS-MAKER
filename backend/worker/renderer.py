"""Server-side FFmpeg renderer with GPU support and ASS subtitles.

Production Tasks 3.3, 3.4, 3.5, 3.7, 3.10
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Optional

from backend.worker.queue import RenderJob, RENDER_TIMEOUT_SEC

logger = logging.getLogger(__name__)


def _has_nvenc() -> bool:
    try:
        result = os.popen("ffmpeg -hide_banner -encoders 2>/dev/null | grep nvenc").read()
        return "h264_nvenc" in result
    except Exception:
        return False

HAS_GPU = _has_nvenc()


# --- ASS Subtitle Generation (Task 3.5) ---

def to_ass_time(secs: float) -> str:
    clamped = max(0.0, secs)
    h = int(clamped // 3600)
    m = int((clamped % 3600) // 60)
    s = int(clamped % 60)
    cs = round((clamped - int(clamped)) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def generate_ass_subtitles(words: list[dict], segment_start: float, segment_dur: float, style: str) -> str:
    header = "[Script Info]\nTitle: Shorts Subtitle\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nTimer: 100.0000\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Arial Black,64,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,10,10,120,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"

    valid_words = []
    for w in words:
        try:
            start, end, word = float(w["start"]), float(w["end"]), str(w["word"])
            if end <= start or not word:
                continue
            rs = max(0.0, min(start - segment_start, segment_dur))
            re = max(0.0, min(end - segment_start, segment_dur))
            if re <= rs:
                continue
            valid_words.append({"word": word, "start": rs, "end": re})
        except (TypeError, ValueError, KeyError):
            continue

    if not valid_words:
        return header + "\n"

    dialogues = []
    if style == "TikTok-animated":
        for w in valid_words:
            dialogues.append(f"Dialogue: 0,{to_ass_time(w['start'])},{to_ass_time(w['end'])},Default,,0,0,120,,{{\\an2\\c&H00FFFF&}}{w['word']}")
    elif style == "Bold-centered-white":
        for g in _group(valid_words, 4):
            dialogues.append(f"Dialogue: 0,{to_ass_time(g[0]['start'])},{to_ass_time(g[-1]['end'])},Default,,0,0,120,,{{\\an2\\fs72\\b1}}{' '.join(w['word'] for w in g)}")
    else:
        for g in _group(valid_words, 4):
            dialogues.append(f"Dialogue: 0,{to_ass_time(g[0]['start'])},{to_ass_time(g[-1]['end'])},Default,,0,0,60,,{{\\an2\\fs48}}{' '.join(w['word'] for w in g)}")

    return header + "\n" + "\n".join(dialogues) + "\n"


def _group(items, n):
    groups, i = [], 0
    while i < len(items):
        groups.append(items[i:i + min(n, len(items) - i)])
        i += min(n, len(items) - i)
    return groups


# --- FFmpeg Render (Tasks 3.3, 3.4, 3.10) ---

async def render_segment(job: RenderJob, source_path: str, output_dir: str) -> tuple[str, str]:
    """Render one segment. Returns (output_path, thumbnail_path)."""
    words = json.loads(job.words_json)
    dur = max(0.001, job.end_sec - job.start_sec)

    subs_path = os.path.join(output_dir, f"subs_{job.segment_index}.ass")
    with open(subs_path, "w") as f:
        f.write(generate_ass_subtitles(words, job.start_sec, dur, job.subtitle_style))

    output_path = os.path.join(output_dir, f"out_{job.segment_index}.mp4")
    thumb_path = os.path.join(output_dir, f"thumb_{job.segment_index}.jpg")

    title = job.title.replace("'", "\\'").replace(":", "\\:")[:200]
    vf = f"crop=ih*(9/16):ih,subtitles={subs_path},drawtext=text='{title}':x=(w-text_w)/2:y=80:fontsize=52:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=12"

    enc = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23"] if HAS_GPU else ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"]

    args = ["ffmpeg", "-y", "-nostdin", "-ss", str(job.start_sec), "-i", source_path, "-t", str(dur), "-vf", vf, *enc, "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", output_path]

    try:
        proc = await asyncio.create_subprocess_exec(*args, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=RENDER_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        raise RuntimeError(f"Render timeout: segment {job.segment_index} exceeded {RENDER_TIMEOUT_SEC}s")

    if proc.returncode != 0:
        raise RuntimeError(f"Render failed (rc={proc.returncode}): {(stderr or b'').decode()[-500:]}")

    # Thumbnail (Task 3.7)
    try:
        tp = await asyncio.create_subprocess_exec("ffmpeg", "-y", "-nostdin", "-ss", str(dur/2), "-i", output_path, "-vframes", "1", "-vf", "scale=360:-1", thumb_path, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await asyncio.wait_for(tp.communicate(), timeout=30)
    except Exception:
        thumb_path = ""

    try:
        os.unlink(subs_path)
    except OSError:
        pass

    return output_path, thumb_path if os.path.exists(thumb_path) else ""
