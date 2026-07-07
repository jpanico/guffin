"""How a calendar date renders as text.

Public symbols:

- :class:`DateFormat` — the selectable string formats for a :class:`datetime.date`.
- :func:`format_date` — render a :class:`datetime.date` per a :class:`DateFormat`.
"""

import datetime
import enum
from typing import assert_never

from pydantic import validate_call

from guffin.roam.primitives import daily_note_title


class DateFormat(enum.StrEnum):
    """How a :class:`datetime.date` renders as a string.

    Attributes:
        ROAM_LONG: Roam's verbose long-form date, e.g. ``January 1st, 2026`` — an English month
            name, an ordinal day, and the year; the style Roam uses for its daily-note page titles.
        ISO: ISO 8601, e.g. ``2026-01-01``.
    """

    ROAM_LONG = "roam-long"
    ISO = "iso"


@validate_call
def format_date(value: datetime.date, date_format: DateFormat) -> str:
    """Return *value* rendered as *date_format*.

    Args:
        value: The calendar date to render.
        date_format: The chosen output format.

    Returns:
        The formatted date string, e.g. ``January 1st, 2026`` (ROAM_LONG) or ``2026-01-01`` (ISO).
    """
    match date_format:
        case DateFormat.ROAM_LONG:
            return daily_note_title(value)
        case DateFormat.ISO:
            return value.isoformat()
        case _ as unreachable:
            assert_never(unreachable)
