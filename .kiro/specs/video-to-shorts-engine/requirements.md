# Requirements Document

## Introduction

The Video-to-Shorts Engine is a local-first web application that transforms long-form video into multiple short-form vertical (9:16) clips with burned-in karaoke-style subtitles and a title overlay. The system follows a "Hybrid Local-First" architecture (Strategy A): a FastAPI backend handles audio extraction, local Whisper transcription, and Gemini-based segment selection, while a Next.js frontend performs all video rendering in the browser via ffmpeg.wasm. The backend stores no persistent video data — uploaded video and extracted audio are deleted immediately after the analysis pipeline finishes. Users upload a video, configure the number, duration, tone, and subtitle style of the shorts, watch real-time progress over Server-Sent Events, then preview, edit titles, download individual MP4 clips, or export a ZIP bundle of all clips.

## Glossary

- **Shorts_Engine**: The full system, comprising backend and frontend.
- **Backend**: The FastAPI Python service exposing `/api/process-video` and `/api/stream/{task_id}`.
- **Frontend**: The Next.js 14 (App Router) web application served at `http://localhost:3000`.
- **Pipeline**: The sequential server-side process (extract audio → transcribe → analyze → cleanup).
- **Renderer**: The browser-side ffmpeg.wasm rendering subsystem invoked through the `useFFmpegRenderer` hook.
- **Task_Registry**: An in-process Python dictionary keyed by `task_id` storing pipeline phase, progress, and result.
- **Task_ID**: A UUID4 string identifying one upload-to-result session.
- **Workspace_Directory**: The per-task directory at `/tmp/shorts_workspace/{task_id}/` holding `input.{ext}` and `audio.wav` during processing only.
- **Cleanup_Task**: A background task that removes the Workspace_Directory after the Pipeline finishes and again as a safety net after 3600 seconds.
- **Whisper**: The locally executed OpenAI Whisper model used for CPU transcription with word-level timestamps.
- **Whisper_Model_Size**: A configurable model identifier from the set `{tiny, base, small, medium}`, read from the `WHISPER_MODEL_SIZE` environment variable (default `base`).
- **Gemini_Analyzer**: The component in `analyze.py` that calls Google Gemini 2.5 Flash via the `google-genai` SDK with a Pydantic response schema.
- **Short_Segment**: A single selected clip described by start time, end time, title, hook, reason, and per-word timestamps.
- **Shorts_Analysis_Result**: The Pydantic root object returned by Gemini, containing the list of Short_Segments.
- **Style_Tone**: One of `Funny`, `Educational`, `Motivational`, `Highlights`, `Story-driven`, or a free-form `Custom` string.
- **Subtitle_Style**: One of `TikTok-animated`, `Bold-centered-white`, or `Minimal-bottom`.
- **ASS_Subtitles**: An Advanced SubStation Alpha subtitle file generated client-side and burned into each rendered short.
- **SSE_Stream**: The Server-Sent Events response from `GET /api/stream/{task_id}`.
- **Drop_Zone**: The frontend component that accepts video files via drag-and-drop or file picker.
- **Config_Panel**: The frontend component that captures shorts count, duration, style/tone, and subtitle style.
- **Progress_Tracker**: The frontend component that renders the vertical pipeline timeline driven by the SSE_Stream.
- **Results_Grid**: The frontend component that displays rendered shorts in a responsive 2- or 3-column grid.
- **ZIP_Bundle**: A client-generated ZIP archive containing all rendered shorts, produced via dynamically imported JSZip.

## Requirements

### Requirement 1: Video Upload and Workspace Setup

**User Story:** As a user, I want to upload a long-form video to the Backend, so that the Shorts_Engine can analyze it and prepare it for short-form rendering.

#### Acceptance Criteria

