/**
 * SubtitlePreview — Task 9.2
 *
 * A React component that renders a live preview of how subtitles
 * will look in a mock 9:16 phone frame with the selected style applied.
 */

"use client";

import React from "react";
import type { SubtitleTemplate } from "./SubtitleEngine";

interface SubtitlePreviewProps {
  template: SubtitleTemplate;
  sampleText?: string;
}

/**
 * Convert ASS color format (&HBBGGRR or &HAABBGGRR) to CSS rgba.
 */
function assColorToCSS(assColor: string): string {
  const cleaned = assColor.replace(/&H/gi, "").replace(/&/g, "");
  if (cleaned.length === 8) {
    // &HAABBGGRR
    const a = parseInt(cleaned.slice(0, 2), 16);
    const b = parseInt(cleaned.slice(2, 4), 16);
    const g = parseInt(cleaned.slice(4, 6), 16);
    const r = parseInt(cleaned.slice(6, 8), 16);
    return `rgba(${r}, ${g}, ${b}, ${((255 - a) / 255).toFixed(2)})`;
  }
  // &HBBGGRR (no alpha, fully opaque)
  const b = parseInt(cleaned.slice(0, 2), 16);
  const g = parseInt(cleaned.slice(2, 4), 16);
  const r = parseInt(cleaned.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, 1)`;
}


/** Map position to CSS flexbox alignment */
function getPositionStyle(position: string): React.CSSProperties {
  switch (position) {
    case "top":
      return { justifyContent: "flex-start", paddingTop: "40px" };
    case "center":
      return { justifyContent: "center" };
    case "bottom":
    default:
      return { justifyContent: "flex-end", paddingBottom: "40px" };
  }
}

/** Get animation CSS class name */
function getAnimationClass(animationType: string): string {
  switch (animationType) {
    case "word-highlight": return "animate-highlight";
    case "color-fill": return "animate-fill";
    case "scale-pop": return "animate-scale";
    case "bounce": return "animate-bounce-in";
    case "typewriter": return "animate-typewriter";
    case "neon-glow": return "animate-glow";
    default: return "";
  }
}


export default function SubtitlePreview({
  template,
  sampleText = "This is how your subtitles will look",
}: SubtitlePreviewProps) {
  const primaryCSS = assColorToCSS(template.primaryColor);
  const secondaryCSS = assColorToCSS(template.secondaryColor);
  const outlineCSS = assColorToCSS(template.outlineColor);
  const bgCSS = assColorToCSS(template.backgroundColor);
  const animClass = getAnimationClass(template.animationType);
  const posStyle = getPositionStyle(template.position);

  // Build text style based on template
  const textStyle: React.CSSProperties = {
    fontFamily: template.fontFamily === "CustomUserFont"
      ? "'Arial Black', sans-serif"
      : `'${template.fontFamily}', sans-serif`,
    fontSize: `${Math.round(template.fontSize * 0.35)}px`,
    color: primaryCSS,
    textShadow: template.animationType === "shadow-drop"
      ? `3px 3px 6px rgba(0,0,0,0.8)`
      : template.animationType === "neon-glow"
        ? `0 0 10px ${secondaryCSS}, 0 0 20px ${secondaryCSS}, 0 0 40px ${secondaryCSS}`
        : `1px 1px 2px ${outlineCSS}`,
    WebkitTextStroke: template.animationType === "outline-only"
      ? "2px white"
      : undefined,
    padding: "8px 16px",
    borderRadius: template.id === "bg-pill"
      ? "999px"
      : template.id === "bg-rounded"
        ? "12px"
        : "0",
    backgroundColor: (
      template.category === "background" ||
      template.id === "bg-rounded" ||
      template.id === "bg-pill" ||
      template.id === "bg-fullwidth"
    ) ? bgCSS : "transparent",
    textAlign: "center",
    maxWidth: template.id === "bg-fullwidth" ? "100%" : "90%",
    width: template.id === "bg-fullwidth" ? "100%" : "auto",
    fontWeight: "bold",
    letterSpacing: "0.5px",
  };


  // For outline-only style, make text transparent
  if (template.animationType === "outline-only") {
    textStyle.color = "transparent";
  }

  return (
    <div className="subtitle-preview-wrapper">
      {/* Mock 9:16 phone frame */}
      <div
        className="subtitle-preview-frame"
        style={{
          width: "220px",
          height: "390px",
          borderRadius: "24px",
          border: "3px solid #333",
          background: "linear-gradient(180deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)",
          position: "relative",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          ...posStyle,
          boxShadow: "0 8px 32px rgba(0,0,0,0.3)",
        }}
      >
        {/* Notch */}
        <div
          style={{
            position: "absolute",
            top: "8px",
            left: "50%",
            transform: "translateX(-50%)",
            width: "60px",
            height: "6px",
            borderRadius: "3px",
            backgroundColor: "#333",
          }}
        />

        {/* Subtitle text */}
        <div
          className={`subtitle-text ${animClass}`}
          style={textStyle}
        >
          {sampleText}
        </div>
      </div>

      {/* Template info below the frame */}
      <div style={{ marginTop: "12px", textAlign: "center" }}>
        <h4 style={{ margin: "0 0 4px 0", fontSize: "14px", fontWeight: 600 }}>
          {template.name}
        </h4>
        <p style={{ margin: 0, fontSize: "12px", color: "#888", maxWidth: "220px" }}>
          {template.description}
        </p>
      </div>


      {/* Inline CSS animations */}
      <style>{`
        .subtitle-preview-wrapper {
          display: inline-flex;
          flex-direction: column;
          align-items: center;
        }

        .animate-highlight {
          animation: highlight-pulse 1.5s ease-in-out infinite;
        }

        .animate-fill {
          background: linear-gradient(90deg, currentColor 50%, transparent 50%);
          background-size: 200% 100%;
          -webkit-background-clip: text;
          background-clip: text;
          animation: fill-slide 2s linear infinite;
        }

        .animate-scale {
          animation: scale-pop 0.8s ease-out infinite;
        }

        .animate-bounce-in {
          animation: bounce-in 1s ease infinite;
        }

        .animate-typewriter {
          overflow: hidden;
          white-space: nowrap;
          border-right: 2px solid currentColor;
          animation: typewriter 2s steps(30) infinite, blink 0.5s step-end infinite alternate;
        }

        .animate-glow {
          animation: neon-pulse 1.5s ease-in-out infinite;
        }

        @keyframes highlight-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; transform: scale(1.02); }
        }

        @keyframes fill-slide {
          0% { background-position: 100% 0; }
          100% { background-position: 0 0; }
        }

        @keyframes scale-pop {
          0% { transform: scale(1.3); }
          30% { transform: scale(1); }
          100% { transform: scale(1); }
        }

        @keyframes bounce-in {
          0% { transform: translateY(20px); opacity: 0; }
          50% { transform: translateY(-5px); opacity: 1; }
          100% { transform: translateY(0); opacity: 1; }
        }

        @keyframes typewriter {
          0% { width: 0; }
          100% { width: 100%; }
        }

        @keyframes blink {
          50% { border-color: transparent; }
        }

        @keyframes neon-pulse {
          0%, 100% { filter: brightness(1); }
          50% { filter: brightness(1.3); }
        }
      `}</style>
    </div>
  );
}
