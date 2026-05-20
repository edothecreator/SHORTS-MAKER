# Design Document

## Overview

The Video-to-Shorts Engine implements the "Hybrid Local-First" (Strategy A) architecture: a thin FastAPI backend handles only what cannot run in the browser (audio extraction, local Whisper transcription, Gemini segment selection), and a Next.js frontend handles all video rendering via ffmpeg.wasm. The backend retains zero permanent video data — the upload and the extracted WAV are deleted within seconds of pipeline completion, and a periodic Cleanup_Task removes any stale Workspace_Directory entries as a safety net.

This design satisfies the requirements document by:

- Splitting responsibilities so the server only sees raw audio and a transcript (not rendered video).
- Streaming progress to the browser via SSE so the user sees Uploading → Extracting Audio → Transcribing → Analyzing Highlights → Rendering k/N → Done.
- Enforcing the Gemini response with a strict Pydantic schema (`ShortsAnalysisResult`) so downstream rendering never receives malformed data.
- Performing all video rendering (cut, 9:16 center-crop, ASS subtitle burn-in, drawtext title overlay, MP4 mux) inside the browser's WASM sandbox using ffmpeg.wasm v0.12.
- Producing per-segment Blobs that the user can preview, retitle, download individually, or bundle into a ZIP via dynamically imported JSZip.

The key non-obvious decisions and their rationale:

- **Strict serial rendering** in `useFFmpegRenderer`. ffmpeg.wasm shares one heap; concurrent `ffmpeg.exec` calls would corrupt state and exhaust memory on multi-GB sources. We enforce a `Promise` chain that prevents a second exec from starting until the previous resolves or rejects.
- **`source.mp4` is written to the WASM filesystem only once** per session and reused for every segment. Writing a 1–2 GB file is the expensive step; segment cuts are cheap with `-ss` seeking and `-c:v libx264 -preset ultrafast`.
- **In-process `Task_Registry` dictionary** rather than a database. The system is single-process, single-user (localhost), and the registry's lifetime equals the pipeline's lifetime. Persistence would contradict requirement 3 (zero permanent storage of pipeline data).
- **SSE polling cadence (1 s ± 200 ms)** is driven by a coroutine reading the registry, not by direct events. This is simpler than wiring a pub/sub and matches the requirement's polling model exactly.
- **COOP/COEP `same-origin` + `credentialless`** is non-negotiable. ffmpeg.wasm uses `SharedArrayBuffer`, which browsers gate behind cross-origin isolation. We set the headers in `next.config.js` so every route is isolated, and the renderer health-checks `window.crossOriginIsolated` before attempting to load core assets.

## Architecture

### High-Level Flow

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant FE as Next.js Frontend
    participant BE as FastAPI Backend
    participant FF as System FFmpeg
    participant W as Whisper (CPU)
    participant G as Gemini 2.5 Flash
    participant WASM as ffmpeg.wasm (Browser)

    U->>FE: Drop .mp4 + configure (count, duration, tone, subs)
    FE->>BE: POST /api/process-video (multipart)
    BE->>BE: uuid4(), save /tmp/shorts_workspace/{id}/input.{ext}
    BE-->>FE: {"taskId": "<uuid>"}
    FE->>BE: GET /api/stream/{task_id}  (EventSource)
    BE-->>FE: SSE step="Uploading" progress=10
    BE->>FF: ffmpeg -i input.{ext} -vn -ar 16000 -ac 1 audio.wav
    FF-->>BE: audio.wav
    BE-->>FE: SSE step="Extracting Audio" progress=25
    BE->>W: model.transcribe(audio.wav, word_timestamps=True)
    W-->>BE: {segments[*].words[*]}
    BE-->>FE: SSE step="Transcribing" progress=60
    BE->>G: generate_content(prompt, schema=ShortsAnalysisResult)
    G-->>BE: response.parsed
    BE-->>FE: SSE step="Analyzing Highlights" progress=75
    BE->>BE: delete input.{ext} + audio.wav
    BE-->>FE: SSE step="Done" progress=100 data={segments: [...]}
    BE--xFE: close stream

    Note over FE,WASM: Local rendering — server is no longer involved
    FE->>WASM: load core@0.12.6 UMD via toBlobURL
    FE->>WASM: writeFile('source.mp4', videoFile)
    loop for each segment k of N
        FE->>FE: generateAssSubtitles(words, style, start_sec)
        FE->>WASM: writeFile('subs.ass', ass)
        FE->>WASM: ffmpeg.exec([-ss, -i, -t, -vf crop+subtitles+drawtext, ...])
        WASM-->>FE: out_k.mp4
        FE->>FE: new Blob([data], 'video/mp4'); URL.createObjectURL
        FE->>WASM: deleteFile('out_k.mp4'); deleteFile('subs.ass')
    end
    FE->>U: ResultsGrid (preview + download + ZIP)
