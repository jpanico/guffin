"""Roam TODO-item construct: the checkbox marker leading a TODO block and the state it encodes.

Public symbols:

- **Pattern constants**: :data:`TODO_MARKER_PATTERN` / :data:`TODO_MARKER_RE` — regex matching the
  page-reference TODO marker (``{{[[TODO]]}}`` / ``{{[[DONE]]}}``), capturing the state keyword in
  the ``state`` named group.
- **Enums**: :class:`TodoState` — the two states of a Roam TODO item, named by the marker keyword
  that encodes each.
- **Functions**: :func:`todo_state` — the state of the TODO marker leading a block string, else
  ``None``.
"""

import enum
from typing import Final

import regex
from pydantic import validate_call


class TodoState(enum.StrEnum):
    """State of a Roam TODO item, named by the marker keyword that encodes it.

    Each member's value is the keyword inside the page-reference marker ``{{[[<KEYWORD>]]}}``
    leading the item's block string, so a keyword captured from the marker resolves to its state
    by plain value lookup.

    - **TODO**: the item is open (unchecked).
    - **DONE**: the item is completed (checked).
    """

    TODO = "TODO"
    DONE = "DONE"


TODO_MARKER_PATTERN: Final[str] = r"\{\{\[\[(?P<state>" + "|".join(state.value for state in TodoState) + r")\]\]\}\}"
"""Regex pattern matching the marker leading the block string of a Roam TODO item.

Only the page-reference spelling exists: a bare ``{{TODO}}``/``{{DONE}}`` component is not
handled properly by the Roam UI.  The keyword alternation is derived from :class:`TodoState`,
and the ``state`` named group captures the keyword naming the item's state.
"""

TODO_MARKER_RE: Final[regex.Pattern[str]] = regex.compile(TODO_MARKER_PATTERN)
"""Compiled form of :data:`TODO_MARKER_PATTERN`."""


@validate_call
def todo_state(string: str) -> TodoState | None:
    """Return the state of the TODO marker leading *string*, or ``None`` when none leads it.

    The marker must lead the string (after stripping surrounding whitespace); a marker appearing
    later amid the text does not make the string a TODO item.

    Args:
        string: A raw block string that may lead with a Roam TODO marker.

    Returns:
        The :class:`TodoState` named by the leading marker's keyword, or ``None`` when *string*
        leads with no TODO marker.
    """
    matched: Final[regex.Match[str] | None] = TODO_MARKER_RE.match(string.strip())
    return TodoState(matched.group("state")) if matched else None
