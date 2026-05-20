/**
 * Task 9.2 — Unit tests for ConfigPanel
 * Requirements: 8.4, 8.5, 8.6, 8.7, 8.8
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ConfigPanel from "../ConfigPanel";
import type { Config } from "../../types";

const DEFAULT_CONFIG: Config = {
  shortsCount: 3,
  durationPerShort: 30,
  styleTone: "Highlights",
  customTone: "",
  subtitleStyle: "TikTok-animated",
};

describe("ConfigPanel", () => {
  it("slider clamps to integers in [1, 10] and emits on change", () => {
    const onChange = vi.fn();
    render(<ConfigPanel config={DEFAULT_CONFIG} onChange={onChange} />);

    const slider = screen.getByRole("slider");
    fireEvent.change(slider, { target: { value: "7" } });

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ shortsCount: 7 })
    );
  });

  it("duration buttons enforce single selection and emit the chosen integer", () => {
    const onChange = vi.fn();
    render(<ConfigPanel config={DEFAULT_CONFIG} onChange={onChange} />);

    const btn15 = screen.getByText("15s");
    fireEvent.click(btn15);

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ durationPerShort: 15 })
    );

    // The currently selected button (30s) should have aria-pressed=true
    const btn30 = screen.getByText("30s");
    expect(btn30.getAttribute("aria-pressed")).toBe("true");
    expect(btn15.getAttribute("aria-pressed")).toBe("false");
  });

  it("Custom style reveals text input and trimmed value flows through onChange", () => {
    const onChange = vi.fn();
    const customConfig: Config = { ...DEFAULT_CONFIG, styleTone: "Custom" };
    render(<ConfigPanel config={customConfig} onChange={onChange} />);

    const input = screen.getByPlaceholderText(/describe your custom/i);
    expect(input).toBeTruthy();

    fireEvent.change(input, { target: { value: "  my custom tone  " } });

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ customTone: "  my custom tone  " })
    );
  });

  it("Custom text input is hidden when style is not Custom", () => {
    const onChange = vi.fn();
    render(<ConfigPanel config={DEFAULT_CONFIG} onChange={onChange} />);

    const input = screen.queryByPlaceholderText(/describe your custom/i);
    expect(input).toBeNull();
  });

  it("subtitle selector emits one of the three allowed values", () => {
    const onChange = vi.fn();
    render(<ConfigPanel config={DEFAULT_CONFIG} onChange={onChange} />);

    const select = screen.getByDisplayValue("TikTok-animated");
    fireEvent.change(select, { target: { value: "Minimal-bottom" } });

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ subtitleStyle: "Minimal-bottom" })
    );
  });

  it("all controls are visually disabled when disabled prop is true", () => {
    const onChange = vi.fn();
    render(
      <ConfigPanel config={DEFAULT_CONFIG} onChange={onChange} disabled />
    );

    const slider = screen.getByRole("slider");
    expect(slider).toBeDisabled();
  });
});
