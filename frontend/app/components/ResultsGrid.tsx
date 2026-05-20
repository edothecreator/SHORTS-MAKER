"use client";

import { useState, useCallback, useRef } from "react";
import type { RenderedClip } from "../types";

// Task 12.1 — Requirements: 9.6, 9.7, 9.8, 9.9, 9.10, 9.11, 9.12, 9.13, 9.14

/**
 * Sanitize a title for use as a filename.
 * Strips [\\/:*?"<>|], collapses whitespace, trims.
 * Returns "untitled" if the result is empty.
 */
export function sanitize(title: string): string {
  const cleaned = title
    .replace(/[\\/:*?"<>|]/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return cleaned || "untitled";
}

/**
 * Deduplicate filenames by appending (2), (3), ... to collisions.
 */
function deduplicateNames(names: string[]): string[] {
  const counts: Record<string, number> = {};
  const result: string[] = [];
  for (const name of names) {
    if (counts[name] == null) {
      counts[name] = 1;
      result.push(name);
    } else {
      counts[name]++;
      result.push(`${name} (${counts[name]})`);
    }
  }
  return result;
}

interface ResultsGridProps {
  clips: RenderedClip[];
  onTitlesChange?: (titles: string[]) => void;
}

export default function ResultsGrid({ clips, onTitlesChange }: ResultsGridProps) {
  const [titles, setTitles] = useState<string[]>(clips.map((c) => c.title));
  const [titleErrors, setTitleErrors] = useState<(string | null)[]>(
    clips.map(() => null)
  );
  const [zipError, setZipError] = useState<string | null>(null);
  const [zipping, setZipping] = useState(false);
  const downloadRef = useRef<HTMLAnchorElement>(null);

  const handleTitleCommit = useCallback(
    (index: number, value: string) => {
      const truncated = value.slice(0, 100);
      const sanitized = sanitize(truncated);

      if (sanitized === "untitled" && truncated.trim() === "") {
        // Revert to previous value and show error.
        const newErrors = [...titleErrors];
        newErrors[index] = "Title cannot be empty";
        setTitleErrors(newErrors);
        return;
      }

      const newTitles = [...titles];
      newTitles[index] = truncated;
      setTitles(newTitles);
      if (onTitlesChange) onTitlesChange(newTitles);

      const newErrors = [...titleErrors];
      newErrors[index] = null;
      setTitleErrors(newErrors);
    },
    [titles, titleErrors, onTitlesChange]
  );

  const handleDownloadOne = useCallback(
    (index: number) => {
      const clip = clips[index];
      if (!clip.blob) return;
      const url = URL.createObjectURL(clip.blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${sanitize(titles[index] || clip.title)}.mp4`;
      a.click();
      URL.revokeObjectURL(url);
    },
    [clips, titles]
  );

  const allValid =
    clips.every((c) => c.blob != null) &&
    titles.every((t) => sanitize(t) !== "untitled" || t.trim() !== "");

  const handleDownloadAll = useCallback(async () => {
    if (!allValid || zipping) return;
    setZipError(null);
    setZipping(true);

    try {
      const JSZip = (await import("jszip")).default;
      const zip = new JSZip();

      const rawNames = titles.map((t) => sanitize(t));
      const dedupedNames = deduplicateNames(rawNames);

      for (let i = 0; i < clips.length; i++) {
        const blob = clips[i].blob;
        if (blob) {
          zip.file(`${dedupedNames[i]}.mp4`, blob);
        }
      }

      const zipBlob = await zip.generateAsync({ type: "blob" });
      const url = URL.createObjectURL(zipBlob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "shorts.zip";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setZipError(
        err instanceof Error ? err.message : "Failed to create ZIP"
      );
    } finally {
      setZipping(false);
    }
  }, [clips, titles, allValid, zipping]);

  return (
    <div>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        {clips.map((clip, i) => (
          <div
            key={i}
            className="rounded-lg overflow-hidden"
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
            }}
          >
            {/* Video preview */}
            <video
              src={clip.url}
              controls
              className="aspect-[9/16] w-full object-cover"
            />

            <div className="p-3 space-y-2">
              {/* Editable title */}
              <input
                type="text"
                maxLength={100}
                defaultValue={titles[i]}
                onBlur={(e) => handleTitleCommit(i, e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    (e.target as HTMLInputElement).blur();
                  }
                }}
                className="w-full text-amber-500 bg-transparent border-none outline-none text-sm font-semibold"
              />
              {titleErrors[i] && (
                <p className="text-xs" style={{ color: "var(--error)" }}>
                  {titleErrors[i]}
                </p>
              )}

              {/* Hook */}
              <p className="text-xs" style={{ color: "var(--muted)" }}>
                {clip.hook}
              </p>

              {/* Individual download */}
              <button
                onClick={() => handleDownloadOne(i)}
                className="text-xs px-3 py-1 rounded"
                style={{
                  background: "var(--accent)",
                  color: "var(--text)",
                }}
              >
                Download
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Download All as ZIP */}
      <div className="mt-6 flex items-center gap-3">
        <button
          onClick={handleDownloadAll}
          disabled={!allValid || zipping}
          className="px-5 py-2 rounded font-semibold transition-colors disabled:opacity-50"
          style={{
            background: "var(--accent)",
            color: "var(--text)",
          }}
        >
          {zipping ? "Creating ZIP..." : "Download All as ZIP"}
        </button>
        {zipError && (
          <span className="text-sm" style={{ color: "var(--error)" }}>
            {zipError}
          </span>
        )}
      </div>

      {/* Hidden download anchor */}
      <a ref={downloadRef} className="hidden" />
    </div>
  );
}
