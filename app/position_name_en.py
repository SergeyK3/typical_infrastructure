"""Английские названия типовых должностей для шаблонов default и hosp."""

from __future__ import annotations

# Общие должности (enterprise default и часть hosp)
DEFAULT_POSITION_NAME_EN: dict[str, str] = {
    "ADM_DIRECTOR": "Director",
    "ADM_ZAMADM": "Deputy Director for Administrative Affairs",
    "ADM_SYS_ADMIN": "System Administrator",
    "INFO_SYSTEM_SUPPORT": "Information Systems Support Specialist",
    "HR_HEAD": "Head of HR Department",
    "HR_RECRUITER": "Recruiter",
    "HR_GENERALIST": "HR Generalist",
    "MKT_MANAGER": "Marketing Specialist",
    "LEADGEN_SPECIALIST": "Lead Generation Specialist",
    "SALES_MANAGER": "Sales Manager",
    "SALES_TEAM_LEAD": "Head of Sales Department",
    "ACC_ACCOUNTANT": "Accountant",
    "ACC_CHIEF_ACCOUNTANT": "Chief Accountant",
    "PROD_SUPERVISOR": "Head of Production",
    "PROD_TECH_DIR": "Deputy Director for Production (Technical Director)",
    "QUAL_SPECIALIST": "Quality Control Specialist",
    "QUAL_HEAD": "Head of Quality Control Department",
    "PR_SPECIALIST": "Public Relations Specialist",
}

# Должности и переопределения для шаблона hosp (медицинский контур)
HOSP_POSITION_NAME_EN: dict[str, str] = {
    **DEFAULT_POSITION_NAME_EN,
    "ADM_ZAM_LECH": "Deputy Director for Medical Affairs",
    "ADM_ZAM_STRATEG": "Deputy Director for Strategy",
    "ADM_ZAM_POLYCLINIC": "Deputy Director for Outpatient Care",
    "ADM_ZAM_QM": "Deputy Director for Quality Assurance",
    "MAIN_NURSE": "Chief Nurse",
    "HEAD_DEPT": "Head of Department",
    "DEPT_CHIEF_NURSE": "Senior Ward Nurse",
    "ORDINATOR amb": "Outpatient Physician",
    "ORDINATOR hosp": "Inpatient Physician",
    "NURSE amb": "Outpatient Nurse",
    "POST_NURSE": "Ward Nurse",
    "PROCEDURE_NURSE": "Procedure Room Nurse",
    "CALL OPERATOR warm": "Call Center Operator (Registration)",
    "CALL OPERATOR cold": "Call Center Operator (Outbound)",
    "MEDREGISTR": "Medical Registrar",
    "NURSE_HOUSEKEEP": "Housekeeping Nurse",
    "ORDERLY": "Orderly",
}


def position_name_en_for(template_code: str, position_code: str) -> str | None:
    code = (position_code or "").strip()
    if not code:
        return None
    if template_code == "hosp":
        return HOSP_POSITION_NAME_EN.get(code)
    return DEFAULT_POSITION_NAME_EN.get(code)
