"""Roam Research block-quote constructs: the ``[[>]]`` marker, its callout subtype, and helpers.

In Roam's Markdown model ``[[>]]`` is the block-quote marker; a callout is a styled
subtype of block quote whose marker is ``[[>]] [[!<TYPE>]]``.

Public symbols:

- **Pattern constants**: :data:`ROAM_BLOCK_QUOTE_PREFIX` — string prefix for a Roam block
  quote (and callout); :data:`CALLOUT_RE` — compiled regex that matches and decomposes a full
  callout block string.
- **Enumerations**: :class:`CalloutType` — the twelve Roam callout type keywords.
- **Callout model**: :class:`RoamCallout` — parsed decomposition of a callout block string.
- **Callout parser**: :func:`parse_callout` — parse a raw block string as a :class:`RoamCallout`.
- **Block-quote predicate**: :func:`is_roam_block_quote` — return ``True`` when a string is a
  Roam or standard Markdown block quote.
- **Block-quote marker stripper**: :func:`strip_block_quote_marker` — strip the leading block-quote
  marker from a block-quote string and return the remaining content.
"""

import enum
from typing import Final

import regex
from pydantic import BaseModel, ConfigDict, Field, validate_call

from guffin.common.markdown import MD_BLOCK_QUOTE_PREFIX

ROAM_BLOCK_QUOTE_PREFIX: Final[str] = "[[>]]"
"""String prefix for a Roam block quote (and by extension, a Roam callout).

In Roam's Markdown model ``[[>]]`` is the block-quote marker; callouts are a
styled subtype of block quote whose marker is ``[[>]] [[!<TYPE>]]``.  Used as
a fast pre-filter before applying :data:`CALLOUT_RE` and by
:func:`is_roam_block_quote`.
"""


class CalloutType(enum.StrEnum):
    """The twelve Roam callout type keywords as they appear in the raw block string marker.

    The marker format is ``[[>]] [[!<TYPE>]]`` where ``<TYPE>`` is one of these values
    (always uppercase in the Roam source).

    These map one-to-one to the lowercase :class:`~guffin.vertex.CalloutVertex.CalloutType`
    values in the export model; convert with ``CalloutVertex.CalloutType(member.lower())``.
    """

    INFO = "INFO"
    QUOTE = "QUOTE"
    EXAMPLE = "EXAMPLE"
    NOTE = "NOTE"
    WARNING = "WARNING"
    DANGER = "DANGER"
    TIP = "TIP"
    SUMMARY = "SUMMARY"
    SUCCESS = "SUCCESS"
    QUESTION = "QUESTION"
    FAILURE = "FAILURE"
    BUG = "BUG"


CALLOUT_RE: Final[regex.Pattern[str]] = regex.compile(
    rf"(?P<prefix>{regex.escape(ROAM_BLOCK_QUOTE_PREFIX)})"
    rf" \[\[!(?P<callout_type>{'|'.join(ct.value for ct in CalloutType)})\]\]"
    r"\s*(?P<title>[^\n]*)(?:\n(?P<body>.*))?",
    regex.DOTALL,
)
"""Compiled regex matching and decomposing a full Roam callout block string.

Named groups:

- ``prefix`` — the literal ``[[>]]`` opener.
- ``callout_type`` — one of the twelve recognised type keywords (``INFO``, ``QUOTE``,
  ``EXAMPLE``, ``NOTE``, ``WARNING``, ``DANGER``, ``TIP``, ``SUMMARY``, ``SUCCESS``,
  ``QUESTION``, ``FAILURE``, ``BUG``).
- ``title`` — the remainder of the first line after the marker and any intervening
  whitespace; may be an empty string when no title text is present.
- ``body`` — everything after the first newline; ``None`` when the string contains no
  newline.  ``regex.DOTALL`` is set so ``.`` matches embedded newlines within the body.
"""


