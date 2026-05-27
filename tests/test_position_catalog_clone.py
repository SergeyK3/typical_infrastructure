"""Клонирование строки глобального каталога типовых должностей."""


def test_clone_position_catalog_row(client):
    rows = client.get("/api/position-catalog", params={"template_code": "default", "limit": 200}).json()["items"]
    hr = next(r for r in rows if r["position_code"] == "HR_GENERALIST")

    r = client.post(
        f"/api/position-catalog/{hr['position_code']}/clone",
        params={"template_code": "default"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["row"]["position_code"].startswith("HR_GENERALIST_COPY")
    assert "Копия" in data["row"]["position_name_ru"]
    assert data["dept_links_created"] >= 1

    rows2 = client.get("/api/position-catalog", params={"template_code": "default", "limit": 200}).json()["items"]
    assert any(x["position_code"] == data["row"]["position_code"] for x in rows2)


def test_rename_position_catalog_code(client):
    clone = client.post(
        "/api/position-catalog/HR_GENERALIST/clone",
        params={"template_code": "default"},
    )
    assert clone.status_code == 201, clone.text
    old_code = clone.json()["row"]["position_code"]

    r = client.patch(
        f"/api/position-catalog/{old_code}",
        params={"template_code": "default"},
        json={
            "position_code": "HR_GENERALIST_TEST_RENAME",
            "position_name_ru": "Тестовое переименование",
            "position_level": "DEPUTY",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["position_code"] == "HR_GENERALIST_TEST_RENAME"
    assert data["position_level"] == "DEPUTY"
    assert data["position_name_ru"] == "Тестовое переименование"

    rows = client.get("/api/position-catalog", params={"template_code": "default", "limit": 500}).json()["items"]
    assert not any(x["position_code"] == old_code for x in rows)
    assert any(x["position_code"] == "HR_GENERALIST_TEST_RENAME" for x in rows)


def test_clone_position_catalog_not_found(client):
    r = client.post(
        "/api/position-catalog/NO_SUCH_POSITION/clone",
        params={"template_code": "default"},
    )
    assert r.status_code == 404
