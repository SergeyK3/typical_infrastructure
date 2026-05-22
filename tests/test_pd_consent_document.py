"""Нормализация URL согласия ПДн (/edit → /view)."""

from skill_assessment.services.pd_consent_document import _normalize_consent_url


def test_edit_url_becomes_view():
    url = "https://docs.google.com/document/d/abc123/edit?usp=sharing"
    assert "/view" in _normalize_consent_url(url)
    assert "/edit" not in _normalize_consent_url(url)


def test_view_url_unchanged():
    url = "https://docs.google.com/document/d/abc123/view?usp=sharing"
    assert _normalize_consent_url(url) == url
