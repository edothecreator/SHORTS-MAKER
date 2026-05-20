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
