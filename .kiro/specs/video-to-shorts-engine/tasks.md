# Implementation Plan: Video-to-Shorts Engine

## Overview

This plan converts the Hybrid Local-First design into a sequence of incremental coding tasks. Each task builds on the previous ones and ends with everything wired together — no orphaned modules. The repository is organized as a `backend/` FastAPI service and a `frontend/` Next.js 14 App Router project, plus a top-level `README.md`. Backend tests live under `backend/tests/` (the `backend/` root is constrained by Requirement 12.1 to exactly five files) and frontend tests live alongside their components in `__tests__/` folders.

The implementation order is: scaffold the repository, build the backend pipeline bottom-up (transcribe → analyze → main + SSE + cleanup), scaffold the frontend with COOP/COEP, build each frontend component (DropZone, ConfigPanel, ProgressTracker, useFFmpegRenderer, ResultsGrid), then wire the orchestrator page that drives upload → SSE → render → results. Property-based tests target the three properties most amenable to PBT: ASS round-trip, ASS time clamping, and segment non-overlap.

## Tasks

- [x] 1. Repository and backend scaffolding
  - [x] 1.1 Create top-level structure and backend manifest files
    - Create `backend/` with empty `main.py`, `transcribe.py`, `analyze.py`
    - Create `backend/requirements.txt` listing exactly: `fastapi`, `uvicorn`, `python-multipart`, `python-dotenv`, `openai-whisper`, `google-genai`, `pydantic`
    - Create `backend/.env.example` with `GOOGLE_API_KEY=` and `WHISPER_MODEL_SIZE=base`
    - Create `backend/tests/` directory with empty `__init__.py`
    - Create `frontend/` directory and `README.md` placeholder at repo root
    - _Requirements: 12.1, 12.3, 12.4, 12.6, 12.7, 12.14_

  - [x] 1.2 Implement environment loading and startup validation in `backend/main.py`
    - Load `.env` via `python-dotenv` at module import
    - Validate `GOOGLE_API_KEY` non-empty and `WHISPER_MODEL_SIZE` non-empty at startup; abort within 5 seconds otherwise
    - Resolve effective Whisper model size, falling back to `base` with a recorded warning when value not in `{tiny, base, small, medium, large}`
    - _Requirements: 12.6, 12.13, 2.6_

- [x] 2. Backend transcription module
  - [x] 2.1 Implement `backend/transcribe.py`
    - Add module-level `_model_cache: dict[str, Any]` and `_load_model(size)` helper
    - Implement `async def run_whisper_transcription(audio_file_path, model_size="base")` using `loop.run_in_executor` with `word_timestamps=True`
    - Return raw whisper transcription dict whose `segments[*].words[*]` carry `word`, `start`, `end`
    - _Requirements: 2.5, 2.6, 2.7, 12.11_

  - [ ]* 2.2 Write unit tests for `backend/transcribe.py`
    - Test that `_load_model` caches by size and returns the same instance on repeat calls (mock `whisper.load_model`)
    - Test that `run_whisper_transcription` runs the inference off the event loop via `loop.run_in_executor`
    - _Requirements: 2.5_

