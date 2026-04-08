# Monitor de EPI (câmeras RTSP + YOLO)

Serviço em Python que lê streams RTSP (NVR/câmeras IP), executa detecção com modelo YOLOv8 (`.pt`) e dispara alertas (log, arquivo, webhook opcional).

## Uso rápido

1. Copie `config.example.yaml` para `config.yaml` e configure URLs RTSP + caminho do modelo em `models/ppe.pt`.
2. `pip install -r requirements.txt`
3. `python -m src.main`

## VPS — erro “Configure model.weights”

Não cole o YAML no terminal (o bash tenta executar como comandos). Edite o ficheiro com `nano config.yaml` **ou** rode:

```bash
cd /opt/epi && source .venv/bin/activate && python scripts/ativar_fallback_teste.py && python -m src.main
```

1. Copie `config.example.yaml` para `config.yaml` (o script acima cria se faltar).
2. **Teste só o pipeline (sem modelo EPI):** `model.fallback_yolov8n: true` (baixa `yolov8n.pt` na primeira execução).
3. **Produção:** envie `models/ppe.pt` (SCP) e use `fallback_yolov8n: false` + classes corretas em `detection`.

## VPS

Clone, venv, `pip install -r requirements.txt`, editar `config.yaml`, `python -m src.main`.
