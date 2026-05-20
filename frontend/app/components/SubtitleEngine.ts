/**
 * Advanced Subtitle Engine — Production Task 9
 *
 * Provides 20 subtitle style templates, advanced ASS generation,
 * emoji auto-insertion, RTL language support, and custom font configuration.
 *
 * This module does NOT modify useFFmpegRenderer.ts. It provides an independent,
 * more advanced subtitle system that can be used alongside or as a replacement.
 */

import type { WordTimestamp } from "../types";

// ============================================================================
// Types
// ============================================================================

export type SubtitleCategory =
  | "animation"
  | "effect"
  | "background"
  | "position"
  | "layout"
  | "font";

export type SubtitlePosition = "top" | "center" | "bottom";

export type AnimationType =
  | "none"
  | "word-highlight"
  | "color-fill"
  | "scale-pop"
  | "bounce"
  | "typewriter"
  | "gradient"
  | "neon-glow"
  | "shadow-drop"
  | "outline-only"
  | "split-color";


export interface SubtitleTemplate {
  id: string;
  name: string;
  description: string;
  category: SubtitleCategory;
  fontFamily: string;
  fontSize: number;
  primaryColor: string;       // ASS color format &HBBGGRR
  secondaryColor: string;     // ASS color format &HBBGGRR
  outlineColor: string;       // ASS color format &HBBGGRR
  backgroundColor: string;    // ASS color format &HAABBGGRR
  position: SubtitlePosition;
  animationType: AnimationType;
  assOverrideTags: string;    // Raw ASS override tags for this style
}

export interface CustomFontConfig {
  fontPath: string;
  fontFamily: string;
  fallbackFont: string;
}


// ============================================================================
// Task 9.1: 20 Subtitle Style Templates
// ============================================================================

