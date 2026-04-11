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

O script descarrega um `.mp4` para `samples/video_teste.mp4` e define essa rota na primeira câmera (substitui o RTSP de exemplo que a VPS não consegue abrir). Só modelo, sem trocar URL: `python scripts/ativar_fallback_teste.py --sem-video`.

1. Copie `config.example.yaml` para `config.yaml` (o script acima cria se faltar).
2. **Teste só o pipeline (sem modelo EPI):** `model.fallback_yolov8n: true` (baixa `yolov8n.pt` na primeira execução).
3. **Produção:** envie `models/ppe.pt` (SCP) e use `fallback_yolov8n: false` + classes corretas em `detection`.

## Testar na VPS (sem câmera / sem RTSP)

1. O ficheiro de vídeo tem de existir **antes** de arrancar o serviço (o programa deteta se é ficheiro na primeira abertura).
2. Exemplo:

```bash
mkdir -p /opt/epi/samples
wget -qO /opt/epi/samples/video_teste.mp4 \
  "https://github.com/intel-iot-devkit/sample-videos/raw/master/person-bicycle-car-detection.mp4"
nano /opt/epi/config.yaml
```

Em `cameras` → `url` use o caminho absoluto (ex.: `"/opt/epi/samples/video_teste.mp4"`) e comente ou apague a linha RTSP de exemplo.

3. `python -m src.main` — o vídeo repete em loop para o pipeline processar continuamente.

## VPS

Clone, venv, `pip install -r requirements.txt`, editar `config.yaml`, `python -m src.main`.
