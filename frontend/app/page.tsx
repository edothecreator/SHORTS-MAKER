"use client";

import { useState, useEffect, useCallback } from "react";
import type { Config, RenderedClip, ShortSegment } from "./types";
import DropZone from "./components/DropZone";
import ConfigPanel from "./components/ConfigPanel";
import ProgressTracker from "./components/ProgressTracker";
import ResultsGrid from "./components/ResultsGrid";
import { renderAll } from "./components/useFFmpegRenderer";

// Task 13.1 — Requirements: 8.9, 8.11, 8.12, 9.6, 13.1, 13.2, 13.5

export type Phase =
  | "idle"
  | "uploading"
  | "processing"
  | "rendering"
  | "done"
  | "failed";

const DEFAULT_CONFIG: Config = {
  shortsCount: 3,
  durationPerShort: 30,
  styleTone: "Highlights",
  customTone: "",
  subtitleStyle: "TikTok-animated",
};

const API_BASE = "http://localhost:8000";

export default function Home() {
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [config, setConfig] = useState<Config>(DEFAULT_CONFIG);
  const [phase, setPhase] = useState<Phase>("idle");
  const [step, setStep] = useState<string>("");
  const [progress, setProgress] = useState<number>(0);
  const [renderIndex, setRenderIndex] = useState<{
    k: number;
    n: number;
  } | null>(null);
  const [clips, setClips] = useState<RenderedClip[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Req 10.3, 10.4: Block when cross-origin isolation is not active.
  useEffect(() => {
    if (typeof window !== "undefined" && !window.crossOriginIsolated) {
      setError(
        "Cross-origin isolation is not active. SharedArrayBuffer is unavailable. " +
          "Ensure the app is served with COOP and COEP headers."
      );
    }
  }, []);

  // SSE consumer: resolves on Done, rejects on Failed.
  const streamUntilDone = useCallback(
    (taskId: string): Promise<ShortSegment[]> => {
      return new Promise((resolve, reject) => {
        const es = new EventSource(`${API_BASE}/api/stream/${taskId}`);

        es.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            setStep(data.step || "");
            setProgress(data.progress || 0);

            if (data.step === "Done") {
              es.close();
              const segments: ShortSegment[] = data.data?.segments || [];
              resolve(segments);
            } else if (data.step === "Failed") {
              es.close();
              reject(new Error(data.error || "Pipeline failed"));
            }
          } catch (err) {
            // Ignore parse errors on individual frames.
          }
        };

        es.onerror = () => {
          es.close();
          reject(new Error("SSE connection lost"));
        };
      });
    },
    []
  );

  // Main orchestrator: upload → SSE → render → results.
  const onGenerate = useCallback(async () => {
    // Block if cross-origin isolation failed.
    if (typeof window !== "undefined" && !window.crossOriginIsolated) {
      setError("Cannot proceed: cross-origin isolation is not active.");
      return;
    }

    // Validate: video must be selected.
    if (!videoFile) {
      setError("Please select a video file before generating.");
      return;
    }

    // Validate: Custom tone must be non-empty after trim.
    if (
      config.styleTone === "Custom" &&
      config.customTone.trim().length === 0
    ) {
      setError(
        "Please enter a custom style/tone description before generating."
      );
      return;
    }

    // Clear state and start.
    setError(null);
    setClips([]);
    setRenderIndex(null);
    setPhase("uploading");
    setStep("Uploading");
    setProgress(10);

    try {
      // ---- 1) Upload ----
      const formData = new FormData();
      formData.append("video_file", videoFile);
      formData.append("shorts_count", String(config.shortsCount));
      formData.append("duration_per_short", String(config.durationPerShort));
      formData.append(
        "style_tone",
        config.styleTone === "Custom" ? config.customTone.trim() : config.styleTone
      );

      const uploadRes = await fetch(`${API_BASE}/api/process-video`, {
        method: "POST",
        body: formData,
      });

      if (!uploadRes.ok) {
        const body = await uploadRes.json().catch(() => ({}));
        throw new Error(body.detail || `Upload failed (HTTP ${uploadRes.status})`);
      }

      const { taskId } = await uploadRes.json();

      // ---- 2) SSE streaming ----
      setPhase("processing");
      const segments = await streamUntilDone(taskId);

      // ---- 3) Render in browser ----
      setPhase("rendering");
      setStep("Rendering");

      const renderedClips = await renderAll(
        segments,
        videoFile,
        config.subtitleStyle,
        (k, n) => {
          setRenderIndex({ k, n });
          setStep("Rendering");
        },
        (k, ratio) => {
          setProgress(Math.round(ratio * 100));
        }
      );

      // ---- 4) Done ----
      setClips(renderedClips);
      setPhase("done");
      setStep("Done");
      setProgress(100);
      setRenderIndex(null);
    } catch (err) {
      setPhase("failed");
      setError(err instanceof Error ? err.message : "An unexpected error occurred");
    }
  }, [videoFile, config, streamUntilDone]);

  const isWorking = phase === "uploading" || phase === "processing" || phase === "rendering";

  return (
    <main className="min-h-screen p-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-8" style={{ color: "var(--text)" }}>
        Shorts Engine Studio
      </h1>

      {error && (
        <div
          className="mb-4 p-3 rounded border"
          style={{
            borderColor: "var(--error)",
            color: "var(--error)",
            background: "var(--surface)",
          }}
        >
          {error}
        </div>
      )}

      {/* File selection */}
      <div className="mb-6">
        <DropZone onFileSelected={setVideoFile} disabled={isWorking} />
      </div>

      {/* Configuration */}
      <div className="mb-6">
        <ConfigPanel
          config={config}
          onChange={setConfig}
          disabled={isWorking}
        />
      </div>

      {/* Generate button */}
      <button
        onClick={onGenerate}
        disabled={isWorking}
        className="mb-6 px-6 py-3 rounded font-semibold transition-colors disabled:opacity-50"
        style={{
          background: "var(--accent)",
          color: "var(--text)",
        }}
      >
        {isWorking ? "Processing..." : "Generate Shorts"}
      </button>

      {/* Progress tracker (visible when working) */}
      {isWorking && (
        <div className="mb-6">
          <ProgressTracker currentStep={step} renderIndex={renderIndex} />
        </div>
      )}

      {/* Results grid (visible when done) */}
      {phase === "done" && clips.length > 0 && (
        <div className="mt-8">
          <ResultsGrid clips={clips} />
        </div>
      )}
    </main>
  );
}
