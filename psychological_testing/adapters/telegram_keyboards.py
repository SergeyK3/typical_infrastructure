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
MENU_CALLBACK_PREFIX = f"{CALLBACK_PREFIX}:menu:"


def build_menu_callback_data(action: str) -> str:
    """``pt:menu:{action}`` — главное меню (legacy test id, cancel, help)."""
    data = f"{MENU_CALLBACK_PREFIX}{action}"
    if len(data.encode("utf-8")) > 64:
        raise ValueError(f"callback_data too long: {data!r}")
    return data


def build_step_menu_callback_data(step_key: str, *, dialog: bool = False) -> str:
    """``pt:menu:step:{step_key}`` или ``...:dialog`` для MBTI-диалога."""
    action = f"step:{step_key}:dialog" if dialog else f"step:{step_key}"
    return build_menu_callback_data(action)


def parse_menu_callback(data: str) -> str | None:
    if not data.startswith(MENU_CALLBACK_PREFIX):
        return None
    action = data[len(MENU_CALLBACK_PREFIX) :].strip()
    return action or None


def parse_menu_step_action(action: str) -> tuple[str, bool] | None:
    """``step:{step_key}`` или ``step:{step_key}:dialog`` → (step_key, is_dialog)."""
    if not action.startswith("step:"):
        return None
    rest = action[5:]
    if rest.endswith(":dialog"):
        return rest[: -len(":dialog")], True
    return rest, False


def welcome_menu_keyboard(
    *,
    allowed_steps: list[dict[str, str]] | None = None,
    allowed_test_ids: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Кнопки главного меню.

    ``allowed_steps`` — режим HR-назначения (по step_key, подпись label_ru).
    ``allowed_test_ids=None`` без ``allowed_steps`` — все тесты (свободный режим).
    При одном назначенном тесте — одна кнопка «Пройти» (без «Справка» и без отмены).
    """
    rows: list[list[tuple[str, str]]] = []
    single_assignment = (
        allowed_steps is None
        and allowed_test_ids is not None
        and len(allowed_test_ids) == 1
    )

    if allowed_steps is not None:
        pair_row: list[tuple[str, str]] = []
        single_step = len(allowed_steps) == 1
        for step in allowed_steps:
            step_key = str(step["step_key"])
            test_id = str(step["test_id"])
            start_label = "Пройти" if single_step else str(step.get("label_ru") or test_id)
            if test_id == "mbti":
                rows.append(
                    [
                        (start_label, build_step_menu_callback_data(step_key)),
                        (
                            "Диалог с Akma",
                            build_step_menu_callback_data(step_key, dialog=True),
                        ),
                    ]
                )
                continue
            pair_row.append((start_label, build_step_menu_callback_data(step_key)))
            if len(pair_row) == 2:
                rows.append(pair_row)
                pair_row = []
        if pair_row:
            rows.append(pair_row)
    elif single_assignment:
        test_id = next(iter(allowed_test_ids))  # type: ignore[arg-type]
        if test_id == "mbti":
            rows.append([("Пройти", build_menu_callback_data("mbti"))])
        else:
            rows.append([("Пройти", build_menu_callback_data(test_id))])
    else:
        allowed = allowed_test_ids

        def _show(test_id: str) -> bool:
            return allowed is None or test_id in allowed

        test_rows: list[list[tuple[str, str]]] = []
        if _show("mbti"):
            test_rows.append(
                [
                    ("MBTI", build_menu_callback_data("mbti")),
                    ("MBTI, диалог с Акma", build_menu_callback_data("mbti_dialog")),
                ]
            )
        pair_row = []
        for test_id, label in (
            ("paei", "PAEI"),
            ("soft_skills", "Soft Skills"),
            ("disc", "DISC"),
            ("hexaco", "HEXACO"),
        ):
            if not _show(test_id):
                continue
            pair_row.append((label, build_menu_callback_data(test_id)))
            if len(pair_row) == 2:
                test_rows.append(pair_row)
                pair_row = []
        if pair_row:
            test_rows.append(pair_row)
        rows.extend(test_rows)

    return inline_keyboard(rows)


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
    row = [
        (str(n), build_callback_data(session_id, item_id, str(n)))
        for n in range(min_v, max_v + 1)
    ]
    return inline_keyboard([row])


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
