from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

import cv2

from webapp.detector_service import predict_frame
from webapp.video_util import draw_detections, encode_jpeg

log = logging.getLogger(__name__)

_lock = threading.Lock()
_thread: threading.Thread | None = None
_running = False
_url: str | None = None
_last_jpeg: bytes | None = None
_error: str | None = None


def _open_capture(url: str) -> cv2.VideoCapture:
    p = Path(url)
    if p.is_file():
        return cv2.VideoCapture(str(p.resolve()))
    return cv2.VideoCapture(url, cv2.CAP_FFMPEG)


def _loop(url: str) -> None:
    global _last_jpeg, _error  # noqa: PLW0603
    cap = _open_capture(url)
    if not cap.isOpened():
        with _lock:
            _error = f"Não foi possível abrir: {url}"
        log.error("%s", _error)
        return

    is_file = Path(url).is_file()
    stride = 2
    n = 0
    while _running:
        ok, frame = cap.read()
        if not ok:
            if is_file:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            time.sleep(0.5)
            cap.release()
            cap = _open_capture(url)
            if not cap.isOpened():
                with _lock:
                    _error = "Stream perdido"
                break
            continue
        n += 1
        if n % stride != 0:
            continue
        try:
            dets = predict_frame(frame)
            vis = draw_detections(frame, dets)
            jpeg = encode_jpeg(vis, quality=80)
            with _lock:
                _last_jpeg = jpeg
                _error = None
        except Exception as e:
            with _lock:
                _error = str(e)
            log.exception("Inferência tempo real")

    cap.release()


def start_live(url: str) -> None:
    global _running, _thread, _url, _last_jpeg, _error
    stop_live()
    with _lock:
        _url = url.strip()
        _last_jpeg = None
        _error = None
    _running = True
    _thread = threading.Thread(target=_loop, args=(_url,), name="live-rtsp", daemon=True)
    _thread.start()


def stop_live() -> None:
    global _running, _thread
    _running = False
    if _thread is not None:
        _thread.join(timeout=5.0)
        _thread = None


def get_snapshot_jpeg() -> tuple[bytes | None, str | None]:
    with _lock:
        return _last_jpeg, _error


def status() -> dict[str, Any]:
    with _lock:
        alive = _thread is not None and _thread.is_alive()
        return {
            "running": bool(_running and alive),
            "url": _url,
            "error": _error,
        }
