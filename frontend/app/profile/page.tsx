"use client";

import { useSession } from "next-auth/react";
import { redirect } from "next/navigation";

/**
 * Production Task 1.10: User profile page (name, email, avatar, plan info)
 */
export default function ProfilePage() {
  const { data: session, status } = useSession();

  if (status === "loading") {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <p style={{ color: "var(--muted)" }}>Loading...</p>
      </main>
    );
  }

  if (!session) {
    redirect("/auth/login");
  }

  const user = session.user;

  return (
    <main className="min-h-screen p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-8" style={{ color: "var(--text)" }}>
        Profile
      </h1>

      <div
        className="p-6 rounded-lg"
        style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
      >
        {/* Avatar */}
        <div className="flex items-center gap-4 mb-6">
          {user?.image ? (
            <img
              src={user.image}
              alt="Avatar"
              className="w-16 h-16 rounded-full"
            />
          ) : (
            <div
              className="w-16 h-16 rounded-full flex items-center justify-center text-xl font-bold"
              style={{ background: "var(--accent)", color: "var(--text)" }}
            >
              {(user?.name?.[0] || user?.email?.[0] || "?").toUpperCase()}
            </div>
          )}
          <div>
            <h2 className="text-lg font-semibold" style={{ color: "var(--text)" }}>
              {user?.name || "No name set"}
            </h2>
            <p className="text-sm" style={{ color: "var(--muted)" }}>
              {user?.email}
            </p>
          </div>
        </div>

        {/* Plan info */}
        <div className="space-y-4">
          <div className="flex justify-between items-center py-3 border-b" style={{ borderColor: "var(--border)" }}>
            <span className="text-sm" style={{ color: "var(--muted)" }}>Plan</span>
            <span className="text-sm font-medium px-3 py-1 rounded" style={{ background: "var(--bg)", color: "var(--accent)" }}>
              Free
            </span>
          </div>
          <div className="flex justify-between items-center py-3 border-b" style={{ borderColor: "var(--border)" }}>
            <span className="text-sm" style={{ color: "var(--muted)" }}>Email</span>
            <span className="text-sm" style={{ color: "var(--text)" }}>{user?.email}</span>
          </div>
          <div className="flex justify-between items-center py-3 border-b" style={{ borderColor: "var(--border)" }}>
            <span className="text-sm" style={{ color: "var(--muted)" }}>Account type</span>
            <span className="text-sm" style={{ color: "var(--text)" }}>
              {user?.image ? "OAuth (Google/GitHub)" : "Email/Password"}
            </span>
          </div>
        </div>

        {/* Upgrade CTA */}
        <div className="mt-6 p-4 rounded" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
          <p className="text-sm mb-2" style={{ color: "var(--text)" }}>
            Upgrade to <strong>Pro</strong> for more videos, higher quality, and priority rendering.
          </p>
          <button
            className="px-4 py-2 rounded font-medium text-sm"
            style={{ background: "var(--accent)", color: "var(--text)" }}
          >
            Upgrade Plan
          </button>
        </div>
      </div>
    </main>
  );
}