- [x] 3. Backend analyzer module
  - [x] 3.1 Define Pydantic schema in `backend/analyze.py`
    - Implement `WordTimestamp(word: str[1..100], start: float>=0, end: float>=0)`
    - Implement `ShortSegment(start_sec, end_sec>0, title: str[1..50], hook: str[1..200], reason: str[1..500], words: list[WordTimestamp])`
    - Implement `ShortsAnalysisResult(segments: list[ShortSegment][1..50])`
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 3.2 Implement `_build_prompt` in `backend/analyze.py`
    - Compose role + task + hard rules sections covering duration bound, no-overlap, hook = first 5 words, title rules (1..50, no `#`), `words` containment + ascending order
    - Add style-tone block for `Funny` / `Educational` / `Motivational` / `Highlights` / `Story-driven`, and a `Custom` branch that embeds the literal user text truncated to 1000 characters
    - Append a compact JSON transcript dump (`{"w": word, "s": start, "e": end}`) and instruct Gemini to return exactly `shorts_count` segments
    - _Requirements: 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10_

  - [x] 3.3 Implement Gemini call with retry in `backend/analyze.py`
    - Build `client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])` and call `models.generate_content` with `response_mime_type="application/json"` and `response_schema=ShortsAnalysisResult`
    - Apply per-call timeout of 120 seconds
    - Wrap the call in `_call_with_retry(fn, attempts=3, backoff=2.0)` with categorized error messages on final failure
    - Raise `ValueError(f"Gemini parse failed: {response.text!r}")` when `response.parsed is None`
    - _Requirements: 2.9, 2.10, 2.11, 2.12, 5.11, 5.12, 5.14_

  - [x] 3.4 Implement `_validate_result` post-parse validator in `backend/analyze.py`
    - Reject when `len(segments) != shorts_count`
    - Sort by `start_sec` and reject when any pair overlaps (`a.end_sec > b.start_sec`)
    - Reject when any segment has non-positive duration or `end_sec - start_sec > duration_per_short`
    - Wire `analyze_video_transcript(transcript, style_tone, max_count, target_duration)` async entry point that builds prompt → calls Gemini → validates → returns `ShortsAnalysisResult`
    - _Requirements: 5.13, 2.13_

  - [x]* 3.5 Write unit tests for `backend/analyze.py`
    - Parametrize over the 6 `style_tone` values asserting the prompt embeds the expected style profile, and that `Custom` text longer than 1000 chars is truncated
    - Assert `_validate_result` raises on count mismatch, overlap, duration overrun, and non-positive duration
    - Assert `response.parsed is None` raises `ValueError` with the raw text included
    - _Requirements: 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 5.12, 5.13, 2.11_

  - [x]* 3.6 Write property-based test for segment non-overlap [PBT]
    - **Property 3: Segment non-overlap**
    - **Validates: Requirements 5.8, 5.13**
    - Use `hypothesis` to generate random `ShortsAnalysisResult` candidates with arbitrary `(start_sec, end_sec)` values; assert that whenever `_validate_result` accepts a result, sorting by `start_sec` yields `segments[i].end_sec <= segments[i+1].start_sec`, and whenever any pair overlaps it raises `ValueError`

