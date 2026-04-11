"""
Prepara teste na VPS: fallback yolov8n + (opcional) vídeo local em vez de RTSP fictício.

Uso:
  cd /opt/epi && source .venv/bin/activate
  python scripts/ativar_fallback_teste.py          # modelo + descarrega vídeo e ajusta url
  python scripts/ativar_fallback_teste.py --sem-video   # só fallback do modelo (mantém url RTSP)
"""

from __future__ import annotations

import argparse
import shutil
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "config.example.yaml"
CFG = ROOT / "config.yaml"
SAMPLES = ROOT / "samples"
VIDEO_URL = (
    "https://github.com/intel-iot-devkit/sample-videos/raw/master/"
    "person-bicycle-car-detection.mp4"
)
VIDEO_NAME = "video_teste.mp4"


def baixar_video(dest: Path) -> None:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    print(f"A descarregar vídeo de teste para {dest} ...")
    urllib.request.urlretrieve(VIDEO_URL, dest)
    print("Download concluído.")


def main() -> int:
    p = argparse.ArgumentParser(description="Config de teste na VPS (YOLOv8n + vídeo local).")
    p.add_argument(
        "--sem-video",
        action="store_true",
        help="Só ativa fallback_yolov8n; não altera a URL da câmera.",
    )
    args = p.parse_args()

    if not CFG.is_file():
        if not EXAMPLE.is_file():
            print("Falta config.example.yaml na raiz do projeto.")
            return 1
        shutil.copy(EXAMPLE, CFG)
        print(f"Criado {CFG} a partir do exemplo.")

    with open(CFG, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    data.setdefault("model", {})
    data["model"]["fallback_yolov8n"] = True

    if not args.sem_video:
        video_path = SAMPLES / VIDEO_NAME
        if not video_path.is_file():
            try:
                baixar_video(video_path)
            except Exception as e:
                print(f"Erro ao descarregar vídeo: {e}")
                print("Coloque manualmente um .mp4 em samples/ e defina cameras[].url no config.yaml.")
                return 1

        abs_url = str(video_path.resolve())
        data.setdefault("cameras", [])
        if not data["cameras"]:
            data["cameras"] = [{"id": "teste_local", "url": abs_url, "enabled": True}]
        else:
            data["cameras"][0]["url"] = abs_url
            data["cameras"][0].setdefault("id", "teste_local")
            data["cameras"][0]["enabled"] = True
        print(f"OK: primeira câmera com url = {abs_url}")

    with open(CFG, "w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )

    print(f"OK: model.fallback_yolov8n=true em {CFG}")
    print("Agora: python -m src.main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
