"""Inline keyboards for psychological testing (callback prefix ``pt:``)."""

from __future__ import annotations

from typing import Any

from psychological_testing.domain.entities import TestDefinition
from psychological_testing.shared_engine.item_bank_loader import (
    DimensionBankItem,
    ForcedChoiceItem,
    LikertBankItem,
)
from psychological_testing.shared_engine.question_selector import SelectableItem

SessionItem = SelectableItem | ForcedChoiceItem | DimensionBankItem | LikertBankItem

CALLBACK_PREFIX = "pt"


def build_callback_data(session_id: str, item_id: str, value: str) -> str:
    """``pt:{session_id}:{item_id}:{value}`` (< 64 bytes for Telegram)."""
    data = f"{CALLBACK_PREFIX}:{session_id}:{item_id}:{value}"
    if len(data.encode("utf-8")) > 64:
        raise ValueError(f"callback_data too long: {data!r}")
    return data


def parse_callback_data(data: str) -> tuple[str, str, str] | None:
    if not data.startswith(f"{CALLBACK_PREFIX}:"):
        return None
    parts = data.split(":", 3)
    if len(parts) != 4:
        return None
    return parts[1], parts[2], parts[3]


def inline_keyboard(rows: list[list[tuple[str, str]]]) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": label, "callback_data": cb} for label, cb in row] for row in rows
        ]
    }


def _likert_keyboard(
    definition: TestDefinition,
    session_id: str,
    item_id: str,
) -> dict[str, Any]:
    min_v = int(definition.response_scale.get("min", 1))
    max_v = int(definition.response_scale.get("max", 5))
    values = list(range(min_v, max_v + 1))
    row_top = [
        (str(n), build_callback_data(session_id, item_id, str(n)))
        for n in values[:3]
    ]
    row_bottom = [
        (str(n), build_callback_data(session_id, item_id, str(n)))
        for n in values[3:]
    ]
    return inline_keyboard([row_top, row_bottom])


def keyboard_for_item(
    definition: TestDefinition,
    session_id: str,
    item: SessionItem,
) -> dict[str, Any] | None:
    test_id = definition.test_id
    if test_id == "mbti":
        assert isinstance(item, SelectableItem)
        return inline_keyboard(
            [
                [
                    ("A", build_callback_data(session_id, item.id, "A")),
                    ("B", build_callback_data(session_id, item.id, "B")),
                ]
            ]
        )
    if test_id == "paei":
        assert isinstance(item, ForcedChoiceItem)
        row = [
            (code, build_callback_data(session_id, item.id, code))
            for code in ("P", "A", "E", "I")
            if code in item.options
        ]
        return inline_keyboard([row])
    if definition.scoring_type in ("likert_sum", "likert_per_dimension"):
        return _likert_keyboard(definition, session_id, item.id)
    return None
