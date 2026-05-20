"use client";

// Task 10.1 — Requirements: 9.1, 9.2, 9.3, 9.4, 9.5

const STEPS = [
  "Uploading",
  "Extracting Audio",
  "Transcribing",
  "Analyzing Highlights",
  "Rendering",
  "Done",
] as const;

interface ProgressTrackerProps {
  currentStep: string;
  renderIndex?: { k: number; n: number } | null;
  errorStep?: string | null;
}

export default function ProgressTracker({
  currentStep,
  renderIndex,
  errorStep,
}: ProgressTrackerProps) {
  const knownIndex = STEPS.indexOf(currentStep as (typeof STEPS)[number]);
  const isUnknownStep = currentStep !== "" && knownIndex === -1;

  return (
    <div className="space-y-2">
      {STEPS.map((step, idx) => {
        // Determine state: complete, active, or pending.
        let state: "complete" | "active" | "pending";
        if (knownIndex === -1) {
          // Unknown step: keep all as pending (no step highlighted).
          state = "pending";
        } else if (idx < knownIndex) {
          state = "complete";
        } else if (idx === knownIndex) {
          state = "active";
        } else {
          state = "pending";
        }

        // Build the label. When rendering is active and renderIndex is set,
        // substitute "Rendering Short k/n".
        let label: string = step;
        if (step === "Rendering" && state === "active" && renderIndex) {
          label = `Rendering Short ${renderIndex.k}/${renderIndex.n}`;
        }

        // Stall indicator: show on active step when errorStep matches.
        const isStalled = errorStep === step && state === "active";

        return (
          <div key={step} className="flex items-center gap-3">
            {/* Status dot */}
            <div
              className="w-3 h-3 rounded-full flex-shrink-0"
              style={{
                background:
                  state === "complete"
                    ? "var(--success)"
                    : state === "active"
                    ? "var(--accent)"
                    : "var(--muted)",
                animation:
                  state === "active" && !isStalled
                    ? "pulse 2s infinite"
                    : undefined,
                boxShadow: isStalled
                  ? "0 0 0 3px var(--error)"
                  : undefined,
              }}
            />

            {/* Label */}
            <span
              className="text-sm"
              style={{
                color:
                  state === "complete"
                    ? "var(--success)"
                    : state === "active"
                    ? "var(--text)"
                    : "var(--muted)",
                fontWeight: state === "active" ? 600 : 400,
              }}
            >
              {label}
              {isStalled && (
                <span className="ml-2 text-xs" style={{ color: "var(--error)" }}>
                  (stalled)
                </span>
              )}
            </span>
          </div>
        );
      })}

      {/* Unknown step indicator */}
      {isUnknownStep && (
        <div className="flex items-center gap-3">
          <div
            className="w-3 h-3 rounded-full flex-shrink-0"
            style={{ background: "var(--error)" }}
          />
          <span className="text-sm" style={{ color: "var(--error)" }}>
            Unknown step: {currentStep}
          </span>
        </div>
      )}
    </div>
  );
}