export const SUBTITLE_TEMPLATES: SubtitleTemplate[] = [
  {
    id: "word-highlight",
    name: "Word Highlight",
    description: "TikTok-style word-by-word highlighting with accent color",
    category: "animation",
    fontFamily: "Arial Black",
    fontSize: 64,
    primaryColor: "&H00FFFFFF",
    secondaryColor: "&H0000FFFF",
    outlineColor: "&H00000000",
    backgroundColor: "&H80000000",
    position: "bottom",
    animationType: "word-highlight",
    assOverrideTags: "\\an2\\c&H00FFFF&",
  },
  {
    id: "color-fill",
    name: "Color Fill",
    description: "Word fills with color progressively as spoken",
    category: "animation",
    fontFamily: "Arial Black",
    fontSize: 68,
    primaryColor: "&H00FFFFFF",
    secondaryColor: "&H0042F5FF",
    outlineColor: "&H00000000",
    backgroundColor: "&H00000000",
    position: "center",
    animationType: "color-fill",
    assOverrideTags: "\\an5\\c&HFFFFFF&\\3c&H000000&\\bord3",
  },

  {
    id: "scale-pop",
    name: "Scale Pop",
    description: "Each word scales up dramatically then returns to normal size",
    category: "animation",
    fontFamily: "Impact",
    fontSize: 72,
    primaryColor: "&H00FFFFFF",
    secondaryColor: "&H0000FFFF",
    outlineColor: "&H00000000",
    backgroundColor: "&H00000000",
    position: "center",
    animationType: "scale-pop",
    assOverrideTags: "\\an5\\fscx130\\fscy130\\t(0,100,\\fscx100\\fscy100)",
  },
  {
    id: "bounce",
    name: "Bounce",
    description: "Words bounce in with a spring animation effect",
    category: "animation",
    fontFamily: "Arial Black",
    fontSize: 64,
    primaryColor: "&H00FFFFFF",
    secondaryColor: "&H0000FFFF",
    outlineColor: "&H00000000",
    backgroundColor: "&H00000000",
    position: "bottom",
    animationType: "bounce",
    assOverrideTags: "\\an2\\move(540,1500,540,1400)\\t(0,150,\\frz0)",
  },

  {
    id: "typewriter",
    name: "Typewriter",
    description: "Letters appear one by one like being typed",
    category: "animation",
    fontFamily: "Courier New",
    fontSize: 56,
    primaryColor: "&H0000FF00",
    secondaryColor: "&H00000000",
    outlineColor: "&H00000000",
    backgroundColor: "&H80000000",
    position: "bottom",
    animationType: "typewriter",
    assOverrideTags: "\\an2\\fe0\\t(0,500,\\fe1)",
  },
  {
    id: "gradient-text",
    name: "Gradient Text",
    description: "Text with a gradient color effect across the line",
    category: "effect",
    fontFamily: "Arial Black",
    fontSize: 66,
    primaryColor: "&H00FF88FF",
    secondaryColor: "&H00FFAA00",
    outlineColor: "&H00000000",
    backgroundColor: "&H00000000",
    position: "center",
    animationType: "gradient",
    assOverrideTags: "\\an5\\1c&HFF88FF&\\t(0,500,\\1c&HFFAA00&)",
  },

  {
    id: "neon-glow",
    name: "Neon Glow",
    description: "Glowing neon light effect with blur shadow",
    category: "effect",
    fontFamily: "Arial",
    fontSize: 62,
    primaryColor: "&H0000FFFF",
    secondaryColor: "&H0000FF00",
    outlineColor: "&H0000FFFF",
    backgroundColor: "&H00000000",
    position: "center",
    animationType: "neon-glow",
    assOverrideTags: "\\an5\\blur3\\bord4\\3c&H00FFFF&\\shad0",
  },
  {
    id: "shadow-drop",
    name: "Shadow Drop",
    description: "Dramatic drop shadow for cinematic look",
    category: "effect",
    fontFamily: "Arial Black",
    fontSize: 68,
    primaryColor: "&H00FFFFFF",
    secondaryColor: "&H00000000",
    outlineColor: "&H00000000",
    backgroundColor: "&H00000000",
    position: "center",
    animationType: "shadow-drop",
    assOverrideTags: "\\an5\\shad5\\4c&H00000000&\\bord0",
  },

  {
    id: "outline-only",
    name: "Outline Only",
    description: "Outlined text with no fill — clean minimal look",
    category: "effect",
    fontFamily: "Arial Black",
    fontSize: 70,
    primaryColor: "&H00000000",
    secondaryColor: "&H00FFFFFF",
    outlineColor: "&H00FFFFFF",
    backgroundColor: "&H00000000",
    position: "center",
    animationType: "outline-only",
    assOverrideTags: "\\an5\\1c&H000000&\\1a&HFF&\\3c&HFFFFFF&\\bord4",
  },
  {
    id: "split-color",
    name: "Split Color",
    description: "Top half and bottom half of text in different colors",
    category: "effect",
    fontFamily: "Impact",
    fontSize: 72,
    primaryColor: "&H0000FFFF",
    secondaryColor: "&H00FF00FF",
    outlineColor: "&H00000000",
    backgroundColor: "&H00000000",
    position: "center",
    animationType: "split-color",
    assOverrideTags: "\\an5\\c&H00FFFF&\\clip(0,0,1080,960)\\bord2",
  },

  {
    id: "emoji-auto",
    name: "Emoji Auto-Insert",
    description: "Automatically inserts relevant emoji based on word sentiment",
    category: "effect",
    fontFamily: "Arial",
    fontSize: 60,
    primaryColor: "&H00FFFFFF",
    secondaryColor: "&H0000FFFF",
    outlineColor: "&H00000000",
    backgroundColor: "&H80000000",
    position: "bottom",
    animationType: "none",
    assOverrideTags: "\\an2\\bord2\\shad1",
  },
  {
    id: "bg-rounded",
    name: "Rounded Background",
    description: "Text with a rounded background box behind it",
    category: "background",
    fontFamily: "Arial",
    fontSize: 58,
    primaryColor: "&H00FFFFFF",
    secondaryColor: "&H00000000",
    outlineColor: "&H00000000",
    backgroundColor: "&HCC000000",
    position: "bottom",
    animationType: "none",
    assOverrideTags: "\\an2\\bord8\\shad0\\3c&H000000&\\4c&HCC000000&",
  },

  {
    id: "bg-pill",
    name: "Pill Background",
    description: "Pill-shaped colored background behind each word group",
    category: "background",
    fontFamily: "Arial Black",
    fontSize: 54,
    primaryColor: "&H00FFFFFF",
    secondaryColor: "&H00000000",
    outlineColor: "&H00FFFFFF",
    backgroundColor: "&HE6FF4500",
    position: "bottom",
    animationType: "none",
    assOverrideTags: "\\an2\\bord12\\shad0\\3c&HFF4500&\\4c&HE6FF4500&",
  },
  {
    id: "bg-fullwidth",
    name: "Full-Width Bar",
    description: "Full-width colored bar background spanning the screen",
    category: "background",
    fontFamily: "Arial",
    fontSize: 56,
    primaryColor: "&H00FFFFFF",
    secondaryColor: "&H00000000",
    outlineColor: "&H00000000",
    backgroundColor: "&HCC222222",
    position: "bottom",
    animationType: "none",
    assOverrideTags: "\\an2\\bord0\\shad0\\4a&H33&\\4c&H222222&",
  },

  {
    id: "position-top",
    name: "Top Position",
    description: "Subtitles positioned at the top of the frame",
    category: "position",
    fontFamily: "Arial Black",
    fontSize: 60,
    primaryColor: "&H00FFFFFF",
    secondaryColor: "&H0000FFFF",
    outlineColor: "&H00000000",
    backgroundColor: "&H80000000",
    position: "top",
    animationType: "none",
    assOverrideTags: "\\an8\\bord3\\shad1",
  },
  {
    id: "position-center",
    name: "Center Position",
    description: "Subtitles centered vertically in the frame",
    category: "position",
    fontFamily: "Arial Black",
    fontSize: 64,
    primaryColor: "&H00FFFFFF",
    secondaryColor: "&H0000FFFF",
    outlineColor: "&H00000000",
    backgroundColor: "&H00000000",
    position: "center",
    animationType: "none",
    assOverrideTags: "\\an5\\bord3\\shad2",
  },

  {
    id: "position-bottom",
    name: "Bottom Position",
    description: "Subtitles at the bottom with strong outline",
    category: "position",
    fontFamily: "Arial Black",
    fontSize: 62,
    primaryColor: "&H00FFFFFF",
    secondaryColor: "&H0000FFFF",
    outlineColor: "&H00000000",
    backgroundColor: "&H80000000",
    position: "bottom",
    animationType: "none",
    assOverrideTags: "\\an2\\bord4\\shad1",
  },
  {
    id: "multi-line",
    name: "Multi-Line",
    description: "Multiple lines of subtitles visible simultaneously",
    category: "layout",
    fontFamily: "Arial",
    fontSize: 52,
    primaryColor: "&H00FFFFFF",
    secondaryColor: "&H0000FFFF",
    outlineColor: "&H00000000",
    backgroundColor: "&H80000000",
    position: "bottom",
    animationType: "none",
    assOverrideTags: "\\an2\\bord2\\shad1\\q2",
  },

  {
    id: "single-line",
    name: "Single Line",
    description: "Only one line of text visible at a time for maximum impact",
    category: "layout",
    fontFamily: "Arial Black",
    fontSize: 70,
    primaryColor: "&H00FFFFFF",
    secondaryColor: "&H0000FFFF",
    outlineColor: "&H00000000",
    backgroundColor: "&H00000000",
    position: "center",
    animationType: "none",
    assOverrideTags: "\\an5\\bord3\\shad2\\q1",
  },
  {
    id: "custom-font",
    name: "Custom Font",
    description: "Uses a user-uploaded custom font (TTF/OTF)",
    category: "font",
    fontFamily: "CustomUserFont",
    fontSize: 60,
    primaryColor: "&H00FFFFFF",
    secondaryColor: "&H0000FFFF",
    outlineColor: "&H00000000",
    backgroundColor: "&H00000000",
    position: "bottom",
    animationType: "none",
    assOverrideTags: "\\an2\\bord3\\shad1",
  },
];