1. WHEN the Frontend sends a POST request to `/api/process-video` with multipart fields `video_file`, `style_tone`, `shorts_count`, and `duration_per_short`, THE Backend SHALL generate a Task_ID using `uuid4()`.
2. WHEN a request is accepted, THE Backend SHALL save the uploaded video to `/tmp/shorts_workspace/{task_id}/input.{ext}` preserving the original file extension.
3. WHEN the upload is saved, THE Backend SHALL register an entry in the Task_Registry keyed by Task_ID with initial fields `step="Uploading"` and `progress=10`.
4. WHEN the upload is saved, THE Backend SHALL schedule `run_processing_pipeline(task_id)` and `cleanup_task_directory(task_id, delay=3600)` as FastAPI BackgroundTasks.
5. WHEN the BackgroundTasks are scheduled, THE Backend SHALL respond with HTTP 200 and JSON body `{"taskId": "<uuid>"}` within 5 seconds of receiving the complete upload.
6. IF `shorts_count` is not an integer in the inclusive range 1 to 10, THEN THE Backend SHALL respond with HTTP 422, SHALL NOT create a Workspace_Directory, and SHALL NOT register an entry in the Task_Registry.
7. IF `duration_per_short` is not in the set `{15, 30, 60}`, THEN THE Backend SHALL respond with HTTP 422, SHALL NOT create a Workspace_Directory, and SHALL NOT register an entry in the Task_Registry.
8. IF `style_tone` is missing, empty after trimming whitespace, or longer than 500 characters, THEN THE Backend SHALL respond with HTTP 422, SHALL NOT create a Workspace_Directory, and SHALL NOT register an entry in the Task_Registry.
9. IF the uploaded `video_file` exceeds 2 GB (2,147,483,648 bytes), THEN THE Frontend SHALL reject the upload before transmission and SHALL display an error message naming the 2 GB limit.
10. IF the uploaded file extension is not in `{.mp4, .mov, .mkv}` (case-insensitive), THEN THE Frontend SHALL reject the file before transmission and SHALL display an error message naming the supported extensions.
11. IF the multipart `video_file` field is missing or contains zero bytes, THEN THE Backend SHALL respond with HTTP 422, SHALL NOT create a Workspace_Directory, and SHALL NOT register an entry in the Task_Registry.
12. IF saving the uploaded video to the Workspace_Directory fails due to a disk write or filesystem error, THEN THE Backend SHALL respond with HTTP 500, SHALL NOT register an entry in the Task_Registry, SHALL NOT schedule BackgroundTasks, and SHALL remove any partially written files for that Task_ID.

### Requirement 2: Server-Side Processing Pipeline

**User Story:** As a user, I want the Backend to extract audio, transcribe it locally, and select highlight segments using Gemini, so that I receive accurate Short_Segments without any cloud video processing.

#### Acceptance Criteria

1. WHEN `run_processing_pipeline` begins, THE Backend SHALL update the Task_Registry entry to `step="Extracting Audio"` and `progress=25` within 1 second of pipeline start.
2. WHEN extracting audio, THE Backend SHALL invoke the system FFmpeg binary as a subprocess to produce `/tmp/shorts_workspace/{task_id}/audio.wav` encoded as 16 kHz mono PCM, with a maximum subprocess duration of 600 seconds.
3. IF the FFmpeg subprocess exits with a non-zero return code, exceeds the 600 second duration, or the binary is not found on the system PATH, THEN THE Backend SHALL terminate the pipeline and update the Task_Registry entry to `step="Failed"` with an `error` field containing a message indicating audio extraction failure and the underlying cause.
4. WHEN audio extraction completes successfully, THE Backend SHALL update the Task_Registry entry to `step="Transcribing"` and `progress=60`.
5. WHEN transcribing, THE Backend SHALL load the local Whisper model whose size is read from `WHISPER_MODEL_SIZE` (default `base`, allowed values: `tiny`, `base`, `small`, `medium`, `large`) and SHALL execute the transcription on CPU using `loop.run_in_executor` so that the FastAPI event loop is not blocked.
6. IF the value of `WHISPER_MODEL_SIZE` is not one of the allowed values, THEN THE Backend SHALL fall back to `base` and SHALL record a warning in the Task_Registry entry indicating the invalid configuration value.
7. WHEN transcription completes, THE Backend SHALL produce a list of WordTimestamp records, each containing `word: str` (length 1 to 200 characters), `start: float`, and `end: float` in seconds, where `0.0 <= start <= end` and `end` does not exceed the source media duration.
8. WHEN transcription completes, THE Backend SHALL update the Task_Registry entry to `step="Analyzing Highlights"` and `progress=75`.
9. WHEN analyzing, THE Gemini_Analyzer SHALL call Google Gemini 2.5 Flash via the `google-genai` SDK with `response_mime_type="application/json"` and `response_schema=ShortsAnalysisResult`, applying a per-call timeout of 120 seconds.
10. WHEN the Gemini response is received within the timeout, THE Gemini_Analyzer SHALL return `response.parsed` as a `ShortsAnalysisResult` instance.
11. IF `response.parsed` is `None`, THEN THE Gemini_Analyzer SHALL raise `ValueError` whose message contains the raw `response.text`.
12. IF the Gemini API call fails due to network error, timeout, rate limiting, or returns a non-success status, THEN THE Gemini_Analyzer SHALL retry up to 2 additional times with at least 2 seconds between attempts, and if all attempts fail SHALL raise an exception whose message identifies the failure category.
13. WHEN the Gemini_Analyzer returns successfully, THE Backend SHALL update the Task_Registry entry to `step="Done"`, `progress=100`, and `data=result.model_dump()`.
14. IF any pipeline phase raises an exception, THEN THE Backend SHALL update the Task_Registry entry to `step="Failed"` with an `error` field containing the exception message and SHALL delete all files and subdirectories within `/tmp/shorts_workspace/{task_id}/` such that the directory contains no residual files within 10 seconds of the failure.

