r"""D:\MyActivity\MyInfoBusiness\MyPythonApps\10 Typical_infrastructure\app\seed.py"""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Client,
    EnterpriseTemplate,
    KpiTemplate,
    PositionCatalog,
    PositionDeptType,
    PositionRegulation,
    RegulationInstruction,
    RegulationKpi,
    Role,
    TemplateOrgUnitRow,
)
from app.org_structures import DEFAULT_ORG_UNITS
from app.org_unit_ops import format_org_unit_name
from app.position_name_en import DEFAULT_POSITION_NAME_EN, position_name_en_for
from app.template_constants import DEFAULT_TEMPLATE_CODE
from app.utils import new_id32


def _id(prefix: str, code: str) -> str:
    # Deterministic 32-char ids for stable seeds
    return uuid5(NAMESPACE_URL, f"seed:{prefix}:{code}").hex


ROLE_SEEDS: list[tuple[str, str]] = [
    ("admin", "Administrator"),
    ("hr", "HR"),
    ("manager", "Manager"),
    ("employee", "Employee"),
]

TEMPLATE_SEEDS: list[dict] = [
    {
        "code": "default",
        "name": "Default enterprise template",
        "version": "1",
        "description": "Baseline template",
        "is_active": True,
    }
]

def _position_catalog_seed(
    position_code: str,
    position_name_ru: str,
    function_code: str,
    position_level: str,
    is_managerial: bool,
) -> dict:
    return {
        "position_code": position_code,
        "position_name_ru": position_name_ru,
        "position_name_en": DEFAULT_POSITION_NAME_EN.get(position_code),
        "function_code": function_code,
        "position_level": position_level,
        "is_managerial": is_managerial,
    }


# Справочник типовых должностей (формат [FUNCTION]_[ROLE])
POSITION_CATALOG_SEEDS: list[dict] = [
    _position_catalog_seed("ADM_DIRECTOR", "Директор", "ADM", "DIR", True),
    _position_catalog_seed(
        "ADM_ZAMADM",
        "Заместитель директора по административным вопросам",
        "ADM",
        "HEAD",
        True,
    ),
    _position_catalog_seed("ADM_SYS_ADMIN", "Системный администратор", "ADM", "SPEC", False),
    _position_catalog_seed(
        "INFO_SYSTEM_SUPPORT",
        "Специалист по поддержке информационных систем",
        "ADM",
        "SPEC",
        False,
    ),
    _position_catalog_seed("HR_HEAD", "Руководитель отдела кадров", "HR", "HEAD", True),
    _position_catalog_seed("HR_RECRUITER", "Рекрутер", "HR", "SPEC", False),
    _position_catalog_seed("HR_GENERALIST", "HR-генералист", "HR", "SPEC", False),
    _position_catalog_seed("MKT_MANAGER", "Маркетолог", "MKT", "MGR", True),
    _position_catalog_seed("LEADGEN_SPECIALIST", "Специалист по лидогенерации", "LEAD", "SPEC", False),
    _position_catalog_seed("SALES_MANAGER", "Менеджер по продажам", "SALES", "MGR", True),
    _position_catalog_seed("SALES_TEAM_LEAD", "Руководитель отдела продаж", "SALES", "HEAD", True),
    _position_catalog_seed("ACC_ACCOUNTANT", "Бухгалтер", "ACC", "SPEC", False),
    _position_catalog_seed("ACC_CHIEF_ACCOUNTANT", "Главный бухгалтер", "ACC", "HEAD", True),
    _position_catalog_seed("PROD_SUPERVISOR", "Начальник производства", "PROD", "HEAD", True),
    _position_catalog_seed(
        "PROD_TECH_DIR",
        "Заместитель директора по производству (технический директор)",
        "PROD",
        "HEAD",
        True,
    ),
    _position_catalog_seed("QUAL_SPECIALIST", "Специалист по контролю качества", "QUAL", "SPEC", False),
    _position_catalog_seed("QUAL_HEAD", "Начальник ОКК", "QUAL", "HEAD", True),
    _position_catalog_seed("PR_SPECIALIST", "Специалист по связям с общественностью", "PR", "SPEC", False),
]

