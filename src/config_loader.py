from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | None = None) -> dict[str, Any]:
    base = Path(__file__).resolve().parent.parent
    cfg_path = Path(path or os.environ.get("EPI_CONFIG", base / "config.yaml"))
    if not cfg_path.is_file():
        raise FileNotFoundError(
            f"Arquivo de configuração não encontrado: {cfg_path}. "
            "Copie config.example.yaml para config.yaml e edite."
        )
    with open(cfg_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}