// ============================================================================
// Task 9.6: Emoji Auto-Insertion
// ============================================================================

/** Keyword → emoji mapping for sentiment-based auto-insertion */
const EMOJI_MAP: Record<string, string> = {
  love: "❤️",
  heart: "❤️",
  fire: "🔥",
  hot: "🔥",
  laugh: "😂",
  funny: "😂",
  lol: "😂",
  haha: "😂",
  cry: "😢",
  sad: "😢",
  happy: "😊",
  smile: "😊",
  wow: "😮",
  amazing: "🤩",
  awesome: "🤩",
  cool: "😎",
  money: "💰",
  rich: "💰",
  dollar: "💵",
  music: "🎵",
  song: "🎵",
  dance: "💃",
  food: "🍕",
  eat: "🍽️",
  drink: "🍹",
  coffee: "☕",
  sleep: "😴",
  tired: "😴",
  think: "🤔",
  idea: "💡",
  brain: "🧠",
  smart: "🧠",
  strong: "💪",
  win: "🏆",
  trophy: "🏆",
  celebrate: "🎉",
  party: "🎉",
  king: "👑",
  queen: "👑",
  star: "⭐",
  rocket: "🚀",
  fast: "🚀",
  growth: "📈",
  up: "📈",
  down: "📉",
  warning: "⚠️",
  danger: "⚠️",
  stop: "🛑",
  check: "✅",
  yes: "✅",
  no: "❌",
  wrong: "❌",
  question: "❓",
  time: "⏰",
  clock: "⏰",
  bomb: "💣",
  mind: "🤯",
  crazy: "🤯",
  shock: "😱",
  scared: "😱",
  angry: "😡",
  mad: "😡",
  clap: "👏",
  pray: "🙏",
  please: "🙏",
  thanks: "🙏",
  eyes: "👀",
  look: "👀",
  see: "👀",
  point: "👉",
  wave: "👋",
  hello: "👋",
  bye: "👋",
  sun: "☀️",
  rain: "🌧️",
  cold: "🥶",
  earth: "🌍",
  world: "🌍",
  dog: "🐶",
  cat: "🐱",
};


