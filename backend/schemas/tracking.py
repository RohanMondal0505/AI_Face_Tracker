"""Typed outgoing tracking payloads (JSON-compatible dictionaries)."""

from typing import TypedDict


class LandmarkPoint(TypedDict):
    x: float
    y: float


class TrackingResult(TypedDict):
    type: str
    face_detected: bool
    blink_count: int
    eye_status: str
    head_status: str
    calibration_progress: float
    landmarks: list[LandmarkPoint]


