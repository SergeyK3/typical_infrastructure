"""Backfill missing default template org units from DEFAULT_ORG_UNITS."""

from __future__ import annotations

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import TemplateOrgUnitRow
from app.seed import seed_template_org_units
from app.template_constants import DEFAULT_TEMPLATE_CODE


def test_template_org_units_include_sales_and_lead(client):
    r = client.get(
        "/api/template-org-units",
        params={"template_code": "default", "limit": 500, "offset": 0},
    )
    assert r.status_code == 200
    depts = {u["code"] for u in r.json()["items"] if u["unit_type"] == "department"}
    assert {"SALES", "LEAD"}.issubset(depts)


def test_seed_template_org_units_backfills_missing_departments(client):
    db = SessionLocal()
    try:
        db.execute(
            delete(TemplateOrgUnitRow).where(
                TemplateOrgUnitRow.template_code == DEFAULT_TEMPLATE_CODE,
                TemplateOrgUnitRow.code.in_(("SALES", "LEAD", "MKT_LEADGEN", "HR_REG_CTRL")),
            )
        )
        db.commit()

        changed = seed_template_org_units(db)
        assert changed >= 4

        codes = set(
            db.scalars(
                select(TemplateOrgUnitRow.code).where(
                    TemplateOrgUnitRow.template_code == DEFAULT_TEMPLATE_CODE
                )
            ).all()
        )
        assert {"SALES", "LEAD", "MKT_LEADGEN", "HR_REG_CTRL"}.issubset(codes)

        mkt_sales = db.scalar(
            select(TemplateOrgUnitRow).where(
                TemplateOrgUnitRow.template_code == DEFAULT_TEMPLATE_CODE,
                TemplateOrgUnitRow.code == "MKT_SALES",
            )
        )
        assert mkt_sales is not None
        assert mkt_sales.parent_code == "SALES"
    finally:
        db.close()
