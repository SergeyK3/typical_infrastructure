r"""D:\MyActivity\MyInfoBusiness\MyPythonApps\10 Typical_infrastructure\app\api.py"""

from __future__ import annotations

from fastapi import APIRouter

from app.routers.accounts import router as accounts_router
from app.routers.catalog_copy import router as catalog_copy_router
from app.routers.client_kpis import router as client_kpis_router
from app.routers.client_regulations import router as client_regulations_router
from app.routers.clients import router as clients_router
from app.routers.enterprise_templates import router as enterprise_templates_router
from app.routers.employees import router as employees_router
from app.routers.kpi_templates import router as kpi_templates_router
from app.routers.onboarding import router as onboarding_router
from app.routers.org_units import router as org_units_router
from app.routers.psychological_testing import router as psychological_testing_router
from app.routers.position_catalog import router as position_catalog_router
from app.routers.positions import router as positions_router
from app.routers.regulations import router as regulations_router
from app.routers.roles import router as roles_router
from app.routers.template_org_units import router as template_org_units_router
from app.routers.users import router as users_router

router = APIRouter()

router.include_router(accounts_router)
router.include_router(catalog_copy_router)
router.include_router(client_kpis_router)
router.include_router(client_regulations_router)
router.include_router(clients_router)
router.include_router(enterprise_templates_router)
router.include_router(employees_router)
router.include_router(kpi_templates_router)
router.include_router(onboarding_router)
router.include_router(org_units_router)
router.include_router(psychological_testing_router)
router.include_router(position_catalog_router)
router.include_router(positions_router)
router.include_router(regulations_router)
router.include_router(roles_router)
router.include_router(template_org_units_router)
router.include_router(users_router)


