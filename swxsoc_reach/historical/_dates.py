"""Shared helpers for the historical orchestrators."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable


def iter_dates(start: date, end: date) -> Iterable[date]:
    """Yield each UTC date in ``[start, end]`` inclusive.

    Raises
    ------
    ValueError
        If ``end`` is before ``start``.
    """
    if end < start:
        raise ValueError(
            f"end_date {end.isoformat()} must be >= start_date {start.isoformat()}"
        )
    current = start
    while current <= end:
        yield current
        current = current + timedelta(days=1)