# Связь должность ↔ тип подразделения (dept_type_code = код отделения)
POSITION_DEPT_TYPE_SEEDS: list[tuple[str, str, bool]] = [
    ("ADM_DIRECTOR", "ADM", True),
    ("ADM_ZAMADM", "ADM", True),
    ("ADM_SYS_ADMIN", "ADM", True),
    ("INFO_SYSTEM_SUPPORT", "ADM", True),
    ("HR_HEAD", "HR", True),
    ("HR_RECRUITER", "HR", True),
    ("HR_GENERALIST", "HR", True),
    ("MKT_MANAGER", "MKT", True),
    ("LEADGEN_SPECIALIST", "LEAD", True),
    ("SALES_MANAGER", "SALES", True),
    ("SALES_TEAM_LEAD", "SALES", True),
    ("ACC_ACCOUNTANT", "ACC", True),
    ("ACC_CHIEF_ACCOUNTANT", "ACC", True),
    ("PROD_SUPERVISOR", "PROD", True),
    ("PROD_TECH_DIR", "PROD", True),
    ("QUAL_SPECIALIST", "QUAL", True),
    ("QUAL_HEAD", "QUAL", True),
    ("PR_SPECIALIST", "PR", True),
]


def _regulation_code_for_position(position_code: str) -> str:
    """Код глобального регламента (совпадает с regulations_enrichment.json / DOCX)."""
    aliases = {
        "ADM_DIRECTOR": "REG_DIRECTOR_V1",
        "ADM_SYS_ADMIN": "REG_SYSADMIN_V1",
        "SALES_MANAGER": "REG_SALES_MGR_V1",
    }
    if position_code in aliases:
        return aliases[position_code]
    return f"REG_{position_code}_V1"


def _position_regulation_seeds() -> list[dict]:
    """По одному типовому регламенту на каждую должность из POSITION_CATALOG_SEEDS."""
    pos_dept: dict[str, str] = {p: d for p, d, _ in POSITION_DEPT_TYPE_SEEDS}
    rich: dict[str, dict] = {
        "HR_RECRUITER": {
            "regulation_name": "Регламент рекрутера",
            "goal_summary": "Подбор персонала в срок",
            "ckp_short": "Закрытие вакансий в срок, качество кандидатов",
            "google_doc_url": "https://docs.google.com/document/d/example_recruiter",
        },
        "SALES_MANAGER": {
            "regulation_name": "Регламент менеджера по продажам",
            "goal_summary": "Выполнение плана продаж",
            "ckp_short": "План продаж, конверсия, работа с клиентами",
            "google_doc_url": "https://docs.google.com/document/d/example_sales",
        },
    }
    rows: list[dict] = []
    for pc in POSITION_CATALOG_SEEDS:
        pcode = pc["position_code"]
        dept = pos_dept[pcode]
        name_ru = pc["position_name_ru"]
        reg_code = _regulation_code_for_position(pcode)
        row: dict = {
            "regulation_code": reg_code,
            "position_code": pcode,
            "dept_type_code": dept,
            "regulation_name": f"Регламент: {name_ru}",
            "goal_summary": (
                f"Типовой шаблон для должности «{name_ru}». "
                "Заполните цели, ЦКП и ссылки под вашу нормативку."
            ),
            "ckp_short": None,
            "google_doc_url": None,
            "version_no": "V1",
            "status": "active",
            "is_current": True,
        }
        if pcode in rich:
            row.update(rich[pcode])
        rows.append(row)
    return rows


POSITION_REGULATION_SEEDS: list[dict] = _position_regulation_seeds()

# KPI-шаблоны
KPI_TEMPLATE_SEEDS: list[dict] = [
    {"kpi_code": "KPI_SALES_PLAN", "kpi_name": "Выполнение плана продаж", "unit": "%", "period_type": "month", "default_target": 100.0},
    {"kpi_code": "KPI_CONVERSION", "kpi_name": "Конверсия", "unit": "%", "period_type": "month", "default_target": 25.0},
    {"kpi_code": "KPI_RECRUIT_TIME", "kpi_name": "Время закрытия вакансии", "unit": "дней", "period_type": "month", "default_target": 30.0},
    {"kpi_code": "KPI_QUALITY_DEFECTS", "kpi_name": "Количество дефектов", "unit": "шт", "period_type": "month", "default_target": 0.0},
]

