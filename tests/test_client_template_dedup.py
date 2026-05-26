"""Tests for client template dedup and idempotent apply."""

from __future__ import annotations

from sqlalchemy import func, select

from app.client_template_apply import apply_template_to_client
from app.client_template_dedup import dedup_client_template_entities
from app.db import SessionLocal
from app.models import ClientPositionRegulation, OrgUnit, Position
from app.utils import new_id32


def _create_client(client, code: str) -> str:
    payload = {
        "template_code": "default",
        "client": {"code": code, "name": code},
        "admin": {
            "last_name": "A",
            "first_name": "B",
            "login": f"{code}_admin",
            "password": "X",
            "email": None,
        },
    }
    r = client.post("/api/onboarding-runs", json=payload)
    assert r.status_code == 200
    return r.json()["client_id"]


def test_apply_template_syncs_org_unit_types_from_template(client):
    """ECON/FACILITY и др.: при расхождении с шаблоном — department под company, не section под ADM."""
    db = SessionLocal()
    try:
        from app.models import Client, EnterpriseTemplate

        client_row = db.scalars(select(Client).where(Client.code == "mmc")).first()
        if not client_row:
            return
        tpl = db.scalar(select(EnterpriseTemplate).where(EnterpriseTemplate.code == "hosp"))
        if not tpl:
            return
        company = db.scalars(
            select(OrgUnit).where(
                OrgUnit.client_id == client_row.id, OrgUnit.code == "company"
            )
        ).first()
        adm = db.scalars(
            select(OrgUnit).where(OrgUnit.client_id == client_row.id, OrgUnit.code == "ADM")
        ).first()
        if not company or not adm:
            return

        for code in ("ECON", "FACILITY"):
            ou = db.scalars(
                select(OrgUnit).where(
                    OrgUnit.client_id == client_row.id, OrgUnit.code == code
                )
            ).first()
            if not ou:
                continue
            ou.unit_type = "section"
            ou.parent_id = adm.id
        db.commit()

        apply_template_to_client(db, client_row.id, "hosp")
        db.commit()

        for code in ("ECON", "FACILITY"):
            ou = db.scalars(
                select(OrgUnit).where(
                    OrgUnit.client_id == client_row.id, OrgUnit.code == code
                )
            ).first()
            if not ou:
                continue
            assert ou.unit_type == "department", code
            assert ou.parent_id == company.id, code
    finally:
        db.close()


def test_apply_template_cleans_misplaced_positions(client):
    """Повторное применение шаблона убирает должности не в primary-отделении."""
    db = SessionLocal()
    try:
        from app.models import Client, EnterpriseTemplate

        client_row = db.scalars(
            select(Client).where(Client.code == "mmc")
        ).first()
        if not client_row:
            return
        tpl = db.scalar(
            select(EnterpriseTemplate).where(EnterpriseTemplate.code == "hosp")
        )
        if not tpl:
            return
        client_row.template_id = tpl.id
        db.commit()

        apply_template_to_client(db, client_row.id, "hosp")
        db.commit()

        rows = db.scalars(
            select(Position).where(
                Position.client_id == client_row.id,
                Position.position_catalog_code == "MAIN_NURSE",
            )
        ).all()
        assert len(rows) == 1
        ou = db.get(OrgUnit, rows[0].org_unit_id)
        assert ou is not None
        assert ou.code == "ADM"
    finally:
        db.close()


def test_apply_existing_does_not_duplicate_positions(client):
    client_id = _create_client(client, "dedup_apply_pos_x")
    before = client.get(f"/api/positions?client_id={client_id}&limit=500").json()["total"]

    r = client.post(
        "/api/onboarding-runs",
        json={
            "action": "apply_existing",
            "template_code": "default",
            "existing_client_id": client_id,
        },
    )
    assert r.status_code == 200
    after = client.get(f"/api/positions?client_id={client_id}&limit=500").json()["total"]
    assert after == before


def test_dedup_removes_duplicate_positions(client):
    client_id = _create_client(client, "dedup_pos_cleanup_x")
    db = SessionLocal()
    try:
        ou = db.scalars(select(OrgUnit).where(OrgUnit.client_id == client_id, OrgUnit.code == "HR")).first()
        assert ou is not None
        pos2 = Position(
            id=new_id32(),
            client_id=client_id,
            org_unit_id=ou.id,
            code="HR_MANAGER_COPY",
            name="HR-менеджер дубль",
            is_active=True,
            position_catalog_code="HR_MANAGER",
            is_detached=True,
        )
        db.add(pos2)
        db.commit()

        stats = dedup_client_template_entities(db, client_id)
        db.commit()
        assert stats.positions_removed == 1

        remaining = db.scalars(
            select(Position).where(
                Position.client_id == client_id,
                Position.org_unit_id == ou.id,
                Position.position_catalog_code == "HR_MANAGER",
            )
        ).all()
        assert len(remaining) == 1
    finally:
        db.close()


def test_apply_template_skips_existing_regulation_slot(client):
    client_id = _create_client(client, "dedup_apply_reg_x")
    db = SessionLocal()
    try:
        before = db.scalar(
            select(func.count())
            .select_from(ClientPositionRegulation)
            .where(ClientPositionRegulation.client_id == client_id)
        )

        apply_template_to_client(db, client_id, "default")
        db.commit()

        after = db.scalar(
            select(func.count())
            .select_from(ClientPositionRegulation)
            .where(ClientPositionRegulation.client_id == client_id)
        )
        assert after == before
    finally:
        db.close()
