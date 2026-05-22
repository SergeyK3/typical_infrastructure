"""Tests for Russian filename transliteration."""

from psychological_testing.integration.filename_translit import ascii_slug_from_name, transliterate_ru


def test_transliterate_ru_full_name() -> None:
    assert transliterate_ru("Ким Сергей Васильевич") == "Kim Sergey Vasilevich"


def test_ascii_slug_from_name() -> None:
    assert ascii_slug_from_name("Ким Сергей Васильевич") == "Kim_Sergey_Vasilevich"
    assert ascii_slug_from_name("ТОО Второе") == "TOO_Vtoroe"
    assert ascii_slug_from_name("ТОО_Бета") == "TOO_Beta"
