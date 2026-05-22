r"""D:\MyActivity\MyInfoBusiness\MyPythonApps\10 Typical_infrastructure\app\main.py"""

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import HTTPException

from app.error_envelope import http_exception_handler
from app.logging_middleware import RequestTracingMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import models  # noqa: F401 — register models with Base.metadata
from app.api import router as api_router
from app.db import Base, engine, SessionLocal
from app.migrate import run_migrations
from app.seed import (
    seed_enterprise_templates,
    seed_kpi_templates,
    seed_position_catalog,
    seed_regulations,
    seed_roles,
    seed_template_org_units,
)
from app.universal_seed import (
    apply_regulation_enrichment_json,
    link_regulation_kpis_from_templates,
    merge_kpi_templates_from_xlsx,
    merge_position_regulations_from_client_xlsx,
)
from app.settings import settings

# Configure app logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("app").setLevel(logging.INFO)

try:
    import skill_assessment.infrastructure.db_models  # noqa: F401 — register skill assessment tables
    from skill_assessment.router import router as skill_assessment_router
    from skill_assessment.runner import configure_skill_assessment_plugin, run_plugin_startup
except ImportError:
    logging.getLogger("app").exception("skill_assessment module is not available")
    skill_assessment_router = None
    configure_skill_assessment_plugin = None
    run_plugin_startup = None

app = FastAPI(title=settings.app_name)
app.add_middleware(RequestTracingMiddleware)


@app.middleware("http")
async def add_security_headers(request, call_next):
    """Add security headers for trustworthy origin (attribution reporting, etc.)."""
    response = await call_next(request)
    response.headers["Permissions-Policy"] = "attribution-reporting=()"
    return response
app.add_exception_handler(HTTPException, http_exception_handler)
app.include_router(api_router, prefix="/api")
if skill_assessment_router is not None:
    app.include_router(skill_assessment_router, prefix="/api")
if configure_skill_assessment_plugin is not None:
    configure_skill_assessment_plugin(app)

static_dir = Path(__file__).resolve().parent.parent / "static"
_HTML_NO_CACHE = {
    "Cache-Control": "no-store, max-age=0",
    "Pragma": "no-cache",
}


def _html_file_response(path: Path) -> FileResponse:
    return FileResponse(path, media_type="text/html; charset=utf-8", headers=_HTML_NO_CACHE)

_MSG_MAP = {
    "Field required": "Поле обязательно для заполнения",
    "field_required": "Поле обязательно для заполнения",
    "string_too_short": "Значение слишком короткое",
    "string_too_long": "Значение слишком длинное",
    "value_error.missing": "Поле обязательно",
}


def _friendly_msg(msg: str) -> str:
    return _MSG_MAP.get(msg, msg)


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request, exc: RequestValidationError) -> JSONResponse:
    """User-friendly validation error responses in unified envelope."""
    from app.logging_middleware import get_request_id

    errors = []
    for e in exc.errors():
        loc = ".".join(str(x) for x in e.get("loc", []) if x not in ("body",))
        msg = _friendly_msg(e.get("msg", "Invalid value"))
        ctx = e.get("ctx") or {}
        if "min_length" in ctx:
            msg = f"Минимум {ctx['min_length']} символов"
        elif "max_length" in ctx:
            msg = f"Максимум {ctx['max_length']} символов"
        errors.append({"field": loc or "body", "message": msg})
    from app.error_envelope import _envelope

    trace_id = get_request_id()
    body = _envelope("validation_error", "Ошибка валидации полей.", details=errors, trace_id=trace_id)
    return JSONResponse(status_code=422, content=body)


@app.get("/")
def root():
    """Redirect to clients list."""
    return RedirectResponse(url="/clients", status_code=302)


@app.get("/health/ready", tags=["health"])
def health_readiness() -> dict:
    """Readiness probe: service is ready to accept requests."""
    return {"status": "ready", "service": settings.app_name}