REGULATION_KPI_SEEDS: list[dict] = [
    {"regulation_code": "REG_HR_RECRUITER_V1", "kpi_code": "KPI_RECRUIT_TIME", "target_value": 30.0, "weight": 1.0},
    {"regulation_code": "REG_SALES_MGR_V1", "kpi_code": "KPI_SALES_PLAN", "target_value": 100.0, "weight": 0.5},
    {"regulation_code": "REG_SALES_MGR_V1", "kpi_code": "KPI_CONVERSION", "target_value": 25.0, "weight": 0.5},
]

REGULATION_INSTRUCTION_SEEDS: list[dict] = [
    {"regulation_code": "REG_HR_RECRUITER_V1", "instruction_code": "INS_RECRUIT", "instruction_name": "Процедура подбора", "instruction_url": "https://docs.google.com/...", "sort_order": 1},
    {"regulation_code": "REG_SALES_MGR_V1", "instruction_code": "INS_SALES", "instruction_name": "Работа с клиентами", "instruction_url": "https://docs.google.com/...", "sort_order": 1},
]

CLIENT_SEEDS: list[dict] = [
    {"code": "alfa", "name": "ТОО Альфа", "status": "active", "bin": "123456789012"},
    {"code": "beta", "name": "ИП Бета", "status": "active", "bin": "987654321098"},
    {"code": "gamma", "name": "АО Гамма", "status": "active", "bin": "111222333444"},
    {"code": "acme", "name": "ТОО Демо ACME", "status": "active", "bin": "555666777888"},
    {"code": "impl3", "name": "Impl 3 Demo LLC", "status": "active", "bin": None},
    {"code": "delta", "name": "ТОО Дельта", "status": "active", "bin": "999888777666"},
    {"code": "epsilon", "name": "ИП Эпсилон", "status": "active", "bin": None},
    {"code": "sigma", "name": "ООО Сигма", "status": "active", "bin": "444555666777"},
]


def seed_roles(db: Session) -> int:
    existing = set(db.scalars(select(Role.code)).all())
    created = 0
    for code, name in ROLE_SEEDS:
        if code in existing:
            continue
        db.add(
            Role(
                id=_id("role", code),
                code=code,
                name=name,
                is_active=True,
            )
        )
        created += 1
    if created:
        db.commit()
    return created


def seed_kpi_templates(db: Session) -> int:
    """Seed KPI templates: общие метрики + по одному шаблону на типовую должность (position_catalog)."""
    existing = {
        (r.template_code, r.kpi_code)
        for r in db.scalars(select(KpiTemplate)).all()
    }
    created = 0
    for k in KPI_TEMPLATE_SEEDS:
        key = (DEFAULT_TEMPLATE_CODE, k["kpi_code"])
        if key in existing:
            continue
        db.add(KpiTemplate(**k, template_code=DEFAULT_TEMPLATE_CODE, is_active=True, position_code=None))
        created += 1
        existing.add(key)
    for pc in POSITION_CATALOG_SEEDS:
        code = f"KPI_TMPL_{pc['position_code']}"
        key = (DEFAULT_TEMPLATE_CODE, code)
        if key in existing:
            continue
        name_ru = pc["position_name_ru"]
        db.add(
            KpiTemplate(
                template_code=DEFAULT_TEMPLATE_CODE,
                kpi_code=code,
                kpi_name=f"Шаблон KPI: {name_ru}",
                unit="%",
                period_type="month",
                formula_or_rule=None,
                default_target=None,
                is_active=True,
                position_code=pc["position_code"],
            )
        )
        existing.add(key)
        created += 1
    if created:
        db.commit()
    return created