```

### System Layers

| Layer | Responsibility | Key Files |
|---|---|---|
| Frontend UI | Drop, configure, show progress, preview, download | `app/page.tsx`, `app/components/{DropZone,ConfigPanel,ProgressTracker,ResultsGrid}.tsx` |
| Frontend Renderer | ffmpeg.wasm orchestration, ASS generation | `app/components/useFFmpegRenderer.ts` |
| API Adapter (Frontend) | POST upload, EventSource stream | inside `app/page.tsx` |
| Backend HTTP | FastAPI routes, CORS, BackgroundTasks | `backend/main.py` |
| Backend Pipeline | Audio extract, transcribe, analyze, cleanup | `backend/main.py` (pipeline fn), `backend/transcribe.py`, `backend/analyze.py` |
| External | System FFmpeg binary, Whisper local model, Gemini 2.5 Flash API | (no source) |

### Threading and Concurrency Model

- The FastAPI app runs under a single uvicorn worker. The default thread pool executor is used by `loop.run_in_executor` to push blocking Whisper inference off the event loop (requirement 2.5).
- Each upload spawns two BackgroundTasks: `run_processing_pipeline(task_id)` and `cleanup_task_directory(task_id, delay=3600)`. They share access to the in-process `Task_Registry` dict; writes are confined to single-key mutations and reads by the SSE coroutine, so a `dict` (CPython atomic single-key set) is sufficient — no lock is required.
- The Cleanup_Task scanner (one global asyncio task started at app startup) wakes every ≤ 300 s (requirement 3.7) and removes any Workspace_Directory whose creation time is older than 3600 s.
- The browser-side renderer runs all segment renders sequentially via an internal `Promise` chain. The renderer surface returns an `await`-able `renderShort` and a `renderAll` driver; concurrency is impossible by API shape.

## Components and Interfaces

### Backend: `backend/main.py`

**Purpose:** FastAPI HTTP entry, route handlers, BackgroundTask scheduling, SSE streaming, in-process Task_Registry, and the `run_processing_pipeline` and `cleanup_task_directory` async functions.

**Public surface:**

```python
app = FastAPI()  # CORS allow_origins=["http://localhost:3000"]

# In-process state. Lifetime = process lifetime. Not persisted.
task_registry: dict[str, dict] = {}

@app.post("/api/process-video")
async def process_video(
    background: BackgroundTasks,
    video_file: UploadFile = File(...),
    style_tone: str = Form(...),
    shorts_count: int = Form(...),
    duration_per_short: int = Form(...),
) -> dict[str, str]: ...

@app.get("/api/stream/{task_id}")
async def stream(task_id: str) -> StreamingResponse: ...

async def run_processing_pipeline(task_id: str) -> None: ...
async def cleanup_task_directory(task_id: str, delay: int = 3600) -> None: ...
```

**Task_Registry entry shape:**

```python
{
    "step": str,          # one of "Uploading" | "Extracting Audio" | "Transcribing" | "Analyzing Highlights" | "Done" | "Failed"
    "progress": int,      # 10 | 25 | 60 | 75 | 100
    "created_at": float,  # time.time() — used by Cleanup_Task safety net
    "data": dict | None,  # ShortsAnalysisResult.model_dump() when step == "Done"
    "error": str | None,  # exception message when step == "Failed"
    "warning": str | None,# e.g. invalid WHISPER_MODEL_SIZE fallback
}
```

**Validation flow (criterion-aligned):**

1. Manual validation of `shorts_count` (1..10), `duration_per_short` (∈ {15,30,60}), `style_tone` (1..500 trimmed). Return HTTP 422 on failure (req 1.6, 1.7, 1.8).
2. Reject empty/zero-byte upload with HTTP 422 (req 1.11).
3. Compute extension from `video_file.filename` (lowercase). Frontend already filters but backend re-validates implicitly by saving with the original extension.
4. `task_id = str(uuid4())`, `workspace = Path("/tmp/shorts_workspace") / task_id`, `workspace.mkdir(parents=True, exist_ok=False)`.
5. Stream the upload to `workspace / f"input.{ext}"` in 1 MiB chunks. On `OSError`, delete partial file and respond HTTP 500 without registering the task (req 1.12).
6. Register `task_registry[task_id] = {...}` with `step="Uploading"`, `progress=10`, `created_at=time.time()`.
7. `background.add_task(run_processing_pipeline, task_id)`, `background.add_task(cleanup_task_directory, task_id, 3600)`.
8. Return `{"taskId": task_id}` (req 1.5).

**Pipeline `run_processing_pipeline(task_id)`:**

```python
async def run_processing_pipeline(task_id: str) -> None:
    workspace = Path("/tmp/shorts_workspace") / task_id
    input_path = next(workspace.glob("input.*"))
    audio_path = workspace / "audio.wav"
    try:
        _set(task_id, step="Extracting Audio", progress=25)
        await _extract_audio(input_path, audio_path)  # asyncio subprocess, 600 s timeout

        _set(task_id, step="Transcribing", progress=60)
        whisper_output = await run_whisper_transcription(str(audio_path), model_size=_resolve_model())

        _set(task_id, step="Analyzing Highlights", progress=75)
        result = await analyze_video_transcript(
            whisper_output,
            style_tone=task_registry[task_id]["_style_tone"],
            max_count=task_registry[task_id]["_shorts_count"],
            target_duration=task_registry[task_id]["_duration_per_short"],
        )

        _set(task_id, step="Done", progress=100, data=result.model_dump())
    except Exception as e:
        _set(task_id, step="Failed", error=str(e))
    finally:
        await _safe_delete(input_path)   # 3 retries × 1 s
        await _safe_delete(audio_path)   # 3 retries × 1 s
