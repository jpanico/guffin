"""The W3CDTF reduced-precision date — structured model, parsing, and pattern — with no domain coupling.

Public symbols:

- :data:`W3CDTF_DATE_PATTERN` — regex pattern for a W3CDTF reduced-precision date
  (``YYYY``, ``YYYY-MM``, or ``YYYY-MM-DD``); :data:`W3CDTF_DATE_RE` — compiled
  :data:`W3CDTF_DATE_PATTERN`.
- **Enumerations**: :class:`DatePrecision` — the precision level a reduced-precision date is
  expressed at (year / month / day).
- **Models**: :class:`W3cdtfDate` — a W3CDTF reduced-precision date as structured data
  (year, optional month, optional day; precision derived from which parts are present),
  parsed from and serialized to the canonical W3CDTF string.
- :func:`verified_w3cdtf_date` — parse a string into a :class:`W3cdtfDate` after verifying
  it is a W3CDTF reduced-precision date, calendar validity included.
"""

import datetime
import enum
from typing import Final, Self

import regex
from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator, validate_call

W3CDTF_DATE_PATTERN: Final[str] = r"(?P<year>\d{4})(?:-(?P<month>\d{2})(?:-(?P<day>\d{2}))?)?"
"""Regex pattern for a W3CDTF reduced-precision date: ``YYYY``, ``YYYY-MM``, or ``YYYY-MM-DD``.

The date-only subset of the W3C profile of ISO 8601 (`W3C Date and Time Formats
<https://www.w3.org/TR/NOTE-datetime>`_): year first, most-significant-part outward.  Unanchored;
``fullmatch`` against it to test whether a string is *wholly* such a date.  Captures the shape
only — named groups ``year``/``month``/``day`` — with the calendar validity of the month and day
parts checked separately (see :class:`W3cdtfDate`).
"""

W3CDTF_DATE_RE: Final[regex.Pattern[str]] = regex.compile(W3CDTF_DATE_PATTERN)
"""Compiled :data:`W3CDTF_DATE_PATTERN`."""


class DatePrecision(enum.StrEnum):
    """The precision level a W3CDTF reduced-precision date is expressed at.

    Attributes:
        YEAR: Year only (``YYYY``).
        MONTH: Year and month (``YYYY-MM``).
        DAY: Full calendar day (``YYYY-MM-DD``).
    """

    YEAR = "year"
    MONTH = "month"
    DAY = "day"


class W3cdtfDate(BaseModel):
    """A W3CDTF reduced-precision date as structured data.

    The date-only subset of the W3C profile of ISO 8601 (`W3C Date and Time Formats
    <https://www.w3.org/TR/NOTE-datetime>`_): a year, optionally narrowed by a month,
    optionally narrowed further by a day.  The precision is not stored — it is derived from
    which parts are present (:attr:`precision`), so it can never disagree with the data.

    Parses directly from the canonical W3CDTF string at every Pydantic boundary (a plain
    ``"1298-07"`` validates into the model) and serializes back to that string;
    :func:`str` renders it.

    Attributes:
        year: The four-digit year.
        month: The month (1-12), or ``None`` for a year-precision date.
        day: The day of month, or ``None`` for a year- or month-precision date; always a
            real calendar day for its year and month.
    """

    model_config = ConfigDict(frozen=True)

    year: int = Field(..., ge=1, le=9999)
    month: int | None = Field(default=None, ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=31)

    @model_validator(mode="before")
    @classmethod
    def _parsed_text(cls, data: object) -> object:
        """Parse a W3CDTF string into the model's parts; pass any other input through."""
        if not isinstance(data, str):
            return data
        date_match = W3CDTF_DATE_RE.fullmatch(data)
        if date_match is None:
            raise ValueError(f"date {data!r} is not a W3CDTF date (YYYY, YYYY-MM, or YYYY-MM-DD)")
        month_text = date_match.group("month")
        day_text = date_match.group("day")
        return {
            "year": int(date_match.group("year")),
            "month": int(month_text) if month_text is not None else None,
            "day": int(day_text) if day_text is not None else None,
        }

    @model_validator(mode="after")
    def _parts_must_nest_and_be_calendar_valid(self) -> Self:
        """Reject a day without a month, and a day that is not a real calendar day."""
        if self.day is not None and self.month is None:
            raise ValueError("a W3CDTF date with a day must also carry a month")
        if self.month is not None and self.day is not None:
            try:
                datetime.date(self.year, self.month, self.day)
            except ValueError as exc:
                raise ValueError(f"date {self} is not a valid calendar date: {exc}") from exc
        return self

    @model_serializer
    def _canonical_text(self) -> str:
        """Serialize as the canonical W3CDTF string."""
        return str(self)

    @property
    def precision(self) -> DatePrecision:
        """The precision the date is expressed at, derived from which parts are present."""
        if self.day is not None:
            return DatePrecision.DAY
        if self.month is not None:
            return DatePrecision.MONTH
        return DatePrecision.YEAR

    def __str__(self) -> str:
        """Render the canonical W3CDTF string: ``YYYY``, ``YYYY-MM``, or ``YYYY-MM-DD``."""
        if self.day is not None:
            return f"{self.year:04d}-{self.month:02d}-{self.day:02d}"
        if self.month is not None:
            return f"{self.year:04d}-{self.month:02d}"
        return f"{self.year:04d}"


@validate_call
def verified_w3cdtf_date(date_text: str) -> W3cdtfDate:
    """Parse *date_text* into a :class:`W3cdtfDate` after verifying it is a W3CDTF date.

    The imperative boundary for untyped text: the string must be wholly ``YYYY``,
    ``YYYY-MM``, or ``YYYY-MM-DD`` (year first), with a real calendar month and day when
    present — ``1298-13`` and ``1298-02-30`` are rejected, not just shape mismatches.

    Args:
        date_text: The candidate date string.

    Returns:
        The parsed :class:`W3cdtfDate`.

    Raises:
        ValueError: If *date_text* is not a W3CDTF reduced-precision date (wrong shape, month
            outside 1-12, or a day invalid for its month).
    """
    return W3cdtfDate.model_validate(date_text)
