from __future__ import annotations

from typing import Any


def normalize_name(s: str) -> str:
    return s.strip().lower().replace(" ", "_").replace("-", "_")


def check_violation(
    detections: list[dict[str, Any]],
    violation_classes: list[str],
) -> tuple[bool, list[str]]:
    """True se alguma detecção corresponde a uma classe de violação."""
    violations_norm = {normalize_name(v) for v in violation_classes}
    matched: list[str] = []
    for d in detections:
        n = normalize_name(str(d["name"]))
        if n in violations_norm or str(d["name"]) in violation_classes:
            matched.append(str(d["name"]))
    return len(matched) > 0, matched


def check_missing_when_person(
    detections: list[dict[str, Any]],
    person_class: str,
    required_any_of: list[str],
) -> tuple[bool, list[str]]:
    """
    Se houver 'person' e nenhuma das classes obrigatórias (capacete/colete), considera violação.
    Heurística simples; modelos dedicados a EPI costumam ser melhores.
    """
    p_norm = normalize_name(person_class)
    req_norm = {normalize_name(x) for x in required_any_of}
    has_person = any(normalize_name(str(d["name"])) == p_norm for d in detections)
    if not has_person:
        return False, []
    has_required = any(normalize_name(str(d["name"])) in req_norm for d in detections)
    if has_required:
        return False, []
    return True, ["person_sem_epi_obrigatorio"]
