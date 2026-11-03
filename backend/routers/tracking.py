"""WebSocket transport for per-connection face tracking."""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..config import ALLOWED_ORIGINS
from ..services.face_tracker import FaceTracker

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/track")
async def track(socket: WebSocket):
    if socket.headers.get("origin") not in ALLOWED_ORIGINS:
        await socket.close(code=1008)
        return
    await socket.accept()
    # One worker keeps model operations ordered and off the async event loop.
    executor = ThreadPoolExecutor(max_workers=1)
    loop = asyncio.get_running_loop()
    tracker = None
    try:
        tracker = await loop.run_in_executor(executor, FaceTracker)
        await socket.send_json({"type": "ready"})
        while True:
            message = await socket.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message.get("text") is not None:
                try:
                    command = json.loads(message["text"])
                except json.JSONDecodeError:
                    await socket.send_json({"type": "error", "message": "Invalid command."})
                    continue
                if isinstance(command, dict) and command.get("type") == "reset":
                    await loop.run_in_executor(executor, tracker.reset)
                    await socket.send_json({"type": "reset"})
                else:
                    await socket.send_json({"type": "error", "message": "Unknown command."})
                continue
            frame = message.get("bytes", b"")
            if not frame or len(frame) > 1_000_000:
                await socket.send_json({"type": "error", "message": "Frame must be between 1 byte and 1 MB."})
                continue
            try:
                result = await loop.run_in_executor(executor, tracker.process, frame)
            except ValueError as exc:
                await socket.send_json({"type": "error", "message": str(exc)})
                continue
            await socket.send_json(result)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Tracking session failed")
        try:
            await socket.send_json({"type": "error", "message": "Tracker failed. Check the backend terminal."})
            await socket.close(code=1011)
        except RuntimeError:
            pass
    finally:
        if tracker is not None:
            await loop.run_in_executor(executor, tracker.close)
        executor.shutdown(wait=False)
