// Shared TypeScript types for the Shorts Engine Studio frontend.
// Task 7.1 — Requirements: 5.1, 5.2, 8.4, 8.5, 8.6, 8.8, 9.8

export interface WordTimestamp {
  word: string;
  start: number;
  end: number;
}

export interface ShortSegment {
  start_sec: number;
  end_sec: number;
  title: string;
  hook: string;
  reason: string;
  words: WordTimestamp[];
}

export interface ShortsAnalysisResult {
  segments: ShortSegment[];
}

export type StyleTone =
  | "Funny"
  | "Educational"
  | "Motivational"
  | "Highlights"
  | "Story-driven"
  | "Custom";

export type SubtitleStyle =
  | "TikTok-animated"
  | "Bold-centered-white"
  | "Minimal-bottom";

export interface Config {
  shortsCount: number; // 1..10
  durationPerShort: 15 | 30 | 60;
  styleTone: StyleTone;
  customTone: string;
  subtitleStyle: SubtitleStyle;
}

export interface RenderedClip {
  url: string;
  title: string;
  hook: string;
  blob: Blob;
}
