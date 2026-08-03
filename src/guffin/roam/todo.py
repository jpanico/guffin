"""Roam TODO-item construct: the checkbox marker opening a TODO block and the state it encodes.

Public symbols:

- **Pattern constants**: :data:`TODO_MARKER_PATTERN` / :data:`TODO_MARKER_RE` — regex matching the
  page-reference TODO marker (``{{[[TODO]]}}`` / ``{{[[DONE]]}}``), capturing the state keyword in
  the ``state`` named group; :data:`LEADING_MARKUP_PATTERN` — the formatting markup that may
  precede the marker without unseating it; :data:`TODO_ITEM_PATTERN` / :data:`TODO_ITEM_RE` —
  regex matching a whole TODO item's opening (optional leading markup, then the marker in the
  ``marker`` named group).
- **Enums**: :class:`TodoState` — the two states of a Roam TODO item, named by the marker keyword
  that encodes each.
- **Models**: :class:`RoamTodo` — a TODO item's block string decomposed into its state and its
  marker-free text.
- **Functions**: :func:`parse_todo` — decompose a TODO item block string into a
  :class:`RoamTodo`, else ``None``; :func:`todo_state` — the state of a TODO item block string,
  else ``None``.
"""

import enum
from typing import Final

import regex
from pydantic import BaseModel, ConfigDict, Field, validate_call

from guffin.roam.markdown import COLOR_TAG_PATTERN, INLINE_STYLE_DELIMITER_PATTERN


class TodoState(enum.StrEnum):
    """State of a Roam TODO item, named by the marker keyword that encodes it.

    Each member's value is the keyword inside the page-reference marker ``{{[[<KEYWORD>]]}}``
    opening the item's block string, so a keyword captured from the marker resolves to its state
    by plain value lookup.

    - **TODO**: the item is open (unchecked).
    - **DONE**: the item is completed (checked).
    """

    TODO = "TODO"
    DONE = "DONE"


TODO_MARKER_PATTERN: Final[str] = r"\{\{\[\[(?P<state>" + "|".join(state.value for state in TodoState) + r")\]\]\}\}"
"""Regex pattern matching the checkbox marker of a Roam TODO item.

Only the page-reference spelling exists: a bare ``{{TODO}}``/``{{DONE}}`` component is not
handled properly by the Roam UI.  The keyword alternation is derived from :class:`TodoState`,
and the ``state`` named group captures the keyword naming the item's state.
"""

TODO_MARKER_RE: Final[regex.Pattern[str]] = regex.compile(TODO_MARKER_PATTERN)
"""Compiled form of :data:`TODO_MARKER_PATTERN`."""

LEADING_MARKUP_PATTERN: Final[str] = rf"(?:\s+|{COLOR_TAG_PATTERN}\s+|{INLINE_STYLE_DELIMITER_PATTERN})*"
"""Regex pattern matching the formatting markup that may precede a TODO marker without unseating it.

Roam renders the marker as a checkbox even when formatting wraps it, so recognition sees
through whitespace, Color Highlighter tags
(:data:`~guffin.roam.markdown.COLOR_TAG_PATTERN`), and the inline-styling delimiters
(:data:`~guffin.roam.markdown.INLINE_STYLE_DELIMITER_PATTERN`) — any run of them, in any
order.  Ordinary text ahead of the marker still disqualifies it: the marker must be the block's
first *content*.
"""

TODO_ITEM_PATTERN: Final[str] = rf"{LEADING_MARKUP_PATTERN}(?P<marker>{TODO_MARKER_PATTERN})[ \t]*"
"""Regex pattern matching the opening of a Roam TODO item's block string.

Optional leading formatting markup (:data:`LEADING_MARKUP_PATTERN`), then the checkbox marker —
captured whole in the ``marker`` named group, its keyword in ``state`` — and any spacing that
follows it.
"""

TODO_ITEM_RE: Final[regex.Pattern[str]] = regex.compile(TODO_ITEM_PATTERN)
"""Compiled form of :data:`TODO_ITEM_PATTERN`."""


class RoamTodo(BaseModel):
    """A Roam TODO item's block string decomposed into its state and its marker-free text.

    Attributes:
        state: The item's state, named by the marker's keyword.
        text: The block string with the marker (and its trailing spacing) excised, so any
            formatting markup that wrapped the marker still wraps the remaining text.
    """

    model_config = ConfigDict(frozen=True)

    state: TodoState = Field(..., description="The item's state, named by the marker's keyword.")
    text: str = Field(..., description="The block string with the marker and its trailing spacing excised.")


@validate_call
def parse_todo(string: str) -> RoamTodo | None:
    """Decompose the Roam TODO item *string* into a :class:`RoamTodo`, or ``None`` when it is none.

    The checkbox marker must be the block's first content, but formatting markup may wrap it —
    Roam renders the checkbox either way, so recognition sees through the
    :data:`LEADING_MARKUP_PATTERN` markup (whitespace, ``#c:COLOR`` tags, emphasis openers).
    The marker and its trailing spacing are excised from the returned
    :attr:`~RoamTodo.text`, leaving any markup that wrapped the marker wrapping the remaining
    text.

    Args:
        string: A raw block string that may open with a Roam TODO marker.

    Returns:
        The decomposed :class:`RoamTodo`, or ``None`` when no marker opens *string*'s content.
    """
    stripped: Final[str] = string.strip()
    matched: Final[regex.Match[str] | None] = TODO_ITEM_RE.match(stripped)
    if matched is None:
        return None
    text: Final[str] = stripped[: matched.start("marker")] + stripped[matched.end() :]
    return RoamTodo(state=TodoState(matched.group("state")), text=text)


@validate_call
def todo_state(string: str) -> TodoState | None:
    """Return the state of the Roam TODO item *string*, or ``None`` when it is none.

    Recognition matches :func:`parse_todo`: the checkbox marker must be the block's first
    content, seen through any leading formatting markup.

    Args:
        string: A raw block string that may open with a Roam TODO marker.

    Returns:
        The :class:`TodoState` named by the marker's keyword, or ``None`` when no marker opens
        *string*'s content.
    """
    parsed: Final[RoamTodo | None] = parse_todo(string)
    return parsed.state if parsed is not None else None