- [ ] 4. Backend FastAPI app, pipeline, SSE, and cleanup
  - [x] 4.1 Configure FastAPI app, CORS, and lifespan in `backend/main.py`
    - Instantiate `app = FastAPI()`
    - Add `CORSMiddleware` with `allow_origins=["http://localhost:3000"]` only
    - Register the in-process `task_registry: dict[str, dict]`
    - Register a startup hook that launches the cleanup scanner task
    - _Requirements: 4.9, 12.12_

  - [x] 4.2 Implement `POST /api/process-video` upload + workspace endpoint in `backend/main.py`
    - Manually validate `shorts_count` (int, 1..10), `duration_per_short` (∈ {15, 30, 60}), `style_tone` (1..500 trimmed) returning HTTP 422 without registering or creating a workspace
    - Reject missing/zero-byte `video_file` with HTTP 422
    - Generate `task_id = str(uuid4())` and `workspace = Path("/tmp/shorts_workspace")/task_id` with `mkdir(parents=True, exist_ok=False)`
    - Stream upload to `workspace/f"input.{ext}"` in 1 MiB chunks; on `OSError` delete partial file and return HTTP 500 without registering
    - Register `task_registry[task_id]` with `step="Uploading"`, `progress=10`, `created_at=time.time()`, and stash `_style_tone`, `_shorts_count`, `_duration_per_short`
    - Schedule `BackgroundTasks` for `run_processing_pipeline(task_id)` and `cleanup_task_directory(task_id, 3600)`
    - Respond `{"taskId": task_id}`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.11, 1.12_

  - [x] 4.3 Implement `_extract_audio` async subprocess wrapper in `backend/main.py`
    - Invoke `ffmpeg -y -nostdin -i {input} -vn -acodec pcm_s16le -ac 1 -ar 16000 {audio.wav}` via `asyncio.create_subprocess_exec`
    - Wrap in `asyncio.wait_for(..., timeout=600)`
    - Convert non-zero rc, `TimeoutError`, and `FileNotFoundError` into a `RuntimeError("Audio extraction failed: ...")` with the underlying cause
    - _Requirements: 2.2, 2.3_

  - [x] 4.4 Implement `run_processing_pipeline` in `backend/main.py`
    - Set `step="Extracting Audio"`, `progress=25`; await `_extract_audio`
    - Set `step="Transcribing"`, `progress=60`; await `run_whisper_transcription` with the resolved Whisper model size
    - Set `step="Analyzing Highlights"`, `progress=75`; await `analyze_video_transcript` with stashed form fields
    - Set `step="Done"`, `progress=100`, `data=result.model_dump()`
    - Wrap pipeline in `try/except/finally`: on exception, set `step="Failed"` with `error=str(e)`; in `finally`, await `_safe_delete(input_path)` and `_safe_delete(audio_path)`
    - _Requirements: 2.1, 2.4, 2.8, 2.13, 2.14, 3.1, 3.2_

  - [x] 4.5 Implement `_safe_delete` helper in `backend/main.py`
    - Try `path.unlink(missing_ok=True)` up to 3 times with 1 second between attempts on `OSError`
    - On final failure, set `cleanup_warning` field on the registry entry without changing `step`
    - _Requirements: 3.6_

  - [x] 4.6 Implement `GET /api/stream/{task_id}` SSE endpoint in `backend/main.py`
    - Return HTTP 404 when `task_id` not in `task_registry`
    - Return `StreamingResponse(media_type="text/event-stream")` with `Cache-Control: no-cache`, `Connection: keep-alive`
    - Emit initial snapshot within 1 second; emit subsequent messages on a 1 s ± 200 ms cadence
    - Track `last_step_change`; emit final stall message and close after 600 s of no `step` advance
    - On `step ∈ {"Done", "Failed"}`, emit a final message and close within 1 additional second
    - Stop emitting and release resources within 5 seconds of client disconnect
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [x] 4.7 Implement `cleanup_task_directory` and `_cleanup_scanner` in `backend/main.py`
    - `cleanup_task_directory(task_id, delay)`: `await asyncio.sleep(delay)` then `shutil.rmtree(workspace, ignore_errors=True)`
    - `_cleanup_scanner()`: launched at startup; loop forever sleeping 300 s and removing any subdirectory of `/tmp/shorts_workspace/` older than 3600 s
    - _Requirements: 3.3, 3.4, 3.5, 3.7_

  - [ ]* 4.8 Write FastAPI TestClient unit tests for `backend/main.py`
    - Happy path: monkeypatch the pipeline, POST returns 200 with `{"taskId": <uuid>}`
    - 422 cases: invalid `shorts_count` (0, 11, "abc"), invalid `duration_per_short` (10, 45), empty/oversized `style_tone`, missing/zero-byte `video_file`
    - 500 case: simulate `OSError` during chunked write and assert no registry entry, no `BackgroundTasks` scheduled, partial file removed
    - SSE: 404 for unknown `task_id`; on `Done`, the stream emits the initial snapshot, the result `data`, and closes within 1 second
    - _Requirements: 1.5, 1.6, 1.7, 1.8, 1.11, 1.12, 4.1, 4.2, 4.4, 4.5, 4.6_

  - [ ]* 4.9 Write pipeline integration test
    - Mock Whisper to return a fixed transcript and Gemini client to return a fixed `ShortsAnalysisResult`
    - Drive a full upload-to-Done flow against a tiny synthetic `test.mp4` and assert the registry transitions through `Uploading → Extracting Audio → Transcribing → Analyzing Highlights → Done` with the exact progress values
    - Assert `/tmp/shorts_workspace/{task_id}/` contains no `input.*` and no `audio.wav` within 10 seconds of `Done`
    - _Requirements: 2.1, 2.4, 2.8, 2.13, 3.1, 3.2, 13.4, 13.6_

- [ ] 5. Backend checkpoint
  - Ensure all backend tests pass, ask the user if questions arise.