def seed_regulations(db: Session) -> int:
    """Seed position regulations, regulation KPIs, and regulation instructions."""
    existing_codes = {
        (r.template_code, r.regulation_code)
        for r in db.scalars(select(PositionRegulation)).all()
    }
    created = 0
    for r in POSITION_REGULATION_SEEDS:
        key = (DEFAULT_TEMPLATE_CODE, r["regulation_code"])
        if key in existing_codes:
            continue
        db.add(
            PositionRegulation(
                id=_id("regulation", r["regulation_code"]),
                template_code=DEFAULT_TEMPLATE_CODE,
                regulation_code=r["regulation_code"],
                position_code=r["position_code"],
                dept_type_code=r["dept_type_code"],
                regulation_name=r["regulation_name"],
                goal_summary=r.get("goal_summary"),
                ckp_short=r.get("ckp_short"),
                ckp_full=r.get("ckp_full"),
                google_doc_url=r.get("google_doc_url"),
                version_no=r["version_no"],
                status=r.get("status", "active"),
                is_current=r.get("is_current", True),
            )
        )
        created += 1
    if created:
        db.flush()
    existing_rk = {
        (rk.template_code, rk.regulation_code, rk.kpi_code) for rk in db.scalars(select(RegulationKpi)).all()
    }
    for rk in REGULATION_KPI_SEEDS:
        key = (DEFAULT_TEMPLATE_CODE, rk["regulation_code"], rk["kpi_code"])
        if key in existing_rk:
            continue
        db.add(
            RegulationKpi(
                id=_id("reg_kpi", f"{rk['regulation_code']}_{rk['kpi_code']}"),
                template_code=DEFAULT_TEMPLATE_CODE,
                regulation_code=rk["regulation_code"],
                kpi_code=rk["kpi_code"],
                target_value=rk.get("target_value"),
                period_type=rk.get("period_type", "month"),
                weight=rk.get("weight"),
                is_required=True,
            )
        )
        created += 1
    existing_ri = {
        (ri.template_code, ri.regulation_code, ri.instruction_code)
        for ri in db.scalars(select(RegulationInstruction)).all()
    }
    for ri in REGULATION_INSTRUCTION_SEEDS:
        key = (DEFAULT_TEMPLATE_CODE, ri["regulation_code"], ri["instruction_code"])
        if key in existing_ri:
            continue
        db.add(
            RegulationInstruction(
                id=_id("reg_ins", f"{ri['regulation_code']}_{ri['instruction_code']}"),
                template_code=DEFAULT_TEMPLATE_CODE,
                regulation_code=ri["regulation_code"],
                instruction_code=ri["instruction_code"],
                instruction_name=ri["instruction_name"],
                instruction_url=ri.get("instruction_url"),
                is_required=True,
                sort_order=ri.get("sort_order", 0),
            )
        )
        created += 1
    if created:
        db.commit()
    return created


def seed_position_catalog(db: Session) -> int:
    """Seed position catalog and position-dept-type links."""
    existing_rows = {
        (r.template_code, r.position_code): r for r in db.scalars(select(PositionCatalog)).all()
    }
    created = 0
    for p in POSITION_CATALOG_SEEDS:
        key = (DEFAULT_TEMPLATE_CODE, p["position_code"])
        existing = existing_rows.get(key)
        if existing:
            en = (p.get("position_name_en") or "").strip()
            if en and not (existing.position_name_en or "").strip():
                existing.position_name_en = en
                created += 1
            continue
        db.add(
            PositionCatalog(
                template_code=DEFAULT_TEMPLATE_CODE,
                position_code=p["position_code"],
                position_name_ru=p["position_name_ru"],
                position_name_en=p.get("position_name_en"),
                function_code=p["function_code"],
                position_level=p["position_level"],
                is_managerial=p["is_managerial"],
                is_active=True,
            )
        )
        created += 1
    for row in existing_rows.values():
        en = position_name_en_for(row.template_code, row.position_code)
        if en and not (row.position_name_en or "").strip():
            row.position_name_en = en
            created += 1
    if created:
        db.flush()
    existing_links = {
        (r.template_code, r.position_code, r.dept_type_code)
        for r in db.scalars(select(PositionDeptType)).all()
    }
    for pos_code, dept_code, is_primary in POSITION_DEPT_TYPE_SEEDS:
        key = (DEFAULT_TEMPLATE_CODE, pos_code, dept_code)
        if key in existing_links:
            continue
        db.add(
            PositionDeptType(
                template_code=DEFAULT_TEMPLATE_CODE,
                position_code=pos_code,
                dept_type_code=dept_code,
                is_primary=is_primary,
            )
        )
        created += 1
    if created:
        db.commit()
    return created


def seed_enterprise_templates(db: Session) -> int:
    existing = set(db.scalars(select(EnterpriseTemplate.code)).all())
    created = 0
    for t in TEMPLATE_SEEDS:
        if t["code"] in existing:
            continue
        db.add(
            EnterpriseTemplate(
                id=_id("template", t["code"]),
                **t,
            )
        )
        created += 1
    if created:
        db.commit()
    return created