### Requirement 3: Zero Permanent Server Storage

**User Story:** As a privacy-conscious user, I want the Backend to retain no copies of my video or extracted audio after processing, so that no permanent server-side artifacts exist.

#### Acceptance Criteria

1. WHEN the Pipeline reaches the `step="Done"` state, THE Backend SHALL delete `/tmp/shorts_workspace/{task_id}/input.{ext}` and `/tmp/shorts_workspace/{task_id}/audio.wav` within 5 seconds and before the SSE_Stream closes.
2. WHEN the Pipeline reaches the `step="Failed"` state, THE Backend SHALL delete any present `input.{ext}` and `audio.wav` within the Workspace_Directory within 5 seconds of entering the Failed state.
3. WHEN 3600 seconds have elapsed since the Workspace_Directory was created, THE Cleanup_Task SHALL remove the Workspace_Directory recursively as a safety net regardless of pipeline state.
4. THE Backend SHALL NOT write video, audio, or transcript files to any directory outside `/tmp/shorts_workspace/{task_id}/`.
5. THE Backend SHALL NOT persist Short_Segment data, transcripts, or video content to any database, to any remote storage endpoint, or to any disk location outside the Workspace_Directory at any point during or after Pipeline execution.
6. IF deletion of `input.{ext}` or `audio.wav` fails during terminal-state cleanup, THEN THE Backend SHALL retry the deletion up to 3 times with at least 1 second between attempts and surface a cleanup failure indication on the SSE_Stream before relying on the Cleanup_Task safety net.
7. THE Cleanup_Task SHALL scan `/tmp/shorts_workspace/` for expired Workspace_Directory entries at intervals not exceeding 300 seconds.

### Requirement 4: Server-Sent Events Progress Streaming

**User Story:** As a user, I want to watch real-time progress updates while the Backend processes my video, so that I know each phase is advancing.

#### Acceptance Criteria

1. WHEN the Frontend opens an EventSource against `GET /api/stream/{task_id}` for a Task_ID present in the Task_Registry, THE Backend SHALL respond within 2 seconds with HTTP 200, `Content-Type: text/event-stream`, `Cache-Control: no-cache`, and `Connection: keep-alive`.
2. WHEN the SSE_Stream is established, THE Backend SHALL emit the current Task_Registry entry as the first SSE message in the form `data: <json>\n\n` within 1 second of connection acceptance.
3. WHILE the Task_Registry entry exists and `step` is neither `Done` nor `Failed`, THE Backend SHALL emit one SSE message every 1 second (±200 ms) containing `data: <json>\n\n` where `<json>` is the JSON serialization of the Task_Registry entry.
4. WHEN the Task_Registry `step` becomes `Done`, THE Backend SHALL emit, within 1 second of the transition, one final SSE message containing the full result `data` field and SHALL close the SSE_Stream within 1 additional second.
5. WHEN the Task_Registry `step` becomes `Failed`, THE Backend SHALL emit, within 1 second of the transition, one final SSE message containing the `error` field and SHALL close the SSE_Stream within 1 additional second.
6. IF the requested Task_ID is not present in the Task_Registry, THEN THE Backend SHALL respond with HTTP 404 and SHALL NOT open an SSE_Stream.
7. WHEN the Frontend client disconnects from an active SSE_Stream, THE Backend SHALL stop emitting messages for that stream and release associated resources within 5 seconds.
8. IF the Task_Registry `step` does not advance for 600 consecutive seconds while the SSE_Stream is open, THEN THE Backend SHALL emit one final SSE message indicating a stall error and SHALL close the SSE_Stream within 1 additional second, leaving the Task_Registry entry unchanged.
9. THE Backend SHALL include the response header `Access-Control-Allow-Origin: http://localhost:3000` on every HTTP response (including 2xx, 4xx, and 5xx) returned from `/api/process-video` and `/api/stream/{task_id}`.

