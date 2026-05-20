"use client";

import { useSession, signOut } from "next-auth/react";
import Link from "next/link";

/**
 * Production Task 1.11: Sign Out button in navbar
 */
export default function Navbar() {
  const { data: session, status } = useSession();

  return (
    <nav
      className="flex items-center justify-between px-6 py-3 border-b"
      style={{ background: "var(--surface)", borderColor: "var(--border)" }}
    >
      <Link href="/" className="font-bold text-lg" style={{ color: "var(--text)" }}>
        Shorts Engine
      </Link>

      <div className="flex items-center gap-4">
        {status === "loading" ? (
          <span className="text-sm" style={{ color: "var(--muted)" }}>...</span>
        ) : session?.user ? (
          <>
            <Link
              href="/profile"
              className="text-sm hover:underline"
              style={{ color: "var(--muted)" }}
            >
              {session.user.name || session.user.email}
            </Link>
            <button
              onClick={() => signOut({ callbackUrl: "/auth/login" })}
              className="text-sm px-3 py-1 rounded"
              style={{
                border: "1px solid var(--border)",
                color: "var(--text)",
              }}
            >
              Sign Out
            </button>
          </>
        ) : (
          <>
            <Link
              href="/auth/login"
              className="text-sm px-3 py-1 rounded"
              style={{ color: "var(--accent)" }}
            >
              Sign In
            </Link>
            <Link
              href="/auth/signup"
              className="text-sm px-3 py-1 rounded"
              style={{ background: "var(--accent)", color: "var(--text)" }}
            >
              Sign Up
            </Link>
          </>
        )}
      </div>
    </nav>
  );
}
