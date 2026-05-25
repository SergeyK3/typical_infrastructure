r"""D:\MyActivity\MyInfoBusiness\MyPythonApps\10 Typical_infrastructure\app\schemas.py"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import ConfigDict, field_validator, model_validator
from pydantic import BaseModel, Field


T = TypeVar("T")


class ListEnvelope(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class ClientBase(BaseModel):
    code: str
    name: str
    bin: str | None = None
    status: str = Field(min_length=1)
    template_id: str | None = None


class ClientCreate(ClientBase):
    id: str | None = None


class ClientPatch(BaseModel):
    code: str | None = None
    name: str | None = None
    bin: str | None = None
    status: str | None = None
    template_id: str | None = None


class ClientOut(ClientBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


class OrgUnitBase(BaseModel):
    client_id: str
    code: str
    name: str
    parent_id: str | None = None
    unit_type: str
    is_active: bool = True
    sort_order: int = 0
    catalog_source_code: str | None = None
    is_detached: bool = True


class OrgUnitCreate(OrgUnitBase):
    id: str | None = None


class OrgUnitPatch(BaseModel):
    code: str | None = None
    name: str | None = None
    parent_id: str | None = None
    unit_type: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    is_detached: bool | None = None


class OrgUnitOut(OrgUnitBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


class OrgUnitNode(OrgUnitOut):
    children: list["OrgUnitNode"] = []


class OrgUnitCloneIn(BaseModel):
    name_suffix: str = Field(default="Копия", max_length=64)
    new_code: str | None = Field(default=None, max_length=64)
    target_parent_id: str | None = None


class OrgUnitCloneOut(BaseModel):
    org_unit: OrgUnitOut
    positions_created: int
    sections_skipped: int


class OrgUnitReorderItem(BaseModel):
    id: str
    parent_id: str | None = None
    sort_order: int = 0


class OrgUnitBulkCloneIn(BaseModel):
    unit_ids: list[str] = Field(min_length=1)
    name_suffix: str = Field(default="Копия", max_length=64)


class PositionBase(BaseModel):
    client_id: str
    org_unit_id: str
    code: str
    name: str
    grade: str | None = None
    is_active: bool = True
    position_catalog_code: str | None = None
    function_code: str | None = None
    position_level: str | None = None
    is_managerial: bool | None = None
    is_detached: bool = True


class PositionCreate(PositionBase):
    id: str | None = None


class PositionPatch(BaseModel):
    org_unit_id: str | None = None
    code: str | None = None
    name: str | None = None
    grade: str | None = None
    is_active: bool | None = None
    position_catalog_code: str | None = None
    function_code: str | None = None
    position_level: str | None = None
    is_managerial: bool | None = None
    is_detached: bool | None = None


class PositionOut(PositionBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


class PositionCatalogBase(BaseModel):
    template_code: str = "default"
    position_code: str
    position_name_ru: str
    position_name_en: str | None = None
    function_code: str
    position_level: str = "SPEC"
    is_managerial: bool = False
    position_family: str | None = None
    is_active: bool = True
    default_regulation_code: str | None = None
    notes: str | None = None


class PositionCatalogOut(PositionCatalogBase):
    model_config = ConfigDict(from_attributes=True)


class PositionDeptTypeOut(BaseModel):
    template_code: str = "default"
    position_code: str
    dept_type_code: str
    is_primary: bool = True


class PositionCatalogCreate(PositionCatalogBase):
    """Создание строки глобального справочника типовых должностей."""

    pass


class PositionCatalogPatch(BaseModel):
    position_name_ru: str | None = None
    position_name_en: str | None = None
    function_code: str | None = None
    position_level: str | None = None
    is_managerial: bool | None = None
    position_family: str | None = None
    is_active: bool | None = None
    default_regulation_code: str | None = None
    notes: str | None = None


class TemplateOrgUnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    template_code: str
    code: str
    name: str
    parent_code: str | None
    unit_type: str
    sort_order: int
    created_at: datetime
    updated_at: datetime


class TemplateOrgUnitCreate(BaseModel):
    template_code: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=256)
    parent_code: str | None = Field(default=None, max_length=64)
    unit_type: str = Field(min_length=1, max_length=32)
    sort_order: int = 0


class TemplateOrgUnitPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    parent_code: str | None = Field(default=None, max_length=64)
    unit_type: str | None = Field(default=None, min_length=1, max_length=32)
    sort_order: int | None = None


class TemplateOrgUnitNode(TemplateOrgUnitOut):
    children: list["TemplateOrgUnitNode"] = []
    position_count: int = 0


class TemplateOrgUnitCloneOut(BaseModel):
    row: TemplateOrgUnitOut
    position_links_created: int
    sections_skipped: int


class EmployeeBase(BaseModel):
    client_id: str
    last_name: str
    first_name: str
    middle_name: str | None = None
    email: str | None = None
    phone: str | None = None
    telegram_id: str | None = None
    org_unit_id: str | None = None
    position_id: str | None = None
    employment_status: str
    is_manager: bool = False


class EmployeeCreate(EmployeeBase):
    id: str | None = None


class EmployeePatch(BaseModel):
    last_name: str | None = None
    first_name: str | None = None
    middle_name: str | None = None
    email: str | None = None
    phone: str | None = None
    telegram_id: str | None = None
    org_unit_id: str | None = None
    position_id: str | None = None
    employment_status: str | None = None
    is_manager: bool | None = None


class EmployeeOut(EmployeeBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


class EmployeeListOut(EmployeeOut):
    """Список сотрудников: дополнительно логин корпоративной учётной записи (если есть)."""

    account_login: str | None = None


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AccountBase(BaseModel):
    employee_id: str
    login: str
    password_hash: str = Field(min_length=1)
    status: str = Field(default="active", min_length=1)


class AccountCreate(AccountBase):
    id: str | None = None
    role_codes: list[str] = Field(default_factory=list, max_length=20)


class AccountPatch(BaseModel):
    login: str | None = None
    password_hash: str | None = None
    status: str | None = None
    role_codes: list[str] | None = None


class AccountOut(AccountBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


class AccountListItem(BaseModel):
    """Элемент списка аккаунтов без password_hash."""

    model_config = ConfigDict(from_attributes=True)
    id: str
    employee_id: str
    login: str
    status: str
    created_at: datetime
    updated_at: datetime


class AccountWithRolesOut(AccountOut):
    role_codes: list[str] = Field(default_factory=list)


class AccountBulkItem(BaseModel):
    employee_id: str
    login: str
    password_hash: str = Field(min_length=1)
    status: str = Field(default="active", min_length=1)
    role_codes: list[str] = Field(default_factory=list, max_length=20)


class AccountBulkCreateRequest(BaseModel):
    items: list[AccountBulkItem] = Field(max_length=500)


class AccountBulkCreateResult(BaseModel):
    created: list[AccountOut]
    errors: list[dict] = Field(default_factory=list)


class EnterpriseTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    name: str
    version: str
    description: str | None
    is_active: bool
    status: str = "active"
    author: str | None = None
    comment: str | None = None
    archived_at: datetime | None = None
    cloned_from_id: str | None = None
    created_at: datetime
    updated_at: datetime


class EnterpriseTemplateCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(default="1", max_length=16)
    description: str | None = Field(default=None, max_length=512)
    comment: str | None = Field(default=None, max_length=512)
    author: str | None = Field(default=None, max_length=128)


class EnterpriseTemplateSaveFromClient(BaseModel):
    client_id: str
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(default="1", max_length=16)
    description: str | None = Field(default=None, max_length=512)
    comment: str | None = Field(default=None, max_length=512)
    author: str | None = Field(default=None, max_length=128)


class EnterpriseTemplatePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    version: str | None = Field(default=None, min_length=1, max_length=16)
    description: str | None = Field(default=None, max_length=512)
    comment: str | None = Field(default=None, max_length=512)
    author: str | None = Field(default=None, max_length=128)


class EnterpriseTemplateCloneIn(BaseModel):
    new_code: str | None = Field(default=None, min_length=1, max_length=64)
    new_name: str | None = Field(default=None, min_length=1, max_length=128)
    code_prefix: str | None = Field(default=None, max_length=32)
    copy_positions: bool = True
    copy_kpi: bool = True
    copy_regulations: bool = True
    copy_skills: bool = True


class EnterpriseTemplateCloneCounts(BaseModel):
    org_units: int = 0
    positions: int = 0
    position_links: int = 0
    kpi: int = 0
    regulations: int = 0
    regulation_kpis: int = 0
    regulation_instructions: int = 0
    skill_definitions: int = 0
    competency_matrix_rows: int = 0


class EnterpriseTemplateCloneOut(BaseModel):
    template: EnterpriseTemplateOut
    counts: EnterpriseTemplateCloneCounts


class OnboardingClientIn(BaseModel):
    code: str = Field(
        min_length=1,
        max_length=64,
        description="Уникальный код клиента",
        examples=["TOO_ALFA"],
    )
    name: str = Field(
        min_length=1,
        max_length=256,
        description="Название клиента",
        examples=["ТОО Альфа"],
    )


class OnboardingAdminIn(BaseModel):
    last_name: str = Field(min_length=1, max_length=128, description="Фамилия администратора")
    first_name: str = Field(min_length=1, max_length=128, description="Имя администратора")
    login: str = Field(min_length=1, max_length=256, description="Логин (уникален в системе)")
    password: str | None = Field(default=None, max_length=128, description="Пароль (опционально)")
    email: str | None = Field(default=None, max_length=256)


class OnboardingRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")  # reject unknown fields at API boundary

    action: str = Field(default="create", pattern="^(create|apply_existing)$")
    template_code: str = Field(default="default", min_length=1, max_length=64)
    requested_by: str | None = Field(default=None, max_length=128)
    idempotency_key: str | None = Field(default=None, max_length=64)
    client: OnboardingClientIn | None = None
    existing_client_id: str | None = Field(default=None, max_length=32)
    admin: OnboardingAdminIn | None = None

    @model_validator(mode="after")
    def validate_action_requirements(self) -> "OnboardingRunCreate":
        if self.action == "create":
            if self.client is None:
                raise ValueError("client is required for create onboarding")
            if self.admin is None:
                raise ValueError("admin is required for create onboarding")
        if self.action == "apply_existing" and not self.existing_client_id:
            raise ValueError("existing_client_id is required for existing organization onboarding")
        return self


class OnboardingRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str
    client_id: str | None
    template_id: str | None
    requested_by: str | None
    error_code: str | None
    error_message: str | None
    created_entities: dict | None = None  # traceability run-to-entities
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_validator("created_entities", mode="before")
    @classmethod
    def parse_created_entities(cls, v: str | dict | None) -> dict | None:
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str) and v.strip():
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                pass
        return None


class OnboardingRunWithStepsOut(BaseModel):
    class Step(BaseModel):
        model_config = ConfigDict(from_attributes=True)
        id: str
        run_id: str
        step_code: str
        status: str
        detail: str | None
        started_at: datetime | None
        finished_at: datetime | None
        created_at: datetime
        updated_at: datetime

    run: OnboardingRunOut
    steps: list[Step]


# --- Регламенты должностей (Step 12) ---


class KpiTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    template_code: str = "default"
    kpi_code: str
    kpi_name: str
    unit: str = "%"
    period_type: str = "month"
    formula_or_rule: str | None
    default_target: float | None
    is_active: bool
    position_code: str | None = None
    primary_dept_type_code: str | None = None
    position_name_ru: str | None = None
    created_at: datetime
    updated_at: datetime


class KpiTemplateCreate(BaseModel):
    template_code: str = Field(default="default", min_length=1, max_length=64)
    kpi_code: str = Field(min_length=1, max_length=64)
    kpi_name: str = Field(min_length=1, max_length=256)
    unit: str = Field(default="%", max_length=32)
    period_type: str = Field(default="month", max_length=16)
    formula_or_rule: str | None = Field(default=None, max_length=512)
    default_target: float | None = None
    is_active: bool = True
    position_code: str | None = Field(default=None, max_length=64)


class KpiTemplatePatch(BaseModel):
    kpi_name: str | None = Field(default=None, min_length=1, max_length=256)
    unit: str | None = Field(default=None, max_length=32)
    period_type: str | None = Field(default=None, max_length=16)
    formula_or_rule: str | None = Field(default=None, max_length=512)
    default_target: float | None = None
    is_active: bool | None = None
    position_code: str | None = Field(default=None, max_length=64)


class RegulationKpiOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    regulation_code: str
    kpi_code: str
    target_value: float | None
    period_type: str
    weight: float | None
    is_required: bool


class RegulationInstructionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    regulation_code: str
    instruction_code: str
    instruction_name: str
    instruction_url: str | None
    is_required: bool
    sort_order: int


class PositionRegulationBase(BaseModel):
    template_code: str = "default"
    regulation_code: str
    position_code: str
    dept_type_code: str
    regulation_name: str
    goal_summary: str | None = None
    ckp_short: str | None = None
    ckp_full: str | None = None
    google_doc_url: str | None = None
    instructions_folder_url: str | None = None
    version_no: str
    status: str = "draft"
    effective_from: date | None = None
    effective_to: date | None = None
    is_current: bool = False
    owner_unit_code: str | None = None
    notes: str | None = None


class PositionRegulationCreate(PositionRegulationBase):
    id: str | None = None


class PositionRegulationPatch(BaseModel):
    regulation_name: str | None = None
    goal_summary: str | None = None
    ckp_short: str | None = None
    ckp_full: str | None = None
    google_doc_url: str | None = None
    instructions_folder_url: str | None = None
    status: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    is_current: bool | None = None
    owner_unit_code: str | None = None
    notes: str | None = None


class PositionRegulationOut(PositionRegulationBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


class PositionRegulationDetailOut(PositionRegulationOut):
    """Регламент с вложенными KPI и инструкциями."""

    kpis: list[RegulationKpiOut] = Field(default_factory=list)
    instructions: list[RegulationInstructionOut] = Field(default_factory=list)


# --- Клиентские копии регламентов ---


class ClientRegulationKpiIn(BaseModel):
    kpi_code: str
    target_value: float | None = None
    period_type: str = "month"
    weight: float | None = None
    is_required: bool = True


class ClientRegulationInstructionIn(BaseModel):
    instruction_code: str
    instruction_name: str
    instruction_url: str | None = None
    is_required: bool = True
    sort_order: int = 0


class ClientRegulationKpiOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    client_regulation_id: str
    kpi_code: str
    target_value: float | None
    period_type: str
    weight: float | None
    is_required: bool


class ClientRegulationInstructionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    client_regulation_id: str
    instruction_code: str
    instruction_name: str
    instruction_url: str | None
    is_required: bool
    sort_order: int


class ClientPositionRegulationBase(BaseModel):
    client_id: str
    regulation_code: str
    global_regulation_code: str | None = None
    is_detached: bool = True
    position_code: str
    dept_type_code: str
    regulation_name: str
    goal_summary: str | None = None
    ckp_short: str | None = None
    ckp_full: str | None = None
    google_doc_url: str | None = None
    instructions_folder_url: str | None = None
    version_no: str
    status: str = "draft"
    effective_from: date | None = None
    effective_to: date | None = None
    is_current: bool = False
    owner_unit_code: str | None = None
    notes: str | None = None


class ClientPositionRegulationCreate(ClientPositionRegulationBase):
    id: str | None = None
    kpis: list[ClientRegulationKpiIn] = Field(default_factory=list)
    instructions: list[ClientRegulationInstructionIn] = Field(default_factory=list)


class ClientPositionRegulationCopyFromGlobal(BaseModel):
    client_id: str
    global_regulation_code: str
    regulation_code: str | None = Field(
        None,
        description="Код у клиента; если не задан — совпадает с глобальным regulation_code",
    )


class ClientPositionRegulationPatch(BaseModel):
    regulation_name: str | None = None
    goal_summary: str | None = None
    ckp_short: str | None = None
    ckp_full: str | None = None
    google_doc_url: str | None = None
    instructions_folder_url: str | None = None
    status: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    is_current: bool | None = None
    owner_unit_code: str | None = None
    notes: str | None = None
    is_detached: bool | None = None


class ClientPositionRegulationOut(ClientPositionRegulationBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


class ClientPositionRegulationDetailOut(ClientPositionRegulationOut):
    kpis: list[ClientRegulationKpiOut] = Field(default_factory=list)
    instructions: list[ClientRegulationInstructionOut] = Field(default_factory=list)


class PositionFromCatalog(BaseModel):
    """Создать штатную должность организации по строке глобального position_catalog."""

    client_id: str
    org_unit_id: str
    position_catalog_code: str
    code: str | None = None
    name: str | None = None


class OrgUnitFromTemplateNode(BaseModel):
    """Добавить подразделение организации по узлу типового шаблона (app/org_structures)."""

    client_id: str
    template_unit_code: str
    template_code: str = "default"

