"""Выбор связей «типовая должность ↔ отделение» для развёртывания у клиента."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PositionCatalog, PositionDeptType


def _department_codes(structure: list[dict]) -> set[str]:
    return {s["code"] for s in structure if s.get("unit_type") == "department"}


def select_position_dept_links_for_deploy(
    db: Session,
    template_code: str,
    structure: list[dict],
) -> list[PositionDeptType]:
    """
    Одна целевая связь на position_code для развёртывания штатной должности.

    Правила:
    - только отделения (unit_type=department), не секции;
    - при нескольких связях — primary, затем совпадение function_code с кодом отделения;
    - при неоднозначности без primary — связь пропускается (не размножаем должность).
    """
    dept_codes = _department_codes(structure)
    if not dept_codes:
        return []

    catalog_by_code = {
        r.position_code: r
        for r in db.scalars(
            select(PositionCatalog).where(
                PositionCatalog.template_code == template_code,
                PositionCatalog.is_active == True,
            )
        ).all()
    }

    links = db.scalars(
        select(PositionDeptType).where(
            PositionDeptType.template_code == template_code,
            PositionDeptType.dept_type_code.in_(dept_codes),
        )
    ).all()

    by_position: dict[str, list[PositionDeptType]] = defaultdict(list)
    for link in links:
        if link.position_code not in catalog_by_code:
            continue
        by_position[link.position_code].append(link)

    chosen: list[PositionDeptType] = []
    for pos_code, group in by_position.items():
        pick = _pick_best_link(group, catalog_by_code.get(pos_code))
        if pick:
            chosen.append(pick)
    return chosen


def _pick_best_link(
    links: list[PositionDeptType], catalog: PositionCatalog | None
) -> PositionDeptType | None:
    if not links:
        return None
    if len(links) == 1:
        return links[0]

    fn = (catalog.function_code or "").strip() if catalog else ""
    if fn:
        fn_match = [l for l in links if l.dept_type_code.strip() == fn]
        if len(fn_match) == 1:
            return fn_match[0]

    primaries = [l for l in links if l.is_primary]
    if len(primaries) == 1:
        return primaries[0]
    if len(primaries) > 1:
        if fn:
            fn_primary = [l for l in primaries if l.dept_type_code.strip() == fn]
            if fn_primary:
                return fn_primary[0]
        return sorted(primaries, key=lambda l: l.dept_type_code)[0]

    return None


def normalize_template_position_dept_links(db: Session, template_code: str) -> int:
    """
    Оставить одну связь position↔department на код должности (как при deploy).
    Лишние строки в position_dept_types удаляются; у оставшейся is_primary=True.
    """
    from app.template_org_resolve import resolve_template_structure

    structure = resolve_template_structure(db, template_code)
    dept_codes = _department_codes(structure)
    if not dept_codes:
        return 0

    catalog_by_code = {
        r.position_code: r
        for r in db.scalars(
            select(PositionCatalog).where(
                PositionCatalog.template_code == template_code,
                PositionCatalog.is_active == True,
            )
        ).all()
    }

    links = db.scalars(
        select(PositionDeptType).where(
            PositionDeptType.template_code == template_code,
            PositionDeptType.dept_type_code.in_(dept_codes),
        )
    ).all()

    by_position: dict[str, list[PositionDeptType]] = defaultdict(list)
    for link in links:
        if link.position_code in catalog_by_code:
            by_position[link.position_code].append(link)

    removed = 0
    for pos_code, group in by_position.items():
        pick = _pick_best_link(group, catalog_by_code.get(pos_code))
        if not pick:
            continue
        for link in list(group):
            if link.dept_type_code == pick.dept_type_code:
                link.is_primary = True
                continue
            db.delete(link)
            removed += 1
    if removed:
        db.flush()
    return removed
