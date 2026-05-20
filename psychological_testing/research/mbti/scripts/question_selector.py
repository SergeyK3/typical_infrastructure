"""Question selection — re-exports production ``shared_engine.question_selector``."""

from psychological_testing.shared_engine.question_selector import (
    SelectableItem,
    SelectableItem as MbtiItem,
    item_from_dict,
    item_from_dict as _item_from_dict,
    select_from_definition,
    select_questions,
)

__all__ = [
    "MbtiItem",
    "SelectableItem",
    "item_from_dict",
    "select_from_definition",
    "select_questions",
]
