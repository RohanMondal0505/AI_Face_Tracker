"""Shared paths, environment settings, and tracking thresholds."""

import os
from pathlib import Path

MODEL_PATH = Path(__file__).resolve().parent / "models" / "face_landmarker.task"
ALLOWED_ORIGINS = {
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
}

BLINK_THRESHOLD = 0.50
MIN_CLOSED_FRAMES = 2
CALIBRATION_FRAMES = 30
MOVEMENT_THRESHOLD = 0.12
