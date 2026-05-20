"""Simple SQL migration runner for Shorts Engine Studio.

Production Task 2.3: Migrations system.

Usage:
    python -m backend.db.migrate

Reads all .sql files in backend/db/migrations/ in alphabetical order.
Skips any that are already recorded in the _migrations table.
"""
from __future__ import annotations

import os
import sys
import glob
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_migrations():
    """Run all pending SQL migrations."""
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
        # Ensure _migrations table exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # Get already-applied migrations
        applied = set()
        rows = await conn.fetch("SELECT name FROM _migrations")
        for row in rows:
            applied.add(row["name"])

        # Find all migration files
        migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")
        files = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))

        if not files:
            logger.info("No migration files found in %s", migrations_dir)
            return

        pending = 0
        for filepath in files:
            name = os.path.basename(filepath).replace(".sql", "")
            if name in applied:
                logger.info("SKIP (already applied): %s", name)
                continue

            logger.info("APPLYING: %s", name)
            sql = open(filepath).read()
            await conn.execute(sql)

            await conn.execute(
                "INSERT INTO _migrations (name) VALUES ($1) ON CONFLICT (name) DO NOTHING",
                name,
            )
            logger.info("DONE: %s", name)
            pending += 1

        if pending == 0:
            logger.info("All migrations already applied. Nothing to do.")
        else:
            logger.info("Applied %d migration(s) successfully.", pending)

    finally:
        await conn.close()


def main():
    asyncio.run(run_migrations())


if __name__ == "__main__":
    main()
