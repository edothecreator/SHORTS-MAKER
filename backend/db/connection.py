"""PostgreSQL connection pool and Redis client setup.

Production Tasks 2.1, 2.9, 2.10:
- PostgreSQL via asyncpg with connection pooling
- Redis via redis-py async client

Usage:
    from backend.db.connection import get_pool, get_redis

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

    redis = await get_redis()
    await redis.set("key", "value", ex=3600)
"""
from __future__ import annotations

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PostgreSQL Connection Pool (Task 2.1, 2.10)
# ---------------------------------------------------------------------------

_pool = None


async def get_pool():
    """Get or create the asyncpg connection pool.

    Uses DATABASE_URL from environment. Implements connection pooling with:
    - min_size=2 (keep 2 connections warm)
    - max_size=10 (cap at 10 concurrent connections)
    - command_timeout=60 (60s query timeout)

    Returns the pool instance. Call pool.close() on shutdown.
    """
    global _pool
    if _pool is not None:
        return _pool

    try:
        import asyncpg
    except ImportError:
        raise RuntimeError(
            "asyncpg is not installed. Run: pip install asyncpg"
        )

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Set it to your PostgreSQL connection string."
        )

    _pool = await asyncpg.create_pool(
        database_url,
        min_size=2,
        max_size=10,
        command_timeout=60,
    )
    logger.info("PostgreSQL connection pool created (min=2, max=10)")
    return _pool


async def close_pool():
    """Close the connection pool gracefully."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL connection pool closed")


# ---------------------------------------------------------------------------
# Redis Client (Task 2.9)
# ---------------------------------------------------------------------------

_redis = None


async def get_redis():
    """Get or create the async Redis client.

    Uses REDIS_URL from environment (defaults to localhost:6379).
    Used for:
    - Job queue (render jobs)
    - Session caching
    - Rate limiting counters

    Returns the redis client instance.
    """
    global _redis
    if _redis is not None:
        return _redis

    try:
        import redis.asyncio as aioredis
    except ImportError:
        raise RuntimeError(
            "redis is not installed. Run: pip install redis"
        )

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")

    _redis = aioredis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    # Test connection
    await _redis.ping()
    logger.info("Redis client connected to %s", redis_url)
    return _redis


async def close_redis():
    """Close the Redis client gracefully."""
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None
        logger.info("Redis client closed")
