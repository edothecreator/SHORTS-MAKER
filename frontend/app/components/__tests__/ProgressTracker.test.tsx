/**
 * Task 10.2 — Unit tests for ProgressTracker
 * Requirements: 9.1, 9.2, 9.3, 9.5
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ProgressTracker from "../ProgressTracker";

describe("ProgressTracker", () => {
  it("marks earlier steps complete and current step active", () => {
    render(<ProgressTracker currentStep="Transcribing" />);

    // "Uploading" and "Extracting Audio" should show as complete (success color)
    const uploading = screen.getByText("Uploading");
    const extracting = screen.getByText("Extracting Audio");
    const transcribing = screen.getByText("Transcribing");
    const analyzing = screen.getByText("Analyzing Highlights");

    // Active step should be bold (fontWeight 600)
    expect(transcribing.style.fontWeight).toBe("600");
    // Earlier steps should not be bold
    expect(uploading.style.fontWeight).toBe("400");
    expect(extracting.style.fontWeight).toBe("400");
    // Later steps should not be bold
    expect(analyzing.style.fontWeight).toBe("400");
  });

  it("renders 'Rendering Short k/N' substitution when rendering is active", () => {
    render(
      <ProgressTracker
        currentStep="Rendering"
        renderIndex={{ k: 2, n: 5 }}
      />
    );

    expect(screen.getByText("Rendering Short 2/5")).toBeTruthy();
    // The generic "Rendering" label should not appear as-is
    expect(screen.queryByText(/^Rendering$/)).toBeNull();
  });

  it("shows 'Rendering' without substitution when renderIndex is null", () => {
    render(<ProgressTracker currentStep="Rendering" renderIndex={null} />);

    expect(screen.getByText("Rendering")).toBeTruthy();
  });

  it("shows unknown step indicator without changing the step list", () => {
    render(<ProgressTracker currentStep="SomeWeirdStep" />);

    // Unknown step should render with error indicator
    expect(screen.getByText(/unknown step: someweirdstep/i)).toBeTruthy();
    // All known steps should still be present
    expect(screen.getByText("Uploading")).toBeTruthy();
    expect(screen.getByText("Done")).toBeTruthy();
  });

  it("shows stall indicator on active step when errorStep matches", () => {
    render(
      <ProgressTracker
        currentStep="Analyzing Highlights"
        errorStep="Analyzing Highlights"
      />
    );

    expect(screen.getByText("(stalled)")).toBeTruthy();
  });

  it("does not show stall indicator when errorStep does not match active step", () => {
    render(
      <ProgressTracker
        currentStep="Transcribing"
        errorStep="Analyzing Highlights"
      />
    );

    expect(screen.queryByText("(stalled)")).toBeNull();
  });
});
