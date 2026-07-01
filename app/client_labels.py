"""Compact display labels for Client (Organization) — PROJ-ACCESS-ADMIN Stage 2E."""

from __future__ import annotations

from typing import Protocol


class ClientLabelSource(Protocol):
    short_name: str | None
    name: str | None
    code: str | None
    id: str | None


def _strip(value: str | None) -> str:
    return (value or "").strip()


def client_full_label(client: ClientLabelSource) -> str:
    """Official / full organization name for legal context and exports."""
    return _strip(client.name) or _strip(client.code) or _strip(client.id)


def client_compact_label(client: ClientLabelSource) -> str:
    """Compact label for tables, selectors, and breadcrumbs."""
    short = _strip(client.short_name)
    if short:
        return short
    return client_full_label(client)


def client_label_title(client: ClientLabelSource) -> str | None:
    """Full name for tooltip when compact label differs from official name."""
    short = _strip(client.short_name)
    full = _strip(client.name)
    if short and full and short != full:
        return full
    return None