- [ ] 6. Frontend scaffolding
  - [ ] 6.1 Create frontend manifest files
    - `frontend/package.json` with React + Next.js 14, and runtime deps limited to `@ffmpeg/ffmpeg` (>=0.12), `@ffmpeg/util`, `jszip`, `tailwindcss`, `typescript`
    - `frontend/tsconfig.json` for Next.js App Router
    - `frontend/tailwind.config.js` and `frontend/postcss.config.js` configured for `app/**/*.{ts,tsx}`
    - _Requirements: 12.2, 12.5, 12.8_

  - [ ] 6.2 Implement `frontend/next.config.js` with cross-origin isolation
    - Export an `async headers()` function that applies `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: credentialless` to `source: "/(.*)"`
    - _Requirements: 10.1, 10.2_

  - [ ] 6.3 Implement `frontend/app/globals.css`
    - Define CSS variables `--bg`, `--surface`, `--border`, `--accent`, `--accent-hover`, `--text`, `--muted`, `--success`, `--error` with the exact hex values from Requirement 11.1
    - Apply `--bg` as page background and `--text` as default foreground via `body { background: var(--bg); color: var(--text); }`
    - Include the Tailwind directives (`@tailwind base; @tailwind components; @tailwind utilities;`)
    - _Requirements: 11.1, 11.3_

  - [ ] 6.4 Implement `frontend/app/layout.tsx`
    - Set `metadata.title = "Shorts Engine Studio"`
    - Import `./globals.css`
    - Apply `var(--bg)` background and `var(--text)` foreground via root layout classes
    - _Requirements: 11.2, 11.3_

  - [ ]* 6.5 Write smoke test for `next.config.js` headers
    - Import the config and assert the `headers()` source is `"/(.*)"` and includes both COOP `same-origin` and COEP `credentialless` entries
    - _Requirements: 10.1, 10.2, 10.4_

- [ ] 7. Frontend shared types and orchestrator skeleton
  - [ ] 7.1 Define shared TypeScript types in `frontend/app/types.ts`
    - Export `WordTimestamp`, `ShortSegment`, `Config` (count 1..10, duration 15|30|60, tone union, customTone, subtitleStyle union), `RenderedClip { url, title, hook, blob }`
    - _Requirements: 5.1, 5.2, 8.4, 8.5, 8.6, 8.8, 9.8_

  - [ ] 7.2 Implement orchestrator skeleton in `frontend/app/page.tsx`
    - Declare `Phase` state machine `"idle" | "uploading" | "processing" | "rendering" | "done" | "failed"`
    - Declare state hooks for `videoFile`, `config`, `phase`, `step`, `progress`, `renderIndex`, `clips`, `error`
    - Add a `useEffect` that sets an error and blocks further actions when `window.crossOriginIsolated !== true`
    - Provide stub `onGenerate` handler that validates "video selected" and "Custom tone non-empty after trim" preconditions and surfaces errors within 1 second of click
    - _Requirements: 8.10, 8.11, 10.3, 10.4_

- [ ] 8. DropZone component
  - [ ] 8.1 Implement `frontend/app/components/DropZone.tsx`
    - Bind `onDragOver`, `onDragLeave`, `onDrop` and a click-to-browse hidden `<input type="file" accept=".mp4,.mov,.mkv">`
    - Implement `validate(file)` rejecting extensions outside `{.mp4, .mov, .mkv}`, sizes `<= 0`, and sizes `> 2,147,483,648`
    - On invalid file, set local error and surface within 1 second without calling `onFileSelected`
    - On valid file, display name + formatted size and call `onFileSelected(file)`
    - _Requirements: 1.9, 1.10, 8.1, 8.2, 8.3_

  - [ ]* 8.2 Write unit tests for DropZone validation
    - Reject `.avi`, oversize (>2 GB), and zero-byte files with the appropriate error message
    - Accept `.mp4`, `.mov`, `.mkv` files of valid size and call `onFileSelected`
    - _Requirements: 1.9, 1.10, 8.2, 8.3_

- [ ] 9. ConfigPanel component
  - [ ] 9.1 Implement `frontend/app/components/ConfigPanel.tsx`
    - `<input type="range" min="1" max="10" step="1">` for `shorts_count` with default 3 and live numeric label
    - Three buttons for `duration_per_short` (15/30/60) with `aria-pressed` reflecting the single selected value (default 30)
    - `<select>` for `style_tone` listing the 6 options; when `Custom` is chosen, render a `<input type="text" maxLength={200}>` whose trimmed value (1..200 chars) becomes the outgoing `style_tone`
    - `<select>` for `subtitle_style` listing the 3 options
    - Disable all controls when the `disabled` prop is true
    - _Requirements: 8.4, 8.5, 8.6, 8.7, 8.8_

  - [ ]* 9.2 Write unit tests for ConfigPanel
    - Slider clamps to integers in `[1, 10]`
    - Duration buttons enforce single selection and emit the chosen integer
    - `Custom` reveals the text input and trimmed value flows through `onChange`
    - Subtitle selector emits one of the three allowed values
    - _Requirements: 8.4, 8.5, 8.6, 8.7, 8.8_

