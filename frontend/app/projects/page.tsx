"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

/**
 * Production Task 13.2: Project List Page
 *
 * Shows a grid view of user projects with:
 * - Search input at top
 * - Sort dropdown (newest, oldest, favorites)
 * - Project cards with title, status badge, date, thumbnail placeholder
 * - Each card links to project detail
 */

interface ProjectSummary {
  id: string;
  title: string;
  status: string;
  is_favorite: boolean;
  thumbnail_url: string | null;
  clip_count: number;
  created_at: string;
  updated_at: string;
}

interface ProjectListResponse {
  projects: ProjectSummary[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

type SortOption = "newest" | "oldest" | "favorites";

const STATUS_COLORS: Record<string, string> = {
  pending: "var(--muted)",
  processing: "var(--accent)",
  completed: "var(--success)",
  failed: "var(--error)",
  reprocessing: "var(--accent)",
};

function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] || "var(--muted)";
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: "9999px",
        fontSize: "0.7rem",
        fontWeight: 600,
        textTransform: "uppercase",
        letterSpacing: "0.05em",
        backgroundColor: `color-mix(in srgb, ${color} 20%, transparent)`,
        color: color,
        border: `1px solid ${color}`,
      }}
    >
      {status}
    </span>
  );
}

function ProjectCard({ project }: { project: ProjectSummary }) {
  const date = new Date(project.created_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <Link
      href={`/projects/${project.id}`}
      style={{ textDecoration: "none", color: "inherit" }}
    >
      <div
        style={{
          backgroundColor: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "12px",
          overflow: "hidden",
          transition: "border-color 0.2s, transform 0.2s",
          cursor: "pointer",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = "var(--accent)";
          e.currentTarget.style.transform = "translateY(-2px)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = "var(--border)";
          e.currentTarget.style.transform = "translateY(0)";
        }}
      >
        {/* Thumbnail placeholder */}
        <div
          style={{
            width: "100%",
            aspectRatio: "16/9",
            backgroundColor: "var(--bg)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            position: "relative",
          }}
        >
          {project.thumbnail_url ? (
            <img
              src={project.thumbnail_url}
              alt={project.title}
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          ) : (
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="var(--muted)"
              strokeWidth="1.5"
            >
              <rect x="2" y="4" width="20" height="16" rx="2" />
              <polygon points="10,8 16,12 10,16" fill="var(--muted)" stroke="none" />
            </svg>
          )}
          {/* Favorite star */}
          {project.is_favorite && (
            <span
              style={{
                position: "absolute",
                top: "8px",
                right: "8px",
                fontSize: "1.2rem",
              }}
            >
              ⭐
            </span>
          )}
          {/* Clip count badge */}
          {project.clip_count > 0 && (
            <span
              style={{
                position: "absolute",
                bottom: "8px",
                right: "8px",
                backgroundColor: "rgba(0,0,0,0.75)",
                color: "var(--text)",
                padding: "2px 6px",
                borderRadius: "4px",
                fontSize: "0.7rem",
                fontWeight: 600,
              }}
            >
              {project.clip_count} clip{project.clip_count !== 1 ? "s" : ""}
            </span>
          )}
        </div>

        {/* Card body */}
        <div style={{ padding: "12px 16px" }}>
          <h3
            style={{
              margin: "0 0 8px 0",
              fontSize: "0.95rem",
              fontWeight: 600,
              color: "var(--text)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {project.title}
          </h3>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <StatusBadge status={project.status} />
            <span style={{ fontSize: "0.75rem", color: "var(--muted)" }}>
              {date}
            </span>
          </div>
        </div>
      </div>
    </Link>
  );
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortOption>("newest");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchProjects();
  }, [search, sort, page]);

  async function fetchProjects() {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        sort,
        page: String(page),
        page_size: "12",
      });
      if (search.trim()) {
        params.set("search", search.trim());
      }

      const response = await fetch(`/api/projects?${params.toString()}`);
      if (!response.ok) throw new Error("Failed to fetch projects");

      const data: ProjectListResponse = await response.json();
      setProjects(data.projects);
      setTotal(data.total);
      setHasNext(data.has_next);
    } catch (err) {
      console.error("Error fetching projects:", err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "32px 24px" }}>
      {/* Page header */}
      <div style={{ marginBottom: "24px" }}>
        <h1
          style={{
            fontSize: "1.75rem",
            fontWeight: 700,
            color: "var(--text)",
            margin: "0 0 4px 0",
          }}
        >
          My Projects
        </h1>
        <p style={{ color: "var(--muted)", margin: 0, fontSize: "0.9rem" }}>
          {total} project{total !== 1 ? "s" : ""} total
        </p>
      </div>

      {/* Search and sort controls */}
      <div
        style={{
          display: "flex",
          gap: "12px",
          marginBottom: "24px",
          flexWrap: "wrap",
        }}
      >
        {/* Search input */}
        <div style={{ flex: 1, minWidth: "200px" }}>
          <input
            type="text"
            placeholder="Search projects..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            style={{
              width: "100%",
              padding: "10px 14px",
              borderRadius: "8px",
              border: "1px solid var(--border)",
              backgroundColor: "var(--surface)",
              color: "var(--text)",
              fontSize: "0.9rem",
              outline: "none",
              transition: "border-color 0.2s",
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "var(--accent)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "var(--border)";
            }}
          />
        </div>

        {/* Sort dropdown */}
        <select
          value={sort}
          onChange={(e) => {
            setSort(e.target.value as SortOption);
            setPage(1);
          }}
          style={{
            padding: "10px 14px",
            borderRadius: "8px",
            border: "1px solid var(--border)",
            backgroundColor: "var(--surface)",
            color: "var(--text)",
            fontSize: "0.9rem",
            outline: "none",
            cursor: "pointer",
            minWidth: "140px",
          }}
        >
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
          <option value="favorites">Favorites first</option>
        </select>
      </div>

      {/* Project grid */}
      {loading ? (
        <div
          style={{
            textAlign: "center",
            padding: "64px 0",
            color: "var(--muted)",
          }}
        >
          <p>Loading projects...</p>
        </div>
      ) : projects.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: "64px 0",
            color: "var(--muted)",
          }}
        >
          <svg
            width="64"
            height="64"
            viewBox="0 0 24 24"
            fill="none"
            stroke="var(--muted)"
            strokeWidth="1.5"
            style={{ margin: "0 auto 16px" }}
          >
            <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          </svg>
          <p style={{ fontSize: "1.1rem", marginBottom: "4px" }}>
            No projects yet
          </p>
          <p style={{ fontSize: "0.85rem" }}>
            Upload a video to create your first project
          </p>
        </div>
      ) : (
        <>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
              gap: "20px",
            }}
          >
            {projects.map((project) => (
              <ProjectCard key={project.id} project={project} />
            ))}
          </div>

          {/* Pagination */}
          {total > 12 && (
            <div
              style={{
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                gap: "12px",
                marginTop: "32px",
              }}
            >
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                style={{
                  padding: "8px 16px",
                  borderRadius: "6px",
                  border: "1px solid var(--border)",
                  backgroundColor: page <= 1 ? "transparent" : "var(--surface)",
                  color: page <= 1 ? "var(--muted)" : "var(--text)",
                  cursor: page <= 1 ? "not-allowed" : "pointer",
                  fontSize: "0.85rem",
                }}
              >
                Previous
              </button>
              <span style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
                Page {page} of {Math.ceil(total / 12)}
              </span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={!hasNext}
                style={{
                  padding: "8px 16px",
                  borderRadius: "6px",
                  border: "1px solid var(--border)",
                  backgroundColor: !hasNext ? "transparent" : "var(--surface)",
                  color: !hasNext ? "var(--muted)" : "var(--text)",
                  cursor: !hasNext ? "not-allowed" : "pointer",
                  fontSize: "0.85rem",
                }}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
