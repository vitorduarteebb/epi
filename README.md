# Monitor de EPI (câmeras RTSP + YOLO)

Serviço em Python que lê streams RTSP (NVR/câmeras IP), executa detecção com modelo YOLOv8 (`.pt`) e dispara alertas (log, arquivo, webhook opcional).

## Uso rápido

1. Copie `config.example.yaml` para `config.yaml` e configure URLs RTSP + caminho do modelo em `models/ppe.pt`.
2. `pip install -r requirements.txt`
3. `python -m src.main`

## VPS — erro “Configure model.weights”

1. Copie `config.example.yaml` para `config.yaml`.
2. **Teste só o pipeline (sem modelo EPI):** em `config.yaml` defina `model.fallback_yolov8n: true` (baixa `yolov8n.pt` na primeira execução).
3. **Produção:** envie `models/ppe.pt` (SCP) e use `fallback_yolov8n: false` + classes corretas em `detection`.

## VPS

Clone, venv, `pip install -r requirements.txt`, editar `config.yaml`, `python -m src.main`.
