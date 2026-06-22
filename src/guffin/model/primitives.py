"""Foundational UID primitives for the Guffin normalized-graph model.

Public symbols:

- :data:`UID_PATTERN` — unanchored regex string for a nine-character Roam node UID.
- :data:`UID_RE` — compiled unanchored :data:`UID_PATTERN`.
- :data:`ANCHORED_UID_PATTERN` — :data:`UID_PATTERN` anchored at both ends.
- :data:`ANCHORED_UID_RE` — compiled :data:`ANCHORED_UID_PATTERN`.
- :data:`Uid` — nine-character alphanumeric stable block/page identifier type alias.
"""

from typing import Annotated, Final

import regex
from pydantic import Field

UID_PATTERN: Final[str] = r"[A-Za-z0-9_-]{9}"
"""Canonical (unanchored) regex for a Roam node UID: nine alphanumeric/dash/underscore characters.

Left unanchored so it can be embedded within a larger pattern.  To test whether
a string is *wholly* a UID, use :data:`ANCHORED_UID_PATTERN` / :data:`ANCHORED_UID_RE`.
"""

UID_RE: Final[regex.Pattern[str]] = regex.compile(UID_PATTERN)
"""Compiled (unanchored) :data:`UID_PATTERN`; use to find a UID embedded in a larger string."""

ANCHORED_UID_PATTERN: Final[str] = rf"^{UID_PATTERN}$"
""":data:`UID_PATTERN` anchored at both ends, matching a string that is exactly a UID."""

ANCHORED_UID_RE: Final[regex.Pattern[str]] = regex.compile(ANCHORED_UID_PATTERN)
"""Compiled :data:`ANCHORED_UID_PATTERN` for matching a string that is exactly a Roam node UID."""

type Uid = Annotated[str, Field(pattern=ANCHORED_UID_PATTERN)]
"""Nine-character alphanumeric stable block/page identifier (:block/uid)."""
