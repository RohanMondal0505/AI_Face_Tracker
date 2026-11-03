# AI Face Tracker

Next.js webcam frontend connected to a Python / MediaPipe backend over WebSockets.

```text
backend/
  main.py                 FastAPI server and WebSocket endpoint
  face_tracker.py         Per-session blink and head tracking
  models/face_landmarker.task
  requirements.txt
frontend/
  app/                    Next.js App Router UI
  .env.example            Optional backend URL override
  package.json
```

## Run locally

Use Python with a compatible MediaPipe wheel and Node.js 20.9 or newer. The existing
root `.venv` stays in place because moving virtual environments breaks their paths.

From the project root, install Python dependencies (already installed in this workspace):

```sh
python3 -m venv .venv # only if .venv does not already exist
.venv/bin/python -m pip install -r backend/requirements.txt
```

Terminal 1, from the project root:

```sh
.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000 --ws-max-size 1000000
```

Terminal 2, from the project root:

```sh
cd frontend
npm ci
npm run dev
```

Open **http://localhost:3000**, select **Start tracking**, and allow camera access.
Hold still for 30 detected frames to calibrate, then move or blink. **Reset session**
clears the blink count and recalibrates. **Stop tracking** closes the connection and
releases the camera. Each new connection starts a fresh session.

The backend health check is http://localhost:8000/health.

## How it connects

The browser captures JPEG frames at up to 640 pixels wide. Python mirrors each
frame and returns normalized landmarks, blink count, eye state, head position,
and calibration progress. React mirrors the video once and draws the returned
landmarks on an overlay. Only one frame is in flight at a time to avoid a backlog.
The backend does not save frames. Head direction describes movement relative to
the calibrated center, not head rotation angles. Low frame rates may miss quick blinks.

By default the WebSocket URL is `ws://<browser-hostname>:8000/ws/track` (or `wss`
on HTTPS). To override it, copy `frontend/.env.example` to `frontend/.env.local`,
edit `NEXT_PUBLIC_TRACKER_WS_URL`, and restart Next.js. For a different frontend
origin, set `FRONTEND_ORIGINS` on the Python process to a comma-separated list
of allowed origins. Localhost and 127.0.0.1 on port 3000 are allowed by default.

This setup is for local development. Remote camera use requires HTTPS and WSS,
and a public backend should add authentication and connection limits.

## Checks

```sh
cd frontend
npm run build
```

Framework references: [Next.js installation](https://nextjs.org/docs/app/getting-started/installation)
and [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/).
