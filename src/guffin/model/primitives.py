"""Foundational UID primitives for the Guffin normalized-graph model.

Public symbols:

- :data:`SYNTHETIC_UID_PATTERN` — unanchored regex for a synthetic nine-character node UID.
- :data:`DAILY_NOTE_UID_PATTERN` — unanchored regex for a ``MM-DD-YYYY`` daily-note-page UID.
- :data:`UID_PATTERN` — unanchored regex matching *any* node UID (synthetic or daily-note).
- :data:`UID_RE` — compiled unanchored :data:`UID_PATTERN`.
- :data:`ANCHORED_UID_PATTERN` — :data:`UID_PATTERN` anchored at both ends.
- :data:`ANCHORED_UID_RE` — compiled :data:`ANCHORED_UID_PATTERN`.
- :data:`Uid` — stable block/page identifier type alias.
"""

from typing import Annotated, Final

import regex
from pydantic import Field

SYNTHETIC_UID_PATTERN: Final[str] = r"[A-Za-z0-9_-]{9}"
"""Regex for a synthetic node UID: nine alphanumeric/dash/underscore characters (the common case).

Left unanchored so it can be embedded within a larger pattern — e.g. a ``((<uid>))`` block reference,
which only ever contains synthetic UIDs (daily-note pages are referenced by title, not by UID).
"""

DAILY_NOTE_UID_PATTERN: Final[str] = r"[0-9]{2}-[0-9]{2}-[0-9]{4}"
"""Regex for a Daily Note Page UID: ``MM-DD-YYYY`` (e.g. ``08-24-2026``).

A daily-note page — the page a source graph keeps per calendar day — has the date itself as its
UID, unlike the synthetic UIDs of every other node.
"""

UID_PATTERN: Final[str] = rf"(?:{DAILY_NOTE_UID_PATTERN}|{SYNTHETIC_UID_PATTERN})"
"""Unanchored regex for *any* node UID — a :data:`DAILY_NOTE_UID_PATTERN` or :data:`SYNTHETIC_UID_PATTERN`.

The date alternative is listed first so that, matched unanchored, a full ``MM-DD-YYYY`` UID is not
truncated to its first nine characters by the synthetic branch.  To test whether a string is *wholly*
a UID, use :data:`ANCHORED_UID_PATTERN` / :data:`ANCHORED_UID_RE`.
"""

UID_RE: Final[regex.Pattern[str]] = regex.compile(UID_PATTERN)
"""Compiled (unanchored) :data:`UID_PATTERN`; use to find a UID embedded in a larger string."""

ANCHORED_UID_PATTERN: Final[str] = rf"^{UID_PATTERN}$"
""":data:`UID_PATTERN` anchored at both ends, matching a string that is exactly a UID."""

ANCHORED_UID_RE: Final[regex.Pattern[str]] = regex.compile(ANCHORED_UID_PATTERN)
"""Compiled :data:`ANCHORED_UID_PATTERN` for matching a string that is exactly a node UID."""

type Uid = Annotated[str, Field(pattern=ANCHORED_UID_PATTERN)]
"""Stable block/page identifier.

Either a synthetic nine-character UID (:data:`SYNTHETIC_UID_PATTERN`) or a ``MM-DD-YYYY`` Daily Note
Page UID (:data:`DAILY_NOTE_UID_PATTERN`).
"""
