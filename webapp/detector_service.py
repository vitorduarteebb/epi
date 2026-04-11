from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from src.config_loader import load_config
from src.ppe_detector import PPEDetector

log = logging.getLogger(__name__)

_lock = threading.Lock()
_detector: PPEDetector | None = None


def get_detector() -> PPEDetector:
    global _detector
    with _lock:
        if _detector is None:
            try:
                cfg = load_config()
            except FileNotFoundError:
                raise RuntimeError(
                    "Crie config.yaml (copie de config.example.yaml) na raiz do projeto."
                ) from None
            m = cfg.get("model", {})
            weights = m.get("weights", "models/ppe.pt")
            if not Path(weights).is_file():
                if m.get("fallback_yolov8n"):
                    weights = "yolov8n.pt"
                else:
                    raise RuntimeError(
                        "Modelo não encontrado. Coloque models/ppe.pt ou ative model.fallback_yolov8n no config.yaml."
                    )
            _detector = PPEDetector(
                weights=weights,
                imgsz=int(m.get("imgsz", 640)),
                conf=float(m.get("confidence", 0.45)),
                device=m.get("device"),
            )
            log.info("Modelo YOLO carregado para o painel web.")
        return _detector


def predict_frame(frame: Any) -> list[dict[str, Any]]:
    det = get_detector()
    return det.predict(frame)
