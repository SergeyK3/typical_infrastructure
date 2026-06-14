"""Local HTTP E2E checks for auth MVP hardening."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar

BASE = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8000")
SYS_LOGIN = os.environ.get("SYSTEM_ADMIN_LOGIN", "platform_admin")
SYS_PASSWORD = os.environ.get("SYSTEM_ADMIN_PASSWORD", "PlatformAdmin123!")


def main() -> int:
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def req(method: str, path: str, body: dict | None = None, expect: int | None = None):
        data = None
        headers: dict[str, str] = {}
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
        try:
            resp = opener.open(request)
            code = resp.getcode()
            text = resp.read().decode()
        except urllib.error.HTTPError as e:
            code = e.code
            text = e.read().decode()
        if expect is not None and code != expect:
            raise SystemExit(f"FAIL {method} {path}: expected {expect}, got {code}: {text[:300]}")
        parsed = None
        if text:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = text
        return code, parsed

    for path in (
        "/api/employees?client_id=x",
        "/api/org-units?client_id=x",
        "/api/accounts?client_id=x",
        "/api/positions?client_id=x",
        "/api/roles",
    ):
        code, _ = req("GET", path)
        if code != 401:
            raise SystemExit(f"FAIL unauth {path}: {code}")

    _, data = req(
        "POST",
        "/api/auth/login",
        {"login": SYS_LOGIN, "password": SYS_PASSWORD},
        200,
    )
    assert data["is_system"] is True
    assert data["redirect_url"] == "/clients"

    req("GET", "/api/clients", expect=200)

    suffix = str(int(time.time()))
    payload_a = {
        "template_code": "default",
        "client": {"code": f"e2e_a_{suffix}", "name": "E2E A"},
        "admin": {
            "last_name": "A",
            "first_name": "Admin",
            "login": f"e2e_a_admin_{suffix}",
            "password": "TempPass123!",
            "email": f"a_{suffix}@test.example",
        },
    }
    payload_b = {
        "template_code": "default",
        "client": {"code": f"e2e_b_{suffix}", "name": "E2E B"},
        "admin": {
            "last_name": "B",
            "first_name": "Admin",
            "login": f"e2e_b_admin_{suffix}",
            "password": "TempPass123!",
            "email": f"b_{suffix}@test.example",
        },
    }
    _, run_a = req("POST", "/api/onboarding-runs", payload_a, 200)
    _, run_b = req("POST", "/api/onboarding-runs", payload_b, 200)
    client_a = run_a["client_id"]
    client_b = run_b["client_id"]

    req("POST", "/api/auth/logout", {}, 204)
    jar.clear()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    admin_login = f"e2e_a_admin_{suffix}"
    _, admin_a = req(
        "POST",
        "/api/auth/login",
        {"login": admin_login, "password": "TempPass123!"},
        200,
    )
    assert admin_a["client_id"] == client_a

    for path in (
        f"/api/employees?client_id={client_b}",
        f"/api/org-units?client_id={client_b}",
        f"/api/accounts?client_id={client_b}",
        f"/api/positions?client_id={client_b}",
    ):
        code, _ = req("GET", path)
        if code != 403:
            raise SystemExit(f"FAIL cross-tenant {path}: {code}")

    _, emps = req("GET", f"/api/employees?client_id={client_a}&limit=5", expect=200)
    assert emps["total"] >= 1

    _, new_emp = req(
        "POST",
        "/api/employees",
        {
            "client_id": client_a,
            "last_name": "Worker",
            "first_name": "Test",
            "email": f"worker_{suffix}@test.example",
            "employment_status": "active",
        },
        200,
    )
    emp_id = new_emp["id"]
    req(
        "POST",
        "/api/accounts",
        {
            "employee_id": emp_id,
            "login": f"e2e_employee_user_{suffix}",
            "password": "NewUserPass123!",
            "status": "active",
            "role_codes": ["employee"],
        },
        200,
    )

    req("GET", f"/client/{client_a}", expect=200)

    code, _ = req("POST", "/api/accounts/encode-password", {"password": "x"})
    if code != 403:
        raise SystemExit(f"FAIL encode-password org admin: {code}")

    print("E2E OK")
    print(f"client_a={client_a}")
    print(f"client_b={client_b}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