/**
 * Auto-insert emoji into text based on keyword/sentiment matching.
 * Scans each word against the emoji map and appends the matching emoji after the word.
 */
export function autoInsertEmoji(text: string): string {
  if (!text || typeof text !== "string") return text;

  const words = text.split(/\s+/);
  const result: string[] = [];

  for (const word of words) {
    const cleaned = word.toLowerCase().replace(/[^a-z]/g, "");
    const emoji = EMOJI_MAP[cleaned];
    if (emoji) {
      result.push(`${word} ${emoji}`);
    } else {
      result.push(word);
    }
  }

  return result.join(" ");
}

// ============================================================================
// Task 9.7: RTL Language Support
// ============================================================================

/**
 * Detect if text contains RTL characters (Arabic, Hebrew, Farsi, Urdu, etc.)
 * Uses Unicode character ranges for RTL scripts.
 */
export function isRTL(text: string): boolean {
  if (!text || typeof text !== "string") return false;

  // Unicode ranges for RTL scripts:
  // Arabic: U+0600–U+06FF, U+0750–U+077F, U+08A0–U+08FF, U+FB50–U+FDFF, U+FE70–U+FEFF
  // Hebrew: U+0590–U+05FF, U+FB1D–U+FB4F
  // Thaana (Maldivian): U+0780–U+07BF
  // Syriac: U+0700–U+074F
  // N'Ko: U+07C0–U+07FF
  const rtlPattern = /[\u0590-\u05FF\u0600-\u06FF\u0700-\u074F\u0750-\u077F\u0780-\u07BF\u07C0-\u07FF\u08A0-\u08FF\uFB1D-\uFB4F\uFB50-\uFDFF\uFE70-\uFEFF]/;

  // Count RTL vs LTR characters
  let rtlCount = 0;
  let totalAlpha = 0;

  for (const char of text) {
    if (rtlPattern.test(char)) {
      rtlCount++;
      totalAlpha++;
    } else if (/[a-zA-Z]/.test(char)) {
      totalAlpha++;
    }
  }

  // Consider RTL if more than 30% of alphabetic chars are RTL
  return totalAlpha > 0 && rtlCount / totalAlpha > 0.3;
}


