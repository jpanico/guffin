"""Canonical callout colour palette — the single source of truth for callout colours across formats.

A callout type's colour is declared once here as an *accent* per
:class:`~guffin.roam.blockquote.CalloutType`.  Every output format derives its whole callout chrome
from that single accent, so a given type looks the same everywhere: the PDF passes the accent to
gentle-clues (which lightens it for the title band and box border), and the EPUB generates CSS that
uses the accent for the left bar and the same :func:`lighten` for the title band.  ``note`` is a
neutral grey (a note is not an alarm); red is reserved for ``danger``/``failure``/``bug``.

Public symbols:

- **Constants**: :data:`CALLOUT_ACCENT` — the canonical ``CalloutType`` → accent hex-colour map
  (covers every member); :data:`TITLE_TINT_LIGHTEN` — the fraction the title-band tint lightens the
  accent (matches gentle-clues).
- **Functions**: :func:`lighten` — blend a ``#rrggbb`` colour toward white by a fraction;
  :func:`callout_accent` — the accent colour for a callout type; :func:`callout_title_tint` — the
  derived title-band tint for a callout type.
"""

from typing import Final

from pydantic import validate_call

from guffin.roam.blockquote import CalloutType

CALLOUT_ACCENT: Final[dict[CalloutType, str]] = {
    CalloutType.INFO: "#4a90d9",
    CalloutType.NOTE: "#888888",
    CalloutType.EXAMPLE: "#7e57c2",
    CalloutType.SUMMARY: "#00acc1",
    CalloutType.QUESTION: "#f9a825",
    CalloutType.TIP: "#4caf50",
    CalloutType.SUCCESS: "#2e7d32",
    CalloutType.WARNING: "#e07b00",
    CalloutType.DANGER: "#e53935",
    CalloutType.FAILURE: "#c62828",
    CalloutType.BUG: "#d81b60",
}
"""Canonical accent colour (``#rrggbb``) per callout type; covers every ``CalloutType`` member."""

TITLE_TINT_LIGHTEN: Final[float] = 0.85
"""Fraction the title-band tint lightens the accent — matches gentle-clues' ``accent.lighten(85%)``."""


def _mix_to_white(channel: int, amount: float) -> int:
    """Return *channel* (0–255) blended toward white (255) by *amount* (0–1)."""
    return round(channel + (255 - channel) * amount)


@validate_call
def lighten(hex_color: str, amount: float) -> str:
    """Return *hex_color* (``#rrggbb``) blended toward white by *amount* (0–1), as ``#rrggbb``.

    Mirrors Typst's ``color.lighten(<amount>%)`` so the PDF and the EPUB derive matching tints from
    one accent colour.

    Args:
        hex_color: A ``#rrggbb`` colour string.
        amount: Blend fraction toward white, ``0.0`` (unchanged) to ``1.0`` (white).

    Returns:
        The lightened colour as a lowercase ``#rrggbb`` string.
    """
    channels: Final[str] = hex_color.lstrip("#")
    red: Final[int] = _mix_to_white(int(channels[0:2], 16), amount)
    green: Final[int] = _mix_to_white(int(channels[2:4], 16), amount)
    blue: Final[int] = _mix_to_white(int(channels[4:6], 16), amount)
    return f"#{red:02x}{green:02x}{blue:02x}"


@validate_call
def callout_accent(callout_type: CalloutType) -> str:
    """Return the canonical accent colour (``#rrggbb``) for *callout_type*."""
    return CALLOUT_ACCENT[callout_type]


@validate_call
def callout_title_tint(callout_type: CalloutType) -> str:
    """Return the title-band tint (``#rrggbb``) for *callout_type*.

    The tint is the type's accent lightened by :data:`TITLE_TINT_LIGHTEN`.
    """
    return lighten(CALLOUT_ACCENT[callout_type], TITLE_TINT_LIGHTEN)
