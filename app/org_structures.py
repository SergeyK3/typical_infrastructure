r"""Справочники оргструктур для шаблонов предприятий.

Иерархия: company → отделения (department) → секции (section).
Загрузка по template_code: get_template_structure(); list_positions_from_position_catalog() для полного каталога.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Структура: отделения + секции (Step 6 update)
DEFAULT_ORG_UNITS: list[dict] = [
    {"code": "company", "name": "Компания", "unit_type": "company", "parent_code": None, "sort_order": 0},
    # Отделения (parent = company)
    {"code": "ADM", "name": "Администрация", "unit_type": "department", "parent_code": "company", "sort_order": 10},
    {"code": "HR", "name": "HR", "unit_type": "department", "parent_code": "company", "sort_order": 20},
    {"code": "MKT", "name": "Маркетинг", "unit_type": "department", "parent_code": "company", "sort_order": 30},
    {"code": "LEAD", "name": "Лидогенерация", "unit_type": "department", "parent_code": "company", "sort_order": 40},
    {"code": "SALES", "name": "Отдел продаж", "unit_type": "department", "parent_code": "company", "sort_order": 50},
    {"code": "ACC", "name": "Бухгалтерия", "unit_type": "department", "parent_code": "company", "sort_order": 60},
    {"code": "PROD", "name": "Производство", "unit_type": "department", "parent_code": "company", "sort_order": 70},
    {"code": "QUAL", "name": "Контроль качества", "unit_type": "department", "parent_code": "company", "sort_order": 80},
    {"code": "PR", "name": "Развитие, филиалы и СМИ", "unit_type": "department", "parent_code": "company", "sort_order": 90},
    # Секции (parent = код отделения)
    {"code": "ADM_MAIN", "name": "Администрация", "unit_type": "section", "parent_code": "ADM", "sort_order": 1},
    {"code": "HR_RECR_ONB", "name": "Найм и введение", "unit_type": "section", "parent_code": "HR", "sort_order": 1},
    {"code": "HR_INTAKE_REG", "name": "Регистрация входящей информации", "unit_type": "section", "parent_code": "HR", "sort_order": 2},
    {"code": "HR_REG_CTRL", "name": "Контроль регламентов", "unit_type": "section", "parent_code": "HR", "sort_order": 3},
    {"code": "MKT_ADV_MATL", "name": "Подготовка рекламных материалов", "unit_type": "section", "parent_code": "MKT", "sort_order": 1},
    {"code": "MKT_LEADGEN", "name": "Лидогенерация", "unit_type": "section", "parent_code": "LEAD", "sort_order": 1},
    {"code": "MKT_SALES", "name": "Отдел продаж", "unit_type": "section", "parent_code": "SALES", "sort_order": 1},
    {"code": "ACC_REV_ACC", "name": "Учет доходов", "unit_type": "section", "parent_code": "ACC", "sort_order": 1},
    {"code": "ACC_EXP_ACC", "name": "Учет расходов", "unit_type": "section", "parent_code": "ACC", "sort_order": 2},
    {"code": "PROD_PLAN", "name": "Планирование", "unit_type": "section", "parent_code": "PROD", "sort_order": 1},
    {"code": "PROD_PREP", "name": "Подготовка производства", "unit_type": "section", "parent_code": "PROD", "sort_order": 2},
    {"code": "PROD_CORE", "name": "Собственно производство", "unit_type": "section", "parent_code": "PROD", "sort_order": 3},
    {"code": "QUAL_MAIN", "name": "Контроль качества", "unit_type": "section", "parent_code": "QUAL", "sort_order": 1},
    {"code": "PR_MEDIA_REL", "name": "Связь со СМИ", "unit_type": "section", "parent_code": "PR", "sort_order": 1},
]

# Должности для onboarding/enterprise_templates (совместимость; deploy-template использует position_catalog из БД)
DEFAULT_POSITIONS: list[dict] = [
    {"code": "ADM_DIRECTOR", "name": "Директор", "org_unit_code": "ADM", "grade": None, "is_active": True},
    {"code": "ADM_SYS_ADMIN", "name": "Системный администратор", "org_unit_code": "ADM", "grade": None, "is_active": True},
    {"code": "HR_MANAGER", "name": "HR-менеджер", "org_unit_code": "HR", "grade": None, "is_active": True},
    {"code": "ACC_ACCOUNTANT", "name": "Бухгалтер", "org_unit_code": "ACC", "grade": None, "is_active": True},
    {"code": "MKT_MANAGER", "name": "Маркетолог", "org_unit_code": "MKT", "grade": None, "is_active": True},
    {"code": "SALES_MANAGER", "name": "Менеджер по продажам", "org_unit_code": "SALES", "grade": None, "is_active": True},
    {"code": "PROD_SUPERVISOR", "name": "Начальник производства", "org_unit_code": "PROD", "grade": None, "is_active": True},
    {"code": "QUAL_HEAD", "name": "Начальник ОКК", "org_unit_code": "QUAL", "grade": None, "is_active": True},
]

# Код отделения для администратора при onboarding
ADMIN_ORG_UNIT_CODE = "ADM"


def get_template_structure(template_code: str) -> list[dict]:
    """Возвращает структуру оргподразделений для шаблона."""
    if template_code == "default":
        return DEFAULT_ORG_UNITS.copy()
    # fallback: default
    return DEFAULT_ORG_UNITS.copy()


def get_template_positions(template_code: str, org_unit_ids_by_code: dict[str, str]) -> list[dict]:
    """Устаревший список из 8 должностей; для превью и onboarding используйте list_positions_from_position_catalog."""
    if template_code == "default":
        positions = DEFAULT_POSITIONS.copy()
    else:
        positions = DEFAULT_POSITIONS.copy()
    return positions


from app.template_constants import DEFAULT_TEMPLATE_CODE


def list_positions_from_position_catalog(db: "Session", template_code: str = DEFAULT_TEMPLATE_CODE) -> list[dict]:
    """
    Пары «типовая должность ↔ тип подразделения» для указанного template_code.
    """
    from sqlalchemy import select

    from app.models import PositionCatalog, PositionDeptType

    catalog_by_code = {
        r.position_code: r
        for r in db.scalars(
            select(PositionCatalog).where(
                PositionCatalog.template_code == template_code,
                PositionCatalog.is_active == True,
            )
        ).all()
    }
    rows: list[dict] = []
    for link in db.scalars(
        select(PositionDeptType).where(PositionDeptType.template_code == template_code)
    ).all():
        catalog = catalog_by_code.get(link.position_code)
        if not catalog:
            continue
        rows.append(
            {
                "code": catalog.position_code,
                "name": catalog.position_name_ru,
                "org_unit_code": link.dept_type_code,
                "grade": None,
                "is_active": True,
                "function_code": catalog.function_code,
                "position_level": catalog.position_level,
                "is_managerial": catalog.is_managerial,
            }
        )
    rows.sort(key=lambda x: (x["org_unit_code"], x["code"]))
    return rows


def list_template_bundle_preview(db: "Session", template_code: str) -> dict:
    """Сводка bundle для preview: positions, kpi, regulations, skills."""
    from sqlalchemy import func, select

    from app.models import KpiTemplate, PositionRegulation
    from app.template_org_resolve import resolve_template_structure

    structure = resolve_template_structure(db, template_code)
    dept_codes = {s["code"] for s in structure if s.get("unit_type") == "department"}
    positions = list_positions_from_position_catalog(db, template_code)
    position_codes = {p["code"] for p in positions}

    kpi_rows = db.scalars(
        select(KpiTemplate).where(KpiTemplate.template_code == template_code, KpiTemplate.is_active == True)
    ).all()
    kpi = [
        {"code": k.kpi_code, "name": k.kpi_name, "position_code": k.position_code}
        for k in kpi_rows
        if not k.position_code or k.position_code in position_codes
    ]

    regs = db.scalars(
        select(PositionRegulation).where(PositionRegulation.template_code == template_code)
    ).all()
    regulations = [
        {
            "code": r.regulation_code,
            "name": r.regulation_name,
            "position_code": r.position_code,
            "dept_type_code": r.dept_type_code,
        }
        for r in regs
        if r.dept_type_code in dept_codes and r.position_code in position_codes
    ]

    skills_count = 0
    try:
        from skill_assessment.infrastructure.db_models import CompetencyCatalogVersionRow, CompetencyMatrixRow

        version = db.scalar(
            select(CompetencyCatalogVersionRow)
            .where(
                CompetencyCatalogVersionRow.client_id.is_(None),
                CompetencyCatalogVersionRow.template_code == template_code,
                CompetencyCatalogVersionRow.status == "active",
            )
            .order_by(CompetencyCatalogVersionRow.created_at.desc())
            .limit(1)
        )
        if version:
            skills_count = db.scalar(
                select(func.count())
                .select_from(CompetencyMatrixRow)
                .where(CompetencyMatrixRow.version_id == version.id)
            ) or 0
    except ImportError:
        pass

    return {
        "positions": positions,
        "kpi": kpi,
        "regulations": regulations,
        "skills": [{"matrix_rows": skills_count}],
        "counts": {
            "org_units": len(structure),
            "positions": len(positions),
            "kpi": len(kpi),
            "regulations": len(regulations),
            "skills": skills_count,
        },
    }

