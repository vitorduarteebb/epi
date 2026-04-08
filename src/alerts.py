from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)


@dataclass
class AlertState:
    last_alert_ts: dict[str, float] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def should_emit(self, camera_id: str, cooldown_sec: float) -> bool:
        now = time.time()
        with self._lock:
            last = self.last_alert_ts.get(camera_id, 0.0)
            if now - last < cooldown_sec:
                return False
            self.last_alert_ts[camera_id] = now
            return True


class AlertService:
    def __init__(
        self,
        log_console: bool,
        log_file: str | None,
        webhook_url: str | None,
    ) -> None:
        self._log_console = log_console
        self._log_file = log_file
        self._webhook_url = webhook_url

    def notify(
        self,
        camera_id: str,
        reason: str,
        details: dict[str, Any],
    ) -> None:
        payload = {
            "camera_id": camera_id,
            "reason": reason,
            "details": details,
            "ts": time.time(),
        }
        line = json.dumps(payload, ensure_ascii=False)
        if self._log_console:
            log.warning("[ALERTA EPI] %s", line)
        if self._log_file:
            p = Path(self._log_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        if self._webhook_url:
            try:
                httpx.post(self._webhook_url, json=payload, timeout=10.0)
            except Exception as e:
                log.error("Falha ao enviar webhook: %s", e)
