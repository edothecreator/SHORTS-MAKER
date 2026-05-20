"use client";

import { useState } from "react";
import Link from "next/link";

export default function ResetPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      if (!res.ok) {
        const data = await res.json();
        setError(data.error || "Failed to send reset link.");
        setLoading(false);
        return;
      }

      setSent(true);
      setLoading(false);
    } catch {
      setError("Network error. Please try again.");
      setLoading(false);
    }
  };

  if (sent) {
    return (
      <main className="min-h-screen flex items-center justify-center p-4">
        <div
          className="w-full max-w-md p-8 rounded-lg text-center"
          style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
        >
          <h1 className="text-2xl font-bold mb-4" style={{ color: "var(--success)" }}>
            Check your email
          </h1>
          <p style={{ color: "var(--muted)" }}>
            If an account exists with <strong style={{ color: "var(--text)" }}>{email}</strong>,
            you&apos;ll receive a password reset link shortly.
          </p>
          <Link
            href="/auth/login"
            className="inline-block mt-6 px-6 py-2 rounded font-medium"
            style={{ background: "var(--accent)", color: "var(--text)" }}
          >
            Back to Login
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div
        className="w-full max-w-md p-8 rounded-lg"
        style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
      >
        <h1 className="text-2xl font-bold mb-2 text-center" style={{ color: "var(--text)" }}>
          Reset Password
        </h1>
        <p className="text-center mb-6 text-sm" style={{ color: "var(--muted)" }}>
          Enter your email and we&apos;ll send you a reset link.
        </p>

        {error && (
          <div className="mb-4 p-3 rounded text-sm" style={{ background: "var(--bg)", color: "var(--error)", border: "1px solid var(--error)" }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm mb-1" style={{ color: "var(--muted)" }}>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full p-2.5 rounded"
              style={{ background: "var(--bg)", color: "var(--text)", border: "1px solid var(--border)" }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded font-semibold transition-colors disabled:opacity-50"
            style={{ background: "var(--accent)", color: "var(--text)" }}
          >
            {loading ? "Sending..." : "Send Reset Link"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm" style={{ color: "var(--muted)" }}>
          <Link href="/auth/login" style={{ color: "var(--accent)" }}>
            Back to Login
          </Link>
        </p>
      </div>
    </main>
  );
}
