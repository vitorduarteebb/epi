"""Lista os nomes de classe de um arquivo .pt (útil para preencher config.yaml)."""

from __future__ import annotations

import sys
from pathlib import Path

# Uso: python scripts/listar_classes_modelo.py caminho/para/modelo.pt


def main() -> int:
    if len(sys.argv) < 2:
        print("Uso: python scripts/listar_classes_modelo.py <modelo.pt>")
        return 1
    p = Path(sys.argv[1])
    if not p.is_file():
        print(f"Arquivo não encontrado: {p}")
        return 1
    from ultralytics import YOLO

    m = YOLO(str(p))
    names = m.model.names if hasattr(m, "model") and m.model else {}
    print("Classes do modelo:")
    for i, n in sorted(names.items(), key=lambda x: int(x[0])):
        print(f"  {i}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
