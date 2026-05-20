"""Seed database with test data for development.

Production Task 2.11: Seed database with test data.

Usage:
    python -m backend.db.seed

Creates:
- 3 test users (free, pro, business plans)
- 2 sample projects per user
- Sample renders for completed projects
- Sample usage logs
"""
from __future__ import annotations

import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed():
    """Insert test data into the database."""
    try:
        import asyncpg
    except ImportError:
        print("ERROR: asyncpg not installed. Run: pip install asyncpg")
        sys.exit(1)

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set.")
        sys.exit(1)

    conn = await asyncpg.connect(database_url)

    try:
        # Check if already seeded
        count = await conn.fetchval("SELECT COUNT(*) FROM users")
        if count > 0:
            logger.info("Database already has %d users. Skipping seed.", count)
            return

        now = datetime.now(timezone.utc)

        # --- Users ---
        # Password hash for "password123" (bcrypt)
        # In real usage, generate with: bcrypt.hashpw(b"password123", bcrypt.gensalt())
        test_hash = "$2b$12$LJ3p3H2K1K8v5X9X9X9X9OX9X9X9X9X9X9X9X9X9X9X9X9X9X9"

        users = [
            {
                "email": "free@test.com",
                "name": "Free User",
                "plan": "free",
                "credits": 3,
            },
            {
                "email": "pro@test.com",
                "name": "Pro User",
                "plan": "pro",
                "credits": 30,
            },
            {
                "email": "business@test.com",
                "name": "Business User",
                "plan": "business",
                "credits": 999,
            },
        ]

        user_ids = []
        for u in users:
            uid = await conn.fetchval(
                """
                INSERT INTO users (email, name, password_hash, plan, credits_remaining, email_verified_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                u["email"],
                u["name"],
                test_hash,
                u["plan"],
                u["credits"],
                now,
            )
            user_ids.append(uid)
            logger.info("Created user: %s (%s plan)", u["email"], u["plan"])

        # --- Projects ---
        projects_data = [
            {"title": "Podcast Episode 42", "status": "done", "user_idx": 0},
            {"title": "Tech Talk Highlights", "status": "processing", "user_idx": 0},
            {"title": "Interview with CEO", "status": "done", "user_idx": 1},
            {"title": "Product Demo", "status": "failed", "user_idx": 1},
            {"title": "Conference Keynote", "status": "done", "user_idx": 2},
            {"title": "Team Meeting Recap", "status": "pending", "user_idx": 2},
        ]

        project_ids = []
        for p in projects_data:
            config = {
                "shorts_count": 3,
                "duration_per_short": 30,
                "style_tone": "Highlights",
                "subtitle_style": "TikTok-animated",
            }
            pid = await conn.fetchval(
                """
                INSERT INTO projects (user_id, title, video_filename, config_json, status)
                VALUES ($1, $2, $3, $4::jsonb, $5)
                RETURNING id
                """,
                user_ids[p["user_idx"]],
                p["title"],
                f"{p['title'].lower().replace(' ', '_')}.mp4",
                str(config).replace("'", '"'),
                p["status"],
            )
            project_ids.append(pid)
            logger.info("Created project: %s (%s)", p["title"], p["status"])

        # --- Renders (for completed projects) ---
        for i, p in enumerate(projects_data):
            if p["status"] != "done":
                continue
            for seg in range(3):
                await conn.execute(
                    """
                    INSERT INTO renders (project_id, segment_index, title, hook, start_sec, end_sec)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    project_ids[i],
                    seg,
                    f"Clip {seg + 1} from {p['title']}",
                    "This is the hook text for the clip",
                    float(seg * 30),
                    float((seg + 1) * 30),
                )
            logger.info("Created 3 renders for project: %s", p["title"])

        # --- Usage Logs ---
        for idx, uid in enumerate(user_ids):
            for day in range(7):
                await conn.execute(
                    """
                    INSERT INTO usage_logs (user_id, action, credits_used, timestamp)
                    VALUES ($1, $2, $3, $4)
                    """,
                    uid,
                    "video_processed",
                    1,
                    now - timedelta(days=day),
                )
            logger.info("Created 7 usage log entries for user #%d", idx + 1)

        # --- Subscriptions (for paid users) ---
        for idx, u in enumerate(users):
            if u["plan"] == "free":
                continue
            await conn.execute(
                """
                INSERT INTO subscriptions (user_id, plan, status, current_period_start, current_period_end)
                VALUES ($1, $2, $3, $4, $5)
                """,
                user_ids[idx],
                u["plan"],
                "active",
                now - timedelta(days=15),
                now + timedelta(days=15),
            )
            logger.info("Created subscription for %s", u["email"])

        logger.info("Seed complete! Created %d users, %d projects.", len(users), len(projects_data))

    finally:
        await conn.close()


def main():
    asyncio.run(seed())


if __name__ == "__main__":
    main()
