"""Медицинский шаблон предприятия (template_code=medical): default + медицинские дополнения."""

from __future__ import annotations

from app.template_constants import MEDICAL_TEMPLATE_CODE

# Дополнительные узлы поверх DEFAULT_ORG_UNITS (коды, которых нет в default).
MEDICAL_ORG_UNIT_ADDITIONS: list[dict] = [
    {
        "code": "OPER",
        "name": "Операционный блок",
        "unit_type": "department",
        "parent_code": "company",
        "sort_order": 85,
        "segment_code": "CLINIC",
    },
    {
        "code": "POLYCLINNC",
        "name": "Поликлиника",
        "unit_type": "department",
        "parent_code": "company",
        "sort_order": 86,
        "segment_code": "POLYCLINIC",
    },
    {
        "code": "STAT",
        "name": "Стационар",
        "unit_type": "department",
        "parent_code": "company",
        "sort_order": 87,
        "segment_code": "CLINIC",
    },
    {
        "code": "ADMISSION",
        "name": "Колл-центр и регистратура",
        "unit_type": "department",
        "parent_code": "company",
        "sort_order": 88,
        "segment_code": "SERVICE",
    },
    {
        "code": "FACILITY",
        "name": "Хозяйственная служба",
        "unit_type": "department",
        "parent_code": "company",
        "sort_order": 89,
        "segment_code": "AUXILIARY",
    },
    {
        "code": "ECON",
        "name": "Экономический блок",
        "unit_type": "department",
        "parent_code": "company",
        "sort_order": 90,
        "segment_code": "ADMINISTRATIVE",
    },
]


def merged_medical_org_units() -> list[dict]:
    """Все узлы default плюс медицинские отделения (без замены default-структуры)."""
    from app.org_structures import DEFAULT_ORG_UNITS

    default_codes = {u["code"] for u in DEFAULT_ORG_UNITS}
    merged = [dict(u) for u in DEFAULT_ORG_UNITS]
    for spec in MEDICAL_ORG_UNIT_ADDITIONS:
        if spec["code"] not in default_codes:
            merged.append(dict(spec))
    return merged


# Обратная совместимость для импортов
MEDICAL_ORG_UNITS = merged_medical_org_units()

MEDICAL_SEGMENT_CODE_SEEDS: list[tuple[str, str, str, int]] = [
    (MEDICAL_TEMPLATE_CODE, "CLINIC", "Клиника (стационар)", 10),
    (MEDICAL_TEMPLATE_CODE, "PARACLINIC", "Параклиника", 20),
    (MEDICAL_TEMPLATE_CODE, "POLYCLINIC", "Поликлиника", 30),
    (MEDICAL_TEMPLATE_CODE, "AUXILIARY", "Вспомогательные службы", 40),
    (MEDICAL_TEMPLATE_CODE, "SERVICE", "Сервисные подразделения", 50),
    (MEDICAL_TEMPLATE_CODE, "ADMINISTRATIVE", "Управление", 60),
]

# Только должности сверх POSITION_CATALOG_SEEDS (default уже в каталоге medical при seed).
MEDICAL_POSITION_SPECS: list[dict] = [
    {"position_code": "MAIN_NURSE", "position_name_ru": "Главная медсестра", "function_code": "ADM", "position_level": "HEAD", "is_managerial": True, "dept_type_code": "ADM"},
    {"position_code": "ADM_ZAM_LECH", "position_name_ru": "Заместитель директора по медицинской части", "function_code": "MED", "position_level": "HEAD", "is_managerial": True, "dept_type_code": "OPER"},
    {"position_code": "ADM_ZAM_STRATEG", "position_name_ru": "Заместитель директора по стратегии", "function_code": "ADM", "position_level": "HEAD", "is_managerial": True, "dept_type_code": "ADM"},
    {"position_code": "ADM_ZAM_POLYCLINIC", "position_name_ru": "Заместитель директора по амбулаторной помощи", "function_code": "MED", "position_level": "HEAD", "is_managerial": True, "dept_type_code": "POLYCLINNC"},
    {"position_code": "ADM_ZAM_QM", "position_name_ru": "Заместитель директора по качеству", "function_code": "QUAL", "position_level": "HEAD", "is_managerial": True, "dept_type_code": "QUAL"},
    {"position_code": "ORDINATOR amb", "position_name_ru": "Врач амбулаторного приёма", "function_code": "MED", "position_level": "SPEC", "is_managerial": False, "dept_type_code": "POLYCLINNC"},
    {"position_code": "ORDINATOR hosp", "position_name_ru": "Врач стационара", "function_code": "MED", "position_level": "SPEC", "is_managerial": False, "dept_type_code": "STAT"},
    {"position_code": "HEAD_DEPT", "position_name_ru": "Заведующий отделением", "function_code": "MED", "position_level": "HEAD", "is_managerial": True, "dept_type_code": "STAT"},
    {"position_code": "NURSE amb", "position_name_ru": "Медсестра амбулаторного приёма", "function_code": "MED", "position_level": "SPEC", "is_managerial": False, "dept_type_code": "POLYCLINNC"},
    {"position_code": "POST_NURSE", "position_name_ru": "Постовая медсестра", "function_code": "MED", "position_level": "SPEC", "is_managerial": False, "dept_type_code": "STAT"},
    {"position_code": "PROCEDURE_NURSE", "position_name_ru": "Медсестра процедурного кабинета", "function_code": "MED", "position_level": "SPEC", "is_managerial": False, "dept_type_code": "POLYCLINNC"},
    {"position_code": "DEPT_CHIEF_NURSE", "position_name_ru": "Старшая медсестра отделения", "function_code": "MED", "position_level": "HEAD", "is_managerial": True, "dept_type_code": "STAT"},
    {"position_code": "CALL OPERATOR cold", "position_name_ru": "Оператор колл-центра (исходящие)", "function_code": "ADM", "position_level": "SPEC", "is_managerial": False, "dept_type_code": "ADMISSION"},
    {"position_code": "CALL OPERATOR warm", "position_name_ru": "Оператор колл-центра (регистрация)", "function_code": "ADM", "position_level": "SPEC", "is_managerial": False, "dept_type_code": "ADMISSION"},
    {"position_code": "MEDREGISTR", "position_name_ru": "Медицинский регистратор", "function_code": "ADM", "position_level": "SPEC", "is_managerial": False, "dept_type_code": "ADMISSION"},
    {"position_code": "ORDERLY", "position_name_ru": "Санитар", "function_code": "MED", "position_level": "SPEC", "is_managerial": False, "dept_type_code": "STAT"},
    {"position_code": "NURSE_HOUSEKEEP", "position_name_ru": "Медсестра по хозяйству", "function_code": "ADM", "position_level": "SPEC", "is_managerial": False, "dept_type_code": "FACILITY"},
]