class RoamCallout(BaseModel):
    """Parsed decomposition of a callout block string.

    Captures the three semantic components extracted from the raw block string
    by :data:`CALLOUT_RE`.

    Attributes:
        callout_type: Callout category keyword from the ``[[>]] [[!<TYPE>]]`` marker.
        title: Callout heading text — the remainder of the first line after the marker.
        body: Callout body text — everything after the first newline in the block string;
            empty string when absent.
    """

    model_config = ConfigDict(frozen=True)

    callout_type: CalloutType = Field(..., description="Callout category keyword from the [[>]] [[!<TYPE>]] marker.")
    title: str = Field(..., description="Callout heading text — the remainder of the first line after the marker.")
    body: str = Field(
        ..., description="Callout body text — everything after the first newline; empty string when absent."
    )


@validate_call
def parse_callout(block_string: str) -> RoamCallout | None:
    """Parse *block_string* as a :class:`RoamCallout`, or return ``None`` if it is not a callout.

    Returns ``None`` when *block_string* does not start with :data:`ROAM_BLOCK_QUOTE_PREFIX`.

    Args:
        block_string: The raw block string to parse.

    Returns:
        A :class:`RoamCallout` when *block_string* matches :data:`CALLOUT_RE`; ``None`` otherwise.
        The ``body`` field is an empty string when *block_string* contains no newline.

    Raises:
        ValueError: When *block_string* starts with :data:`ROAM_BLOCK_QUOTE_PREFIX` but does not match
            :data:`CALLOUT_RE` (malformed callout marker).
    """
    if not block_string.startswith(ROAM_BLOCK_QUOTE_PREFIX):
        return None
    m: Final[regex.Match[str] | None] = CALLOUT_RE.match(block_string)
    if m is None:
        raise ValueError(
            f"block string starts with {ROAM_BLOCK_QUOTE_PREFIX!r} "
            f"but does not match callout pattern; got {block_string!r}"
        )
    return RoamCallout(
        callout_type=CalloutType(m.group("callout_type")),
        title=m.group("title"),
        body=m.group("body") or "",
    )


@validate_call
def is_roam_block_quote(block_string: str) -> bool:
    """Return ``True`` if *block_string* is a Roam or standard Markdown block quote.

    Recognises two forms:

    - **Standard Markdown**: *block_string* starts with :data:`MD_BLOCK_QUOTE_PREFIX` (``>``).
    - **Roam-specific**: *block_string* starts with :data:`ROAM_BLOCK_QUOTE_PREFIX` (``[[>]]``) but does
      not match :data:`CALLOUT_RE` — i.e. a plain ``[[>]]``-prefixed blockquote rather
      than a typed callout.

    Args:
        block_string: The string to test.

    Returns:
        ``True`` when *block_string* matches either the standard or Roam blockquote form.
    """
    if block_string.startswith(ROAM_BLOCK_QUOTE_PREFIX):
        return not CALLOUT_RE.match(block_string)
    return block_string.startswith(MD_BLOCK_QUOTE_PREFIX)


@validate_call
def strip_block_quote_marker(block_string: str) -> str:
    """Strip the leading block-quote marker from *block_string* and return the remaining content.

    Strips :data:`ROAM_BLOCK_QUOTE_PREFIX` (``[[>]]``) for Roam-style block quotes or
    :data:`MD_BLOCK_QUOTE_PREFIX` (``>``) for standard Markdown block quotes, then
    strips any leading whitespace from the remainder.

    Args:
        block_string: A block-quote string as recognised by :func:`is_roam_block_quote`.

    Returns:
        The content of the block quote with the leading marker and any intervening
        whitespace removed.

    Raises:
        ValueError: If *block_string* is not a block quote according to
            :func:`is_roam_block_quote`.
    """
    if not is_roam_block_quote(block_string):
        raise ValueError(f"string is not a block quote: {block_string!r}")
    prefix: Final[str] = (
        ROAM_BLOCK_QUOTE_PREFIX if block_string.startswith(ROAM_BLOCK_QUOTE_PREFIX) else MD_BLOCK_QUOTE_PREFIX
    )
    return block_string[len(prefix) :].lstrip()