```

The form fields `style_tone`, `shorts_count`, `duration_per_short` are stashed on the registry entry under leading-underscore keys at upload time so the pipeline can read them without re-parsing the form.

**`_extract_audio` exact arguments:**

```
ffmpeg -y -nostdin -i {input_path} -vn -acodec pcm_s16le -ac 1 -ar 16000 {audio_path}
```

Run via `asyncio.create_subprocess_exec` with `asyncio.wait_for(..., timeout=600)`. On non-zero return, `TimeoutError`, or `FileNotFoundError`, raise a `RuntimeError("Audio extraction failed: ...")` which the pipeline turns into `step="Failed"` (req 2.3).

**SSE endpoint `/api/stream/{task_id}`:**

```python
@app.get("/api/stream/{task_id}")
async def stream(task_id: str):
    if task_id not in task_registry:
        raise HTTPException(404)

    async def event_gen():
        # Initial snapshot within 1 s of connect (req 4.2)
        yield _format_sse(task_registry[task_id])
        last_step_change = time.time()
        last_step = task_registry[task_id]["step"]
        while True:
            await asyncio.sleep(1.0)
            entry = task_registry.get(task_id)
            if entry is None:
                break
            if entry["step"] != last_step:
                last_step = entry["step"]
                last_step_change = time.time()
            elif time.time() - last_step_change > 600:  # req 4.8 stall
                yield _format_sse({"step": "Failed", "error": "Pipeline stalled"})
                break
            yield _format_sse(entry)
            if entry["step"] in ("Done", "Failed"):
                break

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
```

Where `_format_sse(payload)` returns `f"data: {json.dumps(payload)}\n\n"`.

**Cleanup logic:**

- `cleanup_task_directory(task_id, delay)` sleeps `delay` seconds, then `shutil.rmtree(workspace, ignore_errors=True)`.
- A separate startup task `_cleanup_scanner()` runs forever, sleeping 300 s between scans, removing any subdirectory of `/tmp/shorts_workspace/` older than 3600 s (req 3.7).
- `_safe_delete(path)` retries up to 3 times with 1 s sleep on `OSError` (req 3.6); on final failure it stores a `cleanup_warning` field on the registry entry without changing `step`.

### Backend: `backend/transcribe.py`

**Purpose:** Async wrapper around Whisper that pushes inference to the default executor.

```python
import asyncio
import whisper
from typing import Any

_model_cache: dict[str, Any] = {}

def _load_model(size: str):
    if size not in _model_cache:
        _model_cache[size] = whisper.load_model(size)
    return _model_cache[size]

async def run_whisper_transcription(audio_file_path: str, model_size: str = "base") -> dict:
    """
    Run Whisper on a thread executor with word_timestamps=True so the FastAPI
    event loop is not blocked. Returns the raw whisper.transcribe dict whose
    'segments' list contains 'words' with 'start' and 'end' floats.
    """
    loop = asyncio.get_running_loop()

    def _inference():
        model = _load_model(model_size)
        return model.transcribe(audio_file_path, word_timestamps=True)

    return await loop.run_in_executor(None, _inference)
```

The `_model_cache` is a module-level dict so the second pipeline run in the same process reuses the loaded weights rather than reloading from disk.

### Backend: `backend/analyze.py`

**Purpose:** Build the strategist prompt, call Gemini 2.5 Flash with a Pydantic response schema, validate post-parse constraints, return `ShortsAnalysisResult`.

```python
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

class WordTimestamp(BaseModel):
    word: str = Field(min_length=1, max_length=100)
    start: float = Field(ge=0.0)
    end: float = Field(ge=0.0)

class ShortSegment(BaseModel):
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(gt=0.0)
    title: str = Field(min_length=1, max_length=50)
    hook: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=500)
    words: list[WordTimestamp] = Field(min_length=0, max_length=1000)

class ShortsAnalysisResult(BaseModel):
    segments: list[ShortSegment] = Field(min_length=1, max_length=50)
```

**Prompt construction (`_build_prompt`):**

Three sections concatenated:

1. Role + task: viral short-form strategist; extract exactly `max_count` non-overlapping clips of ≤ `target_duration` seconds.
2. Hard rules: clip duration ≤ target, no overlap, hook = first 5 words, title ≤ 50 chars no `#`, fill `words` with every Whisper word whose `start ≥ start_sec` and `end ≤ end_sec`, ascending order.
3. Style block selected from the Style_Tone, with the `Custom` branch embedding the user's literal text (truncated to 1000 chars).
4. Transcript dump: a compact JSON array `[{"w": word, "s": start, "e": end}, ...]` of every Whisper word with timestamps. Compact keys keep the prompt token count bounded.

**Call:**

```python
client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=ShortsAnalysisResult,
    ),
)
```

**Retry policy:** wrap the call in `_call_with_retry(fn, attempts=3, backoff=2.0)` per requirement 2.12. Network/timeout/non-success → exception with category prefix.

**Validation post-parse (req 5.13):**

