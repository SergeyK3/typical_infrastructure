"""Backfill log_group для клиентских org_units из medical Excel."""

from __future__ import annotations

from sqlalchemy import select

from app.db import SessionLocal
from app.medical_org_groups import LOG_GROUP_CLINICAL
from app.medical_template_excel import load_medical_org_excel
from app.models import OrgUnit
from app.seed import seed_medical_template_bundle
from scripts.backfill_medical_org_unit_groups import (
    backfill_client_org_units,
    sync_template_org_units,
)
from tests.conftest import onboarding_payload


def _onboard_medical(client, *, suffix: str) -> str:
    r = client.post(
        "/api/onboarding-runs",
        json=onboarding_payload(
            client_code=f"med_grp_{suffix}",
            client_name=f"Med Group {suffix}",
            admin_login=f"med_grp_admin_{suffix}",
            template_code="medical",
        ),
    )
    assert r.status_code == 200
    return r.json()["client_id"]


def test_seed_medical_template_sets_log_group(client):
    db = SessionLocal()
    try:
        seed_medical_template_bundle(db)
        from app.models import TemplateOrgUnitRow

        oper = db.scalars(
            select(TemplateOrgUnitRow).where(
                TemplateOrgUnitRow.template_code == "medical",
                TemplateOrgUnitRow.code == "OPER",
            )
        ).first()
        assert oper is not None
        assert oper.log_group == "paraclinical"
        poly = db.scalars(
            select(TemplateOrgUnitRow).where(
                TemplateOrgUnitRow.template_code == "medical",
                TemplateOrgUnitRow.code == "POLYCLINNC",
            )
        ).first()
        assert poly is not None
        assert poly.log_group == "clinical"
    finally:
        db.close()


def test_backfill_dry_run_does_not_change_db(client):
    client_id = _onboard_medical(client, suffix="dry")
    excel = load_medical_org_excel()
    db = SessionLocal()
    try:
        before = {
            row.id: row.log_group
            for row in db.scalars(select(OrgUnit).where(OrgUnit.client_id == client_id)).all()
        }
        stats = backfill_client_org_units(db, client_id, excel, apply=False)
        db.expire_all()
        after = {
            row.id: row.log_group
            for row in db.scalars(select(OrgUnit).where(OrgUnit.client_id == client_id)).all()
        }
        assert before == after
        assert stats.updated >= 1
    finally:
        db.close()


def test_backfill_apply_updates_and_is_idempotent(client):
    client_id = _onboard_medical(client, suffix="apply")
    excel = load_medical_org_excel()
    db = SessionLocal()
    try:
        stats1 = backfill_client_org_units(db, client_id, excel, apply=True)
        assert stats1.updated >= 1

        poly = db.scalars(
            select(OrgUnit).where(
                OrgUnit.client_id == client_id,
                OrgUnit.code == "POLYCLINNC",
            )
        ).first()
        assert poly is not None
        assert poly.log_group == LOG_GROUP_CLINICAL

        stats2 = backfill_client_org_units(db, client_id, excel, apply=True)
        assert stats2.updated == 0
        assert stats2.skipped >= stats1.updated
    finally:
        db.close()


def test_org_units_tree_effective_log_group_after_backfill(client):
    client_id = _onboard_medical(client, suffix="api")
    excel = load_medical_org_excel()
    db = SessionLocal()
    try:
        backfill_client_org_units(db, client_id, excel, apply=True)
    finally:
        db.close()

    tree = client.get("/api/org-units/tree", params={"client_id": client_id}).json()

    def flatten(nodes, out=None):
        out = out or []
        for n in nodes or []:
            out.append(n)
            flatten(n.get("children") or [], out)
        return out

    poly = next(u for u in flatten(tree) if u["code"] == "POLYCLINNC")
    assert poly.get("effective_log_group") == LOG_GROUP_CLINICAL


def test_sync_template_dry_run(client):
    excel = load_medical_org_excel()
    db = SessionLocal()
    try:
        seed_medical_template_bundle(db)
        stats = sync_template_org_units(db, excel, apply=False)
        assert stats.found > 0
    finally:
        db.close()
