"""How a calendar date renders as text.

Public symbols:

- :class:`DateFormat` — the selectable string formats for a :class:`datetime.date`.
- :func:`format_date` — render a :class:`datetime.date` per a :class:`DateFormat`.
"""

import datetime
import enum
from typing import assert_never

from pydantic import validate_call

from guffin.common.date import ENGLISH_MONTH_ABBREVIATIONS
from guffin.roam.primitives import daily_note_title


class DateFormat(enum.StrEnum):
    """How a :class:`datetime.date` renders as a string.

    Attributes:
        ROAM_LONG: Roam's verbose long-form date, e.g. ``January 1st, 2026`` — an English month
            name, an ordinal day, and the year; the style Roam uses for its daily-note page titles.
        ISO: ISO 8601, e.g. ``2026-01-01``.
        ABBREV_MONTH_DAY: An abbreviated English month name followed by the day of the month, with
            no year, e.g. ``Jan 1``.
    """

    ROAM_LONG = "roam-long"
    ISO = "iso"
    ABBREV_MONTH_DAY = "abbrev-month-day"


@validate_call
def format_date(value: datetime.date, date_format: DateFormat) -> str:
    """Return *value* rendered as *date_format*.

    Args:
        value: The calendar date to render.
        date_format: The chosen output format.

    Returns:
        The formatted date string, e.g. ``January 1st, 2026`` (ROAM_LONG), ``2026-01-01`` (ISO),
        or ``Jan 1`` (ABBREV_MONTH_DAY).
    """
    match date_format:
        case DateFormat.ROAM_LONG:
            return daily_note_title(value)
        case DateFormat.ISO:
            return value.isoformat()
        case DateFormat.ABBREV_MONTH_DAY:
            return f"{ENGLISH_MONTH_ABBREVIATIONS[value.month - 1]} {value.day}"
        case _ as unreachable:
            assert_never(unreachable)