```python
def _validate_result(r: ShortsAnalysisResult, count: int, max_dur: int) -> None:
    if len(r.segments) != count:
        raise ValueError(f"Gemini returned {len(r.segments)} segments, expected {count}")
    sorted_segs = sorted(r.segments, key=lambda s: s.start_sec)
    for a, b in zip(sorted_segs, sorted_segs[1:]):
        if a.end_sec > b.start_sec:
            raise ValueError(f"Segments overlap: [{a.start_sec},{a.end_sec}] and [{b.start_sec},{b.end_sec}]")
    for s in r.segments:
        if s.end_sec - s.start_sec > max_dur:
            raise ValueError(f"Segment {s.start_sec}-{s.end_sec} exceeds duration {max_dur}")
        if s.end_sec <= s.start_sec:
            raise ValueError(f"Segment {s.start_sec}-{s.end_sec} has non-positive duration")
```

If `response.parsed is None`, raise `ValueError(f"Gemini parse failed: {response.text!r}")` (req 2.11, 5.12).

### Frontend: `app/page.tsx`

**Purpose:** Top-level orchestrator. Holds session state, drives the upload + SSE + render flow.

**State:**

```ts
type Phase = "idle" | "uploading" | "processing" | "rendering" | "done" | "failed";

interface RenderedClip {
  url: string;        // ObjectURL
  title: string;      // editable
  hook: string;
  blob: Blob;
}

const [videoFile, setVideoFile] = useState<File | null>(null);
const [config, setConfig] = useState<Config>({ count: 3, duration: 30, tone: "Funny", customTone: "", subtitleStyle: "TikTok-animated" });
const [phase, setPhase] = useState<Phase>("idle");
const [step, setStep] = useState<string>("");
const [progress, setProgress] = useState<number>(0);
const [renderIndex, setRenderIndex] = useState<{ k: number; n: number } | null>(null);
const [clips, setClips] = useState<RenderedClip[]>([]);
const [error, setError] = useState<string | null>(null);
```

**Submit handler (`onGenerate`):**

```ts
async function onGenerate() {
  if (!videoFile) { setError("Select a video first."); return; }
  const tone = config.tone === "Custom" ? config.customTone.trim() : config.tone;
  if (config.tone === "Custom" && tone.length < 1) { setError("Custom tone is required."); return; }

  setPhase("uploading"); setError(null);
  const fd = new FormData();
  fd.append("video_file", videoFile);
  fd.append("style_tone", tone);
  fd.append("shorts_count", String(config.count));
  fd.append("duration_per_short", String(config.duration));

  const res = await fetch("http://localhost:8000/api/process-video", { method: "POST", body: fd });
  if (!res.ok) { setError(`Upload failed (${res.status}).`); setPhase("failed"); return; }
  const { taskId } = await res.json();

  setPhase("processing");
  const segments = await streamUntilDone(taskId);  // Promise<ShortSegment[]>

  setPhase("rendering");
  const rendered = await renderAllShorts(segments, videoFile, config.subtitleStyle, (k, n) => setRenderIndex({ k, n }));
  setClips(rendered);
  setPhase("done");
}
```

**SSE consumer `streamUntilDone`:**

```ts
function streamUntilDone(taskId: string): Promise<ShortSegment[]> {
  return new Promise((resolve, reject) => {
    const es = new EventSource(`http://localhost:8000/api/stream/${taskId}`);
    es.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      setStep(msg.step); setProgress(msg.progress ?? 0);
      if (msg.step === "Done") { es.close(); resolve(msg.data.segments); }
      if (msg.step === "Failed") { es.close(); reject(new Error(msg.error ?? "Pipeline failed")); }
    };
    es.onerror = () => { es.close(); reject(new Error("SSE connection lost")); };
  });
}
```

### Frontend: `app/components/DropZone.tsx`

**Purpose:** Drag-and-drop zone + click-to-browse. Validates extension and size before notifying the parent.

**Props:** `{ file: File | null; onFileSelected: (file: File | null) => void }`

**Validation logic:**

```ts
const SUPPORTED = [".mp4", ".mov", ".mkv"];
const MAX_BYTES = 2_147_483_648;

