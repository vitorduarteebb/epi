from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def read_frame(video_path: Path, index: int) -> tuple[np.ndarray | None, int]:
    """Lê um frame por índice. Devolve (frame, total_frames_aprox)."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None, 0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return None, total
    return frame, total


def draw_detections(
    frame: np.ndarray,
    detections: list[dict],
    color_ok: tuple[int, int, int] = (0, 220, 100),
) -> np.ndarray:
    out = frame.copy()
    for d in detections:
        xyxy = d.get("xyxy") or []
        if len(xyxy) < 4:
            continue
        x1, y1, x2, y2 = map(int, xyxy[:4])
        label = f"{d.get('name', '?')} {float(d.get('conf', 0)):.2f}"
        cv2.rectangle(out, (x1, y1), (x2, y2), color_ok, 2)
        cv2.putText(
            out,
            label,
            (x1, max(0, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color_ok,
            1,
            cv2.LINE_AA,
        )
    return out


def encode_jpeg(frame: np.ndarray, quality: int = 85) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("Falha ao codificar JPEG")
    return buf.tobytes()
