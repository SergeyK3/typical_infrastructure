"""Business-day calendar helpers (Mon–Fri)."""

from __future__ import annotations

from datetime import date, datetime, timedelta


def add_business_days(start: date, days: int) -> date:
    """Add ``days`` business days (weekends skipped). ``days`` must be >= 0."""
    if days < 0:
        raise ValueError("days_must_be_non_negative")
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def default_assignment_due_at(*, from_date: date | None = None, business_days: int = 3) -> datetime:
    """End of day (23:59:59) after ``business_days`` business days from ``from_date``."""
    base = from_date or date.today()
    due_date = add_business_days(base, business_days)
    return datetime(due_date.year, due_date.month, due_date.day, 23, 59, 59)
