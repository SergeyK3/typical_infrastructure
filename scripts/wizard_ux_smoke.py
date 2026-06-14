#!/usr/bin/env python3
"""UX polish + medical template smoke checks (API + static HTML)."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar


def _request(
    opener: urllib.request.OpenerDirector,
    url: str,
    *,
    method: str = "GET",
    data: dict | None = None,
    headers: dict | None = None,
) -> tuple[int, str, dict]:
    body = None
    req_headers = dict(headers or {})
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, method=method, headers=req_headers)
    try:
        with opener.open(req, timeout=30) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            return resp.status, text, dict(resp.headers)
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", errors="replace")
        return e.code, text, dict(e.headers)


def login(opener: urllib.request.OpenerDirector, base: str, login: str, password: str) -> None:
    status, text, _ = _request(
        opener,
        f"{base}/api/auth/login",
        method="POST",
        data={"login": login, "password": password},
    )
    if status != 200:
        raise RuntimeError(f"login failed ({status}): {text[:300]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Wizard UX + medical template smoke")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--login", default="platform_admin")
    parser.add_argument("--password", default="PlatformAdmin123!")
    args = parser.parse_args()
    base = args.url.rstrip("/")

    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    failures: list[str] = []

    def ok(msg: str) -> None:
        print(f"  OK   {msg}")

    def fail(msg: str) -> None:
        print(f"  FAIL {msg}")
        failures.append(msg)

    print(f"Wizard UX smoke: {base}")
    login(opener, base, args.login, args.password)
    ok("system_admin login")

    status, html, _ = _request(opener, f"{base}/clients")
    if status != 200:
        fail(f"/clients HTTP {status}")
    elif "Чтобы войти в организацию" not in html:
        fail("clients hint missing")
    else:
        ok("clients hint")

    status, html, _ = _request(opener, f"{base}/wizard")
    if status != 200:
        fail(f"/wizard HTTP {status}")
    else:
        for needle in (
            "Создать организацию",
            "Dry Run — это проверка сценария без внесения изменений в систему.",
            "Перейти в организацию",
            "Список клиентов",
            "Создать ещё организацию",
        ):
            if needle not in html:
                fail(f"wizard missing: {needle}")
            else:
                ok(f"wizard text: {needle[:40]}...")

    status, text, _ = _request(opener, f"{base}/api/enterprise-templates")
    if status != 200:
        fail(f"enterprise-templates HTTP {status}")
    else:
        rows = json.loads(text)
        codes = {r["code"]: r["name"] for r in rows if r.get("is_active", True)}
        if "default" not in codes or "medical" not in codes:
            fail(f"templates dropdown data: {codes}")
        else:
            ok(f"templates: default={codes['default']!r}, medical={codes['medical']!r}")

    status, text, _ = _request(opener, f"{base}/api/enterprise-templates/medical/structure-preview")
    if status != 200:
        fail(f"medical structure-preview HTTP {status}")
    else:
        preview = json.loads(text)
        ou = {u["code"] for u in preview.get("org_units", [])}
        if not {"POLYCLINNC", "STAT"}.issubset(ou):
            fail(f"medical org units: {sorted(ou)}")
        else:
            ok("medical structure-preview POLYCLINNC+STAT")

    code = f"ux_smoke_{int(__import__('time').time())}"
    payload = {
        "template_code": "medical",
        "client": {"code": code, "name": f"UX Smoke {code}"},
        "admin": {
            "last_name": "UX",
            "first_name": "Smoke",
            "login": f"{code}_admin",
            "password": "UxSmoke123!",
            "email": None,
        },
    }
    status, text, _ = _request(
        opener, f"{base}/api/onboarding-runs", method="POST", data=payload
    )
    if status != 200:
        fail(f"medical onboarding HTTP {status}: {text[:300]}")
    else:
        run = json.loads(text)
        client_id = run.get("client_id")
        ok(f"medical onboarding client_id={client_id}")
        if client_id:
            st, ou_text, _ = _request(opener, f"{base}/api/org-units?client_id={client_id}&limit=200")
            if st != 200:
                fail(f"org-units HTTP {st}")
            else:
                items = json.loads(ou_text).get("items", [])
                codes = {x["code"] for x in items}
                if "STAT" not in codes or "POLYCLINNC" not in codes:
                    fail(f"deployed org units: {sorted(codes)}")
                else:
                    ok("medical org deployed")

    print(f"\nResult: {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