### Requirement 5: Gemini Response Schema Enforcement

**User Story:** As a developer, I want the Gemini response to be enforced by a strict Pydantic schema, so that downstream rendering code can rely on structured Short_Segment data.

#### Acceptance Criteria

1. THE Gemini_Analyzer SHALL define a Pydantic model `WordTimestamp` with fields `word: str` (length 1 to 100 characters), `start: float` (greater than or equal to 0.0), and `end: float` (greater than or equal to `start`).
2. THE Gemini_Analyzer SHALL define a Pydantic model `ShortSegment` with fields `start_sec: float` (greater than or equal to 0.0), `end_sec: float` (strictly greater than `start_sec`), `title: str` (length 1 to 50 characters), `hook: str` (length 1 to 200 characters), `reason: str` (length 1 to 500 characters), and `words: list[WordTimestamp]` (length 1 to 1000 items).
3. THE Gemini_Analyzer SHALL define a Pydantic model `ShortsAnalysisResult` with field `segments: list[ShortSegment]` (length 1 to 50 items).
4. WHEN constructing the prompt, THE Gemini_Analyzer SHALL instruct Gemini that `end_sec - start_sec` MUST be greater than 0.0 seconds and less than or equal to the user's `duration_per_short` value in seconds.
5. WHEN constructing the prompt, THE Gemini_Analyzer SHALL instruct Gemini that `title` MUST be between 1 and 50 characters inclusive and SHALL contain no `#` characters.
6. WHEN constructing the prompt, THE Gemini_Analyzer SHALL instruct Gemini that `hook` MUST be the first 5 whitespace-separated words of the segment's spoken content, joined by single spaces.
7. WHEN constructing the prompt, THE Gemini_Analyzer SHALL instruct Gemini that the `words` list MUST contain every transcribed word whose `start` is greater than or equal to `start_sec` and whose `end` is less than or equal to `end_sec`, in ascending `start` order, with `word`, `start`, and `end` values preserved exactly from the Whisper output.
8. WHEN constructing the prompt, THE Gemini_Analyzer SHALL instruct Gemini that for any two segments A and B in the result, the intervals `[A.start_sec, A.end_sec]` and `[B.start_sec, B.end_sec]` MUST NOT overlap (i.e., `A.end_sec <= B.start_sec` or `B.end_sec <= A.start_sec`).
9. WHEN constructing the prompt, THE Gemini_Analyzer SHALL include a style profile section that maps each Style_Tone option (`Funny`, `Educational`, `Motivational`, `Highlights`, `Story-driven`) to its selection criteria, and for the `Custom` Style_Tone SHALL embed the user-provided text (truncated to 1000 characters if longer) literally as the selection criterion.
10. WHEN constructing the prompt, THE Gemini_Analyzer SHALL instruct Gemini to return exactly `shorts_count` segments, where `shorts_count` is an integer between 1 and 50 inclusive.
11. WHEN parsing the Gemini response, THE Gemini_Analyzer SHALL return the value of `response.parsed` typed as `ShortsAnalysisResult`.
12. IF `response.parsed` is `None` or Pydantic validation of the response fails, THEN THE Gemini_Analyzer SHALL raise `ValueError` with an error message indicating the parse failure and including the raw `response.text` content, and SHALL NOT return a partial result.
13. WHEN `response.parsed` is successfully obtained, THE Gemini_Analyzer SHALL validate that the number of returned segments equals `shorts_count`, that no two segments overlap in time per criterion 8, and that every segment satisfies `end_sec - start_sec <= duration_per_short`, and IF any of these post-parse checks fail, THEN THE Gemini_Analyzer SHALL raise `ValueError` with an error message identifying which constraint was violated.
14. IF the Gemini API call does not return a response within 120 seconds or fails with a network or service error, THEN THE Gemini_Analyzer SHALL raise an exception indicating the API failure cause and SHALL NOT return a `ShortsAnalysisResult`.

### Requirement 6: Round-Trip ASS Subtitle Generation

**User Story:** As a user, I want each rendered short to display burned-in karaoke-style subtitles, so that the captions match the spoken words frame-accurately.

#### Acceptance Criteria

