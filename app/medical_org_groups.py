"""Справочник групп отделений медицинского шаблона (group_id → log_group slug)."""

from __future__ import annotations

# Стабильные коды log_group (хранятся в template_org_units.log_group и org_units.log_group).
LOG_GROUP_CLINICAL = "clinical"
LOG_GROUP_PARACLINICAL = "paraclinical"
LOG_GROUP_ADMIN_HOUSEHOLD = "admin_household"

MEDICAL_LOG_GROUP_LABELS: dict[str, str] = {
    LOG_GROUP_CLINICAL: "Клинические",
    LOG_GROUP_PARACLINICAL: "Параклинические",
    LOG_GROUP_ADMIN_HOUSEHOLD: "Административно-хозяйственные",
}

# group_id из Excel «Лист1» → slug log_group / effective_log_group.
GROUP_ID_TO_LOG_GROUP: dict[str, str] = {
    "1": LOG_GROUP_CLINICAL,
    "2": LOG_GROUP_PARACLINICAL,
    "3": LOG_GROUP_ADMIN_HOUSEHOLD,
}

# Узлы без group_id (корень и служебные).
ALLOWED_EMPTY_GROUP_UNIT_TYPES = frozenset({"company"})


def normalize_group_id(raw: object) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s


def group_id_to_log_group(group_id: object) -> str | None:
    gid = normalize_group_id(group_id)
    if not gid:
        return None
    slug = GROUP_ID_TO_LOG_GROUP.get(gid)
    if slug:
        return slug
    raise ValueError(f"unknown_medical_group_id:{gid}")


def log_group_label(log_group: str | None) -> str:
    lg = (log_group or "").strip()
    if not lg:
        return ""
    return MEDICAL_LOG_GROUP_LABELS.get(lg, lg)