function validate(f: File): string | null {
  const ext = "." + (f.name.split(".").pop() ?? "").toLowerCase();
  if (!SUPPORTED.includes(ext)) return `Unsupported type. Allowed: ${SUPPORTED.join(", ")}.`;
  if (f.size <= 0) return "File is empty.";
  if (f.size > MAX_BYTES) return "File exceeds the 2 GB limit.";
  return null;
}
```

On invalid file, sets local `error` state, does **not** call `onFileSelected`, and surfaces the error within 1 s of drop (requirement 8.3). On valid file, formats `file.size` (KB / MB / GB) and shows the file name + size.

The drop handler binds `onDragOver`, `onDragLeave`, `onDrop`. The dashed border highlights via a `dragActive` boolean. A hidden `<input type="file" accept=".mp4,.mov,.mkv">` is triggered by clicking the zone.

### Frontend: `app/components/ConfigPanel.tsx`

**Purpose:** All user configuration. Single controlled component.

**Controls:**

- `shorts_count`: `<input type="range" min="1" max="10" step="1">` with live label, default 3 (req 8.4).
- `duration_per_short`: 3 buttons; the selected one carries an `aria-pressed="true"` and the accent background. Default 30 (req 8.5).
- `style_tone`: `<select>` with the 6 options. When set to `Custom`, an additional `<input type="text" maxLength="200">` appears (req 8.6, 8.7).
- `subtitle_style`: `<select>` with 3 options (req 8.8).

**Props:**

```ts
interface ConfigPanelProps {
  config: Config;
  onChange: (c: Config) => void;
  disabled: boolean;  // disabled while processing/rendering
}
```

### Frontend: `app/components/ProgressTracker.tsx`

**Purpose:** Vertical pipeline timeline + linear progress bar.

**Step model:**

```ts
const STEPS = [
  "Uploading",
  "Extracting Audio",
  "Transcribing",
  "Analyzing Highlights",
  "Rendering",     // displayed as "Rendering Short k/N" when renderIndex is set
  "Done",
];
```

A step is `complete` if its index is less than the current step index, `active` if equal, `pending` otherwise. Active step shows a pulsing amber dot (`--accent`); complete shows a green checkmark (`--success`); pending shows a grey dot (`--muted`).

**Props:**

```ts
interface ProgressTrackerProps {
  currentStep: string;        // raw SSE step string
  progress: number;           // 0..100
  renderIndex: { k: number; n: number } | null;
  errorStep?: string | null;  // when set, marks that step with red dot
}
```

When `currentStep === "Rendering"` (synthesized by the page during the rendering phase) and `renderIndex` is set, the label rendered for the active step is `Rendering Short {k}/{n}`.

### Frontend: `app/components/useFFmpegRenderer.ts`

**Purpose:** Custom hook that owns the singleton `FFmpeg` instance, exposes `init`, `renderShort`, and `renderAll`, and produces the `.ass` string for each segment.

**Module-level singleton:**

```ts
let _ffmpeg: FFmpeg | null = null;
let _initPromise: Promise<FFmpeg> | null = null;
let _sourceWritten = false;

async function initFFmpeg(): Promise<FFmpeg> {
  if (_ffmpeg) return _ffmpeg;
  if (_initPromise) return _initPromise;

  _initPromise = (async () => {
    const ffmpeg = new FFmpeg();
    const baseURL = "https://unpkg.com/@ffmpeg/core@0.12.6/dist/umd";
    await Promise.race([
      ffmpeg.load({
        coreURL: await toBlobURL(`${baseURL}/ffmpeg-core.js`, "text/javascript"),
        wasmURL: await toBlobURL(`${baseURL}/ffmpeg-core.wasm`, "application/wasm"),
      }),
      new Promise((_, rej) => setTimeout(() => rej(new Error("ffmpeg load timeout (30s)")), 30_000)),
    ]);
    _ffmpeg = ffmpeg;
    return ffmpeg;
  })();

  try { return await _initPromise; }
  catch (e) { _initPromise = null; throw e; }
}
```

`_initPromise` is reset to `null` on failure so a subsequent invocation can retry (req 7.2).

**ASS generation `generateAssSubtitles`:**

```ts
type SubtitleStyle = "TikTok-animated" | "Bold-centered-white" | "Minimal-bottom";

const ASS_HEADER = (fontSize: number, marginV: number) => `[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,${fontSize},&H00FFFFFF,&H0000FFFF,&H00000000,&H96000000,1,0,0,0,100,100,2,0,1,4,2,2,20,20,${marginV},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
`;

function toAssTime(secs: number): string {
  if (secs < 0) secs = 0;
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = Math.floor(secs % 60);
  const cs = Math.floor((secs % 1) * 100);
  return `${h}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}.${String(cs).padStart(2,"0")}`;
}