/**
 * Apply RTL layout adjustments to ASS subtitle content.
 * - Sets text direction to RTL
 * - Adjusts alignment for RTL reading (right-aligned)
 * - Adds Unicode RTL markers around dialogue text
 */
export function applyRTLLayout(assContent: string): string {
  if (!assContent || typeof assContent !== "string") return assContent;

  // Replace alignment tags for RTL:
  // \an2 (bottom-center) → \an3 (bottom-right)
  // \an5 (middle-center) → \an6 (middle-right)
  // \an8 (top-center) → \an9 (top-right)
  let rtlContent = assContent
    .replace(/\\an2/g, "\\an3")
    .replace(/\\an5/g, "\\an6")
    .replace(/\\an8/g, "\\an9");

  // Add Unicode RLE (Right-to-Left Embedding) marker before dialogue text
  const RLE = "\u202B"; // Right-to-Left Embedding
  const PDF = "\u202C"; // Pop Directional Formatting

  // Wrap dialogue text content with RTL markers
  rtlContent = rtlContent.replace(
    /(Dialogue:[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,)(.+)/g,
    (match, prefix, text) => `${prefix}${RLE}${text}${PDF}`
  );

  return rtlContent;
}

// ============================================================================
// Task 9.5: Custom Font Support
// ============================================================================

/**
 * Apply a custom user-uploaded font to ASS content.
 * Replaces the default font in the ASS Style definition and all override tags
 * with the user's custom font family.
 */
export function applyCustomFont(
  assContent: string,
  fontPath: string,
  fontFamily: string
): string {
  if (!assContent || !fontFamily) return assContent;

  // Replace font in Style line (format: Style: Name,Fontname,Fontsize,...)
  let updated = assContent.replace(
    /(Style:\s*\w+),([^,]+),/g,
    (match, prefix) => `${prefix},${fontFamily},`
  );

  // Replace \\fn tags in override blocks
  updated = updated.replace(
    /\\fn[^\\}]+/g,
    `\\fn${fontFamily}`
  );

  // Add a comment noting the custom font path for the renderer
  const fontComment = `; Custom Font: ${fontFamily} (${fontPath})\n`;
  updated = updated.replace(
    "[Script Info]",
    `[Script Info]\n${fontComment}`
  );

  return updated;
}


// ============================================================================
// ASS Generation Engine
// ============================================================================

