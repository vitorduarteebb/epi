"""
Ativa model.fallback_yolov8n no config.yaml (teste de pipeline na VPS sem models/ppe.pt).

Uso na VPS:
  cd /opt/epi && source .venv/bin/activate && python scripts/ativar_fallback_teste.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "config.example.yaml"
CFG = ROOT / "config.yaml"


def main() -> int:
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
