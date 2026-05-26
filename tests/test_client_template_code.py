"""Клиент: привязка template_code при создании и в ответе API."""


def test_create_client_with_template_code(client):
    r = client.post(
        "/api/clients",
        json={
            "code": "tpl_code_client",
            "name": "Tpl Code Client",
            "status": "active",
            "template_code": "default",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["template_code"] == "default"
    assert data["template_id"]

    r2 = client.get("/api/clients/" + data["id"])
    assert r2.status_code == 200
    assert r2.json()["template_code"] == "default"


def test_create_client_unknown_template_code(client):
    r = client.post(
        "/api/clients",
        json={
            "code": "tpl_bad_client",
            "name": "Tpl Bad Client",
            "status": "active",
            "template_code": "no_such_template_xyz",
        },
    )
    assert r.status_code == 404