1. WHEN the Renderer prepares a Short_Segment, THE Renderer SHALL generate a complete ASS_Subtitles string encoded as UTF-8 containing a `[Script Info]` section with `PlayResX: 1080` and `PlayResY: 1920`, a `[V4+ Styles]` section, and an `[Events]` section.
2. THE Renderer SHALL define a default style using font `Arial Black`, font size `72`, primary colour white, secondary colour yellow, `BorderStyle 1`, `Outline 4`, `Shadow 2`, `Alignment 2`, and `MarginV 120`.
3. WHEN emitting `[Events]` Dialogue lines, THE Renderer SHALL convert every word's `start` and `end` timestamps from absolute video time to clip-relative time by subtracting `segment.start_sec` and SHALL clamp resulting values to the inclusive range `[0, segment.duration_sec]`.
4. THE Renderer SHALL format every ASS time value as `H:MM:SS.cs` where `cs` is centiseconds expressed as exactly two digits, with each emitted timestamp differing from the source word timestamp by no more than 10 milliseconds.
5. WHERE Subtitle_Style is `TikTok-animated`, THE Renderer SHALL emit one Dialogue line per word and SHALL apply the override `{\an2\c&H00FFFF&}` to highlight the current word in yellow.
6. WHERE Subtitle_Style is `Bold-centered-white`, THE Renderer SHALL group 3 to 4 words per Dialogue line and SHALL render them centered using the bold white default style.
7. WHERE Subtitle_Style is `Minimal-bottom`, THE Renderer SHALL group 3 to 4 words per Dialogue line using a font size of 48 aligned to the bottom of the frame.
8. THE Renderer SHALL produce ASS_Subtitles such that re-parsing the emitted string yields word groupings, timestamps within 1 centisecond, and override tags byte-identical to those generated.
9. IF a word entry is missing a `start` or `end` field, contains a non-numeric timestamp, or has `end` less than or equal to `start`, THEN THE Renderer SHALL omit that word from the Dialogue output and SHALL record a validation error indicating the offending word index while continuing to emit remaining valid words.
10. IF the Short_Segment contains zero valid words after validation, THEN THE Renderer SHALL still emit a syntactically complete ASS_Subtitles string with `[Script Info]` and `[V4+ Styles]` sections and an empty `[Events]` section, and SHALL return an indication that no subtitles were produced.

### Requirement 7: Browser-Side Rendering with ffmpeg.wasm

**User Story:** As a user, I want all video rendering to happen in my browser, so that the server never receives or stores rendered output.

#### Acceptance Criteria

1. WHEN the Renderer is first invoked in a browser session, THE Renderer SHALL initialize `@ffmpeg/ffmpeg` v0.12 or higher with `@ffmpeg/core@0.12.6` UMD assets loaded via `toBlobURL` from `https://unpkg.com` within 30 seconds.
2. IF initialization of ffmpeg.wasm fails or exceeds 30 seconds, THEN THE Renderer SHALL reject the initialization promise with an error indicating ffmpeg load failure and SHALL allow a subsequent invocation to retry initialization.
3. THE Renderer SHALL initialize ffmpeg.wasm exactly once per browser session and SHALL reuse the initialized instance for every Short_Segment.
4. WHEN rendering the first Short_Segment of a session, THE Renderer SHALL write the source video as `source.mp4` into the WASM filesystem and SHALL reuse it for every subsequent Short_Segment without rewriting it.
5. IF the source video size exceeds 2 GB or the available WASM memory is insufficient to load it, THEN THE Renderer SHALL reject the render request with an error indicating source video too large and SHALL NOT invoke ffmpeg.
6. WHEN rendering a Short_Segment, THE Renderer SHALL write the segment's ASS_Subtitles as `subs.ass` into the WASM filesystem before invoking ffmpeg.
7. WHEN invoking ffmpeg, THE Renderer SHALL pass arguments equivalent to `-ss <start_sec> -i source.mp4 -t <duration> -vf "crop=ih*(9/16):ih,subtitles=subs.ass,drawtext=text='<escaped_title>':x=(w-text_w)/2:y=80:fontsize=52:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=12" -c:v libx264 -preset ultrafast -crf 23 -c:a aac -b:a 128k -movflags +faststart out_<index>.mp4`, where `<start_sec>` and `<duration>` are non-negative numbers in seconds with up to 3 decimal places and `<index>` is a non-negative integer.
8. WHEN escaping the title for `drawtext`, THE Renderer SHALL replace every `'` with `\'` and every `:` with `\:` and SHALL truncate the resulting escaped title to a maximum of 200 characters.
9. WHEN ffmpeg completes a segment successfully, THE Renderer SHALL read `out_<index>.mp4` from the WASM filesystem, return it as a `Blob` of MIME type `video/mp4`, and SHALL delete `out_<index>.mp4` and `subs.ass` from the WASM filesystem before resolving.
10. THE Renderer SHALL render Short_Segments strictly sequentially and SHALL NOT issue a second `ffmpeg.exec` call until the previous call's promise has either resolved or rejected.
11. WHILE a Short_Segment is rendering, THE Renderer SHALL invoke the `onProgress(index, ratio)` callback with `ratio` values reported by ffmpeg's progress events, where `ratio` is a number in the range 0.0 to 1.0 inclusive.
12. IF `ffmpeg.exec` rejects or no progress event is received for 60 consecutive seconds, THEN THE Renderer SHALL propagate an error to the caller indicating render failure and SHALL delete `subs.ass` and `out_<index>.mp4` (if present) from the WASM filesystem while retaining `source.mp4` for subsequent segments.

