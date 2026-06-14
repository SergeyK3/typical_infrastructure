#!/usr/bin/env python3
"""Smoke checks after deployment. Run against staging/production URL."""
from __future__ import annotations

import argparse
import sys
import urllib.request
import urllib.error
import json


def check(url: str, path: str, expected_status: int = 200) -> bool:
    full = f"{url.rstrip('/')}{path}"
    try:
        req = urllib.request.Request(full)
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status != expected_status:
                print(f"  FAIL {path}: expected {expected_status}, got {r.status}")
                return False
            data = r.read().decode()
            if path == "/health/ready":
                obj = json.loads(data)
                if obj.get("status") != "ready":
                    print(f"  FAIL {path}: status != ready")
                    return False
            print(f"  OK   {path}")
            return True
    except urllib.error.HTTPError as e:
        if e.code == expected_status:
            print(f"  OK   {path} (expected {expected_status})")
            return True
        print(f"  FAIL {path}: HTTP {e.code}")
        return False
    except Exception as e:
        print(f"  FAIL {path}: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke checks after deploy")
    parser.add_argument("--url", default="http://127.0.0.1:8100", help="Base URL")
    args = parser.parse_args()
    url = args.url.rstrip("/")

    checks = [
        ("/health/ready", 200),
        ("/api/clients", 200),
        ("/api/enterprise-templates", 200),
        ("/api/enterprise-templates/default/structure-preview", 200),
        ("/api/enterprise-templates/medical/structure-preview", 200),
        ("/api/onboarding-runs", 200),
    ]

    print(f"Smoke checks: {url}")
    ok = 0
    for path, status in checks:
        if check(url, path, status):
            ok += 1

    print(f"\nResult: {ok}/{len(checks)} passed")
    return 0 if ok == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
