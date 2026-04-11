# Monitor de EPI (câmeras RTSP + YOLO)

Serviço em Python que lê streams RTSP (NVR/câmeras IP), executa detecção com modelo YOLOv8 (`.pt`) e dispara alertas (log, arquivo, webhook opcional).

## Painel web (treino + tempo real)

Interface **local** (FastAPI) — sem chamadas a APIs de IA na nuvem: o modelo corre na tua máquina/VPS.

- **Treino:** envia vídeos, vê deteções frame a frame e marca **Correto** / **Incorreto** (grava em SQLite para futura exportação/retreino).
- **Vídeo inteiro:** botão **Analisar vídeo inteiro** (ou `POST /api/video/{id}/analyze-full`) amostra o ficheiro e devolve **um relatório agregado** em português (não substitui a vista frame a frame).
- **Tempo real:** indica URL RTSP ou caminho de um `.mp4` no servidor; vê o fluxo com caixas desenhadas (MJPEG).

Na raiz do projeto, com `config.yaml` e venv ativo:

```bash
pip install -r requirements.txt
python -m uvicorn webapp.app:app --host 0.0.0.0 --port 8090
```

Abre no browser: `http://SEU_IP:8090` (na VPS abre também a porta **8090** no firewall / painel do hosting).

**Se no browser vires 404 em `/api/stats` ou `/api/model-info`:** o processo na porta 8090 **não** é o uvicorn deste painel. Exemplos típicos: `python -m http.server 8090` (só ficheiros estáticos), ou nginx a servir HTML sem fazer **proxy** de `/api` e `/static` para o uvicorn. Solução: na raiz do projeto, com venv ativo, `python -m uvicorn webapp.app:app --host 0.0.0.0 --port 8090`. Confirma com `curl http://127.0.0.1:8090/api/health` — deve devolver JSON com `service: epi-web`.

**Se abrires o site na porta 80 (ou outra) mas o uvicorn só na 8090:** os `fetch` para `/api/...` vão bater no servidor da porta 80 e dão 404. Ou fazes **proxy** no nginx de `/`, `/static` e `/api` para `127.0.0.1:8090`, ou abres diretamente `http://SEU_IP:8090`, ou no `index.html` defines `<meta name="epi-api-base" content="http://SEU_IP:8090" />` (sem barra no fim) para o JavaScript chamar a API na porta certa.

**404 mesmo em `http://IP:8090/api/...`:** a porta 8090 está ocupada por **outro programa** ou um uvicorn **antigo/errado**. Na VPS: `ss -tlnp | grep 8090` e `curl -s http://127.0.0.1:8090/api/health` — tem de ser JSON com `"service":"epi-web"`. Se `curl http://127.0.0.1:8090/openapi.json` falhar, não é esta app. Mata o processo na 8090 (`fuser -k 8090/tcp`) e volta a arrancar só `python -m uvicorn webapp.app:app --host 0.0.0.0 --port 8090` em `/opt/epi`. Opcional: copia `deploy/epi-web.service` para `/etc/systemd/system/`, `systemctl daemon-reload`, `systemctl enable --now epi-web`.

O painel de **Treino** mostra: taxa de acerto global, totais (correto/incorreto), tendência nos últimos até 50 registos, gráfico de atividade por dia, tabela por vídeo e histórico recente — dados vêm de `data/web_feedback.db` (endpoint `GET /api/stats`).

Em cada frame, o quadro **«O que a IA está a dizer»** explica em português: com **yolov8n** (COCO) só aparecem pessoas/objetos genéricos — **não** mede capacete/colete; com um `models/ppe.pt` treinado para EPI, o texto reflete classes como «sem capacete», etc.

O monitor em linha de comando (`python -m src.main`) e o painel são **serviços separados**; podes usar só um deles ou os dois (portas diferentes: 8080 health do CLI vs 8090 painel).

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

## Abrir no browser (health check)

O monitor **não** usa a porta 80 por defeito. Com o serviço a correr (`python -m src.main`), abre:

**`http://SEU_IP:8080/`** (página simples) ou **`http://SEU_IP:8080/health`** (JSON).

Na VPS:

```bash
ufw allow 8080/tcp
ufw reload
```

No **painel do hosting** (Hostinger, etc.), abre também a porta **8080** nas regras de firewall / rede — o `ufw` sozinho não chega se o provedor bloquear tráfego de entrada.

Para desativar o HTTP: em `config.yaml`, `http.enabled: false`.

## VPS

Clone, venv, `pip install -r requirements.txt`, editar `config.yaml`, `python -m src.main`.
