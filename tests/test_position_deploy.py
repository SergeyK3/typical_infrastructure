"""Tests for position deploy link selection."""

from __future__ import annotations

from types import SimpleNamespace

from app.position_deploy import _pick_best_link, select_position_dept_links_for_deploy


def _link(dept: str, primary: bool = False):
    return SimpleNamespace(dept_type_code=dept, is_primary=primary)


def _catalog(fn: str):
    return SimpleNamespace(function_code=fn)


def test_pick_best_link_prefers_single_primary():
    pick = _pick_best_link([_link("HR", True), _link("LAUNDRY", False)], _catalog("MED"))
    assert pick.dept_type_code == "HR"


def test_pick_best_link_prefers_function_code():
    pick = _pick_best_link(
        [_link("MED", True), _link("LAUNDRY", True)],
        _catalog("MED"),
    )
    assert pick.dept_type_code == "MED"


def test_pick_best_link_skips_ambiguous():
    assert _pick_best_link([_link("A", False), _link("B", False)], _catalog("X")) is None


def test_normalize_template_position_dept_links_keeps_one_primary(client):
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import PositionDeptType
    from app.position_deploy import normalize_template_position_dept_links

    db = SessionLocal()
    try:
        has_hosp = db.scalar(
            select(PositionDeptType).where(
                PositionDeptType.template_code == "hosp",
                PositionDeptType.position_code == "MAIN_NURSE",
            ).limit(1)
        )
        if not has_hosp:
            return
        normalize_template_position_dept_links(db, "hosp")
        db.commit()
        rows = db.scalars(
            select(PositionDeptType).where(
                PositionDeptType.template_code == "hosp",
                PositionDeptType.position_code == "MAIN_NURSE",
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].dept_type_code == "ADM"
        assert rows[0].is_primary is True
    finally:
        db.close()


def test_onboarding_one_position_per_catalog_code(client):
    payload = {
        "template_code": "default",
        "client": {"code": "one_pos_per_cat_x", "name": "One Pos Per Cat"},
        "admin": {
            "last_name": "A",
            "first_name": "B",
            "login": "one_pos_per_cat_admin",
            "password": "X",
            "email": None,
        },
    }
    r = client.post("/api/onboarding-runs", json=payload)
    assert r.status_code == 200
    client_id = r.json()["client_id"]
    positions = client.get(f"/api/positions?client_id={client_id}&limit=500").json()["items"]
    codes = [p.get("position_catalog_code") or p["code"] for p in positions]
    assert len(codes) == len(set(codes))
