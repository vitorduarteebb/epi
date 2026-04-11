"""
Textos em português para o painel: explicar se o modelo mede EPI ou só objetos genéricos.
"""

from __future__ import annotations

import re
from typing import Any

# Palavras que sugerem modelo treinado para EPI / segurança
_EPI_CLASS_HINTS = re.compile(
    r"helmet|hardhat|capacete|vest|colete|mask|máscara|goggle|óculos|glove|luva|"
    r"safety|ppe|epi|no[-_]?hardhat|no[-_]?helmet|without|sem[-_ ]|viola|"
    r"no[-_]?safety|reflective|refletivo",
    re.I,
)

_VIOLATION_HINTS = re.compile(
    r"^no[-_]|without|sem[-_ ]|missing|no[-_]?hardhat|no[-_]?helmet|no[-_]?vest|"
    r"not[-_]?wearing|unprotected|incorreto|viola",
    re.I,
)


def model_supports_epi_hint(class_names: dict[Any, str] | None) -> bool:
    if not class_names:
        return False
    blob = " ".join(str(v) for v in class_names.values())
    return bool(_EPI_CLASS_HINTS.search(blob))


def friendly_detection_line(name: str, conf: float) -> tuple[str, str]:
    """
    Devolve (linha curta, nível: 'ok'|'warn'|'bad'|'neutral') para UI.
    """
    n = (name or "").strip()
    low = n.lower()

    if _VIOLATION_HINTS.search(low) or low.startswith("no-"):
        return (
            f"⚠ Possível não conformidade: «{n}» ({conf:.0%})",
            "bad",
        )
    if _EPI_CLASS_HINTS.search(low) and not _VIOLATION_HINTS.search(low):
        if "person" in low and len(low) < 12:
            pass
        else:
            return (f"✓ Indício positivo / equipamento: «{n}» ({conf:.0%})", "ok")

    if low == "person":
        return (
            f"Pessoa ({conf:.0%}) — modelo genérico: não indica se está com EPI",
            "neutral",
        )
    if low in ("car", "bicycle", "motorcycle", "bus", "truck", "boat"):
        return (f"«{n}» ({conf:.0%}) — classe COCO, irrelevante para EPI neste contexto", "neutral")
    return (f"«{n}» ({conf:.0%})", "neutral")


def build_summary(
    detections: list[dict[str, Any]],
    model_class_names: dict[int, str] | None,
    using_fallback_yolov8n: bool,
    weights_label: str,
) -> dict[str, Any]:
    """
    Resumo legível para o painel.
    """
    supports = model_supports_epi_hint(model_class_names)
    n = len(detections)

    lines: list[dict[str, Any]] = []
    bad_like = 0
    good_like = 0
    for d in detections:
        name = str(d.get("name", "?"))
        conf = float(d.get("conf", 0))
        text, level = friendly_detection_line(name, conf)
        lines.append({"name": name, "conf": conf, "text": text, "level": level})
        if level == "bad":
            bad_like += 1
        elif level == "ok":
            good_like += 1

    if using_fallback_yolov8n or not supports:
        title = "Este modelo não avalia EPI (equipamento de proteção)"
        detail = (
            "Estás a usar um YOLO genérico (ex.: yolov8n/COCO): as caixas mostram "
            "«pessoa», «carro», etc., mas não indicam se há capacete, colete ou outros EPI. "
            "Para ver «com / sem EPI», coloca em config.yaml um ficheiro "
            "`models/ppe.pt` treinado para o teu cenário (Roboflow ou treino próprio) e "
            "desativa `fallback_yolov8n`."
        )
        level = "warning"
        epi_status = "nao_avaliado"
    elif bad_like > 0:
        title = f"Atenção: {bad_like} deteção(ões) sugerem falta de EPI ou risco"
        detail = (
            "Revê as caixas vermelhas/laranja. Confirma abaixo se a IA classificou bem "
            "e usa «Correto» / «Incorreto» para o treino."
        )
        level = "danger"
        epi_status = "possivel_inconformidade"
    elif good_like > 0 and n > 0:
        title = "Deteções de equipamento / contexto de segurança"
        detail = (
            "O modelo listou classes relacionadas com EPI. Valida visualmente se "
            "correspondem à realidade antes de marcar «Correto»."
        )
        level = "success"
        epi_status = "indicios_epi"
    elif n == 0:
        title = "Nenhuma deteção neste frame"
        detail = "Aumenta a confiança mínima no config ou escolhe outro frame."
        level = "info"
        epi_status = "vazio"
    else:
        title = f"{n} objeto(s) detetado(s)"
        detail = (
            "Classes do modelo: verifica se incluem nomes explícitos de EPI. "
            f"Ficheiro de pesos: {weights_label}"
        )
        level = "info"
        epi_status = "generico"

    return {
        "banner_title": title,
        "banner_detail": detail,
        "banner_level": level,
        "epi_status": epi_status,
        "model_epi_capable": supports,
        "using_fallback_yolov8n": using_fallback_yolov8n,
        "weights_label": weights_label,
        "lines": lines,
        "counts": {"detections": n, "hint_bad": bad_like, "hint_ok": good_like},
    }
