"""
Análise do vídeo completo: amostra frames, agrega deteções, devolve um relatório único.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2

from webapp.detection_summary import count_detection_categories, model_supports_epi_hint
from webapp.detector_service import get_model_info, predict_frame

log = logging.getLogger(__name__)


def analyze_full_video(
    video_path: Path,
    frame_stride: int = 30,
    max_frames: int = 400,
) -> dict[str, Any]:
    """
    Percorre o vídeo saltando `frame_stride` frames de cada vez (ex.: 30 ≈ 1 s a 30 fps).
    Limita a `max_frames` inferências para não bloquear a VPS durante horas.
    """
    frame_stride = max(1, frame_stride)
    max_frames = max(1, max_frames)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError("Não foi possível abrir o vídeo")

    total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    fps = float(cap.get(cv2.CAP_PROP_FPS)) or 25.0

    minfo = get_model_info()
    class_names = minfo.get("class_names") or {}
    supports = model_supports_epi_hint(class_names)
    using_fb = bool(minfo.get("using_fallback_yolov8n"))

    agg = {
        "sem_epi": 0,
        "com_epi": 0,
        "pessoa": 0,
        "coco_outro": 0,
        "outro": 0,
        "total_boxes": 0,
    }
    frames_sampled = 0
    frames_with_sem_epi = 0
    frames_with_com_epi = 0
    frames_with_person = 0
    max_pessoas_um_frame = 0
    truncated = False

    idx = 0
    while idx < total_video_frames and frames_sampled < max_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            break
        try:
            dets = predict_frame(frame)
        except Exception as e:
            log.warning("Frame %s: %s", idx, e)
            idx += frame_stride
            continue

        cats = count_detection_categories(dets)
        for k in ("sem_epi", "com_epi", "pessoa", "coco_outro", "outro"):
            agg[k] += cats.get(k, 0)
        agg["total_boxes"] += cats.get("total", 0)

        if cats.get("sem_epi", 0) > 0:
            frames_with_sem_epi += 1
        if cats.get("com_epi", 0) > 0:
            frames_with_com_epi += 1
        if cats.get("pessoa", 0) > 0:
            frames_with_person += 1
        max_pessoas_um_frame = max(max_pessoas_um_frame, cats.get("pessoa", 0))

        frames_sampled += 1
        idx += frame_stride

        if idx >= total_video_frames:
            break

    cap.release()

    # Parámos por limite de inferências mas ainda havia frames por analisar
    truncated = (frames_sampled == max_frames) and (idx < total_video_frames)

    dur_est = (total_video_frames / fps) if fps > 0 else 0

    report_pt, detail_pt = _build_full_report_pt(
        agg=agg,
        frames_sampled=frames_sampled,
        frame_stride=frame_stride,
        total_video_frames=total_video_frames,
        frames_with_sem_epi=frames_with_sem_epi,
        frames_with_com_epi=frames_with_com_epi,
        frames_with_person=frames_with_person,
        max_pessoas_um_frame=max_pessoas_um_frame,
        supports_epi=supports,
        using_fallback=using_fb,
        truncated=truncated,
        duration_sec=dur_est,
    )

    return {
        "video_frames_total": total_video_frames,
        "fps": round(fps, 2),
        "duration_sec": round(dur_est, 1),
        "frame_stride": frame_stride,
        "frames_sampled": frames_sampled,
        "max_frames_limit": max_frames,
        "truncated": truncated,
        "aggregated": agg,
        "frames_with_sem_epi": frames_with_sem_epi,
        "frames_with_com_epi": frames_with_com_epi,
        "frames_with_person": frames_with_person,
        "max_pessoas_num_frame": max_pessoas_um_frame,
        "mean_pessoas_por_frame_amostrado": round(agg["pessoa"] / frames_sampled, 2)
        if frames_sampled
        else 0,
        "report_pt": report_pt,
        "detail_pt": detail_pt,
        "summary_pt": report_pt + " " + detail_pt,
        "model_info": {
            "weights_effective": minfo.get("weights_effective"),
            "using_fallback_yolov8n": using_fb,
            "model_epi_capable": supports,
        },
    }


def _build_full_report_pt(
    *,
    agg: dict[str, int],
    frames_sampled: int,
    frame_stride: int,
    total_video_frames: int,
    frames_with_sem_epi: int,
    frames_with_com_epi: int,
    frames_with_person: int,
    max_pessoas_um_frame: int,
    supports_epi: bool,
    using_fallback: bool,
    truncated: bool,
    duration_sec: float,
) -> tuple[str, str]:
    generic = using_fallback or not supports

    linha1 = (
        f"Relatório do vídeo (~{duration_sec:.0f} s, {total_video_frames} frames): "
        f"analisámos {frames_sampled} frame(s) amostrado(s) (a cada {frame_stride} frames)."
    )
    if truncated:
        linha1 += " Análise limitada ao máximo configurado — vídeo longo."

    linha2 = (
        f"Soma de todas as caixas no vídeo: {agg['pessoa']} «pessoa», "
        f"{agg['sem_epi']} alerta(s) sem EPI, {agg['com_epi']} com equipamento, "
        f"{agg['coco_outro']} objeto(s) COCO, {agg['outro']} outras classes. "
        f"Frames amostrados com pelo menos uma pessoa: {frames_with_person}. "
        f"Máximo de pessoas num único frame: {max_pessoas_um_frame}."
    )

    if generic:
        linha3 = (
            "Com modelo COCO/genérico não existe resposta «X pessoas com EPI e Y sem EPI» no conjunto do vídeo: "
            "só contamos caixas «pessoa» e objetos. A mesma pessoa repetida em vários frames aumenta a contagem."
        )
    else:
        linha3 = (
            f"Em {frames_with_sem_epi} frame(s) amostrado(s) apareceu pelo menos um alerta de falta de EPI; "
            f"em {frames_with_com_epi} apareceu equipamento detetado. "
            "Isto resume o que o modelo viu — confirma visualmente se necessário."
        )

    return linha1, linha2 + " " + linha3
