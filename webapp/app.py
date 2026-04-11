from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from webapp import db
from webapp import live_session
from webapp.detection_summary import build_summary
from webapp.detector_service import get_model_info, predict_frame
from webapp.video_analyze import analyze_full_video
from webapp.video_util import draw_detections, encode_jpeg, read_frame

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"
UPLOAD_DIR = ROOT / "data" / "web_uploads"

app = FastAPI(title="Monitor EPI — painel local", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/favicon.ico")
def favicon() -> RedirectResponse:
    """Evita 404 no browser quando pede /favicon.ico na raiz."""
    return RedirectResponse(url="/static/favicon.svg", status_code=307)


app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


class FeedbackBody(BaseModel):
    frame_idx: int = Field(ge=0)
    approved: bool
    detections: list[dict[str, Any]] = Field(default_factory=list)
    notes: str = ""


class LiveStartBody(BaseModel):
    url: str = Field(min_length=3)


class AnalyzeFullBody(BaseModel):
    frame_stride: int = Field(default=30, ge=1, le=600)
    max_frames: int = Field(default=400, ge=1, le=5000)


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)) -> JSONResponse:
    if not file.filename:
        raise HTTPException(400, "Ficheiro inválido")
    ext = Path(file.filename).suffix.lower()
    if ext not in (".mp4", ".avi", ".mkv", ".mov", ".webm"):
        raise HTTPException(400, "Formato não suportado. Use mp4, avi, mkv, mov ou webm.")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(file.filename).stem
    suffix = Path(file.filename).suffix.lower()
    n = 0
    while True:
        candidate = UPLOAD_DIR / (f"{stem}{suffix}" if n == 0 else f"{stem}_{n}{suffix}")
        if not candidate.exists():
            dest = candidate
            break
        n += 1

    content = await file.read()
    if len(content) > 500 * 1024 * 1024:
        raise HTTPException(400, "Ficheiro demasiado grande (máx. 500 MB).")
    dest.write_bytes(content)
    vid = db.insert_video(file.filename, dest)
    return JSONResponse({"id": vid, "path": str(dest), "name": file.filename})


@app.get("/api/videos")
def list_videos() -> JSONResponse:
    return JSONResponse({"videos": db.list_videos()})


@app.get("/api/stats")
def training_stats() -> JSONResponse:
    return JSONResponse(db.get_training_stats())


@app.get("/api/model-info")
def model_info() -> JSONResponse:
    try:
        return JSONResponse(get_model_info())
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@app.get("/api/video/{video_id}/frame/{frame_idx}")
def get_frame(video_id: str, frame_idx: int) -> JSONResponse:
    row = db.get_video(video_id)
    if not row:
        raise HTTPException(404, "Vídeo não encontrado")
    path = Path(row["path"])
    if not path.is_file():
        raise HTTPException(404, "Ficheiro em falta no disco")
    frame, total = read_frame(path, frame_idx)
    if frame is None:
        raise HTTPException(400, "Não foi possível ler o frame")
    try:
        dets = predict_frame(frame)
        minfo = get_model_info()
        summary = build_summary(
            dets,
            minfo.get("class_names"),
            bool(minfo.get("using_fallback_yolov8n")),
            str(minfo.get("weights_effective", "")),
        )
    except Exception as e:
        raise HTTPException(500, str(e)) from e
    vis = draw_detections(frame, dets)
    jpeg = encode_jpeg(vis, quality=88)
    b64 = base64.b64encode(jpeg).decode("ascii")
    return JSONResponse(
        {
            "frame_idx": frame_idx,
            "total_frames": total,
            "detections": dets,
            "image_base64": b64,
            "summary": summary,
            "model_info": {
                "weights_effective": minfo.get("weights_effective"),
                "using_fallback_yolov8n": minfo.get("using_fallback_yolov8n"),
                "model_epi_capable": summary.get("model_epi_capable"),
            },
        }
    )


@app.post("/api/video/{video_id}/analyze-full")
def analyze_video_full(
    video_id: str,
    body: AnalyzeFullBody = AnalyzeFullBody(),
) -> JSONResponse:
    """Amostra o vídeo inteiro e devolve um relatório agregado (não só um frame)."""
    row = db.get_video(video_id)
    if not row:
        raise HTTPException(404, "Vídeo não encontrado")
    path = Path(row["path"])
    if not path.is_file():
        raise HTTPException(404, "Ficheiro em falta no disco")
    stride = body.frame_stride
    mxf = body.max_frames
    try:
        report = analyze_full_video(path, frame_stride=stride, max_frames=mxf)
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        log.exception("analyze-full")
        raise HTTPException(500, str(e)) from e
    return JSONResponse(report)


@app.post("/api/video/{video_id}/feedback")
def post_feedback(video_id: str, body: FeedbackBody) -> JSONResponse:
    if not db.get_video(video_id):
        raise HTTPException(404, "Vídeo não encontrado")
    db.upsert_feedback(
        video_id,
        body.frame_idx,
        body.approved,
        body.detections,
        body.notes or None,
    )
    return JSONResponse({"ok": True})


@app.get("/api/feedback")
def get_feedback(video_id: str | None = None) -> JSONResponse:
    return JSONResponse({"items": db.list_feedback(video_id)})


@app.post("/api/live/start")
def live_start(body: LiveStartBody) -> JSONResponse:
    live_session.start_live(body.url)
    return JSONResponse({"ok": True, "status": live_session.status()})


@app.post("/api/live/stop")
def live_stop() -> JSONResponse:
    live_session.stop_live()
    return JSONResponse({"ok": True})


@app.get("/api/live/status")
def live_status() -> JSONResponse:
    return JSONResponse(live_session.status())


async def _mjpeg_generator() -> Any:
    while True:
        jpeg, err = live_session.get_snapshot_jpeg()
        if jpeg:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
        elif err:
            log.debug("live mjpeg: %s", err)
        await asyncio.sleep(0.06)


@app.get("/api/live/mjpeg")
def live_mjpeg() -> StreamingResponse:
    return StreamingResponse(
        _mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"ok": "true", "service": "epi-web"}


def main() -> None:
    import uvicorn

    uvicorn.run(
        "webapp.app:app",
        host="0.0.0.0",
        port=8090,
        reload=False,
    )


if __name__ == "__main__":
    main()