function generateAssSubtitles(words: WordTimestamp[], style: SubtitleStyle, segmentStartSec: number, segmentDurSec: number): string {
  const valid = words.filter(w => Number.isFinite(w.start) && Number.isFinite(w.end) && w.end > w.start);
  const rebased = valid.map(w => ({
    word: w.word,
    s: Math.max(0, Math.min(segmentDurSec, w.start - segmentStartSec)),
    e: Math.max(0, Math.min(segmentDurSec, w.end - segmentStartSec)),
  }));

  if (style === "TikTok-animated") {
    const header = ASS_HEADER(72, 120);
    const events = rebased.map(w =>
      `Dialogue: 0,${toAssTime(w.s)},${toAssTime(w.e)},Default,,0,0,0,,{\\an2\\c&H00FFFF&}${escapeAss(w.word)}`
    ).join("\n");
    return header + events + "\n";
  }
  if (style === "Bold-centered-white") {
    return ASS_HEADER(72, 120) + groupedEvents(rebased, /*size*/72) + "\n";
  }
  // Minimal-bottom
  return ASS_HEADER(48, 60) + groupedEvents(rebased, /*size*/48) + "\n";
}
```

`groupedEvents` walks `rebased` 4 words at a time, emits one Dialogue per group whose `Start` is the first word's `s` and `End` is the last word's `e`. `escapeAss` replaces `{` `}` `\` to keep ASS-safe text.

**`renderShort`:**

```ts
async function renderShort(
  segment: ShortSegment,
  videoFile: File,
  index: number,
  subtitleStyle: SubtitleStyle,
  onProgress: (ratio: number) => void,
): Promise<{ url: string; blob: Blob; title: string; hook: string }> {
  const ffmpeg = await initFFmpeg();

  if (!_sourceWritten) {
    await ffmpeg.writeFile("source.mp4", await fetchFile(videoFile));
    _sourceWritten = true;
  }

  const dur = Math.max(0.001, segment.end_sec - segment.start_sec);
  const ass = generateAssSubtitles(segment.words, subtitleStyle, segment.start_sec, dur);
  await ffmpeg.writeFile("subs.ass", new TextEncoder().encode(ass));

  const safeTitle = segment.title.replace(/'/g, "\\'").replace(/:/g, "\\:").slice(0, 200);
  const out = `out_${index}.mp4`;

  const onP = (e: { progress: number }) => {
    const r = Math.max(0, Math.min(1, e.progress));
    onProgress(r);
  };
  ffmpeg.on("progress", onP);
  try {
    await ffmpeg.exec([
      "-ss", segment.start_sec.toFixed(3),
      "-i", "source.mp4",
      "-t", dur.toFixed(3),
      "-vf", [
        "crop=ih*(9/16):ih",
        "subtitles=subs.ass",
        `drawtext=text='${safeTitle}':x=(w-text_w)/2:y=80:fontsize=52:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=12`,
      ].join(","),
      "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
      "-c:a", "aac", "-b:a", "128k",
      "-movflags", "+faststart",
      out,
    ]);
  } finally {
    ffmpeg.off("progress", onP);
  }

  const data = await ffmpeg.readFile(out);
  await ffmpeg.deleteFile(out).catch(() => {});
  await ffmpeg.deleteFile("subs.ass").catch(() => {});

  const blob = new Blob([data as Uint8Array], { type: "video/mp4" });
  const url = URL.createObjectURL(blob);
  return { url, blob, title: segment.title, hook: segment.hook };
}
```

**`renderAll`:** sequential `for` loop awaiting `renderShort` per segment, calling `onIndex(k, n)` before each. Strict serialization is structural, not advisory.

### Frontend: `app/components/ResultsGrid.tsx`

**Purpose:** Display rendered clips, allow inline title edit, individual download, and ZIP bundle.

**Props:** `{ clips: RenderedClip[]; onTitleChange: (i: number, title: string) => void }`

**Layout:** Tailwind grid `grid-cols-2 lg:grid-cols-3 gap-4`. Each card:

- `<input type="text" maxLength={100}>` styled `text-amber-500 bg-transparent` for the title (req 9.8, 9.9).
- `<p class="text-xs text-[var(--muted)]">{hook}</p>`.
- `<video src={url} controls class="aspect-[9/16] w-full">`.
- `<button>Download</button>` triggers a hidden anchor with `download={sanitize(title)}.mp4`.

**`sanitize`:** strips `[\\\/:*?"<>|]`, collapses whitespace, trims; if result is empty, returns `"untitled"` and triggers an inline error indicator (req 9.11).

**ZIP button:**

```ts
async function downloadZip() {
  setZipBusy(true);
  try {
    const { default: JSZip } = await import("jszip");
    const zip = new JSZip();
    const seen = new Set<string>();
    clips.forEach((c, i) => {
      let name = sanitize(c.title) + ".mp4";
      let n = 1;
      while (seen.has(name)) { name = `${sanitize(c.title)} (${++n}).mp4`; }
      seen.add(name);
      zip.file(name, c.blob);
    });
    const out = await zip.generateAsync({ type: "blob" });
    triggerDownload(URL.createObjectURL(out), "shorts.zip");
  } catch (e) {
    setZipError("Could not build ZIP bundle.");
  } finally {
    setZipBusy(false);
  }
}
```

### Frontend: `next.config.js`

```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Cross-Origin-Opener-Policy",   value: "same-origin" },
          { key: "Cross-Origin-Embedder-Policy", value: "credentialless" },
        ],
      },
    ];
  },
};
module.exports = nextConfig;
```

A startup-time client check in `app/page.tsx`:

```ts
useEffect(() => {
  if (!window.crossOriginIsolated) {
    setError("Cross-Origin Isolation is not active. ffmpeg.wasm cannot run.");
  }
}, []);
```

## Data Models

### Backend Pydantic models

```python
class WordTimestamp(BaseModel):
    word: str = Field(min_length=1, max_length=100)
    start: float = Field(ge=0.0)
    end: float = Field(ge=0.0)

class ShortSegment(BaseModel):
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(gt=0.0)
    title: str = Field(min_length=1, max_length=50)
    hook: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=500)
    words: list[WordTimestamp] = Field(min_length=0, max_length=1000)

class ShortsAnalysisResult(BaseModel):
    segments: list[ShortSegment] = Field(min_length=1, max_length=50)
```

### SSE message envelope

```json
{
  "step": "Transcribing",
  "progress": 60,
  "data": null,
  "error": null,
  "warning": null
}
```

When `step == "Done"`:

```json
{
  "step": "Done",
  "progress": 100,
  "data": {
    "segments": [
      {
        "start_sec": 12.34,
        "end_sec": 72.34,
        "title": "...",
        "hook": "...",
        "reason": "...",
        "words": [{"word": "Hello", "start": 12.40, "end": 12.62}, ...]
      }
    ]
  },
  "error": null
}
```

### Frontend types

```ts
export interface WordTimestamp { word: string; start: number; end: number; }
export interface ShortSegment {
  start_sec: number; end_sec: number;
  title: string; hook: string; reason: string;
  words: WordTimestamp[];
}
export interface Config {
  count: number;        // 1..10
  duration: 15 | 30 | 60;
  tone: "Funny" | "Educational" | "Motivational" | "Highlights" | "Story-driven" | "Custom";
  customTone: string;
  subtitleStyle: "TikTok-animated" | "Bold-centered-white" | "Minimal-bottom";
}
```

## Error Handling

| Failure | Detection | User-visible result | Server-side action |
|---|---|---|---|
| Invalid `shorts_count` / `duration_per_short` / `style_tone` | FastAPI manual validation | HTTP 422 + message | No workspace, no registry entry (req 1.6–1.8) |
| Empty / missing video file | UploadFile size check | HTTP 422 | No workspace, no registry entry (req 1.11) |
| Disk write fails saving upload | `OSError` in chunked write | HTTP 500 | Partial file removed; no registry entry (req 1.12) |
| Extension/size rejected client-side | `validate()` in DropZone | Inline error within 1 s | n/a (req 8.3) |
| FFmpeg subprocess fails / not on PATH / timeout 600 s | non-zero rc, `TimeoutError`, `FileNotFoundError` | SSE step="Failed" with error message | Workspace cleaned within 10 s (req 2.3, 2.14) |
| Whisper model size invalid | `WHISPER_MODEL_SIZE not in {tiny,base,small,medium,large}` | SSE warning field | Fall back to `base` (req 2.6) |
| Whisper inference exception | exception in executor | SSE step="Failed" | Workspace cleaned (req 2.14) |
| Gemini network/timeout/non-success | exception from `generate_content` | SSE step="Failed" after 3 attempts | Workspace cleaned (req 2.12) |
| `response.parsed is None` or post-parse constraint fails | `_validate_result` raises | SSE step="Failed" | Workspace cleaned (req 5.12, 5.13) |
| Pipeline stalls > 600 s | SSE coroutine compares `last_step_change` | SSE final stall message + close | Registry untouched (req 4.8) |
| Cleanup deletion fails | `_safe_delete` retries 3× | `cleanup_warning` on registry | Cleanup_Task safety net at 3600 s (req 3.6, 3.7) |
| ffmpeg.wasm load fails / 30 s timeout | `Promise.race` rejection | Inline error on page | `_initPromise = null` → next attempt retries (req 7.2) |
| `ffmpeg.exec` rejects | Promise rejection in `renderShort` | Render phase fails, page shows error | Delete `subs.ass` and `out_<i>.mp4`, keep `source.mp4` (req 7.12) |
| `ffmpeg.exec` no progress for 60 s | watchdog timer | Render phase fails | Same cleanup as above (req 7.12) |
| ZIP build fails | exception in `downloadZip` | Error indicator on ZIP button; clips preserved | n/a (req 9.14) |

The frontend treats every failure terminal: it displays the error, sets `phase = "failed"`, and re-enables the "Generate Shorts" button so the user can retry without reload (req 8.11).

## Correctness Properties

These invariants must hold at every reachable state and are derived directly from the requirements. They are the targets of the property-based and integration tests.

### Property 1: Zero residual server artifacts

For every Task_ID that has reached `Done` or `Failed` and whose SSE_Stream has closed, `/tmp/shorts_workspace/{task_id}/` contains no `input.*` and no `audio.wav` file within 10 s.

**Validates: Requirements 3.1, 3.2, 13.4**

### Property 2: Pipeline progress monotonicity

The `progress` value of any Task_Registry entry is non-decreasing over time, and `step` advances only along the path `Uploading → Extracting Audio → Transcribing → Analyzing Highlights → Done`, with `Failed` reachable from any non-terminal state.

**Validates: Requirements 2.1, 2.4, 2.8, 2.13, 2.14**

### Property 3: Segment non-overlap

For every successful pipeline result, sorting `segments` by `start_sec` yields a sequence where `segments[i].end_sec <= segments[i+1].start_sec`.

**Validates: Requirements 5.8, 5.13**

### Property 4: Segment duration bound

Every segment satisfies `0 < end_sec - start_sec <= duration_per_short`.

**Validates: Requirements 5.4, 5.13**

### Property 5: Segment count exact

`len(result.segments) == shorts_count` for every successful run.

**Validates: Requirements 5.10, 5.13**

### Property 6: Word containment

For every segment, every `WordTimestamp` in `segment.words` satisfies `segment.start_sec <= word.start` and `word.end <= segment.end_sec`, in ascending `start` order.

**Validates: Requirements 5.7**

### Property 7: ASS round-trip

For every `(words, style, segmentStart, segmentDur)` input where each word has finite `start`, `end`, and `end > start`, parsing the output of `generateAssSubtitles` yields the same word groupings, timestamps within 1 centisecond, and identical override tags.

**Validates: Requirements 6.8**

### Property 8: ASS time clamping

Every emitted ASS time value `t` satisfies `0 <= t <= segmentDurSec` regardless of input word timestamps.

**Validates: Requirements 6.3, 6.4**

### Property 9: ffmpeg.wasm serialization

At any wall-clock instant during `renderAll`, the number of in-flight `ffmpeg.exec` calls is at most 1.

**Validates: Requirements 7.10**

### Property 10: WASM heap reclamation

After every successful `renderShort(index)` call, neither `out_<index>.mp4` nor `subs.ass` exists in the WASM filesystem; `source.mp4` exists exactly when at least one segment has been rendered.

**Validates: Requirements 7.4, 7.9, 7.12**

### Property 11: drawtext escape closure

For every input title `T`, the string passed to `-vf drawtext=text='...'` contains no unescaped `'` and no unescaped `:` and is at most 200 characters.

**Validates: Requirements 7.8**

### Property 12: SSE termination

Every SSE_Stream that has emitted a message with `step == "Done"` or `step == "Failed"` is closed by the server within 1 additional second and emits no further messages.

**Validates: Requirements 4.4, 4.5**

### Property 13: Cross-origin isolation precondition

Before `initFFmpeg` resolves, `window.crossOriginIsolated === true`; if false, `init` rejects without attempting to load core assets.

**Validates: Requirements 10.3, 10.4**

### Property 14: Title sanitisation invariant

The basename used for any per-clip download or ZIP entry contains none of `\ / : * ? " < > |`, is non-empty, and is at most 100 characters; on empty post-sanitisation, the previous valid title is restored in state.

**Validates: Requirements 9.9, 9.10, 9.11**

### Property 15: ZIP uniqueness

All file names in any generated `ZIP_Bundle` are pairwise distinct.

**Validates: Requirements 9.13**

## Testing Strategy

The acceptance flow in requirement 13 is the primary integration test, but it requires a real video. The plan splits tests into unit / integration / e2e tiers.

### Unit tests

**Backend (pytest):**

- `analyze.py`: `_build_prompt` includes the chosen style profile (parametrized over the 6 tones); `Custom` embeds the literal text truncated to 1000 chars; `_validate_result` raises on count mismatch, on overlap, on duration overrun, on non-positive duration; `response.parsed is None` raises `ValueError` with the raw text.
- `transcribe.py`: `_load_model` caches by size; second call returns the same instance (mock `whisper.load_model`).
- `main.py` (using FastAPI TestClient + monkeypatched pipeline): POST returns 200 + taskId on valid input; 422 on each invalid form field; 422 on empty file; 500 on simulated disk error with partial file removed; SSE returns 404 for unknown task_id; SSE emits initial snapshot then close on `Done`.
- Cleanup: `_safe_delete` retries 3× on simulated `OSError`; scanner removes a workspace whose `created_at` is > 3600 s old.

**Frontend (vitest + jsdom + React Testing Library):**

- `DropZone.validate`: rejects `.avi`, oversize, zero-byte; accepts `.mp4`/`.mov`/`.mkv`.
- `ConfigPanel`: range slider clamps 1..10; duration buttons enforce single selection; `Custom` reveals text input; trimmed value flows to `onChange`.
- `ProgressTracker`: marks earlier steps complete and current step active; shows `Rendering Short k/N` when `renderIndex` set.
- `ResultsGrid.sanitize`: strips reserved chars; empty result becomes `"untitled"`; duplicates get `(2)` suffix in ZIP.
- `useFFmpegRenderer.generateAssSubtitles` (the most testable unit, fully synchronous):
  - TikTok style: one Dialogue per word; override tag is exactly `{\an2\c&H00FFFF&}`.
  - Bold-centered-white: 3..4 words per group; group `Start` = first word, `End` = last word.
  - Minimal-bottom: font size 48, MarginV 60.
  - Time conversion: `start - segment.start_sec`, clamped to `[0, dur]`; output format `H:MM:SS.cs`.
  - Round-trip: re-parsing the emitted ASS yields identical timestamps to within 1 cs and identical override tags (req 6.8).
  - Invalid words (missing/non-numeric/inverted) are dropped; remaining words still emit (req 6.9).
  - Zero valid words emits a syntactically complete ASS with empty `[Events]` (req 6.10).

### Integration tests

- Backend pipeline against a 5-second synthetic test fixture: a generated `test.mp4` with a known waveform. Mock Whisper to return a fixed transcript; mock Gemini client to return a fixed `ShortsAnalysisResult`. Assert the registry transitions through every step with the exact progress values, that the Done message includes `data.segments`, and that the workspace is empty within 10 s of Done.
- SSE consumer test: open EventSource against a TestClient stream; verify the cadence is ~1 s, that Done closes the stream, and that no further messages arrive.

### End-to-end

- Manual run of the requirement-13 flow with a real ~3 minute video: drop `.mp4`, configure 4 / 60 s / Motivational / TikTok, click Generate. Assert the Progress_Tracker shows the exact 9-step sequence, the Results_Grid shows 4 cards with playable previews, individual download produces an MP4 that opens in VLC, ZIP download produces an archive containing 4 MP4s, and `/tmp/shorts_workspace/<id>/` is empty within 10 s of stream close.
- Browser support smoke test: confirm `window.crossOriginIsolated === true` on Chrome 120+, Firefox 120+, Safari 17+.
- Memory check: render 6 × 60 s clips from a 1 GB source; observe the WASM heap stays bounded across iterations (no growth between segment 1 and segment 6 because outputs are deleted post-read).

### Property-based tests (selective)

`generateAssSubtitles` is a parser/serializer pair (this design generates ASS, the round-trip property is required by criterion 6.8). Use a property test that:

1. Generates random valid `WordTimestamp[]` (sorted, non-overlapping, finite).
2. Calls `generateAssSubtitles` with each Subtitle_Style.
3. Re-parses the result with a tiny ASS parser.
4. Asserts the parsed timestamps are within 1 cs of the originals (after rebasing) and override tags survive byte-identical.
