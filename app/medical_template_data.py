"""Медицинский шаблон предприятия (template_code=medical) для wizard / Docker seed."""

from __future__ import annotations

from app.template_constants import MEDICAL_TEMPLATE_CODE

# Оргструктура медицинского центра (отделения = dept_type_code для развёртывания должностей).
MEDICAL_ORG_UNITS: list[dict] = [
    {"code": "company", "name": "Медицинский центр", "unit_type": "company", "parent_code": None, "sort_order": 0},
    {"code": "ADM", "name": "Администрация", "unit_type": "department", "parent_code": "company", "sort_order": 10, "segment_code": "ADMINISTRATIVE"},
    {"code": "OPER", "name": "Медицинский блок", "unit_type": "department", "parent_code": "company", "sort_order": 20, "segment_code": "CLINIC"},
    {"code": "POLYCLINNC", "name": "Поликлиника", "unit_type": "department", "parent_code": "company", "sort_order": 30, "segment_code": "POLYCLINIC"},
    {"code": "STAT", "name": "Стационар", "unit_type": "department", "parent_code": "company", "sort_order": 40, "segment_code": "CLINIC"},
    {"code": "QUAL", "name": "Контроль качества", "unit_type": "department", "parent_code": "company", "sort_order": 50, "segment_code": "PARACLINIC"},
    {"code": "ADMISSION", "name": "Колл-центр и регистратура", "unit_type": "department", "parent_code": "company", "sort_order": 60, "segment_code": "SERVICE"},
    {"code": "FACILITY", "name": "Хозяйственная служба", "unit_type": "department", "parent_code": "company", "sort_order": 70, "segment_code": "AUXILIARY"},
    {"code": "ECON", "name": "Экономический блок", "unit_type": "department", "parent_code": "company", "sort_order": 80, "segment_code": "ADMINISTRATIVE"},
]

MEDICAL_SEGMENT_CODE_SEEDS: list[tuple[str, str, str, int]] = [
    (MEDICAL_TEMPLATE_CODE, "CLINIC", "Клиника (стационар)", 10),
    (MEDICAL_TEMPLATE_CODE, "PARACLINIC", "Параклиника", 20),
    (MEDICAL_TEMPLATE_CODE, "POLYCLINIC", "Поликлиника", 30),
    (MEDICAL_TEMPLATE_CODE, "AUXILIARY", "Вспомогательные службы", 40),
    (MEDICAL_TEMPLATE_CODE, "SERVICE", "Сервисные подразделения", 50),
    (MEDICAL_TEMPLATE_CODE, "ADMINISTRATIVE", "Управление", 60),
]

# position_code, name_ru, function_code, level, managerial, dept_type_code
MEDICAL_POSITION_SPECS: list[dict] = [
    {"position_code": "ADM_DIRECTOR", "position_name_ru": "Директор", "function_code": "ADM", "position_level": "DIR", "is_managerial": True, "dept_type_code": "ADM"},
    {"position_code": "MAIN_NURSE", "position_name_ru": "Главная медсестра", "function_code": "ADM", "position_level": "HEAD", "is_managerial": True, "dept_type_code": "ADM"},
    {"position_code": "ADM_ZAMADM", "position_name_ru": "Заместитель директора по административным вопросам", "function_code": "ADM", "position_level": "HEAD", "is_managerial": True, "dept_type_code": "ADM"},
    {"position_code": "ADM_ZAM_LECH", "position_name_ru": "Заместитель директора по медицинской части", "function_code": "MED", "position_level": "HEAD", "is_managerial": True, "dept_type_code": "OPER"},
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
    {"position_code": "ORDERLY", "position_name_ru": "Санитар", "function_code": "MED", "position_level": "SPEC", "is_managerial": False, "dept_type_code": "STAT"},
    {"position_code": "NURSE_HOUSEKEEP", "position_name_ru": "Медсестра по хозяйству", "function_code": "ADM", "position_level": "SPEC", "is_managerial": False, "dept_type_code": "FACILITY"},
]

