"""Stateful face tracking shared by browser sessions (no webcam side effects)."""

import time

import cv2
import mediapipe as mp
import numpy as np

from ..config import (
    MODEL_PATH,
    BLINK_THRESHOLD,
    MIN_CLOSED_FRAMES,
    CALIBRATION_FRAMES,
    MOVEMENT_THRESHOLD,
)
from ..schemas.tracking import LandmarkPoint, TrackingResult


class FaceTracker:
    def __init__(self):
        if not MODEL_PATH.is_file():
            raise FileNotFoundError(f"Model not found: {MODEL_PATH}")
        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL_PATH)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_faces=1,
            output_face_blendshapes=True,
        )
        self.landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)
        self.started = time.monotonic()
        self.timestamp = -1
        self.reset()

    def reset(self):
        self.blink_count = 0
        self.closed_frames = 0
        self.eyes_were_closed = False
        self.baseline_samples = []
        self.baseline = None

    def close(self):
        self.landmarker.close()

    def process(self, encoded_frame: bytes) -> TrackingResult:
        frame = cv2.imdecode(np.frombuffer(encoded_frame, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Invalid image. Send a JPEG frame.")
        if max(frame.shape[:2]) > 1280:
            raise ValueError("Frame dimensions must not exceed 1280 pixels.")
        # Browser sends unmirrored frames; match the original selfie view here.
        rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
        self.timestamp = max(int((time.monotonic() - self.started) * 1000), self.timestamp + 1)
        result = self.landmarker.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)),
            self.timestamp,
        )
        payload: TrackingResult = {
            "type": "result", "face_detected": bool(result.face_landmarks),
            "blink_count": self.blink_count, "eye_status": "—", "head_status": "NO FACE",
            "calibration_progress": 1.0 if self.baseline is not None else 0.0,
            "landmarks": [],
        }
        if not result.face_landmarks:
            self.closed_frames = 0
            self.eyes_were_closed = False
            if self.baseline is None:
                self.baseline_samples.clear()
            return payload

        landmarks = result.face_landmarks[0]
        scores = {item.category_name: item.score for item in result.face_blendshapes[0]} if result.face_blendshapes else {}
        both_closed = all(scores.get(name, 0) > BLINK_THRESHOLD for name in ("eyeBlinkLeft", "eyeBlinkRight"))
        if both_closed:
            self.closed_frames += 1
            if self.closed_frames >= MIN_CLOSED_FRAMES:
                self.eyes_were_closed = True
        else:
            if self.eyes_were_closed:
                self.blink_count += 1
            self.closed_frames = 0
            self.eyes_were_closed = False

        left, right, top, bottom = [landmarks[i] for i in (234, 454, 10, 152)]
        position = np.array([
            (left.x + right.x) / 2, (top.y + bottom.y) / 2,
            max(abs(right.x - left.x), 0.001), max(abs(bottom.y - top.y), 0.001),
        ])
        head_status = "CALIBRATING"
        if self.baseline is None:
            self.baseline_samples.append(position)
            if len(self.baseline_samples) >= CALIBRATION_FRAMES:
                self.baseline = np.mean(self.baseline_samples, axis=0)
        if self.baseline is not None:
            dx, dy = (position[:2] - self.baseline[:2]) / self.baseline[2:]
            directions = []
            if dx < -MOVEMENT_THRESHOLD:
                directions.append("LEFT")
            elif dx > MOVEMENT_THRESHOLD:
                directions.append("RIGHT")
            if dy < -MOVEMENT_THRESHOLD:
                directions.append("UP")
            elif dy > MOVEMENT_THRESHOLD:
                directions.append("DOWN")
            head_status = " + ".join(directions) or "CENTER"
        landmark_points: list[LandmarkPoint] = [
            LandmarkPoint(x=float(point.x), y=float(point.y))
            for point in landmarks
        ]
        payload.update(
            blink_count=self.blink_count,
            eye_status="CLOSED" if both_closed else "OPEN",
            head_status=head_status,
            calibration_progress=min(len(self.baseline_samples) / CALIBRATION_FRAMES, 1.0),
            landmarks=landmark_points,
        )
        return payload
