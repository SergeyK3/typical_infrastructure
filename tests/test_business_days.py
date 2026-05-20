"""Business-day helpers."""

from __future__ import annotations

from datetime import date

from app.business_days import add_business_days, default_assignment_due_at


def test_add_business_days_skips_weekend():
    # Monday 2026-05-18 + 3 business days -> Thursday 2026-05-21
    assert add_business_days(date(2026, 5, 18), 3) == date(2026, 5, 21)


def test_default_assignment_due_at_end_of_day():
    due = default_assignment_due_at(from_date=date(2026, 5, 18), business_days=3)
    assert due.hour == 23 and due.minute == 59
    assert due.date() == date(2026, 5, 21)