/** Convert seconds to ASS timestamp format: H:MM:SS.cs */
function toAssTimestamp(secs: number): string {
  const clamped = Math.max(0, secs);
  const h = Math.floor(clamped / 3600);
  const m = Math.floor((clamped % 3600) / 60);
  const s = Math.floor(clamped % 60);
  const cs = Math.round((clamped - Math.floor(clamped)) * 100);
  return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(cs).padStart(2, "0")}`;
}

/** Get ASS alignment number from position */
function getAlignment(position: SubtitlePosition): number {
  switch (position) {
    case "top": return 8;    // top-center
    case "center": return 5; // middle-center
    case "bottom": return 2; // bottom-center
    default: return 2;
  }
}

/** Get MarginV value based on position */
function getMarginV(position: SubtitlePosition): number {
  switch (position) {
    case "top": return 80;
    case "center": return 0;
    case "bottom": return 120;
    default: return 120;
  }
}


/** Group words into chunks for multi-word display */
function groupWordsForTemplate(
  words: { word: string; start: number; end: number }[],
  template: SubtitleTemplate
): { words: string[]; start: number; end: number }[][] {
  const groups: { words: string[]; start: number; end: number }[][] = [];

  // For single-line or word-highlight styles: one word per group
  if (
    template.id === "single-line" ||
    template.animationType === "word-highlight" ||
    template.animationType === "scale-pop" ||
    template.animationType === "bounce"
  ) {
    for (const w of words) {
      groups.push([{ words: [w.word], start: w.start, end: w.end }]);
    }
    return groups;
  }

  // For multi-line: group 5-6 words
  const groupSize = template.id === "multi-line" ? 6 : 4;
  let i = 0;
  while (i < words.length) {
    const chunk = words.slice(i, i + groupSize);
    groups.push(
      chunk.map((w) => ({ words: [w.word], start: w.start, end: w.end }))
    );
    i += groupSize;
  }
  return groups;
}


/**
 * Generate advanced ASS subtitle content based on a template.
 *
 * @param words - Array of word-level timestamps
 * @param segmentStart - Start time of the segment in seconds (absolute)
 * @param segmentDur - Duration of the segment in seconds
 * @param template - The subtitle template to apply
 * @returns Complete ASS file content string
 */
export function generateAdvancedAss(
  words: WordTimestamp[],
  segmentStart: number,
  segmentDur: number,
  template: SubtitleTemplate
): string {
  const alignment = getAlignment(template.position);
  const marginV = getMarginV(template.position);

  // Build ASS header with template-specific style
  const header = `[Script Info]
