import os

os.environ.setdefault("SQLITE_PATH", ":memory:")

from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as c:
    rows = c.get("/api/enterprise-templates").json()
    src = next(t for t in rows if t["code"] == "default")
    tid = src["id"]
    r = c.post(
        f"/api/enterprise-templates/{tid}/clone",
        json={
            "new_code": "hosp1",
            "new_name": "шаблон стационара",
            "copy_positions": True,
            "copy_kpi": True,
            "copy_regulations": True,
            "copy_skills": True,
        },
    )
    print("status", r.status_code)
    print(r.text[:3000])
