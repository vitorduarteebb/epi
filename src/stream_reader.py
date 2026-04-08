from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

log = logging.getLogger(__name__)


@dataclass
class FrameGrabber:
    """Lê frames de um stream RTSP ou arquivo de vídeo."""

    url: str
    reconnect_delay_sec: float = 3.0

    def __post_init__(self) -> None:
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> bool:
        self.release()
        self._cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        if not self._cap.isOpened():
            log.error("Não foi possível abrir o stream: %s", self.url)
            return False
        return True

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def read(self) -> tuple[bool, np.ndarray | None]:
        if self._cap is None or not self._cap.isOpened():
            return False, None
        ok, frame = self._cap.read()
        return ok, frame