### Requirement 8: Frontend Configuration and Drop Zone

**User Story:** As a user, I want a configuration panel and drop zone, so that I can choose how my shorts are generated.

#### Acceptance Criteria

1. THE Drop_Zone SHALL accept files via drag-and-drop and via a click-to-browse file picker, and SHALL accept exactly one file per submission.
2. THE Drop_Zone SHALL accept only files with extensions in `{.mp4, .mov, .mkv}` and sizes greater than 0 bytes and up to 2,147,483,648 bytes (2 GB) inclusive.
3. IF a file is provided whose extension is not in `{.mp4, .mov, .mkv}` or whose size is 0 bytes or exceeds 2,147,483,648 bytes, THEN THE Drop_Zone SHALL reject the file, SHALL NOT update the selected video state, and SHALL display a visible error indication identifying the rejection reason (unsupported type or size limit exceeded) within 1 second of the drop or selection event.
4. THE Config_Panel SHALL expose a slider for `shorts_count` constrained to integers from 1 to 10 inclusive, with a default value of 3.
5. THE Config_Panel SHALL expose three buttons for `duration_per_short` representing the values 15, 30, and 60 seconds, of which exactly one SHALL be selected at any time, with 30 selected by default.
6. THE Config_Panel SHALL expose a Style_Tone selector listing `Funny`, `Educational`, `Motivational`, `Highlights`, `Story-driven`, and `Custom`, of which exactly one SHALL be selected at any time.
7. WHERE the Style_Tone is `Custom`, THE Config_Panel SHALL display a text input accepting between 1 and 200 characters after trimming leading and trailing whitespace, whose trimmed value becomes the `style_tone` field sent to the Backend.
8. THE Config_Panel SHALL expose a Subtitle_Style selector listing `TikTok-animated`, `Bold-centered-white`, and `Minimal-bottom`, of which exactly one SHALL be selected at any time.
9. WHEN the user clicks "Generate Shorts" with a valid selected video and all required fields populated, THE Frontend SHALL POST the selected video, `style_tone`, `shorts_count`, `duration_per_short`, and `subtitle_style` to `/api/process-video` within 500 milliseconds of the click.
10. IF the user clicks "Generate Shorts" while no video is selected, or while Style_Tone is `Custom` with a trimmed value of fewer than 1 character, THEN THE Frontend SHALL NOT issue the POST request and SHALL display a visible error indication identifying the missing or invalid field within 1 second of the click.
11. IF the POST to `/api/process-video` fails due to a network error or a non-2xx response, THEN THE Frontend SHALL display a visible error indication identifying the failure and SHALL re-enable the "Generate Shorts" control within 2 seconds of the failure being detected.
12. WHEN the Backend responds with a 2xx response containing `{"taskId": "<uuid>"}`, THE Frontend SHALL open an EventSource against `/api/stream/{task_id}` within 500 milliseconds of receiving the response.

### Requirement 9: Progress Tracker and Results Grid

**User Story:** As a user, I want to see pipeline progress and then preview, retitle, and download my generated shorts, so that I can quickly use the output.

#### Acceptance Criteria

