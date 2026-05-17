from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook


def _xlsx_bytes(headers: list[str], rows: list[list[object]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_employee_import_updates_existing_and_resolves_position_inside_department(client):
    r = client.post("/api/clients", json={"id": "client_emp_import", "code": "emp_import", "name": "Emp Import", "status": "active"})
    assert r.status_code == 200, r.text
    client_id = r.json()["id"]

    sales = client.post(
        "/api/org-units",
        json={"id": "ou_sales", "client_id": client_id, "code": "SALES", "name": "Sales", "unit_type": "department"},
    )
    assert sales.status_code == 200, sales.text
    ops = client.post(
        "/api/org-units",
        json={"id": "ou_ops", "client_id": client_id, "code": "OPS", "name": "Ops", "unit_type": "department"},
    )
    assert ops.status_code == 200, ops.text

    sales_pos = client.post(
        "/api/positions",
        json={"id": "pos_sales_manager", "client_id": client_id, "org_unit_id": "ou_sales", "code": "MANAGER", "name": "Manager"},
    )
    assert sales_pos.status_code == 200, sales_pos.text
    ops_pos = client.post(
        "/api/positions",
        json={"id": "pos_ops_manager", "client_id": client_id, "org_unit_id": "ou_ops", "code": "MANAGER", "name": "Manager"},
    )
    assert ops_pos.status_code == 200, ops_pos.text

    existing = client.post(
        "/api/employees",
        json={
            "id": "emp_existing",
            "client_id": client_id,
            "last_name": "Ivanov",
            "first_name": "Ivan",
            "middle_name": None,
            "email": None,
            "phone": None,
            "telegram_id": None,
            "org_unit_id": "ou_ops",
            "position_id": "pos_ops_manager",
            "employment_status": "active",
            "is_manager": False,
        },
    )
    assert existing.status_code == 200, existing.text

    content = _xlsx_bytes(
        ["id", "last_name", "first_name", "org_unit_code", "position_code"],
        [["emp_existing", "Ivanov", "Ivan", "SALES", "MANAGER"]],
    )

    for _ in range(2):
        imported = client.post(
            f"/api/employees/import-excel?client_id={client_id}",
            files={
                "file": (
                    "employees.xlsx",
                    content,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert imported.status_code == 200, imported.text
        assert imported.json()[0]["id"] == "emp_existing"
        assert imported.json()[0]["org_unit_id"] == "ou_sales"
        assert imported.json()[0]["position_id"] == "pos_sales_manager"

    employees = client.get(f"/api/employees?client_id={client_id}&limit=2000")
    assert employees.status_code == 200, employees.text
    assert employees.json()["total"] == 1