def seed_clients(db: Session) -> int:
    """Seed clients only when DB has no clients (first run). Deleted clients stay deleted."""
    existing = set(db.scalars(select(Client.code)).all())
    if existing:
        return 0  # DB already has clients — don't restore seeds
    default_template_id = _id("template", "default")
    created = 0
    for c in CLIENT_SEEDS:
        if c["code"] in existing:
            continue
        db.add(
            Client(
                id=_id("client", c["code"]),
                code=c["code"],
                name=c["name"],
                status=c["status"],
                bin=c.get("bin"),
                template_id=default_template_id,
            )
        )
        created += 1
    if created:
        db.commit()
    return created


def _template_org_unit_row(template_code: str, spec: dict) -> TemplateOrgUnitRow:
    return TemplateOrgUnitRow(
        id=new_id32(),
        template_code=template_code,
        code=spec["code"],
        name=format_org_unit_name(spec["name"], spec["unit_type"]),
        parent_code=spec.get("parent_code"),
        unit_type=spec["unit_type"],
        sort_order=int(spec.get("sort_order", 0)),
        log_group=spec.get("log_group"),
    )


def seed_template_org_units(db: Session) -> int:
    """Перенос встроенной типовой оргструктуры в БД (шаблон default).

    При первом запуске создаёт все узлы. Если шаблон уже есть — дозаполняет
    отсутствующие узлы и выравнивает parent_code по ``DEFAULT_ORG_UNITS``
    (например SALES / LEAD и секции под ними).
    """
    template_code = DEFAULT_TEMPLATE_CODE
    existing = {
        r.code: r
        for r in db.scalars(
            select(TemplateOrgUnitRow).where(TemplateOrgUnitRow.template_code == template_code)
        ).all()
    }
    changed = 0
    if not existing:
        for spec in DEFAULT_ORG_UNITS:
            db.add(_template_org_unit_row(template_code, spec))
            changed += 1
    else:
        for spec in DEFAULT_ORG_UNITS:
            row = existing.get(spec["code"])
            if row is None:
                db.add(_template_org_unit_row(template_code, spec))
                changed += 1
                continue
            expected_parent = spec.get("parent_code")
            if row.parent_code != expected_parent:
                row.parent_code = expected_parent
                changed += 1
            expected_sort = int(spec.get("sort_order", 0))
            if row.sort_order != expected_sort:
                row.sort_order = expected_sort
                changed += 1
            formatted_name = format_org_unit_name(spec["name"], spec["unit_type"])
            if row.name != formatted_name:
                row.name = formatted_name
                changed += 1
        # Удалённые из DEFAULT_ORG_UNITS узлы в БД не трогаем — могут быть правки пользователя.
    if changed:
        db.commit()
    return changed


HOSP_SEGMENT_CODE_SEEDS: list[tuple[str, str, str, int]] = [
    ("hosp", "CLINIC", "Клиника (стационар)", 10),
    ("hosp", "PARACLINIC", "Параклиника", 20),
    ("hosp", "POLYCLINIC", "Поликлиника", 30),
    ("hosp", "AUXILIARY", "Вспомогательные службы", 40),
    ("hosp", "SERVICE", "Сервисные подразделения", 50),
    ("hosp", "ADMINISTRATIVE", "Управление", 60),
]


def seed_template_segment_codes(db: Session) -> int:
    """Словарь segment_code для шаблонов (medical hosp — базовый набор)."""
    from app.models import TemplateSegmentCode

    created = 0
    for template_code, code, label_ru, sort_order in HOSP_SEGMENT_CODE_SEEDS:
        if db.get(TemplateSegmentCode, (template_code, code)):
            continue
        db.add(
            TemplateSegmentCode(
                template_code=template_code,
                code=code,
                label_ru=label_ru,
                sort_order=sort_order,
                is_active=True,
            )
        )
        created += 1
    if created:
        db.commit()
    return created


def seed_all(db: Session) -> dict[str, int]:
    return {
        "roles": seed_roles(db),
        "enterprise_templates": seed_enterprise_templates(db),
        "clients": seed_clients(db),
    }

