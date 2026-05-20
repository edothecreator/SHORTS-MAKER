# Shorts Engine Studio

A local-first web application that transforms long-form video into multiple short-form vertical (9:16) clips with burned-in karaoke-style subtitles and a title overlay.

## Architecture

- **Backend**: FastAPI Python service (`backend/`) — handles audio extraction, local Whisper transcription, and Gemini-based segment selection
- **Frontend**: Next.js 14 App Router (`frontend/`) — handles all video rendering via ffmpeg.wasm in the browser

## Prerequisites

- **Node.js** 20+
- **Python** 3.11+
- **System FFmpeg** on PATH (used by the backend for audio extraction)
- **Modern browser** with cross-origin isolation support (Chromium, Firefox, or Safari)

## Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and set:
#   GOOGLE_API_KEY=<your Gemini API key>
#   WHISPER_MODEL_SIZE=base

# Start the server
uvicorn backend.main:app --port 8000
```

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The app will be available at `http://localhost:3000`. No Docker required.

## Whisper Model Sizes

| Size | Parameters | VRAM (approx) | CPU Time (1 min audio) | Accuracy |
|------|-----------|---------------|------------------------|----------|
| `tiny` | 39M | ~1 GB | ~10s | Basic |
| `base` | 74M | ~1 GB | ~20s | Good (default) |
| `small` | 244M | ~2 GB | ~60s | Better |
| `medium` | 769M | ~5 GB | ~120s | Great |
| `large` | 1550M | ~10 GB | ~300s | Best |

Set `WHISPER_MODEL_SIZE` in your `.env` file. Invalid values fall back to `base` with a warning.

## How It Works

1. **Upload** — Drop a video file (.mp4, .mov, .mkv, max 2 GB)
2. **Configure** — Choose number of shorts, duration, style/tone, subtitle style
3. **Process** — Backend extracts audio → transcribes with Whisper → selects highlights with Gemini
4. **Render** — Browser cuts segments, burns subtitles, and overlays titles via ffmpeg.wasm
5. **Download** — Preview, retitle, download individually or as a ZIP bundle

## Common Issues

### Cross-Origin Isolation Not Active
The app requires `SharedArrayBuffer` for ffmpeg.wasm. Verify in your browser console:
```js
window.crossOriginIsolated // should be true
```
If `false`, ensure you're accessing via `http://localhost:3000` where the COOP/COEP headers are served by `next.config.js`.

### Whisper First-Run Download
The first transcription triggers a model download (~150 MB for `base`). This is cached on disk for subsequent runs. Allow extra time on the first pipeline execution.

### Gemini Schema Parse Errors
If Gemini returns malformed JSON, the backend retries up to 3 times with 2s backoff. Persistent failures surface in the SSE stream as `step="Failed"` with the error message.

### CORS Rejection
The backend only allows requests from `http://localhost:3000`. If you're running the frontend on a different port or domain, update `_ALLOWED_ORIGIN` in `backend/main.py`.

## Project Structure

```
SHORTS-MAKER/
├── backend/
│   ├── main.py          # FastAPI app, routes, pipeline, SSE, cleanup
│   ├── transcribe.py    # Whisper transcription wrapper
│   ├── analyze.py       # Gemini highlight analyzer
│   ├── requirements.txt
│   ├── .env.example
│   └── tests/           # Backend test suite
├── frontend/
│   ├── app/
│   │   ├── page.tsx         # Orchestrator page
│   │   ├── layout.tsx       # Root layout
│   │   ├── globals.css      # Theme variables + Tailwind
│   │   ├── types.ts         # Shared TypeScript types
│   │   └── components/
│   │       ├── DropZone.tsx
│   │       ├── ConfigPanel.tsx
│   │       ├── ProgressTracker.tsx
│   │       ├── ResultsGrid.tsx
│   │       └── useFFmpegRenderer.ts
│   ├── next.config.js   # COOP/COEP headers
│   ├── package.json
│   ├── tailwind.config.js
│   └── tsconfig.json
└── README.md
```

## License

Private project.
