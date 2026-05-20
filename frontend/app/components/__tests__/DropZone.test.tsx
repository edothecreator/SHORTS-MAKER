/**
 * Task 8.2 — Unit tests for DropZone validation
 * Requirements: 1.9, 1.10, 8.2, 8.3
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import DropZone from "../DropZone";

function makeFile(name: string, size: number, type = "video/mp4"): File {
  // Create a File-like object with the specified size.
  const blob = new Blob(["x".repeat(Math.min(size, 100))], { type });
  const file = new File([blob], name, { type });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

function dropFile(container: HTMLElement, file: File) {
  const dataTransfer = { files: [file] } as unknown as DataTransfer;
  fireEvent.drop(container, { dataTransfer });
}

describe("DropZone validation", () => {
  it("rejects files with disallowed extensions (.avi)", () => {
    const onFileSelected = vi.fn();
    render(<DropZone onFileSelected={onFileSelected} />);
    const zone = screen.getByText(/drag & drop/i).closest("div")!;

    dropFile(zone, makeFile("video.avi", 1024));

    expect(screen.getByText(/invalid file type/i)).toBeTruthy();
    expect(onFileSelected).not.toHaveBeenCalled();
  });

  it("rejects files larger than 2 GB", () => {
    const onFileSelected = vi.fn();
    render(<DropZone onFileSelected={onFileSelected} />);
    const zone = screen.getByText(/drag & drop/i).closest("div")!;

    dropFile(zone, makeFile("big.mp4", 2_147_483_649));

    expect(screen.getByText(/file too large/i)).toBeTruthy();
    expect(onFileSelected).not.toHaveBeenCalled();
  });

  it("rejects zero-byte files", () => {
    const onFileSelected = vi.fn();
    render(<DropZone onFileSelected={onFileSelected} />);
    const zone = screen.getByText(/drag & drop/i).closest("div")!;

    dropFile(zone, makeFile("empty.mp4", 0));

    expect(screen.getByText(/empty/i)).toBeTruthy();
    expect(onFileSelected).not.toHaveBeenCalled();
  });

  it("accepts .mp4 files of valid size and calls onFileSelected", () => {
    const onFileSelected = vi.fn();
    render(<DropZone onFileSelected={onFileSelected} />);
    const zone = screen.getByText(/drag & drop/i).closest("div")!;

    const file = makeFile("clip.mp4", 5_000_000);
    dropFile(zone, file);

    expect(onFileSelected).toHaveBeenCalledWith(file);
    expect(screen.getByText("clip.mp4")).toBeTruthy();
  });

  it("accepts .mov files of valid size and calls onFileSelected", () => {
    const onFileSelected = vi.fn();
    render(<DropZone onFileSelected={onFileSelected} />);
    const zone = screen.getByText(/drag & drop/i).closest("div")!;

    const file = makeFile("video.mov", 10_000_000);
    dropFile(zone, file);

    expect(onFileSelected).toHaveBeenCalledWith(file);
  });

  it("accepts .mkv files of valid size and calls onFileSelected", () => {
    const onFileSelected = vi.fn();
    render(<DropZone onFileSelected={onFileSelected} />);
    const zone = screen.getByText(/drag & drop/i).closest("div")!;

    const file = makeFile("movie.mkv", 500_000_000);
    dropFile(zone, file);

    expect(onFileSelected).toHaveBeenCalledWith(file);
  });
});
