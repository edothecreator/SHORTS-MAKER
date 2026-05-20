/**
 * ffmpeg.wasm singleton initialization.
 * Task 11.1 — Requirements: 7.1, 7.2, 7.3
 *
 * This module manages a single shared FFmpeg instance for the entire session.
 * - `initFFmpeg()` loads @ffmpeg/ffmpeg (>=0.12) with @ffmpeg/core@0.12.6
 *   UMD assets via `toBlobURL` from https://unpkg.com.
 * - Wrapped in Promise.race with a 30s timeout that rejects with
 *   Error("ffmpeg load timeout (30s)").
 * - On failure, resets `_initPromise = null` so a subsequent call retries.
 * - Re-uses the initialized instance on every subsequent call.
 */

import { FFmpeg } from "@ffmpeg/ffmpeg";
import { toBlobURL } from "@ffmpeg/util";

// Module-level singleton state.
let _ffmpeg: FFmpeg | null = null;
let _initPromise: Promise<FFmpeg> | null = null;

/**
 * Whether the source video has been written to the WASM filesystem
 * in this session. Reset only on page reload.
 */
export let _sourceWritten = false;

export function resetSourceWritten(): void {
  _sourceWritten = false;
}

const CORE_VERSION = "0.12.6";
const BASE_URL = `https://unpkg.com/@ffmpeg/core@${CORE_VERSION}/dist/umd`;
const LOAD_TIMEOUT_MS = 30_000;

/**
 * Initialize or return the existing FFmpeg instance.
 *
 * On first call, loads the WASM core from unpkg CDN with a 30s timeout.
 * On subsequent calls, returns the cached instance immediately.
 * On failure, clears the cached promise so the next call retries.
 */
export async function initFFmpeg(): Promise<FFmpeg> {
  // Already initialized — return immediately.
  if (_ffmpeg) return _ffmpeg;

  // Already loading — return the in-flight promise.
  if (_initPromise) return _initPromise;

  _initPromise = (async () => {
    const ffmpeg = new FFmpeg();

    const loadPromise = ffmpeg.load({
      coreURL: await toBlobURL(`${BASE_URL}/ffmpeg-core.js`, "text/javascript"),
      wasmURL: await toBlobURL(
        `${BASE_URL}/ffmpeg-core.wasm`,
        "application/wasm"
      ),
    });

    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(
        () => reject(new Error("ffmpeg load timeout (30s)")),
        LOAD_TIMEOUT_MS
      );
    });

    await Promise.race([loadPromise, timeoutPromise]);

    _ffmpeg = ffmpeg;
    return ffmpeg;
  })();

  try {
    return await _initPromise;
  } catch (err) {
    // Reset so next call retries rather than returning a rejected promise.
    _initPromise = null;
    _ffmpeg = null;
    throw err;
  }
}


// ---------------------------------------------------------------------------
// ASS subtitle generation
// ---------------------------------------------------------------------------
// Task 11.2 — Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.9, 6.10

import type { WordTimestamp, SubtitleStyle } from "../types";

export interface AssResult {
  ass: string;
  empty: boolean;
  errors: string[];
}

/**
 * Convert seconds to ASS timestamp format: H:MM:SS.cs (two-digit centiseconds).
 */
