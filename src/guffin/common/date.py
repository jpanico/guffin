"""Date helpers — formatting constants, date-string validation, and the W3CDTF date type — with no domain coupling.

Public symbols:

- :data:`W3CDTF_DATE_PATTERN` — regex pattern for a W3CDTF reduced-precision date
  (``YYYY``, ``YYYY-MM``, or ``YYYY-MM-DD``); :data:`W3CDTF_DATE_RE` — compiled
  :data:`W3CDTF_DATE_PATTERN`.
- :data:`W3cdtfDate` — a validated W3CDTF reduced-precision date string; Pydantic enforces
  shape and calendar validity wherever the annotation appears.
- :data:`ENGLISH_MONTHS` — the twelve English month names in calendar order.
- :data:`ENGLISH_MONTH_ABBREVIATIONS` — the twelve English month abbreviations in calendar order.
- :func:`ordinal_suffix` — the English ordinal suffix (``st``/``nd``/``rd``/``th``) for an
  integer such as a day-of-month.
- :func:`verified_w3cdtf_date` — return a string after verifying it is a W3CDTF
  reduced-precision date, calendar validity included.
"""

import datetime
from typing import Annotated, Final

import regex
from pydantic import AfterValidator, validate_call

W3CDTF_DATE_PATTERN: Final[str] = r"(?P<year>\d{4})(?:-(?P<month>\d{2})(?:-(?P<day>\d{2}))?)?"
"""Regex pattern for a W3CDTF reduced-precision date: ``YYYY``, ``YYYY-MM``, or ``YYYY-MM-DD``.

The date-only subset of the W3C profile of ISO 8601 (`W3C Date and Time Formats
<https://www.w3.org/TR/NOTE-datetime>`_): year first, most-significant-part outward.  Unanchored;
``fullmatch`` against it to test whether a string is *wholly* such a date.  Captures the shape
only — named groups ``year``/``month``/``day`` — with the calendar validity of the month and day
parts checked separately (see :func:`verified_w3cdtf_date`).
"""

W3CDTF_DATE_RE: Final[regex.Pattern[str]] = regex.compile(W3CDTF_DATE_PATTERN)
"""Compiled :data:`W3CDTF_DATE_PATTERN`."""

ENGLISH_MONTHS: Final[tuple[str, ...]] = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
"""The twelve English month names in calendar order; ``ENGLISH_MONTHS[month - 1]`` names month *month* (1-12).

A fixed constant rather than :data:`calendar.month_name`, which is locale-dependent (it would yield
localized names under a non-English ``LC_TIME``).
"""

ENGLISH_MONTH_ABBREVIATIONS: Final[tuple[str, ...]] = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
"""The twelve three-letter English month abbreviations in calendar order.

``ENGLISH_MONTH_ABBREVIATIONS[month - 1]`` abbreviates month *month* (1-12).  A fixed constant
rather than :data:`calendar.month_abbr`, which is locale-dependent (it would yield localized
abbreviations under a non-English ``LC_TIME``).
"""


@validate_call
def ordinal_suffix(number: int) -> str:
    """Return the English ordinal suffix (``st``/``nd``/``rd``/``th``) for *number*.

    Handles the 11-13 exception (``11th``, ``12th``, ``13th``), which overrides the usual
    last-digit rule (``21st``, ``22nd``, ``23rd``).

    Args:
        number: The number to suffix — e.g. a day-of-month.

    Returns:
        One of ``"st"``, ``"nd"``, ``"rd"``, or ``"th"``.
    """
    if 11 <= number % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")


def _checked_w3cdtf_date(date_text: str) -> str:
    """Return *date_text* after checking it is a W3CDTF reduced-precision date.

    The string must be wholly ``YYYY``, ``YYYY-MM``, or ``YYYY-MM-DD`` (year first), with a real
    calendar month and day when present — ``1298-13`` and ``1298-02-30`` are rejected, not just
    shape mismatches.

    Args:
        date_text: The candidate date string.

    Returns:
        *date_text*, unchanged.

    Raises:
        ValueError: If *date_text* is not a W3CDTF reduced-precision date (wrong shape, month
            outside 1–12, or a day invalid for its month).
    """
    date_match: Final[regex.Match[str] | None] = W3CDTF_DATE_RE.fullmatch(date_text)
    if date_match is None:
        raise ValueError(f"date {date_text!r} is not a W3CDTF date (YYYY, YYYY-MM, or YYYY-MM-DD)")
    month: Final[str | None] = date_match.group("month")
    day: Final[str | None] = date_match.group("day")
    if month is None:
        return date_text
    if not 1 <= int(month) <= 12:
        raise ValueError(f"date {date_text!r} has month {month} outside 1-12")
    if day is None:
        return date_text
    try:
        datetime.date(int(date_match.group("year")), int(month), int(day))
    except ValueError as exc:
        raise ValueError(f"date {date_text!r} is not a valid calendar date: {exc}") from exc
    return date_text


type W3cdtfDate = Annotated[str, AfterValidator(_checked_w3cdtf_date)]
"""A validated W3CDTF reduced-precision date string: ``YYYY``, ``YYYY-MM``, or ``YYYY-MM-DD``.

The annotation carries the full check — shape *and* calendar validity — so Pydantic enforces it
wherever the type appears (model fields, ``@validate_call`` parameters): a value typed
``W3cdtfDate`` is a valid W3CDTF reduced-precision date, not merely a string that claims to be
one.  To validate imperatively, use :func:`verified_w3cdtf_date`.
"""


@validate_call
def verified_w3cdtf_date(date_text: str) -> W3cdtfDate:
    """Return *date_text* after verifying it is a W3CDTF reduced-precision date.

    The imperative form of :data:`W3cdtfDate`: applies the same check the annotation carries —
    wholly ``YYYY``, ``YYYY-MM``, or ``YYYY-MM-DD`` (year first), with a real calendar month and
    day when present — ``1298-13`` and ``1298-02-30`` are rejected, not just shape mismatches.

    Args:
        date_text: The candidate date string.

    Returns:
        *date_text*, unchanged, established as a :data:`W3cdtfDate`.

    Raises:
        ValueError: If *date_text* is not a W3CDTF reduced-precision date (wrong shape, month
            outside 1–12, or a day invalid for its month).
    """
    return _checked_w3cdtf_date(date_text)