MEDICAL_REGULATION_SPECS: list[dict] = [
    {"position_code": "ORDINATOR amb", "regulation_code": "REG_DOC_AMBUL_V1", "regulation_name": "Регламент: Врач амбулаторного приёма", "dept_type_code": "POLYCLINNC"},
    {"position_code": "ORDINATOR hosp", "regulation_code": "REG_DOC_INPATIENT_V1", "regulation_name": "Регламент: Врач стационара", "dept_type_code": "STAT"},
    {"position_code": "ADM_ZAM_LECH", "regulation_code": "REG_ADM_ZAM_LECH_V1", "regulation_name": "Регламент: Заместитель директора по медицинской части", "dept_type_code": "OPER"},
    {"position_code": "ADM_ZAM_POLYCLINIC", "regulation_code": "REG_ADM_ZAM_AMBUL_V1", "regulation_name": "Регламент: Заместитель директора по амбулаторной помощи", "dept_type_code": "POLYCLINNC"},
    {"position_code": "ADM_ZAM_QM", "regulation_code": "REG_ADM_ZAM_QUAL_V1", "regulation_name": "Регламент: Заместитель директора по качеству", "dept_type_code": "QUAL"},
    {"position_code": "HEAD_DEPT", "regulation_code": "REG_HEAD_DEPT_V1", "regulation_name": "Регламент: Заведующий отделением", "dept_type_code": "STAT"},
    {"position_code": "NURSE amb", "regulation_code": "REG_NURSE_AMBUL_V1", "regulation_name": "Регламент: Медсестра амбулаторного приёма", "dept_type_code": "POLYCLINNC"},
    {"position_code": "POST_NURSE", "regulation_code": "REG_WARD_NURSE_V1", "regulation_name": "Регламент: Постовая медсестра", "dept_type_code": "STAT"},
    {"position_code": "CALL OPERATOR cold", "regulation_code": "REG_CALL_OUTBOUND_V1", "regulation_name": "Регламент: Оператор исходящих звонков", "dept_type_code": "ADMISSION"},
    {"position_code": "CALL OPERATOR warm", "regulation_code": "REG_CALL_REG_V1", "regulation_name": "Регламент: Оператор регистратуры", "dept_type_code": "ADMISSION"},
    {"position_code": "PROCEDURE_NURSE", "regulation_code": "REG_NURSE_PROCEDURE_V1", "regulation_name": "Регламент: Медсестра процедурного кабинета", "dept_type_code": "POLYCLINNC"},
    {"position_code": "ORDERLY", "regulation_code": "REG_ORDERLY_V1", "regulation_name": "Регламент: Санитар", "dept_type_code": "STAT"},
    {"position_code": "NURSE_HOUSEKEEP", "regulation_code": "REG_NURSE_HOUSEKEEP_V1", "regulation_name": "Регламент: Медсестра по хозяйству", "dept_type_code": "FACILITY"},
    {"position_code": "DEPT_CHIEF_NURSE", "regulation_code": "REG_DEPT_CHIEF_NURSE_V1", "regulation_name": "Регламент: Старшая медсестра отделения", "dept_type_code": "STAT"},
    {"position_code": "ADM_ZAMADM", "regulation_code": "REG_ADM_ZAMADM_V1", "regulation_name": "Регламент: Заместитель директора по административным вопросам", "dept_type_code": "ADM"},
    {"position_code": "MAIN_NURSE", "regulation_code": "REG_MAIN_NURSE_V1", "regulation_name": "Регламент: Главная медсестра", "dept_type_code": "ADM"},
    {"position_code": "ADM_DIRECTOR", "regulation_code": "REG_ADM_DIRECTOR_V1", "regulation_name": "Регламент: Директор медицинского центра", "dept_type_code": "ADM"},
]
