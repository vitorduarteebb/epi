"""
Textos em português para o painel: explicar se o modelo mede EPI ou só objetos genéricos.
Contagens: pessoas, com EPI, sem EPI (alertas), etc.
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

_COCO_VEH = frozenset({"car", "bicycle", "motorcycle", "bus", "truck", "boat", "train", "aeroplane"})


def model_supports_epi_hint(class_names: dict[Any, str] | None) -> bool:
    if not class_names:
        return False
    blob = " ".join(str(v) for v in class_names.values())
    return bool(_EPI_CLASS_HINTS.search(blob))


def _categorize(name: str) -> str:
    """sem_epi | com_epi | pessoa | coco_outro | outro"""
    n = (name or "").strip().lower()
    if not n:
        return "outro"
    if _VIOLATION_HINTS.search(n) or n.startswith("no-"):
        return "sem_epi"
    if n == "person":
        return "pessoa"
    if n in _COCO_VEH:
        return "coco_outro"
    if _EPI_CLASS_HINTS.search(n) and not _VIOLATION_HINTS.search(n):
        return "com_epi"
    return "outro"


def _count_categories(detections: list[dict[str, Any]]) -> dict[str, int]:
    c = {"sem_epi": 0, "com_epi": 0, "pessoa": 0, "coco_outro": 0, "outro": 0}
    for d in detections:
        cat = _categorize(str(d.get("name", "")))
        c[cat] = c.get(cat, 0) + 1
    c["total"] = len(detections)
    return c


def friendly_detection_line(name: str, conf: float) -> tuple[str, str]:
    n = (name or "").strip()
    low = n.lower()

    if _VIOLATION_HINTS.search(low) or low.startswith("no-"):
        return (
            f"⚠ Possível não conformidade: «{n}» ({conf:.0%})",
            "bad",
        )
    if _EPI_CLASS_HINTS.search(low) and not _VIOLATION_HINTS.search(low):
        if low == "person":
            pass
        else:
            return (f"✓ Indício de equipamento: «{n}» ({conf:.0%})", "ok")

    if low == "person":
        return (
            f"Pessoa ({conf:.0%}) — modelo genérico: não indica se está com EPI",
            "neutral",
        )
    if low in _COCO_VEH:
        return (
            f"«{n}» ({conf:.0%}) — classe COCO, irrelevante para EPI neste contexto",
            "neutral",
        )
    return (f"«{n}» ({conf:.0%})", "neutral")


def _headline_pt(
    cats: dict[str, int],
    supports: bool,
    using_fallback_yolov8n: bool,
) -> tuple[str, str]:
    """
    (linha principal, sublinha curta)
    """
    p, sem_e, com_e, coco, out = (
        cats.get("pessoa", 0),
        cats.get("sem_epi", 0),
        cats.get("com_epi", 0),
        cats.get("coco_outro", 0),
        cats.get("outro", 0),
    )
    total = cats.get("total", 0)

    if total == 0:
        return "Nenhuma deteção neste frame.", "Experimenta outro índice de frame ou ajusta a confiança no config."

    generic = using_fallback_yolov8n or not supports

    bits: list[str] = []
    if p:
        bits.append(f"{p} pessoa(s)")
    if sem_e:
        bits.append(f"{sem_e} alerta(s) de possível falta de EPI")
    if com_e:
        bits.append(f"{com_e} deteção(ões) com equipamento de proteção visível")
    if coco:
        bits.append(f"{coco} objeto(s) veículo/outro (COCO)")
    if out:
        bits.append(f"{out} outra(s) classe(s)")

    linha1 = "Neste frame: " + (", ".join(bits) if bits else f"{total} objeto(s).")

    if generic:
        linha2 = (
            "Com este modelo (COCO / genérico) não há contagem «X com EPI e Y sem EPI»: "
            "só se marcam pessoas/objetos. Para números de com/sem EPI, usa um "
            "`models/ppe.pt` treinado para capacete/colete/etc."
        )
        if p and not sem_e and not com_e:
            linha1 = (
                f"Neste frame: {p} pessoa(s) detetada(s). "
                "Não é possível saber quantas estão com ou sem EPI só com este modelo."
            )
        return linha1, linha2

    linha2 = (
        "Confirma nas caixas se «alertas sem EPI» e «equipamento» batem certo com a imagem "
        "antes de marcar Correto / Incorreto."
    )
    if sem_e == 0 and com_e == 0 and p:
        linha2 = (
            f"{p} pessoa(s) sem classe explícita de EPI neste frame — "
            "pode faltar treino ou o enquadramento não mostra o equipamento."
        )
    return linha1, linha2


def build_summary(
    detections: list[dict[str, Any]],
    model_class_names: dict[int, str] | None,
    using_fallback_yolov8n: bool,
    weights_label: str,
) -> dict[str, Any]:
    supports = model_supports_epi_hint(model_class_names)
    n = len(detections)
    cats = _count_categories(detections)

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

    headline_pt, subline_pt = _headline_pt(cats, supports, using_fallback_yolov8n)

    if using_fallback_yolov8n or not supports:
        title = "Modelo genérico — não distingue «com EPI» / «sem EPI»"
        detail = (
            "As contagens de pessoas são reais; as de «com/sem EPI» só aparecem com um modelo "
            "treinado para isso (`models/ppe.pt`)."
        )
        level = "warning"
        epi_status = "nao_avaliado"
    elif bad_like > 0:
        title = f"Atenção: {bad_like} alerta(s) de possível falta de EPI"
        detail = (
            "Revê as caixas. O resumo acima indica quantos alertas «sem EPI» e quantas deteções "
            "«com equipamento» o modelo encontrou neste frame."
        )
        level = "danger"
        epi_status = "possivel_inconformidade"
    elif good_like > 0 and n > 0:
        title = "Equipamento de proteção detetado (pelo modelo)"
        detail = (
            f"Resumo numérico: {cats.get('com_epi', 0)} com EPI visível, "
            f"{cats.get('sem_epi', 0)} sem / alerta, {cats.get('pessoa', 0)} só «pessoa»."
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
            "Classes do modelo: verifica nomes explícitos de EPI. "
            f"Pesos: {weights_label}"
        )
        level = "info"
        epi_status = "generico"

    return {
        "headline_pt": headline_pt,
        "subline_pt": subline_pt,
        "banner_title": title,
        "banner_detail": detail,
        "banner_level": level,
        "epi_status": epi_status,
        "model_epi_capable": supports,
        "using_fallback_yolov8n": using_fallback_yolov8n,
        "weights_label": weights_label,
        "lines": lines,
        "counts": {
            "detections": n,
            "hint_bad": bad_like,
            "hint_ok": good_like,
            **cats,
        },
    }


def count_detection_categories(detections: list[dict[str, Any]]) -> dict[str, int]:
    """Agrega contagens por tipo de classe (uso em análise de vídeo completo)."""
    return _count_categories(detections)