Title: Advanced Subtitle - ${template.name}
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
Timer: 100.0000
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,${template.fontFamily},${template.fontSize},${template.primaryColor},${template.secondaryColor},${template.outlineColor},${template.backgroundColor},-1,0,0,0,100,100,0,0,1,3,1,${alignment},10,10,${marginV},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text`;


  // Filter and convert words to clip-relative timing
  const validWords: { word: string; start: number; end: number }[] = [];
  for (const w of words) {
    if (
      !w ||
      typeof w.start !== "number" ||
      typeof w.end !== "number" ||
      !isFinite(w.start) ||
      !isFinite(w.end) ||
      w.end <= w.start ||
      typeof w.word !== "string"
    ) {
      continue;
    }
    const relStart = Math.max(0, Math.min(w.start - segmentStart, segmentDur));
    const relEnd = Math.max(0, Math.min(w.end - segmentStart, segmentDur));
    if (relEnd <= relStart) continue;
    validWords.push({ word: w.word, start: relStart, end: relEnd });
  }

  // If no valid words, return header only
  if (validWords.length === 0) {
    return header + "\n";
  }

  // Auto-insert emoji for the emoji-auto template
  const processedWords = template.id === "emoji-auto"
    ? validWords.map((w) => ({
        ...w,
        word: autoInsertEmoji(w.word),
      }))
    : validWords;

  // Generate dialogue lines based on animation type
  const dialogues: string[] = [];
  const overrides = template.assOverrideTags;


  switch (template.animationType) {
    case "word-highlight": {
      // One word at a time with highlight color
      for (const w of processedWords) {
        const start = toAssTimestamp(w.start);
        const end = toAssTimestamp(w.end);
        dialogues.push(
          `Dialogue: 0,${start},${end},Default,,0,0,${marginV},,{\\${overrides}}${w.word}`
        );
      }
      break;
    }

    case "color-fill": {
      // Word appears white, then transitions to accent color
      for (const w of processedWords) {
        const start = toAssTimestamp(w.start);
        const end = toAssTimestamp(w.end);
        const durMs = Math.round((w.end - w.start) * 1000);
        dialogues.push(
          `Dialogue: 0,${start},${end},Default,,0,0,${marginV},,{\\${overrides}\\t(0,${durMs},\\c${template.secondaryColor})}${w.word}`
        );
      }
      break;
    }

    case "scale-pop": {
      // Word pops in large then scales to normal
      for (const w of processedWords) {
        const start = toAssTimestamp(w.start);
        const end = toAssTimestamp(w.end);
        dialogues.push(
          `Dialogue: 0,${start},${end},Default,,0,0,${marginV},,{\\an${alignment}\\fscx140\\fscy140\\t(0,150,\\fscx100\\fscy100)}${w.word}`
        );
      }
      break;
    }


    case "bounce": {
      // Words bounce in from below
      for (const w of processedWords) {
        const start = toAssTimestamp(w.start);
        const end = toAssTimestamp(w.end);
        const posY = template.position === "top" ? 80 : template.position === "center" ? 960 : 1800;
        dialogues.push(
          `Dialogue: 0,${start},${end},Default,,0,0,${marginV},,{\\an${alignment}\\move(540,${posY + 100},540,${posY})\\t(0,200,\\frz0)}${w.word}`
        );
      }
      break;
    }

    case "typewriter": {
      // Group words and reveal characters progressively
      const groups = groupConsecutiveWords(processedWords, 4);
      for (const group of groups) {
        const start = toAssTimestamp(group[0].start);
        const end = toAssTimestamp(group[group.length - 1].end);
        const text = group.map((w) => w.word).join(" ");
        const totalChars = text.length;
        const durMs = Math.round((group[group.length - 1].end - group[0].start) * 1000);
        // Use \ko (karaoke) for character reveal
        const charDur = Math.max(1, Math.round(durMs / totalChars / 10));
        dialogues.push(
          `Dialogue: 0,${start},${end},Default,,0,0,${marginV},,{\\an${alignment}\\ko${charDur}}${text}`
        );
      }
      break;
    }


    case "gradient": {
      // Color transitions over duration
      const groups = groupConsecutiveWords(processedWords, 4);
      for (const group of groups) {
        const start = toAssTimestamp(group[0].start);
        const end = toAssTimestamp(group[group.length - 1].end);
        const text = group.map((w) => w.word).join(" ");
        const durMs = Math.round((group[group.length - 1].end - group[0].start) * 1000);
        dialogues.push(
          `Dialogue: 0,${start},${end},Default,,0,0,${marginV},,{\\an${alignment}\\1c${template.primaryColor}\\t(0,${durMs},\\1c${template.secondaryColor})}${text}`
        );
      }
      break;
    }

    case "neon-glow": {
      // Glow effect with blur
      const groups = groupConsecutiveWords(processedWords, 4);
      for (const group of groups) {
        const start = toAssTimestamp(group[0].start);
        const end = toAssTimestamp(group[group.length - 1].end);
        const text = group.map((w) => w.word).join(" ");
        dialogues.push(
          `Dialogue: 0,${start},${end},Default,,0,0,${marginV},,{\\an${alignment}\\blur3\\bord4\\3c${template.outlineColor}\\shad0\\t(0,500,\\blur1)\\t(500,1000,\\blur3)}${text}`
        );
      }
      break;
    }


    case "shadow-drop": {
      // Large shadow effect
      const groups = groupConsecutiveWords(processedWords, 4);
      for (const group of groups) {
        const start = toAssTimestamp(group[0].start);
        const end = toAssTimestamp(group[group.length - 1].end);
        const text = group.map((w) => w.word).join(" ");
        dialogues.push(
          `Dialogue: 0,${start},${end},Default,,0,0,${marginV},,{\\an${alignment}\\shad5\\4c&H00000000&\\bord0}${text}`
        );
      }
      break;
    }

    case "outline-only": {
      // Transparent fill, visible outline
      const groups = groupConsecutiveWords(processedWords, 4);
      for (const group of groups) {
        const start = toAssTimestamp(group[0].start);
        const end = toAssTimestamp(group[group.length - 1].end);
        const text = group.map((w) => w.word).join(" ");
        dialogues.push(
          `Dialogue: 0,${start},${end},Default,,0,0,${marginV},,{\\an${alignment}\\1a&HFF&\\3c&HFFFFFF&\\bord4}${text}`
        );
      }
      break;
    }

    case "split-color": {
      // Two-color effect using clip
      const groups = groupConsecutiveWords(processedWords, 4);
      for (const group of groups) {
        const start = toAssTimestamp(group[0].start);
        const end = toAssTimestamp(group[group.length - 1].end);
        const text = group.map((w) => w.word).join(" ");
        // Render twice: top half in one color, bottom in another
        dialogues.push(
          `Dialogue: 0,${start},${end},Default,,0,0,${marginV},,{\\an${alignment}\\c${template.primaryColor}\\clip(0,0,1080,960)}${text}`
        );
        dialogues.push(
          `Dialogue: 1,${start},${end},Default,,0,0,${marginV},,{\\an${alignment}\\c${template.secondaryColor}\\clip(0,960,1080,1920)}${text}`
        );
      }
      break;
    }


    case "none":
    default: {
      // Standard display — group words and show with template overrides
      const groupSize = template.id === "multi-line" ? 6 : 4;
      const groups = groupConsecutiveWords(processedWords, groupSize);
      for (const group of groups) {
        const start = toAssTimestamp(group[0].start);
        const end = toAssTimestamp(group[group.length - 1].end);
        const text = group.map((w) => w.word).join(" ");
        dialogues.push(
          `Dialogue: 0,${start},${end},Default,,0,0,${marginV},,{\\${overrides}}${text}`
        );
      }
      break;
    }
  }

  // Assemble the full ASS content
  let assContent = header + "\n" + dialogues.join("\n") + "\n";

  // Apply RTL layout if text is RTL
  const allText = processedWords.map((w) => w.word).join(" ");
  if (isRTL(allText)) {
    assContent = applyRTLLayout(assContent);
  }

  return assContent;
}


/** Utility: group consecutive words into chunks */
function groupConsecutiveWords(
  words: { word: string; start: number; end: number }[],
  maxPerGroup: number
): { word: string; start: number; end: number }[][] {
  const groups: { word: string; start: number; end: number }[][] = [];
  let i = 0;
  while (i < words.length) {
    const remaining = words.length - i;
    const take = remaining <= maxPerGroup ? remaining : Math.min(maxPerGroup, remaining);
    groups.push(words.slice(i, i + take));
    i += take;
  }
  return groups;
}

// ============================================================================
// Task 9.3 + 9.4: TODO — Future Interactive Components
// ============================================================================

/**
 * TODO (Future PR): Manual subtitle text editing
 * -------------------------------------------------
 * Task 9.3: Allow manual subtitle text editing (fix transcription errors).
 * This requires a complex interactive text editor component with:
 * - Inline text editing of individual word segments
 * - Real-time ASS regeneration on edit
 * - Undo/redo support
 * - Integration with the timeline/preview system
 *
 * Implementation plan: Create a `SubtitleEditor.tsx` component with
 * contenteditable regions per word, backed by a reducer for state management.
 * Will be implemented incrementally in a future PR.
 *
 * TODO (Future PR): Word-level timing adjustment
 * -------------------------------------------------
 * Task 9.4: Add word-level timing adjustment (drag to shift timing).
 * This requires complex drag-and-drop UI that's better done incrementally:
 * - A horizontal timeline visualization showing each word's time range
 * - Drag handles on word boundaries to adjust start/end times
 * - Snap-to-grid behavior for precise alignment
 * - Visual waveform display for audio reference
 * - Real-time subtitle preview update on drag
 *
 * Implementation plan: Create a `SubtitleTimeline.tsx` component using
 * pointer events and requestAnimationFrame for smooth dragging.
 * Will be implemented incrementally in a future PR.
 */
