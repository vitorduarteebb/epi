from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import cv2

log = logging.getLogger(__name__)


@dataclass
class FrameGrabber:
    """Lê frames de um stream RTSP, HTTP ou ficheiro de vídeo (ex.: .mp4 para testes)."""

    url: str
    reconnect_delay_sec: float = 3.0
    _is_file: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> bool:
        self.release()
        self._is_file = Path(self.url).is_file()
        if self._is_file:
            # Ficheiro local: backend por defeito costuma ser mais fiável que só FFMPEG
            self._cap = cv2.VideoCapture(str(Path(self.url).resolve()))
        else:
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
        if not ok and self._is_file and self._cap is not None:
            # Volta ao início para testar pipeline sem RTSP (VPS sem acesso à câmera)
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._cap.read()
        return ok, frame