MEDICAL_REGULATION_SPECS: list[dict] = [
    {"position_code": "ORDINATOR amb", "regulation_code": "REG_DOC_AMBUL_V1", "regulation_name": "Регламент: Врач амбулаторного приёма", "dept_type_code": "POLYCLINNC"},
    {"position_code": "ORDINATOR hosp", "regulation_code": "REG_DOC_INPATIENT_V1", "regulation_name": "Регламент: Врач стационара", "dept_type_code": "STAT"},
    {"position_code": "ADM_ZAM_LECH", "regulation_code": "REG_ADM_ZAM_LECH_V1", "regulation_name": "Регламент: Заместитель директора по медицинской части", "dept_type_code": "OPER"},
    {"position_code": "ADM_ZAM_STRATEG", "regulation_code": "REG_ADM_ZAM_STRATEG_V1", "regulation_name": "Регламент: Заместитель директора по стратегии", "dept_type_code": "ADM"},
    {"position_code": "ADM_ZAM_POLYCLINIC", "regulation_code": "REG_ADM_ZAM_AMBUL_V1", "regulation_name": "Регламент: Заместитель директора по амбулаторной помощи", "dept_type_code": "POLYCLINNC"},
    {"position_code": "ADM_ZAM_QM", "regulation_code": "REG_ADM_ZAM_QUAL_V1", "regulation_name": "Регламент: Заместитель директора по качеству", "dept_type_code": "QUAL"},
    {"position_code": "HEAD_DEPT", "regulation_code": "REG_HEAD_DEPT_V1", "regulation_name": "Регламент: Заведующий отделением", "dept_type_code": "STAT"},
    {"position_code": "NURSE amb", "regulation_code": "REG_NURSE_AMBUL_V1", "regulation_name": "Регламент: Медсестра амбулаторного приёма", "dept_type_code": "POLYCLINNC"},
    {"position_code": "POST_NURSE", "regulation_code": "REG_WARD_NURSE_V1", "regulation_name": "Регламент: Постовая медсестра", "dept_type_code": "STAT"},
    {"position_code": "CALL OPERATOR cold", "regulation_code": "REG_CALL_OUTBOUND_V1", "regulation_name": "Регламент: Оператор исходящих звонков", "dept_type_code": "ADMISSION"},
    {"position_code": "CALL OPERATOR warm", "regulation_code": "REG_CALL_REG_V1", "regulation_name": "Регламент: Оператор регистратуры", "dept_type_code": "ADMISSION"},
    {"position_code": "MEDREGISTR", "regulation_code": "REG_MEDREGISTR_V1", "regulation_name": "Регламент: Медицинский регистратор", "dept_type_code": "ADMISSION"},
    {"position_code": "PROCEDURE_NURSE", "regulation_code": "REG_NURSE_PROCEDURE_V1", "regulation_name": "Регламент: Медсестра процедурного кабинета", "dept_type_code": "POLYCLINNC"},
    {"position_code": "ORDERLY", "regulation_code": "REG_ORDERLY_V1", "regulation_name": "Регламент: Санитар", "dept_type_code": "STAT"},
    {"position_code": "NURSE_HOUSEKEEP", "regulation_code": "REG_NURSE_HOUSEKEEP_V1", "regulation_name": "Регламент: Медсестра по хозяйству", "dept_type_code": "FACILITY"},
    {"position_code": "DEPT_CHIEF_NURSE", "regulation_code": "REG_DEPT_CHIEF_NURSE_V1", "regulation_name": "Регламент: Старшая медсестра отделения", "dept_type_code": "STAT"},
    {"position_code": "MAIN_NURSE", "regulation_code": "REG_MAIN_NURSE_V1", "regulation_name": "Регламент: Главная медсестра", "dept_type_code": "ADM"},
]