1. THE Progress_Tracker SHALL display a vertical timeline with the labels `Uploading`, `Extracting Audio`, `Transcribing`, `Analyzing Highlights`, `Rendering Short k/N`, and `Done`, where `k` is an integer from 1 to `N` and `N` is the total number of Short_Segments to render (1 to 20).
2. WHEN an SSE message updates the `step` field to a recognized label, THE Progress_Tracker SHALL mark all earlier steps as complete, mark the named step as active, and mark all later steps as pending within 500 ms of message receipt.
3. IF an SSE message contains a `step` value that does not match any defined label, THEN THE Progress_Tracker SHALL retain the previously active step and display an error indicator next to the timeline indicating an unknown pipeline step.
4. IF no SSE message is received for 60 seconds while a step is active, THEN THE Progress_Tracker SHALL display an error indicator on the active step indicating that progress updates have stalled.
5. WHILE the Renderer is rendering segment `k` of `N`, THE Progress_Tracker SHALL display the label `Rendering Short k/N` with the current values of `k` and `N` substituted as integers.
6. WHEN every Short_Segment has been rendered successfully, THE Frontend SHALL hide the Progress_Tracker and show the Results_Grid within 1 second.
7. THE Results_Grid SHALL display Short_Segments in a responsive layout of 2 columns on viewports narrower than 1024 px and 3 columns at viewports 1024 px or wider.
8. THE Results_Grid SHALL render each card with an inline-editable title displayed in amber, the `hook` label, a 9:16 aspect-ratio `<video>` preview of the rendered Blob, and an individual download button.
9. THE Results_Grid SHALL enforce that each editable title is a non-empty string between 1 and 100 characters and SHALL reject input exceeding 100 characters by truncating to the limit.
10. WHEN the user commits a title edit in the Results_Grid, THE Frontend SHALL update the in-memory title for that segment and SHALL use the updated title, sanitized of filesystem-reserved characters, as the basename of the file produced by the individual download button.
11. IF a committed title is empty after sanitization, THEN THE Frontend SHALL revert the title to its previous value and display an error indicator on the affected card indicating an invalid title.
12. THE Results_Grid SHALL display a "Download All as ZIP" button that is enabled only while every Short_Segment has a valid title and a non-null rendered Blob.
13. WHEN the user clicks "Download All as ZIP", THE Frontend SHALL dynamically import `jszip`, build a ZIP_Bundle containing every rendered Blob using each segment's current sanitized title as the file basename, ensure file name uniqueness within the bundle by appending a numeric suffix to duplicates, and trigger a single download within 10 seconds for up to 20 segments totaling up to 2 GB.
14. IF building the ZIP_Bundle fails or the dynamic import of `jszip` fails, THEN THE Frontend SHALL display an error indicator on the "Download All as ZIP" button indicating the bundle could not be created and SHALL retain all in-memory Blobs and titles unchanged.

### Requirement 10: Cross-Origin Isolation Headers

**User Story:** As a developer, I want the Frontend to be served with COOP and COEP headers, so that ffmpeg.wasm can use SharedArrayBuffer.

#### Acceptance Criteria

1. WHEN the Frontend serves any HTTP response for any route, THE Frontend SHALL include the response header `Cross-Origin-Opener-Policy` with the value `same-origin`, configured via `next.config.js`.
2. WHEN the Frontend serves any HTTP response for any route, THE Frontend SHALL include the response header `Cross-Origin-Embedder-Policy` with the value `credentialless`, configured via `next.config.js`.
3. WHEN the Frontend has finished loading any route in a browser, THE Frontend SHALL expose `window.crossOriginIsolated` as `true` so that `SharedArrayBuffer` is available to ffmpeg.wasm.
4. IF a response is served without both required cross-origin isolation headers present and with their exact specified values, THEN THE Frontend SHALL fail its startup health check and surface an error indicating that cross-origin isolation is not active, without serving application routes.

### Requirement 11: Theming and Branding

**User Story:** As a user, I want a consistent dark visual theme, so that the application is easy to use during long editing sessions.

#### Acceptance Criteria

1. THE Frontend SHALL define the following CSS variables in `app/globals.css`: `--bg: #0a0a0a`, `--surface: #111111`, `--border: #1f1f1f`, `--accent: #f59e0b`, `--accent-hover: #d97706`, `--text: #f5f5f5`, `--muted: #6b7280`, `--success: #10b981`, `--error: #ef4444`.
2. THE Frontend SHALL set the document title to `Shorts Engine Studio` on every page of the application.
3. THE Frontend SHALL apply `--bg` as the page background color and `--text` as the default foreground text color consistently on every page of the application.

### Requirement 12: Project Structure and Tooling Constraints

**User Story:** As a developer, I want a fixed project structure and a strict allowed-dependencies list, so that the implementation matches the Hybrid Local-First architecture.

#### Acceptance Criteria

