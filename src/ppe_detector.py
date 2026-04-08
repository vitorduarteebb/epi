from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

log = logging.getLogger(__name__)


class PPEDetector:
    """Encapsula YOLO (Ultralytics) para inferência de EPI."""

    def __init__(self, weights: str, imgsz: int, conf: float, device: str | None) -> None:
        from ultralytics import YOLO

        w = Path(weights)
        if not w.is_file():
            raise FileNotFoundError(
                f"Pesos do modelo não encontrados: {weights}. "
                "Coloque um arquivo .pt treinado para EPI ou ajuste o caminho em config.yaml."
            )
        self._model = YOLO(str(w))
        self._imgsz = imgsz
        self._conf = conf
        self._device = device

    def predict(self, frame: np.ndarray) -> list[dict[str, Any]]:
        """Retorna lista de detecções: name, conf, xyxy."""
        kwargs: dict[str, Any] = {
            "imgsz": self._imgsz,
            "conf": self._conf,
            "verbose": False,
        }
        if self._device:
            kwargs["device"] = self._device

        results = self._model.predict(frame, **kwargs)
        out: list[dict[str, Any]] = []
        if not results:
            return out
        r0 = results[0]
        if r0.boxes is None or len(r0.boxes) == 0:
            return out
        names = r0.names or {}
        for b in r0.boxes:
            cls_id = int(b.cls[0].item())
            name = names.get(cls_id, str(cls_id))
            conf = float(b.conf[0].item())
            xyxy = b.xyxy[0].cpu().numpy().tolist()
            out.append({"name": name, "conf": conf, "xyxy": xyxy})
        return out

    @staticmethod
    def class_names_from_model(weights: str) -> dict[int, str]:
        """Útil para listar nomes após trocar o .pt."""
        from ultralytics import YOLO

        m = YOLO(weights)
        return dict(m.model.names) if hasattr(m, "model") and m.model else {}
