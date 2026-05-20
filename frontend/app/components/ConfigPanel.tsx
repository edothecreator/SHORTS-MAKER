"use client";

import { useCallback } from "react";
import type { Config, StyleTone, SubtitleStyle } from "../types";

// Task 9.1 — Requirements: 8.4, 8.5, 8.6, 8.7, 8.8

const STYLE_TONES: StyleTone[] = [
  "Funny",
  "Educational",
  "Motivational",
  "Highlights",
  "Story-driven",
  "Custom",
];

const SUBTITLE_STYLES: SubtitleStyle[] = [
  "TikTok-animated",
  "Bold-centered-white",
  "Minimal-bottom",
];

const DURATIONS = [15, 30, 60] as const;

interface ConfigPanelProps {
  config: Config;
  onChange: (config: Config) => void;
  disabled?: boolean;
}

export default function ConfigPanel({
  config,
  onChange,
  disabled,
}: ConfigPanelProps) {
  const update = useCallback(
    (partial: Partial<Config>) => {
      onChange({ ...config, ...partial });
    },
    [config, onChange]
  );

  return (
    <div
      className="space-y-5 p-4 rounded-lg"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        opacity: disabled ? 0.5 : 1,
        pointerEvents: disabled ? "none" : "auto",
      }}
    >
      {/* Shorts Count Slider */}
      <div>
        <label className="block text-sm font-medium mb-1" style={{ color: "var(--text)" }}>
          Number of Shorts: <span className="font-bold">{config.shortsCount}</span>
        </label>
        <input
          type="range"
          min={1}
          max={10}
          step={1}
          value={config.shortsCount}
          onChange={(e) => update({ shortsCount: parseInt(e.target.value, 10) })}
          disabled={disabled}
          className="w-full"
        />
      </div>

      {/* Duration Buttons */}
      <div>
        <label className="block text-sm font-medium mb-1" style={{ color: "var(--text)" }}>
          Duration per Short
        </label>
        <div className="flex gap-2">
          {DURATIONS.map((dur) => (
            <button
              key={dur}
              type="button"
              aria-pressed={config.durationPerShort === dur}
              onClick={() => update({ durationPerShort: dur })}
              disabled={disabled}
              className="px-4 py-2 rounded font-medium text-sm transition-colors"
              style={{
                background:
                  config.durationPerShort === dur
                    ? "var(--accent)"
                    : "transparent",
                color: "var(--text)",
                border: `1px solid ${
                  config.durationPerShort === dur
                    ? "var(--accent)"
                    : "var(--border)"
                }`,
              }}
            >
              {dur}s
            </button>
          ))}
        </div>
      </div>

      {/* Style/Tone Select */}
      <div>
        <label className="block text-sm font-medium mb-1" style={{ color: "var(--text)" }}>
          Style / Tone
        </label>
        <select
          value={config.styleTone}
          onChange={(e) =>
            update({ styleTone: e.target.value as StyleTone, customTone: "" })
          }
          disabled={disabled}
          className="w-full p-2 rounded"
          style={{
            background: "var(--bg)",
            color: "var(--text)",
            border: "1px solid var(--border)",
          }}
        >
          {STYLE_TONES.map((tone) => (
            <option key={tone} value={tone}>
              {tone}
            </option>
          ))}
        </select>

        {config.styleTone === "Custom" && (
          <input
            type="text"
            maxLength={200}
            value={config.customTone}
            onChange={(e) => update({ customTone: e.target.value })}
            placeholder="Describe your custom style/tone..."
            disabled={disabled}
            className="w-full mt-2 p-2 rounded"
            style={{
              background: "var(--bg)",
              color: "var(--text)",
              border: "1px solid var(--border)",
            }}
          />
        )}
      </div>

      {/* Subtitle Style Select */}
      <div>
        <label className="block text-sm font-medium mb-1" style={{ color: "var(--text)" }}>
          Subtitle Style
        </label>
        <select
          value={config.subtitleStyle}
          onChange={(e) =>
            update({ subtitleStyle: e.target.value as SubtitleStyle })
          }
          disabled={disabled}
          className="w-full p-2 rounded"
          style={{
            background: "var(--bg)",
            color: "var(--text)",
            border: "1px solid var(--border)",
          }}
        >
          {SUBTITLE_STYLES.map((style) => (
            <option key={style} value={style}>
              {style}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
