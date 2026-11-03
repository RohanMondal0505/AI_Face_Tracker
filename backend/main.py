"""Run from the project root: python -m uvicorn backend.main:app --reload."""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .face_tracker import FaceTracker, MODEL_PATH

app = FastAPI(title="AI Face Tracker")
logger = logging.getLogger(__name__)
ALLOWED_ORIGINS = set(os.getenv(
    "FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(","))


@app.get("/health")
def health():
    return {"status": "ok", "model_available": MODEL_PATH.is_file()}


@app.websocket("/ws/track")
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
