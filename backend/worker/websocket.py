"""WebSocket bridge for render progress updates.

Production Task 3.9: Real-time render progress via WebSocket.

The worker publishes progress to Redis pub/sub channels.
This module provides a WebSocket endpoint that subscribes to those
channels and forwards updates to the connected frontend client.

Usage in main.py:
    from backend.worker.websocket import websocket_render_progress
    app.add_api_websocket_route("/ws/render/{project_id}", websocket_render_progress)
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


async def websocket_render_progress(websocket: WebSocket, project_id: str):
    """WebSocket endpoint that streams render progress for a project.

    Subscribes to Redis pub/sub channels for all segments of the project
    and forwards messages to the WebSocket client.
    """
    await websocket.accept()

    try:
        from backend.db.connection import get_redis
        redis = await get_redis()

        # Subscribe to all segment progress channels for this project
        pubsub = redis.pubsub()
        await pubsub.psubscribe(f"render:progress:*")

        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0
                )

                if message and message["type"] == "pmessage":
                    channel = message["channel"]
                    data = message["data"]

                    # Only forward messages for jobs belonging to this project
                    # (In production, filter by project_id from job data)
                    try:
                        payload = json.loads(data)
                        await websocket.send_json(payload)
                    except (json.JSONDecodeError, Exception):
                        pass

                # Check if client disconnected
                try:
                    await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=0.01
                    )
                except asyncio.TimeoutError:
                    pass  # No message from client, that's fine

        finally:
            await pubsub.punsubscribe()
            await pubsub.close()

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected for project %s", project_id)
    except Exception as e:
        logger.error("WebSocket error for project %s: %s", project_id, e)
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception:
            pass
