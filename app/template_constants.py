r"""Константы и хелперы для bundle шаблонов предприятия."""

from __future__ import annotations

DEFAULT_TEMPLATE_CODE = "default"
MEDICAL_TEMPLATE_CODE = "medical"
LEGACY_MEDICAL_TEMPLATE_CODES = frozenset({"hosp"})


def normalize_template_code(code: str) -> str:
    c = (code or "").strip()
    if c in LEGACY_MEDICAL_TEMPLATE_CODES:
        return MEDICAL_TEMPLATE_CODE
    return c


def is_medical_template(code: str) -> bool:
    return normalize_template_code(code) == MEDICAL_TEMPLATE_CODE
