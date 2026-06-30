"""Импорт и валидация template_org_medical.xlsx (group_id → log_group)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.medical_org_groups import (
    GROUP_ID_TO_LOG_GROUP,
    LOG_GROUP_ADMIN_HOUSEHOLD,
    LOG_GROUP_CLINICAL,
    LOG_GROUP_PARACLINICAL,
    group_id_to_log_group,
)
from app.medical_template_excel import (
    default_medical_org_excel_path,
    load_medical_org_excel,
    validate_medical_org_excel,
)
from app.medical_template_data import merged_medical_org_units


def test_medical_org_excel_exists():
    path = default_medical_org_excel_path()
    assert path.is_file(), f"missing {path}"


def test_medical_org_excel_groups_sheet_maps_all_group_ids():
    data = load_medical_org_excel()
    assert data.group_labels["1"] == "Клинические"
    assert data.group_labels["2"] == "Параклинические"
    assert "хозяйствен" in data.group_labels["3"].lower()
    errors = validate_medical_org_excel(data)
    assert errors == []


def test_medical_org_excel_department_log_groups():
    data = load_medical_org_excel()
    by_code = {r.code: r for r in data.rows if r.unit_type == "department"}
    assert by_code["POLYCLINNC"].log_group == LOG_GROUP_CLINICAL
    assert by_code["STAT"].log_group == LOG_GROUP_CLINICAL
    assert by_code["ADMISSION"].log_group == LOG_GROUP_CLINICAL
    assert by_code["OPER"].log_group == LOG_GROUP_PARACLINICAL
    assert by_code["ADM"].log_group == LOG_GROUP_ADMIN_HOUSEHOLD
    assert by_code["HR"].log_group == LOG_GROUP_ADMIN_HOUSEHOLD


def test_group_id_to_log_group_slugs():
    assert group_id_to_log_group("1") == LOG_GROUP_CLINICAL
    assert group_id_to_log_group(2) == LOG_GROUP_PARACLINICAL
    assert group_id_to_log_group("3") == LOG_GROUP_ADMIN_HOUSEHOLD
    assert set(GROUP_ID_TO_LOG_GROUP.values()) == {
        LOG_GROUP_CLINICAL,
        LOG_GROUP_PARACLINICAL,
        LOG_GROUP_ADMIN_HOUSEHOLD,
    }


def test_merged_medical_org_units_inherit_log_group_from_excel():
    units = merged_medical_org_units()
    oper = next(u for u in units if u["code"] == "OPER")
    poly = next(u for u in units if u["code"] == "POLYCLINNC")
    assert oper["log_group"] == LOG_GROUP_PARACLINICAL
    assert poly["log_group"] == LOG_GROUP_CLINICAL
    assert all(u.get("log_group") for u in units if u["unit_type"] == "department")


def test_all_main_sheet_group_ids_in_groups_sheet():
    data = load_medical_org_excel()
    used = {r.group_id for r in data.rows if r.group_id}
    assert used.issubset(set(data.group_labels))