- [ ] 10. ProgressTracker component
  - [ ] 10.1 Implement `frontend/app/components/ProgressTracker.tsx`
    - Define `STEPS = ["Uploading", "Extracting Audio", "Transcribing", "Analyzing Highlights", "Rendering", "Done"]`
    - Mark earlier steps complete (`--success` check), the named step active (pulsing `--accent`), later steps pending (`--muted`) within 500 ms of message receipt
    - When `currentStep === "Rendering"` and `renderIndex` is set, render the active step label as `Rendering Short {k}/{n}`
    - Render unknown step indicator (red dot) without changing the previously active step
    - Render stall indicator on active step when `errorStep` matches it
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ]* 10.2 Write unit tests for ProgressTracker
    - Step transitions: passing `"Transcribing"` marks Uploading + Extracting Audio complete and Transcribing active
    - `Rendering Short k/N` substitution renders with the supplied `k` and `n` integers
    - Unknown step retains the previous active step and shows an unknown-step error indicator
    - _Requirements: 9.1, 9.2, 9.3, 9.5_

- [ ] 11. ffmpeg.wasm renderer hook
  - [ ] 11.1 Implement singleton init in `frontend/app/components/useFFmpegRenderer.ts`
    - Module-level `_ffmpeg`, `_initPromise`, `_sourceWritten`
    - `initFFmpeg()` loads `@ffmpeg/ffmpeg` (>=0.12) with `@ffmpeg/core@0.12.6` UMD assets via `toBlobURL` from `https://unpkg.com`
    - Wrap load in `Promise.race` with a 30 s timeout that rejects `Error("ffmpeg load timeout (30s)")`
    - Reset `_initPromise = null` on failure so a subsequent call retries
    - Re-use the initialized instance on every subsequent call
    - _Requirements: 7.1, 7.2, 7.3_

  - [ ] 11.2 Implement `generateAssSubtitles` in `useFFmpegRenderer.ts`
    - Build `[Script Info]` section with `PlayResX: 1080`, `PlayResY: 1920`, plus `[V4+ Styles]` Default style (Arial Black, primary white, secondary yellow, BorderStyle 1, Outline 4, Shadow 2, Alignment 2, MarginV 120)
    - Implement `toAssTime(secs)` formatting `H:MM:SS.cs` with two-digit centiseconds
    - Convert each word's `start`/`end` to clip-relative time by subtracting `segmentStartSec` and clamping into `[0, segmentDurSec]`
    - Filter out words missing/non-numeric/inverted timestamps, recording validation errors with offending indices
    - `TikTok-animated`: one Dialogue per word with override `{\an2\c&H00FFFF&}`
    - `Bold-centered-white`: group 3..4 words per line at font 72, MarginV 120
    - `Minimal-bottom`: group 3..4 words per line at font 48, MarginV 60
    - When zero valid words remain, emit a syntactically complete ASS with empty `[Events]` and return an indicator that no subtitles were produced
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.9, 6.10_

  - [ ] 11.3 Implement `renderShort` in `useFFmpegRenderer.ts`
    - On first call of the session, `writeFile("source.mp4", await fetchFile(videoFile))` and set `_sourceWritten = true`; reuse on subsequent calls
    - Reject with "source video too large" when `videoFile.size > 2 GB`
    - Compute `dur = max(0.001, end_sec - start_sec)` and write `subs.ass` produced by `generateAssSubtitles`
    - Escape title: replace `'` → `\'`, `:` → `\:`, then truncate to 200 chars
    - Build args `-ss <start> -i source.mp4 -t <dur> -vf "crop=ih*(9/16):ih,subtitles=subs.ass,drawtext=text='<title>':x=(w-text_w)/2:y=80:fontsize=52:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=12" -c:v libx264 -preset ultrafast -crf 23 -c:a aac -b:a 128k -movflags +faststart out_<index>.mp4`
    - Wire `ffmpeg.on("progress", ...)` to forward `onProgress(ratio)` clamped to `[0, 1]`
    - On success: read `out_<index>.mp4`, return as `Blob` with `type: "video/mp4"`, then `deleteFile` both `out_<index>.mp4` and `subs.ass` (retain `source.mp4`)
    - On `ffmpeg.exec` rejection or 60 s without a progress event, throw a render error and still delete `subs.ass` and the partial output
    - _Requirements: 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 7.11, 7.12_

  - [ ] 11.4 Implement `renderAll` driver
    - Sequential `for` loop awaiting `renderShort(segment, file, index, style, ratio => onProgress(k, ratio))` for each segment
    - Invoke `onIndex(k, n)` before each segment and propagate the first error
    - Structurally guarantee at most one in-flight `ffmpeg.exec` at any wall-clock instant
    - _Requirements: 7.10_

  - [ ]* 11.5 Write unit tests for `generateAssSubtitles`
    - `TikTok-animated`: emits one Dialogue per word and the override tag is exactly `{\an2\c&H00FFFF&}`
    - `Bold-centered-white`: groups of 3..4 words; group `Start` equals first word `s`, `End` equals last word `e`; font 72 / MarginV 120
    - `Minimal-bottom`: font size 48, MarginV 60
    - Time conversion: `start - segmentStartSec` clamped to `[0, dur]`; format `H:MM:SS.cs` with two-digit centiseconds
    - Words missing/non-numeric/`end <= start` are dropped and remaining words still emit
    - Zero valid words yields a syntactically complete ASS with empty `[Events]`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.9, 6.10_

  - [ ]* 11.6 Write property-based test for ASS round-trip [PBT]
    - **Property 7: ASS round-trip**
    - **Validates: Requirements 6.8**
    - Use `fast-check` to generate random valid `WordTimestamp[]` (finite, `end > start`, sortable) plus random `segmentStart` and `segmentDur`
    - For every Subtitle_Style, call `generateAssSubtitles`, parse the emitted `[Events]` with a tiny inline ASS parser, and assert word groupings match, timestamps match within 1 centisecond, and override tags are byte-identical to those generated

  - [ ]* 11.7 Write property-based test for ASS time clamping [PBT]
    - **Property 8: ASS time clamping**
    - **Validates: Requirements 6.3, 6.4**
    - Use `fast-check` to generate random `WordTimestamp[]` with arbitrary (possibly out-of-range) timestamps and any Subtitle_Style; parse every emitted `Start`/`End` time and assert `0 <= t <= segmentDurSec` and that `|t_emitted - (t_source - segmentStartSec)|` after clamping is `<= 10 ms`

