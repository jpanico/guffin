"""Date and time text helpers — formatting vocabulary and formatters — with no domain coupling.

Public symbols:

- :class:`EnglishMonth` — the twelve English calendar months, valued by 1-based month number,
  each carrying its full name and three-letter abbreviation.
- :func:`ordinal_suffix` — the English ordinal suffix (``st``/``nd``/``rd``/``th``) for an
  integer such as a day-of-month.
- :func:`utc_timestamp` — format a datetime as a compact minute-precision UTC timestamp
  with an explicit ``Z`` suffix.
"""

import datetime
import enum

from pydantic import validate_call


class EnglishMonth(enum.IntEnum):
    """An English calendar month, valued by its 1-based month number (1-12).

    ``EnglishMonth(month)`` resolves a :attr:`datetime.date.month` number to its month, rejecting
    anything outside 1-12 with a ``ValueError``.  Each member's English spellings are derived from
    the member name — :attr:`full_name` (``January``) and its three-letter :attr:`abbreviation`
    (``Jan``), which in English is always the name's first three letters.

    A fixed vocabulary rather than :data:`calendar.month_name`/:data:`calendar.month_abbr`, which
    are locale-dependent (they would yield localized spellings under a non-English ``LC_TIME``).
    """

    JANUARY = 1
    FEBRUARY = 2
    MARCH = 3
    APRIL = 4
    MAY = 5
    JUNE = 6
    JULY = 7
    AUGUST = 8
    SEPTEMBER = 9
    OCTOBER = 10
    NOVEMBER = 11
    DECEMBER = 12

    @property
    def full_name(self) -> str:
        """The month's English name, e.g. ``January``."""
        return self.name.title()

    @property
    def abbreviation(self) -> str:
        """The month's three-letter English abbreviation, e.g. ``Jan``."""
        return self.full_name[:3]


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


@validate_call
def utc_timestamp(moment: datetime.datetime) -> str:
    """Return *moment* as a compact minute-precision UTC timestamp with an explicit ``Z`` suffix.

    Normalizes to UTC before formatting, so timestamps captured from different clocks (system
    time, git commit offsets, source-system epochs) render in one zone and read unambiguously —
    e.g. ``2026-07-12T01:12Z``.  A naive *moment* is interpreted as local time.

    Args:
        moment: The instant to format.

    Returns:
        The ``YYYY-MM-DDTHH:MMZ`` UTC rendering of *moment*.
    """
    return moment.astimezone(datetime.UTC).strftime("%Y-%m-%dT%H:%MZ")
