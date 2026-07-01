"""Markdown types and structural predicates.

Public symbols:

- :data:`HeadingLevel` — integer type alias for a Markdown heading depth, constrained to 1–6.
- :data:`MD_BLOCK_QUOTE_PREFIX` — string prefix for a standard CommonMark blockquote line.
- :data:`CODE_BLOCK_RE` — compiled regex matching a backtick-fenced code block where fences
  may share a line with adjacent content.
- :data:`MD_LINK_RE` — compiled regex matching a CommonMark inline link ``[text](url)``.
- :func:`is_fenced_code_block` — whether a string is a single CommonMark fenced code block.
- :func:`contains_fenced_code_block` — whether any line of a string opens a fenced code block.
- :class:`FencedCodeBlock` — the info string and code content extracted from a fenced code block.
- :func:`parse_fenced_code_block` — extract the info string and code content from a fenced code block.
- :func:`unwrap_links` — replace each CommonMark inline link with its display text.
"""

from typing import Annotated, Final, NamedTuple

import regex
from pydantic import Field, validate_call

type HeadingLevel = Annotated[int, Field(ge=1, le=6)]
"""Markdown heading level, constrained to the inclusive range 1–6."""

MD_BLOCK_QUOTE_PREFIX: Final[str] = ">"
"""String prefix that identifies a standard CommonMark blockquote line.

A line beginning with ``>`` (optionally followed by a space) is a CommonMark
block quote marker.
"""

CODE_BLOCK_RE: Final[regex.Pattern[str]] = regex.compile(r"```([^\n]*)\n(.*?)```", regex.DOTALL)
"""Compiled regex matching a backtick-fenced code block where fences may share a line with adjacent content.

Unlike the strict CommonMark form (where each fence must occupy its own line), both the
opening ` ``` ` and the closing ` ``` ` may appear on a line that also contains other content.

Numbered groups (no named groups):

- Group 1 — the info string following the opening ` ``` ` (e.g. ``python``); may be empty.
- Group 2 — the code body between the opening and closing fences; spans newlines
  (:data:`regex.DOTALL` is set).
"""

MD_LINK_RE: Final[regex.Pattern[str]] = regex.compile(r"\[([^\]]*)\]\([^)]*\)")
"""Compiled regex matching a CommonMark inline link ``[text](url)``.

Group 1 captures the link's display text; the destination in parentheses is matched but not
captured.  Used by :func:`unwrap_links` to reduce a link to its display text.
"""


@validate_call
def unwrap_links(text: str) -> str:
    """Replace each CommonMark inline link ``[text](url)`` in *text* with its display text.

    Args:
        text: The string to unwrap.

    Returns:
        *text* with every ``[label](destination)`` link replaced by ``label``; non-link content
        is left unchanged.
    """
    return MD_LINK_RE.sub(r"\1", text)


# Opening code fence: up to three spaces of indentation, then a run of at least
# three backticks or three tildes, then an optional info string (the remainder
# of the line).  Group 1 captures the fence run; group 2 captures the info string.
_OPENING_FENCE_RE: Final[regex.Pattern[str]] = regex.compile(r" {0,3}(`{3,}|~{3,})(.*)")


@validate_call
def is_fenced_code_block(text: str) -> bool:
    r"""Return whether *text* is a single fenced code block per the CommonMark spec.

    A fenced code block opens with a code fence — up to three spaces of
    indentation followed by a run of at least three backticks (```` ``` ````) or
    at least three tildes (``~~~``) — optionally followed by an info string on
    the same line.  When the fence is built from backticks, the info string may
    not contain a backtick.  The content runs until a closing fence (a line
    bearing only indentation of up to three spaces, fence characters of the same
    kind and at least the same count, and trailing whitespace) or, when there is
    none, to the end of *text* — a closing fence is optional in CommonMark.

    *text* qualifies only when it is wholly a single fenced code block: its first
    line is the opening fence and any closing fence is followed by nothing but
    blank lines.  A string whose opening fence is preceded by other content, or
    whose closing fence is followed by further content, returns ``False``.

    Args:
        text: The string to test.

    Returns:
        ``True`` if *text* is a single CommonMark fenced code block; ``False``
        otherwise.
    """
    lines: Final[list[str]] = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    opening: Final[regex.Match[str] | None] = _OPENING_FENCE_RE.fullmatch(lines[0])
    if opening is None:
        return False
    fence: Final[str] = opening.group(1)
    info: Final[str] = opening.group(2)
    if fence[0] == "`" and "`" in info:
        return False
    closing_fence_re: Final[regex.Pattern[str]] = regex.compile(
        rf" {{0,3}}{regex.escape(fence[0])}{{{len(fence)},}}[ \t]*"
    )
    closing_index: Final[int | None] = next(
        (i for i in range(1, len(lines)) if closing_fence_re.fullmatch(lines[i])),
        None,
    )
    if closing_index is None:
        return True
    return all(not line.strip() for line in lines[closing_index + 1 :])


