"use client";

import { signIn } from "next-auth/react";
import { useState } from "react";
import Link from "next/link";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleCredentialsLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const result = await signIn("credentials", {
      email,
      password,
      redirect: false,
    });

    setLoading(false);

    if (result?.error) {
      setError("Invalid email or password.");
    } else {
      window.location.href = "/";
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div
        className="w-full max-w-md p-8 rounded-lg"
        style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
      >
        <h1 className="text-2xl font-bold mb-6 text-center" style={{ color: "var(--text)" }}>
          Sign In
        </h1>

        {error && (
          <div className="mb-4 p-3 rounded text-sm" style={{ background: "var(--bg)", color: "var(--error)", border: "1px solid var(--error)" }}>
            {error}
          </div>
        )}

        {/* OAuth buttons */}
        <div className="space-y-3 mb-6">
          <button
            onClick={() => signIn("google", { callbackUrl: "/" })}
            className="w-full py-2.5 px-4 rounded font-medium border transition-colors"
            style={{ borderColor: "var(--border)", color: "var(--text)" }}
          >
            Continue with Google
          </button>
          <button
            onClick={() => signIn("github", { callbackUrl: "/" })}
            className="w-full py-2.5 px-4 rounded font-medium border transition-colors"
            style={{ borderColor: "var(--border)", color: "var(--text)" }}
          >
            Continue with GitHub
          </button>
        </div>

        <div className="flex items-center gap-3 mb-6">
          <div className="flex-1 h-px" style={{ background: "var(--border)" }} />
          <span className="text-xs" style={{ color: "var(--muted)" }}>or</span>
          <div className="flex-1 h-px" style={{ background: "var(--border)" }} />
        </div>

        {/* Credentials form */}
        <form onSubmit={handleCredentialsLogin} className="space-y-4">
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
          <div>
            <label className="block text-sm mb-1" style={{ color: "var(--muted)" }}>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full p-2.5 rounded"
              style={{ background: "var(--bg)", color: "var(--text)", border: "1px solid var(--border)" }}
            />
          </div>

          <div className="text-right">
            <Link href="/auth/reset-password" className="text-xs" style={{ color: "var(--accent)" }}>
              Forgot password?
            </Link>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded font-semibold transition-colors disabled:opacity-50"
            style={{ background: "var(--accent)", color: "var(--text)" }}
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm" style={{ color: "var(--muted)" }}>
          Don&apos;t have an account?{" "}
          <Link href="/auth/signup" style={{ color: "var(--accent)" }}>
            Sign up
          </Link>
        </p>
      </div>
    </main>
  );
}