1. THE Backend SHALL be located in a top-level `backend/` directory containing exactly the files `main.py`, `transcribe.py`, `analyze.py`, `requirements.txt`, and `.env.example` at the directory root.
2. THE Frontend SHALL be located in a top-level `frontend/` directory containing `next.config.js`, `package.json`, `tsconfig.json`, `app/layout.tsx`, `app/page.tsx`, `app/globals.css`, and an `app/components/` directory containing the components `DropZone`, `ConfigPanel`, `ProgressTracker`, `ResultsGrid`, and `useFFmpegRenderer`.
3. THE repository SHALL contain a top-level `README.md` file.
4. THE Backend `requirements.txt` SHALL declare exactly the following packages and no other runtime packages: `fastapi`, `uvicorn`, `python-multipart`, `python-dotenv`, `openai-whisper`, `google-genai`, and `pydantic`.
5. THE Frontend `package.json` runtime dependencies (non-React and non-Next.js) SHALL declare exactly the following packages and no others: `@ffmpeg/ffmpeg` (>= 0.12), `@ffmpeg/util`, `jszip`, `tailwindcss`, and `typescript`.
6. THE Backend SHALL load configuration at startup from a `.env` file via `python-dotenv` and SHALL require both keys `GOOGLE_API_KEY` (non-empty string) and `WHISPER_MODEL_SIZE` (non-empty string, one of the sizes supported by `openai-whisper`).
7. THE Backend SHALL be runnable via a single `uvicorn` invocation on the host machine without requiring Docker, and the repository SHALL NOT require a `Dockerfile` or `docker-compose.yml` to start the Backend.
8. THE Frontend SHALL be runnable via `npm run dev` on the host machine without requiring Docker, and the repository SHALL NOT require a `Dockerfile` or `docker-compose.yml` to start the Frontend.
9. THE Shorts_Engine SHALL NOT include any code path that downloads media from YouTube, invokes `yt-dlp`, or accepts a remote URL as the upload source.
10. THE Shorts_Engine SHALL NOT call any paid third-party video processing API, including but not limited to Shotstack, Cloudinary Video, and Creatomate.
11. THE Shorts_Engine SHALL NOT call the OpenAI HTTP API, and all transcription SHALL be performed exclusively by the local `openai-whisper` model executing on CPU.
12. THE Backend SHALL configure CORS to allow exactly the single origin `http://localhost:3000` and SHALL reject requests from any other origin with a CORS failure response.
13. IF the Backend starts and either `GOOGLE_API_KEY` or `WHISPER_MODEL_SIZE` is missing or empty in the loaded environment, THEN THE Backend SHALL abort startup within 5 seconds and emit an error indicating which required environment key is missing or empty.
14. IF any file or component listed in criteria 1, 2, or 3 is absent at repository root, THEN THE repository SHALL be considered non-conformant and a structure-validation check SHALL fail with an error indicating which expected path is missing.

### Requirement 13: Acceptance End-to-End Flow

**User Story:** As a user, I want a single end-to-end flow that produces shorts and leaves no server-side files, so that I can verify the system works as designed.

#### Acceptance Criteria

1. WHEN a user opens `http://localhost:3000`, drops a `.mp4` file, configures `shorts_count=4`, `duration_per_short=60`, `style_tone=Motivational`, and `subtitle_style=TikTok-animated`, and clicks "Generate Shorts", THE Shorts_Engine SHALL display Progress_Tracker steps in this exact sequence with each step transitioning to the next within 2 seconds of its underlying operation completing: `Uploading`, `Extracting Audio`, `Transcribing`, `Analyzing Highlights`, `Rendering Short 1/4`, `Rendering Short 2/4`, `Rendering Short 3/4`, `Rendering Short 4/4`, `Done`.
2. WHEN the Pipeline reaches `Done`, THE Results_Grid SHALL display exactly 4 cards within 3 seconds, each containing an editable title field accepting 1 to 100 characters, a `<video>` element rendered at a 9:16 aspect ratio that loads and plays the rendered short on user activation, and an individual download button that delivers a single MP4 file on click.
3. WHEN the user clicks "Download All as ZIP" after the Results_Grid is shown, THE Frontend SHALL initiate delivery of one ZIP_Bundle containing exactly 4 MP4 files within 5 seconds of the click.
4. WHEN the Pipeline has reached `Done` and the SSE_Stream has closed, THE directory `/tmp/shorts_workspace/{task_id}/` SHALL contain no `input.*` files and no `audio.wav` files within 10 seconds of stream closure.
5. IF any Pipeline step fails before reaching `Done`, THEN THE Shorts_Engine SHALL display an error indication on the Progress_Tracker identifying the failed step, halt all subsequent steps, and close the SSE_Stream.
6. IF the Pipeline terminates due to error or user cancellation before reaching `Done`, THEN THE Shorts_Engine SHALL remove all `input.*` files and `audio.wav` files from `/tmp/shorts_workspace/{task_id}/` within 10 seconds of termination.
