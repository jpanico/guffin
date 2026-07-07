"""Date-formatting helpers with no domain coupling.

Public symbols:

- :data:`ENGLISH_MONTHS` — the twelve English month names in calendar order.
- :data:`ENGLISH_MONTH_ABBREVIATIONS` — the twelve English month abbreviations in calendar order.
- :func:`ordinal_suffix` — the English ordinal suffix (``st``/``nd``/``rd``/``th``) for an
  integer such as a day-of-month.
"""

from typing import Final

from pydantic import validate_call

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
