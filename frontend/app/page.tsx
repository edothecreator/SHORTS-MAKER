"use client";

import { useState, useEffect } from "react";
import type { Config, RenderedClip, SubtitleStyle } from "./types";

// Task 7.2 — Requirements: 8.10, 8.11, 10.3, 10.4

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

  // Req 10.3, 10.4: Block further actions when cross-origin isolation is
  // not active. ffmpeg.wasm requires SharedArrayBuffer which is gated
  // behind COOP/COEP.
  useEffect(() => {
    if (typeof window !== "undefined" && !window.crossOriginIsolated) {
      setError(
        "Cross-origin isolation is not active. SharedArrayBuffer is unavailable. " +
          "Ensure the app is served with COOP and COEP headers."
      );
    }
  }, []);

  // Stub onGenerate handler (Req 8.10, 8.11): validates preconditions and
  // surfaces errors within 1 second of click. The full implementation
  // (upload → SSE → render → results) lands in task 13.1.
  const onGenerate = () => {
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

    // Clear previous error and proceed (full flow wired in task 13.1).
    setError(null);
    setPhase("uploading");
  };

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

      {/* Components (DropZone, ConfigPanel, ProgressTracker, ResultsGrid)
          will be composed here in task 13.1 */}

      <button
        onClick={onGenerate}
        disabled={phase !== "idle" && phase !== "failed"}
        className="mt-6 px-6 py-3 rounded font-semibold transition-colors disabled:opacity-50"
        style={{
          background: "var(--accent)",
          color: "var(--text)",
        }}
      >
        Generate Shorts
      </button>
    </main>
  );
}
