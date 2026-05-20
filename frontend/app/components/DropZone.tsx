"use client";

import { useState, useRef, useCallback } from "react";

// Task 8.1 — Requirements: 1.9, 1.10, 8.1, 8.2, 8.3
//
// ─── Task 12.1: URL Input Field (Frontend Integration Plan) ───────────────────
// This DropZone component will be extended to include a URL input field alongside
// the existing file upload. Implementation notes:
//
// 1. Add a tabbed interface or "OR" divider below the drag-and-drop zone:
//    - Tab 1 / Section 1: File Upload (existing drag & drop)
//    - Tab 2 / Section 2: URL Input (text field + "Process" button)
//
// 2. URL Input field requirements:
//    - Text input with placeholder: "Paste YouTube, Vimeo, Twitter/X, Instagram, or TikTok URL"
//    - "Process URL" button (disabled until valid URL pattern detected)
//    - Client-side pattern validation for supported platforms before sending to backend
//    - Display copyright disclaimer (from backend COPYRIGHT_DISCLAIMER) with checkbox
//    - User must accept terms before URL processing begins
//
// 3. On submit:
//    - Call backend POST /api/v1/download/validate with the URL
//    - Show video metadata (title, duration) in a confirmation card
//    - Check duration against plan limits (displayed from backend response)
//    - On confirm, call POST /api/v1/download/start → shows progress bar
//    - Progress updates via WebSocket (same channel as render progress)
//
// 4. Props to add: onUrlSubmitted: (url: string) => void
//
// 5. The DropZone interface will be updated:
//    interface DropZoneProps {
//      onFileSelected: (file: File) => void;
//      onUrlSubmitted?: (url: string) => void;
//      disabled?: boolean;
//    }
// ──────────────────────────────────────────────────────────────────────────────

const ALLOWED_EXTENSIONS = new Set([".mp4", ".mov", ".mkv"]);
const MAX_FILE_SIZE = 2_147_483_648; // 2 GB

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function getExtension(filename: string): string {
  const dot = filename.lastIndexOf(".");
  if (dot === -1) return "";
  return filename.slice(dot).toLowerCase();
}

interface DropZoneProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

export default function DropZone({ onFileSelected, disabled }: DropZoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validate = useCallback((file: File): string | null => {
    const ext = getExtension(file.name);
    if (!ALLOWED_EXTENSIONS.has(ext)) {
      return `Invalid file type "${ext || "(none)"}". Accepted: .mp4, .mov, .mkv`;
    }
    if (file.size <= 0) {
      return "File is empty (0 bytes).";
    }
    if (file.size > MAX_FILE_SIZE) {
      return `File too large (${formatSize(file.size)}). Maximum is 2 GB.`;
    }
    return null;
  }, []);

  const handleFile = useCallback(
    (file: File) => {
      const validationError = validate(file);
      if (validationError) {
        setError(validationError);
        setSelectedFile(null);
        return;
      }
      setError(null);
      setSelectedFile(file);
      onFileSelected(file);
    },
    [validate, onFileSelected]
  );

  const onDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!disabled) setDragOver(true);
    },
    [disabled]
  );

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      if (disabled) return;
      const file = e.dataTransfer.files?.[0];
      if (file) handleFile(file);
    },
    [disabled, handleFile]
  );

  const onClick = useCallback(() => {
    if (!disabled) inputRef.current?.click();
  }, [disabled]);

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
      // Reset so re-selecting the same file triggers onChange again.
      e.target.value = "";
    },
    [handleFile]
  );

  return (
    <div
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      onClick={onClick}
      className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors"
      style={{
        borderColor: dragOver
          ? "var(--accent)"
          : error
          ? "var(--error)"
          : "var(--border)",
        background: dragOver ? "var(--surface)" : "transparent",
        opacity: disabled ? 0.5 : 1,
        pointerEvents: disabled ? "none" : "auto",
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".mp4,.mov,.mkv"
        onChange={onInputChange}
        className="hidden"
      />

      {selectedFile ? (
        <p style={{ color: "var(--text)" }}>
          <span className="font-semibold">{selectedFile.name}</span>{" "}
          <span style={{ color: "var(--muted)" }}>
            ({formatSize(selectedFile.size)})
          </span>
        </p>
      ) : (
        <p style={{ color: "var(--muted)" }}>
          Drag & drop a video here, or click to browse
          <br />
          <span className="text-sm">Accepted: .mp4, .mov, .mkv (max 2 GB)</span>
        </p>
      )}

      {error && (
        <p className="mt-2 text-sm" style={{ color: "var(--error)" }}>
          {error}
        </p>
      )}
    </div>
  );
}
