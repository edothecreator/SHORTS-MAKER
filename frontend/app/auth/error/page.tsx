"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

export default function AuthErrorPage() {
  const searchParams = useSearchParams();
  const error = searchParams.get("error");

  const errorMessages: Record<string, string> = {
    Configuration: "Server configuration error. Please contact support.",
    AccessDenied: "Access denied. You do not have permission.",
    Verification: "Verification link expired or invalid.",
    Default: "An authentication error occurred. Please try again.",
  };

  const message = errorMessages[error || ""] || errorMessages.Default;

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div
        className="w-full max-w-md p-8 rounded-lg text-center"
        style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
      >
        <h1 className="text-2xl font-bold mb-4" style={{ color: "var(--error)" }}>
          Authentication Error
        </h1>
        <p className="mb-6" style={{ color: "var(--muted)" }}>
          {message}
        </p>
        <Link
          href="/auth/login"
          className="inline-block px-6 py-2 rounded font-medium"
          style={{ background: "var(--accent)", color: "var(--text)" }}
        >
          Back to Login
        </Link>
      </div>
    </main>
  );
}