- [ ] 12. ResultsGrid component
  - [ ] 12.1 Implement `frontend/app/components/ResultsGrid.tsx`
    - Tailwind responsive grid: `grid-cols-2 lg:grid-cols-3 gap-4` (2 columns under 1024 px, 3 columns at 1024 px+)
    - Each card: inline `<input type="text" maxLength={100}>` styled `text-amber-500 bg-transparent` for the title; `<p>` for `hook`; `<video src={url} controls class="aspect-[9/16] w-full">`; individual download button using a hidden `<a>` with `download={sanitize(title)}.mp4`
    - On commit, truncate titles longer than 100 chars and reject empty post-sanitize titles by reverting to the previous value with an inline error indicator
    - `sanitize(title)` strips `[\\/:*?"<>|]`, collapses whitespace, trims; empty result becomes `"untitled"`
    - "Download All as ZIP" button enabled only while every clip has a valid title and a non-null `blob`
    - On click, dynamically `import("jszip")`, build the ZIP using sanitized titles and append a numeric `(2)`-style suffix to deduplicate names; trigger a single download within 10 seconds
    - On JSZip import or build failure, display an error indicator on the ZIP button and retain in-memory blobs/titles unchanged
    - _Requirements: 9.6, 9.7, 9.8, 9.9, 9.10, 9.11, 9.12, 9.13, 9.14_

  - [ ]* 12.2 Write unit tests for ResultsGrid
    - `sanitize` strips reserved chars, collapses whitespace, and returns `"untitled"` for empty post-sanitize input with an error flag
    - Inline title editor truncates input over 100 chars and reverts on empty commit
    - ZIP dedup logic appends `(2)`, `(3)`, … to duplicates within a bundle
    - Dynamic JSZip import failure surfaces an error indicator without mutating state
    - _Requirements: 9.9, 9.10, 9.11, 9.13, 9.14_

