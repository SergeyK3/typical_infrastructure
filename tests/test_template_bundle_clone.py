r"""Bundle-клонирование шаблона: изоляция слоёв по template_code."""

from __future__ import annotations


def _default_template(client):
    rows = client.get("/api/enterprise-templates").json()
    tpl = next((t for t in rows if t["code"] == "default"), None)
    assert tpl is not None
    return tpl


def test_clone_bundle_isolation_and_counts(client):
    src = _default_template(client)
    preview = client.get(f"/api/enterprise-templates/{src['id']}/structure-preview").json()
    assert preview["template_code"] == "default"
    src_counts = preview["counts"]

    r = client.post(
        f"/api/enterprise-templates/{src['id']}/clone",
        json={
            "new_code": "retail_bundle_test",
            "new_name": "Retail bundle test",
            "copy_positions": True,
            "copy_kpi": True,
            "copy_regulations": True,
            "copy_skills": True,
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["template"]["code"] == "retail_bundle_test"
    assert data["template"]["status"] == "draft"
    counts = data["counts"]
    assert counts["org_units"] >= src_counts.get("org_units", 1)
    assert counts["positions"] >= 0

    retail_positions = client.get(
        "/api/position-catalog",
        params={"template_code": "retail_bundle_test", "limit": 500},
    ).json()["items"]
    default_positions = client.get(
        "/api/position-catalog",
        params={"template_code": "default", "limit": 500},
    ).json()["items"]
    assert len(retail_positions) == len(default_positions)

    if retail_positions:
        pc = retail_positions[0]["position_code"]
        patch = client.patch(
            f"/api/position-catalog/{pc}",
            params={"template_code": "retail_bundle_test"},
            json={"position_name_ru": "Изолированное имя retail"},
        )
        assert patch.status_code == 200, patch.text

        def _name(items, code):
            for row in items:
                if row["position_code"] == code:
                    return row["position_name_ru"]
            return None

        retail_after = client.get(
            "/api/position-catalog",
            params={"template_code": "retail_bundle_test", "limit": 500},
        ).json()["items"]
        default_after = client.get(
            "/api/position-catalog",
            params={"template_code": "default", "limit": 500},
        ).json()["items"]
        assert _name(retail_after, pc) == "Изолированное имя retail"
        assert _name(default_after, pc) != "Изолированное имя retail"


def _flatten_tree(nodes):
    out = []
    for n in nodes:
        out.append(n)
        out.extend(_flatten_tree(n.get("children") or []))
    return out


def test_clone_without_prefix_copies_skills(client):
    """Клон без code_prefix: skill_code совпадают с источником, но template_code другой."""
    src = _default_template(client)
    code = "no_prefix_skills_clone"
    r = client.post(
        f"/api/enterprise-templates/{src['id']}/clone",
        json={
            "new_code": code,
            "new_name": "No prefix skills",
            "copy_positions": True,
            "copy_kpi": True,
            "copy_regulations": True,
            "copy_skills": True,
        },
    )
    assert r.status_code == 201, r.text
    counts = r.json()["counts"]
    assert counts["skill_definitions"] > 0
    assert counts["competency_matrix_rows"] > 0


def test_clone_with_code_prefix(client):
    src = _default_template(client)
    r = client.post(
        f"/api/enterprise-templates/{src['id']}/clone",
        json={
            "new_code": "prefixed_bundle_test",
            "new_name": "Prefixed bundle",
            "code_prefix": "retail_",
        },
    )
    assert r.status_code == 201, r.text

    tree = _flatten_tree(
        client.get(
            "/api/template-org-units/tree",
            params={"template_code": "prefixed_bundle_test"},
        ).json()
    )
    codes = {n["code"] for n in tree}

    default_tree = _flatten_tree(
        client.get(
            "/api/template-org-units/tree",
            params={"template_code": "default"},
        ).json()
    )
    default_codes = {n["code"] for n in default_tree}

    assert any(c.startswith("retail_") for c in codes)
    assert "HR" in default_codes
    assert "retail_HR" not in default_codes
