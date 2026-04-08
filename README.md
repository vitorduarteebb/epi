# Monitor de EPI (câmeras RTSP + YOLO)

Serviço em Python que lê streams RTSP (NVR/câmeras IP), executa detecção com modelo YOLOv8 (`.pt`) e dispara alertas (log, arquivo, webhook opcional).

## Uso rápido

1. Copie `config.example.yaml` para `config.yaml` e configure URLs RTSP + caminho do modelo em `models/ppe.pt`.
2. `pip install -r requirements.txt`
3. `python -m src.main`

## VPS

Veja a documentação do repositório ou o script de deploy sugerido pelo time (clone, venv, `config.yaml`, systemd).