- [ ] 13. Final wire-up
  - [ ] 13.1 Wire `frontend/app/page.tsx` end-to-end
    - Compose DropZone + ConfigPanel + ProgressTracker + ResultsGrid into the page using the orchestrator state
    - Implement `onGenerate`: validate, build `FormData`, POST to `http://localhost:8000/api/process-video`, transition to `"processing"` and open `EventSource("http://localhost:8000/api/stream/{taskId}")` within 500 ms of receiving `taskId`
    - Implement `streamUntilDone(taskId)` SSE consumer updating `step`/`progress` and resolving on `Done` / rejecting on `Failed`
    - On Done, transition to `"rendering"`, call `useFFmpegRenderer.renderAll(segments, videoFile, subtitleStyle, (k, n) => setRenderIndex({ k, n }))`, then set `phase="done"` and show the `ResultsGrid`
    - On any failure, set `phase="failed"`, surface error, and re-enable the Generate button within 2 seconds
    - _Requirements: 8.9, 8.11, 8.12, 9.6, 13.1, 13.2, 13.5_

  - [ ]* 13.2 Write integration test for the page orchestrator
    - Mock `fetch` and `EventSource` to drive `Uploading → Extracting Audio → Transcribing → Analyzing Highlights → Done`
    - Mock `useFFmpegRenderer.renderAll` to invoke `onIndex(k, n)` for `k = 1..N` and resolve to `RenderedClip[]`
    - Assert the ProgressTracker shows the exact 9-step sequence (`Rendering Short 1/N` … `Rendering Short N/N` then `Done`) and the ResultsGrid renders `N` cards
    - _Requirements: 9.5, 9.6, 13.1, 13.2_

- [ ] 14. README
  - [ ] 14.1 Author top-level `README.md`
    - **Prerequisites:** Node.js 20+, Python 3.11+, system FFmpeg on PATH, modern Chromium/Firefox/Safari with cross-origin isolation support
    - **Backend setup:** `python -m venv .venv` → activate → `pip install -r backend/requirements.txt` → copy `.env.example` to `.env` and fill `GOOGLE_API_KEY` + `WHISPER_MODEL_SIZE` → `uvicorn backend.main:app --port 8000`
    - **Frontend setup:** `cd frontend && npm install && npm run dev` (no Docker required)
    - **Whisper model sizes:** table listing `tiny | base | small | medium | large` with approximate VRAM/CPU expectations
    - **Common issues:** COOP/COEP not active (verify `window.crossOriginIsolated`); Whisper first-run download time and disk usage; Gemini schema parse errors and retry behavior; CORS rejection for origins other than `http://localhost:3000`
    - _Requirements: 12.3, 12.7, 12.8_

- [ ] 15. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test-related sub-tasks; they can be skipped for a faster MVP, but the three property-based tests (3.6, 11.6, 11.7) directly validate Properties 3, 7, and 8 from the design and are recommended for any production run.
- The backend root is constrained to exactly five files (Requirement 12.1), so all backend tests live under `backend/tests/`.
- Tasks that touch the same source file are placed in different waves of the dependency graph to avoid concurrent edits.
- `backend/main.py` is built up incrementally across tasks 1.2 → 4.1 → 4.2 → 4.3 → 4.4 → 4.5 → 4.6 → 4.7; `backend/analyze.py` across 3.1 → 3.2 → 3.3 → 3.4; `useFFmpegRenderer.ts` across 11.1 → 11.2 → 11.3 → 11.4; `app/page.tsx` across 7.2 → 13.1.
- Each task references specific requirements clauses for traceability.
- Checkpoint tasks (5, 15) and top-level parent tasks are not part of the dependency graph below.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1", "3.1", "6.1", "6.3", "14.1"] },
    { "id": 2, "tasks": ["2.2", "3.2", "4.1", "6.2", "6.4", "7.1"] },
    { "id": 3, "tasks": ["3.3", "4.2", "6.5"] },
    { "id": 4, "tasks": ["3.4", "4.3", "7.2"] },
    { "id": 5, "tasks": ["3.5", "3.6", "4.4", "8.1", "9.1", "10.1", "11.1", "12.1"] },
    { "id": 6, "tasks": ["4.5", "8.2", "9.2", "10.2", "11.2", "12.2"] },
    { "id": 7, "tasks": ["4.6", "11.3", "11.5"] },
    { "id": 8, "tasks": ["4.7", "11.4", "11.6", "11.7"] },
    { "id": 9, "tasks": ["4.8", "4.9"] },
    { "id": 10, "tasks": ["13.1"] },
    { "id": 11, "tasks": ["13.2"] }
  ]
}
```