@app.get("/api/ui-config", tags=["ui"])
def ui_config() -> dict:
    """Client UI defaults (theme switch, etc.)."""
    default_theme = os.getenv("UI_DEFAULT_THEME", "dark").strip().lower()
    if default_theme not in ("dark", "light"):
        default_theme = "dark"
    switch_raw = os.getenv("UI_THEME_SWITCH", "1").strip().lower()
    return {
        "default_theme": default_theme,
        "theme_switch": switch_raw not in ("0", "false", "no", "off"),
    }


@app.get("/wizard")
def wizard_page() -> FileResponse:
    """UI wizard for one-click onboarding."""
    wizard_path = static_dir / "wizard" / "index.html"
    if not wizard_path.exists():
        raise HTTPException(status_code=404, detail="wizard_not_found")
    return _html_file_response(wizard_path)


@app.get("/client/{client_id}")
def client_workspace_page(client_id: str) -> FileResponse:
    """Client workspace — manage org structure, positions, employees, accounts."""
    workspace_path = static_dir / "workspace" / "index.html"
    if not workspace_path.exists():
        raise HTTPException(status_code=404, detail="workspace_page_not_found")
    return _html_file_response(workspace_path)


@app.get("/users")
def users_page() -> FileResponse:
    """System users — accounts with access across all clients."""
    users_path = static_dir / "users" / "index.html"
    if not users_path.exists():
        raise HTTPException(status_code=404, detail="users_page_not_found")
    return _html_file_response(users_path)


@app.get("/regulations", include_in_schema=False)
@app.get("/regulations/", include_in_schema=False)
def regulations_page() -> FileResponse:
    """Регламенты должностей — реестр нормативных карточек (query `from_client` для баннера «вернуться в организацию»)."""
    regulations_path = static_dir / "regulations" / "index.html"
    if not regulations_path.exists():
        raise HTTPException(status_code=404, detail="regulations_page_not_found")
    return _html_file_response(regulations_path)


@app.get("/global")
def global_catalogs_hub() -> FileResponse:
    p = static_dir / "global" / "index.html"
    if not p.exists():
        raise HTTPException(status_code=404, detail="global_hub_not_found")
    return _html_file_response(p)


@app.get("/global/template-org")
def global_template_org_page() -> FileResponse:
    p = static_dir / "global" / "template-org.html"
    if not p.exists():
        raise HTTPException(status_code=404, detail="global_template_org_not_found")
    return _html_file_response(p)


@app.get("/global/positions")
def global_position_catalog_page() -> FileResponse:
    p = static_dir / "global" / "positions.html"
    if not p.exists():
        raise HTTPException(status_code=404, detail="global_positions_not_found")
    return _html_file_response(p)


@app.get("/global/skills")
def global_skills_page() -> FileResponse:
    p = static_dir / "global" / "skills.html"
    if not p.exists():
        raise HTTPException(status_code=404, detail="global_skills_not_found")
    return _html_file_response(p)


@app.get("/global/kpi")
def global_kpi_templates_page() -> FileResponse:
    p = static_dir / "global" / "kpi.html"
    if not p.exists():
        raise HTTPException(status_code=404, detail="global_kpi_not_found")
    return _html_file_response(p)


@app.get("/clients")
def clients_page() -> FileResponse:
    """Clients list — view organizations after onboarding."""
    clients_path = static_dir / "clients" / "index.html"
    if not clients_path.exists():
        raise HTTPException(status_code=404, detail="clients_page_not_found")
    return _html_file_response(clients_path)


if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
def _startup() -> None:
    Base.metadata.create_all(bind=engine)
    run_migrations()
    db = SessionLocal()
    try:
        seed_roles(db)
        seed_enterprise_templates(db)
        seed_position_catalog(db)
        seed_kpi_templates(db)
        merge_kpi_templates_from_xlsx(db)
        seed_regulations(db)
        apply_regulation_enrichment_json(db)
        merge_position_regulations_from_client_xlsx(db)
        link_regulation_kpis_from_templates(db)
        seed_template_org_units(db)
        # seed_clients отключён — удалённые клиенты не восстанавливаются
    finally:
        db.close()
    if run_plugin_startup is not None:
        run_plugin_startup()
