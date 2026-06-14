r"""D:\MyActivity\MyInfoBusiness\MyPythonApps\10 Typical_infrastructure\app\models.py"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class EnterpriseTemplate(Base, TimestampMixin):
    __tablename__ = "enterprise_templates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    author: Mapped[str | None] = mapped_column(String(128), nullable=True)
    comment: Mapped[str | None] = mapped_column(String(512), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cloned_from_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class TemplateSegmentCode(Base, TimestampMixin):
    """Словарь значений segment_code для шаблона (CLINIC, PARACLINIC, … — по template_code)."""

    __tablename__ = "template_segment_codes"
    __table_args__ = (
        Index("ix_template_segment_codes_tpl_code", "template_code", "code", unique=True),
    )

    template_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    label_ru: Mapped[str] = mapped_column(String(128), nullable=False)
    label_en: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TemplateOrgUnitRow(Base, TimestampMixin):
    """Глобальная типовая оргструктура (шаблон) в БД — подразделения для onboarding / deploy-template."""

    __tablename__ = "template_org_units"
    __table_args__ = (Index("ix_template_org_units_tpl_code", "template_code", "code", unique=True),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    template_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    parent_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unit_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Логическая группа — только для отделений (unit_type=department).
    log_group: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Сегмент деятельности — только для отделений; секции наследуют от родительского отделения.
    segment_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Client(Base, TimestampMixin):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    bin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    template_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class OrgUnit(Base, TimestampMixin):
    """Подразделение организации.

    Мультитенантность: данные всегда в разрезе client_id. Если узел создан из типового
    шаблона (onboarding / deploy-template), в catalog_source_code сохраняется код из шаблона
    для аудита; переименование (например «Бухгалтерия» → «Отдел финансирования») — правка
    своей строки, глобальный шаблон не меняется.

    is_detached=True: авто-синхронизации с типовым шаблоном нет; источник только исторический.
    Тот же смысл заложен для клиентских копий нормативных справочников (см. ClientPositionRegulation).
    """

    __tablename__ = "org_units"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(32), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    unit_type: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    catalog_source_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_detached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    #: Сегмент деятельности (department); у секций — null, effective — от родителя.
    segment_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class PositionCatalog(Base, TimestampMixin):
    """Глобальный справочник типовых должностей (нормативный реестр).

    У организации рабочие строки — в Position; связь с этим каталогом — position_catalog_code,
    автосинхронизации нет при is_detached=True у позиции.
    """

    __tablename__ = "position_catalog"
    __table_args__ = (Index("ix_position_catalog_tpl_code", "template_code", "position_code", unique=True),)

    template_code: Mapped[str] = mapped_column(String(64), primary_key=True, default="default")
    position_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    position_name_ru: Mapped[str] = mapped_column(String(256), nullable=False)
    position_name_en: Mapped[str | None] = mapped_column(String(256), nullable=True)
    function_code: Mapped[str] = mapped_column(String(32), nullable=False)
    position_level: Mapped[str] = mapped_column(String(16), nullable=False, default="SPEC")
    is_managerial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position_family: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_regulation_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PositionDeptType(Base):
    """Связь типовой должности с типом подразделения (многие ко многим)."""

    __tablename__ = "position_dept_types"
    __table_args__ = (
        Index(
            "ix_position_dept_types_tpl",
            "template_code",
            "position_code",
            "dept_type_code",
            unique=True,
        ),
    )

    template_code: Mapped[str] = mapped_column(String(64), primary_key=True, default="default")
    position_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    dept_type_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Position(Base, TimestampMixin):
    """Штатная позиция — конкретное место в подразделении организации.

    position_catalog_code — историческая ссылка на глобальный PositionCatalog (если строка
    выведена из типового справочника). is_detached=True: изменения в глобальном каталоге
    на эту запись не подтягиваются автоматически.
    """

    __tablename__ = "positions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(32), nullable=False)
    org_unit_id: Mapped[str] = mapped_column(String(32), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    grade: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Ссылка на справочник типовых должностей
    position_catalog_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    function_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    position_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_managerial: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_detached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    #: Наследуется от отделения (effective segment org_unit) при deploy / sync, если не задано явно.
    segment_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Employee(Base, TimestampMixin):
    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(32), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    telegram_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    org_unit_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    position_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    employment_status: Mapped[str] = mapped_column(String(32), nullable=False)
    is_manager: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    employee_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    login: Mapped[str] = mapped_column(String(256), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)


class AccountRole(Base, TimestampMixin):
    __tablename__ = "account_roles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(32), nullable=False)
    role_id: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class OnboardingRun(Base, TimestampMixin):
    __tablename__ = "onboarding_runs"
    __table_args__ = (
        Index("ix_onboarding_runs_idempotency_key", "idempotency_key", unique=True),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    requested_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_entities: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: traceability run-to-entities
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class OnboardingStep(Base, TimestampMixin):
    __tablename__ = "onboarding_steps"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), nullable=False)
    step_code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[str | None] = mapped_column(String(512), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# --- Регламенты должностей (Step 12) ---


class KpiTemplate(Base, TimestampMixin):
    """Глобальный справочник KPI-шаблонов (типовые метрики).

    position_code — необязательная связь с типовой должностью (position_catalog): один
    стартовый шаблон на должность в сиде; позже у организации в регламенте может быть
    несколько KPI (regulation_kpis), в т.ч. из общих шаблонов без должности.

    Клиентские копии/настройки (если появятся отдельной таблицей) — с полем ссылки на
    kpi_code и is_detached по той же политике, что и для регламентов и должностей.
    """

    __tablename__ = "kpi_templates"
    __table_args__ = (Index("ix_kpi_templates_tpl_code", "template_code", "kpi_code", unique=True),)

    template_code: Mapped[str] = mapped_column(String(64), primary_key=True, default="default")
    kpi_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    kpi_name: Mapped[str] = mapped_column(String(256), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="%")
    period_type: Mapped[str] = mapped_column(String(16), nullable=False, default="month")
    formula_or_rule: Mapped[str | None] = mapped_column(String(512), nullable=True)
    default_target: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    position_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class PositionRegulation(Base, TimestampMixin):
    """Глобальный нормативный реестр регламентов должностей (общесистемный справочник)."""

    __tablename__ = "position_regulations"
    __table_args__ = (
        Index("ix_position_regulations_tpl_code", "template_code", "regulation_code", unique=True),
        Index(
            "ix_position_regulations_unique",
            "template_code",
            "position_code",
            "dept_type_code",
            "version_no",
            unique=True,
        ),
        Index("ix_position_regulations_current", "template_code", "position_code", "dept_type_code", "is_current"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    template_code: Mapped[str] = mapped_column(String(64), nullable=False, default="default", index=True)
    regulation_code: Mapped[str] = mapped_column(String(64), nullable=False)
    position_code: Mapped[str] = mapped_column(String(64), nullable=False)
    dept_type_code: Mapped[str] = mapped_column(String(32), nullable=False)
    regulation_name: Mapped[str] = mapped_column(String(256), nullable=False)
    goal_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ckp_short: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ckp_full: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_doc_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    instructions_folder_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    version_no: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # draft, on_review, approved, active, archived
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    owner_unit_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)


class ClientPositionRegulation(Base, TimestampMixin):
    """Регламент должности в разрезе организации (рабочая копия).

    global_regulation_code — код записи из глобального position_regulations на момент копирования
    (исторический якорь). После копии глобальный каталог для этой строки не синхронизируется
    автоматически; is_detached=True фиксирует эту политику (и для строк, созданных с нуля у клиента,
    без глобального прототипа).

    Связанные KPI и инструкции (аналог regulation_kpis / regulation_instructions) при
    необходимости выносятся в отдельные клиентские таблицы с привязкой к id этой записи.
    """

    __tablename__ = "client_position_regulations"
    __table_args__ = (
        Index("ix_client_position_regulations_client_code", "client_id", "regulation_code", unique=True),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(32), nullable=False)
    regulation_code: Mapped[str] = mapped_column(String(64), nullable=False)
    global_regulation_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_detached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    position_code: Mapped[str] = mapped_column(String(64), nullable=False)
    dept_type_code: Mapped[str] = mapped_column(String(32), nullable=False)
    regulation_name: Mapped[str] = mapped_column(String(256), nullable=False)
    goal_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ckp_short: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ckp_full: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_doc_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    instructions_folder_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    version_no: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    owner_unit_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)


class ClientRegulationKpi(Base):
    """KPI клиентской копии регламента (привязка к client_position_regulations.id)."""

    __tablename__ = "client_regulation_kpis"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    client_regulation_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    kpi_code: Mapped[str] = mapped_column(String(64), nullable=False)
    target_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    period_type: Mapped[str] = mapped_column(String(16), nullable=False, default="month")
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ClientStandaloneKpi(Base, TimestampMixin):
    """Локальный KPI организации без привязки к карточке регламента."""

    __tablename__ = "client_standalone_kpis"
    __table_args__ = (Index("ix_client_standalone_kpis_client_code", "client_id", "kpi_code", unique=True),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    kpi_code: Mapped[str] = mapped_column(String(64), nullable=False)
    target_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    period_type: Mapped[str] = mapped_column(String(16), nullable=False, default="month")
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    position_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)


class ClientRegulationInstruction(Base):
    """Инструкции клиентской копии регламента."""

    __tablename__ = "client_regulation_instructions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    client_regulation_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    instruction_code: Mapped[str] = mapped_column(String(64), nullable=False)
    instruction_name: Mapped[str] = mapped_column(String(256), nullable=False)
    instruction_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RegulationKpi(Base):
    """Связь регламента с KPI."""

    __tablename__ = "regulation_kpis"
    __table_args__ = (Index("ix_regulation_kpis_tpl_reg", "template_code", "regulation_code"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    template_code: Mapped[str] = mapped_column(String(64), nullable=False, default="default", index=True)
    regulation_code: Mapped[str] = mapped_column(String(64), nullable=False)
    kpi_code: Mapped[str] = mapped_column(String(64), nullable=False)
    target_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    period_type: Mapped[str] = mapped_column(String(16), nullable=False, default="month")
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class EmployeeConsentRecord(Base, TimestampMixin):
    """Согласие сотрудника (client_id + employee_id), единый слой для Telegram-сценариев."""

    __tablename__ = "employee_consent_records"
    __table_args__ = (
        Index(
            "ix_employee_consent_client_emp_type",
            "client_id",
            "employee_id",
            "consent_type",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(32), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(32), nullable=False)
    #: ``pd_processing`` — согласие на обработку ПДн (задел на другие типы).
    consent_type: Mapped[str] = mapped_column(String(32), nullable=False, default="pd_processing")
    #: ``pending`` | ``decline_pending`` | ``accepted`` | ``declined`` | ``revoked``
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    document_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    declined_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    #: ``telegram`` | ``migrated_part1`` | ``migrated_examination`` | ``hr_manual``
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)


class PtTestProgram(Base, TimestampMixin):
    """Глобальный шаблон программы психотестирования (не привязан к client_id)."""

    __tablename__ = "pt_test_programs"
    __table_args__ = (Index("ix_pt_test_programs_code", "code", unique=True),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title_ru: Mapped[str] = mapped_column(String(256), nullable=False)
    steps_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)


class PtTestAssignment(Base, TimestampMixin):
    """Назначение одного психологического теста сотруднику (HR)."""

    __tablename__ = "pt_test_assignments"
    __table_args__ = (
        Index("ix_pt_assignments_client_employee", "client_id", "employee_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(32), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(32), nullable=False)
    test_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    program_id: Mapped[str] = mapped_column(String(64), nullable=False, default="standard_hr_v1")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled")
    completed_tests_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    released_tests_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    steps_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    completed_step_keys_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    released_step_keys_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    due_reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PtTestSession(Base, TimestampMixin):
    """Психологическое тестирование: сессия (in-progress snapshot или финальный JSON)."""

    __tablename__ = "pt_test_sessions"
    __table_args__ = (
        Index("ix_pt_sessions_client_employee", "client_id", "employee_id"),
        Index("ix_pt_sessions_telegram_chat", "telegram_chat_id"),
        Index("ix_pt_sessions_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(32), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(32), nullable=False)
    test_id: Mapped[str] = mapped_column(String(64), nullable=False)
    test_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="questioning")
    assignment_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    delivery_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="structured")
    step_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class PtTelegramBinding(Base, TimestampMixin):
    """Привязка Telegram chat_id к сотруднику (psych testing)."""

    __tablename__ = "pt_telegram_bindings"
    __table_args__ = (UniqueConstraint("telegram_chat_id", name="uq_pt_tg_chat"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    telegram_chat_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)


class PtTelegramProcessContext(Base, TimestampMixin):
    """Активный psych-поток для chat_id (resume после рестарта worker)."""

    __tablename__ = "pt_telegram_process_context"
    __table_args__ = (UniqueConstraint("telegram_chat_id", name="uq_pt_tg_process_chat"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    telegram_chat_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    client_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    employee_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    active_flow: Mapped[str] = mapped_column(String(32), nullable=False, default="idle", index=True)
    active_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    active_test_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active_step_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active_assignment_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mbti_delivery_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)


class RegulationInstruction(Base):
    """Связь регламента с должностными инструкциями."""

    __tablename__ = "regulation_instructions"
    __table_args__ = (Index("ix_regulation_instructions_tpl_reg", "template_code", "regulation_code"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    template_code: Mapped[str] = mapped_column(String(64), nullable=False, default="default", index=True)
    regulation_code: Mapped[str] = mapped_column(String(64), nullable=False)
    instruction_code: Mapped[str] = mapped_column(String(64), nullable=False)
    instruction_name: Mapped[str] = mapped_column(String(256), nullable=False)
    instruction_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
