"""
Serviço principal: lê streams RTSP, roda detecção YOLO e dispara alertas.

Uso:
  cd na pasta do projeto
  pip install -r requirements.txt
  copie config.example.yaml para config.yaml e configure URLs + modelo .pt
  python -m src.main
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

from src.alerts import AlertService, AlertState
from src.config_loader import load_config
from src.http_health import start_http_server
from src.ppe_detector import PPEDetector
from src.rules import check_missing_when_person, check_violation
from src.stream_reader import FrameGrabber

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


def run_camera(
    cam: dict,
    detector: PPEDetector,
    infer_lock: threading.Lock,
    alert_svc: AlertService,
    alert_state: AlertState,
    proc: dict,
    det_cfg: dict,
) -> None:
    cam_id = cam["id"]
    url = cam["url"]
    stride = int(proc.get("frame_stride", 5))
    cooldown = float(proc.get("alert_cooldown_seconds", 30))
    mode = det_cfg.get("mode", "violation_classes")

    grabber = FrameGrabber(url=url)
    if not grabber.open():
        log.error("Câmera %s: abortando até reconexão manual.", cam_id)
        return

    frame_idx = 0
    try:
        while True:
            ok, frame = grabber.read()
            if not ok or frame is None:
                log.warning("Câmera %s: frame perdido, reconectando...", cam_id)
                grabber.release()
                time.sleep(3)
                grabber.open()
                continue

            frame_idx += 1
            if frame_idx % stride != 0:
                continue

            with infer_lock:
                dets = detector.predict(frame)
            violation = False
            matched: list[str] = []

            if mode == "violation_classes":
                violation, matched = check_violation(
                    dets, det_cfg.get("violation_classes", [])
                )
            elif mode == "missing_when_person":
                violation, matched = check_missing_when_person(
                    dets,
                    det_cfg.get("person_class", "person"),
                    det_cfg.get("required_any_of", []),
                )

            if violation and alert_state.should_emit(cam_id, cooldown):
                alert_svc.notify(
                    camera_id=cam_id,
                    reason="epi_nao_conforme",
                    details={
                        "modo": mode,
                        "classes_detectadas": [d["name"] for d in dets],
                        "violacao": matched,
                    },
                )
    finally:
        grabber.release()


def main() -> int:
    try:
        cfg = load_config()
    except FileNotFoundError as e:
        log.error("%s", e)
        return 1

    model_cfg = cfg.get("model", {})
    weights = model_cfg.get("weights", "models/ppe.pt")
    if not Path(weights).is_file():
        if model_cfg.get("fallback_yolov8n"):
            weights = "yolov8n.pt"
            log.warning(
                "model.fallback_yolov8n=true: a usar yolov8n.pt (COCO). "
                "Isto só valida o pipeline; para EPI real use um .pt treinado e fallback_yolov8n: false."
            )
        else:
            log.error(
                "Ficheiro de pesos inexistente: %s. "
                "Coloque o modelo em models/, ou defina model.fallback_yolov8n: true para testar com yolov8n.pt (download automático). "
                "Para produção, treine/exporte um YOLOv8 para EPI (ex.: Roboflow).",
                weights,
            )
            return 1

    detector = PPEDetector(
        weights=weights,
        imgsz=int(model_cfg.get("imgsz", 640)),
        conf=float(model_cfg.get("confidence", 0.45)),
        device=model_cfg.get("device"),
    )

    alerts_cfg = cfg.get("alerts", {})
    alert_svc = AlertService(
        log_console=bool(alerts_cfg.get("log_to_console", True)),
        log_file=alerts_cfg.get("log_file"),
        webhook_url=alerts_cfg.get("webhook_url"),
    )
    alert_state = AlertState()
    proc = cfg.get("processing", {})
    det_cfg = cfg.get("detection", {})

    cameras = [c for c in cfg.get("cameras", []) if c.get("enabled", True)]
    if not cameras:
        log.error("Nenhuma câmera habilitada em config.yaml.")
        return 1

    http_cfg = cfg.get("http") or {}
    if http_cfg.get("enabled", True):
        host = str(http_cfg.get("host", "0.0.0.0"))
        port = int(http_cfg.get("port", 8080))

        def _status() -> dict:
            return {
                "ok": True,
                "service": "epi-monitor",
                "cameras": len(cameras),
            }

        try:
            start_http_server(host, port, _status)
        except OSError as e:
            log.warning(
                "Servidor HTTP não iniciado (%s). Abra a porta no ufw e no painel do hosting. "
                "Ou desative com http.enabled: false no config.yaml.",
                e,
            )

    infer_lock = threading.Lock()
    threads: list[threading.Thread] = []
    for cam in cameras:
        t = threading.Thread(
            target=run_camera,
            args=(cam, detector, infer_lock, alert_svc, alert_state, proc, det_cfg),
            name=f"cam-{cam.get('id', '?')}",
            daemon=True,
        )
        t.start()
        threads.append(t)

    log.info("Monitorando %d câmera(s). Ctrl+C para encerrar.", len(threads))
    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        log.info("Encerrando...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