@validate_call
def contains_fenced_code_block(text: str) -> bool:
    r"""Return whether any line of *text* opens a CommonMark fenced code block.

    Scans *text* line by line for an opening code fence — up to three spaces of
    indentation followed by a run of at least three backticks (```` ``` ````) or
    at least three tildes (``~~~``).  Unlike :func:`is_fenced_code_block` (which
    requires *text* to be *wholly* a single fenced code block), the fence may
    appear on any line, so this flags text that mixes prose with a block-level
    fence — content that must be parsed at block level rather than inline.

    Args:
        text: The string to scan.

    Returns:
        ``True`` if any line is an opening code fence; ``False`` otherwise.
    """
    return any(_OPENING_FENCE_RE.fullmatch(line) is not None for line in text.splitlines())


class FencedCodeBlock(NamedTuple):
    """The info string and code content extracted from a fenced code block.

    Attributes:
        info: The opening fence's info string (e.g. ``python``), stripped of
            surrounding whitespace; the empty string when the fence carries none.
        code: The code content between the opening and closing fences.
    """

    info: str
    code: str


@validate_call
def parse_fenced_code_block(text: str) -> FencedCodeBlock:
    """Extract the info string and code content from a fenced code block.

    *text* must open with a code fence (as accepted by
    :func:`is_fenced_code_block`).  The closing fence may sit on its own line, be
    attached to the final content line with no separating newline, or be absent
    (in which case the content runs to the end of *text*).

    Args:
        text: A fenced code block string.

    Returns:
        A :class:`FencedCodeBlock` pairing the opening fence's info string with
        the code content between the fences.

    Raises:
        ValueError: If *text* does not open with a code fence.
    """
    lines: Final[list[str]] = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    opening: Final[regex.Match[str] | None] = _OPENING_FENCE_RE.fullmatch(lines[0])
    if opening is None:
        raise ValueError(f"not a fenced code block: {text!r}")
    fence: Final[str] = opening.group(1)
    info: Final[str] = opening.group(2).strip()
    body_lines: Final[list[str]] = lines[1:]

    closing_fence_re: Final[regex.Pattern[str]] = regex.compile(
        rf" {{0,3}}{regex.escape(fence[0])}{{{len(fence)},}}[ \t]*"
    )
    closing_index: Final[int | None] = next(
        (i for i, line in enumerate(body_lines) if closing_fence_re.fullmatch(line)),
        None,
    )
    if closing_index is not None:
        return FencedCodeBlock(info=info, code="\n".join(body_lines[:closing_index]))

    # No standalone closing fence: strip a fence attached to the final content
    # line (the form Roam stores), else treat the block as unterminated.
    if body_lines:
        attached_fence_re: Final[regex.Pattern[str]] = regex.compile(
            rf"{regex.escape(fence[0])}{{{len(fence)},}}[ \t]*$"
        )
        stripped_last: Final[str] = attached_fence_re.sub("", body_lines[-1])
        if stripped_last != body_lines[-1]:
            tail: Final[list[str]] = [stripped_last] if stripped_last else []
            return FencedCodeBlock(info=info, code="\n".join(body_lines[:-1] + tail))
    return FencedCodeBlock(info=info, code="\n".join(body_lines))