export function toAssTime(secs: number): string {
  const clamped = Math.max(0, secs);
  const h = Math.floor(clamped / 3600);
  const m = Math.floor((clamped % 3600) / 60);
  const s = Math.floor(clamped % 60);
  const cs = Math.round((clamped - Math.floor(clamped)) * 100);
  return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(cs).padStart(2, "0")}`;
}

/**
 * Generate an ASS subtitle file for a single short segment.
 *
 * - Converts each word's start/end to clip-relative time by subtracting
 *   segmentStartSec and clamping into [0, segmentDurSec].
 * - Filters out words with missing/non-numeric/inverted timestamps.
 * - Supports three styles: TikTok-animated, Bold-centered-white, Minimal-bottom.
 * - When zero valid words remain, returns a syntactically complete ASS with
 *   empty [Events] and `empty: true`.
 */
export function generateAssSubtitles(
  words: WordTimestamp[],
  segmentStartSec: number,
  segmentDurSec: number,
  style: SubtitleStyle
): AssResult {
  const errors: string[] = [];

  // --- Filter and convert to clip-relative time ---
  const validWords: { word: string; start: number; end: number }[] = [];

  for (let i = 0; i < words.length; i++) {
    const w = words[i];
    if (
      w == null ||
      typeof w.start !== "number" ||
      typeof w.end !== "number" ||
      !isFinite(w.start) ||
      !isFinite(w.end) ||
      typeof w.word !== "string" ||
      w.end <= w.start
    ) {
      errors.push(`Word at index ${i} skipped: invalid timestamps`);
      continue;
    }

    // Convert to clip-relative and clamp to [0, segmentDurSec].
    const relStart = Math.max(0, Math.min(w.start - segmentStartSec, segmentDurSec));
    const relEnd = Math.max(0, Math.min(w.end - segmentStartSec, segmentDurSec));

    if (relEnd <= relStart) {
      errors.push(`Word at index ${i} skipped: zero duration after clamping`);
      continue;
    }

    validWords.push({ word: w.word, start: relStart, end: relEnd });
  }

  // --- Build ASS header ---
  const header = `[Script Info]
Title: Shorts Subtitle
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
Timer: 100.0000

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,64,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,10,10,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text`;

  // If no valid words, return empty ASS.
  if (validWords.length === 0) {
    return { ass: header + "\n", empty: true, errors };
  }

  // --- Build dialogue lines based on style ---
  let dialogues: string[] = [];

  if (style === "TikTok-animated") {
    // One Dialogue per word with override {\an2\c&H00FFFF&}
    for (const w of validWords) {
      const start = toAssTime(w.start);
      const end = toAssTime(w.end);
      dialogues.push(
        `Dialogue: 0,${start},${end},Default,,0,0,120,,{\\an2\\c&H00FFFF&}${w.word}`
      );
    }
  } else if (style === "Bold-centered-white") {
    // Group 3-4 words per line, font 72, MarginV 120
    const groups = groupWords(validWords, 4);
    for (const group of groups) {
      const start = toAssTime(group[0].start);
      const end = toAssTime(group[group.length - 1].end);
      const text = group.map((w) => w.word).join(" ");
      dialogues.push(
        `Dialogue: 0,${start},${end},Default,,0,0,120,,{\\an2\\fs72\\b1}${text}`
      );
    }
  } else {
    // Minimal-bottom: group 3-4 words per line, font 48, MarginV 60
    const groups = groupWords(validWords, 4);
    for (const group of groups) {
      const start = toAssTime(group[0].start);
      const end = toAssTime(group[group.length - 1].end);
      const text = group.map((w) => w.word).join(" ");
      dialogues.push(
        `Dialogue: 0,${start},${end},Default,,0,0,60,,{\\an2\\fs48}${text}`
      );
    }
  }

  const ass = header + "\n" + dialogues.join("\n") + "\n";
  return { ass, empty: false, errors };
}

/**
 * Group words into chunks of up to `maxPerGroup` (3-4 words per line).
 * Tries to keep groups balanced (at least 3 per group when possible).
 */
function groupWords<T>(items: T[], maxPerGroup: number): T[][] {
  const groups: T[][] = [];
  let i = 0;
  while (i < items.length) {
    const remaining = items.length - i;
    // If remaining would leave a lonely 1-2 words in the next group,
    // take 3 instead of 4 to balance.
    const take = remaining <= maxPerGroup ? remaining : Math.min(maxPerGroup, remaining);
    groups.push(items.slice(i, i + take));
    i += take;
  }
  return groups;
}
