# app/excel_export.py
r"""Сборка .xlsx для выгрузки справочников (openpyxl)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any, Iterable
from urllib.parse import quote

from fastapi.responses import Response


def _cell(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.replace(tzinfo=None) if v.tzinfo else v
    if isinstance(v, date):
        return v
    if isinstance(v, Decimal):
        return float(v)
    return v


def xlsx_file_response(
    *,
    download_name: str,
    sheet_title: str,
    headers: list[str],
    rows: Iterable[list[Any]],
) -> Response:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    safe_title = sheet_title[:31] if sheet_title else "Sheet1"
    ws.title = safe_title
    ws.append(headers)
    for row in rows:
        ws.append([_cell(x) for x in row])
    bio = BytesIO()
    wb.save(bio)
    body = bio.getvalue()

    fn = download_name if download_name.lower().endswith(".xlsx") else f"{download_name}.xlsx"
    ascii_fn = fn.encode("ascii", "replace").decode("ascii").replace("?", "_")
    cd = f"attachment; filename=\"{ascii_fn}\"; filename*=UTF-8''{quote(fn)}"
    return Response(
        content=body,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": cd},
    )
