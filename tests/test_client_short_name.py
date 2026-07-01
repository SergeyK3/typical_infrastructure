"""Client short_name — PROJ-ACCESS-ADMIN Stage 2E."""

from __future__ import annotations

from pathlib import Path

from app.client_labels import client_compact_label, client_full_label, client_label_title
from tests.conftest import onboarding_payload

ROOT = Path(__file__).resolve().parents[1]


class _FakeClient:
    def __init__(self, *, name: str = "", short_name: str | None = None, code: str = "", id: str = "c1"):
        self.name = name
        self.short_name = short_name
        self.code = code
        self.id = id


def test_client_compact_label_uses_short_name_when_set():
    c = _FakeClient(name="Многопрофильный медицинский центр г. Астаны", short_name="ММЦ")
    assert client_compact_label(c) == "ММЦ"
    assert client_full_label(c) == "Многопрофильный медицинский центр г. Астаны"
    assert client_label_title(c) == "Многопрофильный медицинский центр г. Астаны"


def test_client_compact_label_falls_back_to_name():
    c = _FakeClient(name="Full Org Name", short_name=None)
    assert client_compact_label(c) == "Full Org Name"
    assert client_label_title(c) is None


def test_client_compact_label_falls_back_when_short_name_blank():
    c = _FakeClient(name="Full Org Name", short_name="   ")
    assert client_compact_label(c) == "Full Org Name"
    assert client_label_title(c) is None


def test_client_label_title_none_when_short_equals_name():
    c = _FakeClient(name="Same", short_name="Same")
    assert client_compact_label(c) == "Same"
    assert client_label_title(c) is None


def test_patch_and_get_client_short_name(client):
    create = client.post(
        "/api/clients",
        json={
            "code": "short_name_org",
            "name": "Многопрофильный медицинский центр г. Астаны",
            "status": "active",
            "template_code": "default",
        },
    )
    assert create.status_code == 200, create.text
    data = create.json()
    assert data["short_name"] is None
    client_id = data["id"]

    patch = client.patch(
        f"/api/clients/{client_id}",
        json={"short_name": "ММЦ"},
    )
    assert patch.status_code == 200, patch.text
    patched = patch.json()
    assert patched["short_name"] == "ММЦ"
    assert patched["name"] == "Многопрофильный медицинский центр г. Астаны"

    got = client.get(f"/api/clients/{client_id}")
    assert got.status_code == 200
    assert got.json()["short_name"] == "ММЦ"


def test_patch_client_clears_short_name_with_empty_string(client):
    create = client.post(
        "/api/clients",
        json={
            "code": "short_name_clear",
            "name": "Clear Test Org",
            "short_name": "CLR",
            "status": "active",
            "template_code": "default",
        },
    )
    assert create.status_code == 200, create.text
    client_id = create.json()["id"]

    patch = client.patch(
        f"/api/clients/{client_id}",
        json={"short_name": ""},
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["short_name"] is None


def test_users_api_returns_client_short_name(client):
    payload = onboarding_payload(client_code="usr_short_api", admin_login="usr_short_api_admin")
    payload["client"]["name"] = "Многопрофильный медицинский центр г. Астаны"
    r = client.post("/api/onboarding-runs", json=payload)
    assert r.status_code == 200, r.text
    client_id = r.json()["client_id"]

    patch = client.patch(f"/api/clients/{client_id}", json={"short_name": "ММЦ"})
    assert patch.status_code == 200, patch.text

    users = client.get("/api/users", params={"client_id": client_id})
    assert users.status_code == 200, users.text
    row = next(item for item in users.json()["items"] if item["login"] == "usr_short_api_admin")
    assert row["client_name"] == "Многопрофильный медицинский центр г. Астаны"
    assert row["client_short_name"] == "ММЦ"


def test_clients_edit_page_has_short_name_field():
    html = (ROOT / "static/clients/index.html").read_text(encoding="utf-8")
    assert 'id="editShortName"' in html
    assert "Краткое название" in html
    assert "ClientDisplay.compactLabel" in html
    assert "client-display.js" in html
