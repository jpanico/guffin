"""Roam Research quote-block constructs: the ``[[>]]`` marker, its callout and pull-quote subtypes.

In Roam's Markdown model ``[[>]]`` is the block-quote marker.  A **callout** is a styled subtype
whose marker is ``[[>]] [[!<TYPE>]]`` (``<TYPE>`` one of the eleven callout keywords).  The
``[[>]] [[!QUOTE]]`` marker is treated separately, as a **pull quote** (quotation + attribution),
not a callout.

Public symbols:

- **Pattern constants**: :data:`ROAM_BLOCK_QUOTE_PREFIX` — string prefix for a Roam block
  quote (and callout / pull quote); :data:`CALLOUT_RE` — compiled regex that matches and decomposes
  a full callout block string; :data:`PULL_QUOTE_RE` — compiled regex that matches and decomposes a
  ``[[>]] [[!QUOTE]]`` pull-quote block string.
- **Enumerations**: :class:`CalloutType` — the eleven Roam callout type keywords.
- **Callout model**: :class:`RoamCallout` — parsed decomposition of a callout block string.
- **Parsers**: :func:`parse_callout` — parse a raw block string as a :class:`RoamCallout`;
  :func:`parse_pull_quote` — parse a ``[[>]] [[!QUOTE]]`` block string into its ``(quote, attribution)``.
- **Quote-block predicate**: :func:`is_quote_block` — return ``True`` when a string is any of the
  three quote-block forms (standard ``>``, Roam-native ``[[>]]``, or ``[[>]] [[!QUOTE]]`` pull quote).
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
:func:`is_quote_block`.
"""


class CalloutType(enum.StrEnum):
    """The eleven Roam callout type keywords as they appear in the raw block string marker.

    The marker format is ``[[>]] [[!<TYPE>]]`` where ``<TYPE>`` is one of these values
    (always uppercase in the Roam source).

    These map one-to-one to the lowercase :class:`~guffin.vertex.CalloutVertex.CalloutType`
    values in the export model; convert with ``CalloutVertex.CalloutType(member.lower())``.

    Note ``QUOTE`` is deliberately absent: ``[[>]] [[!QUOTE]]`` is a pull quote (see
    :data:`PULL_QUOTE_RE`), not a callout.
    """

    INFO = "INFO"
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
- ``callout_type`` — one of the eleven recognised type keywords (``INFO``, ``EXAMPLE``,
  ``NOTE``, ``WARNING``, ``DANGER``, ``TIP``, ``SUMMARY``, ``SUCCESS``, ``QUESTION``,
  ``FAILURE``, ``BUG``).
- ``title`` — the remainder of the first line after the marker and any intervening
  whitespace; may be an empty string when no title text is present.
- ``body`` — everything after the first newline; ``None`` when the string contains no
  newline.  ``regex.DOTALL`` is set so ``.`` matches embedded newlines within the body.
"""


PULL_QUOTE_RE: Final[regex.Pattern[str]] = regex.compile(
    rf"{regex.escape(ROAM_BLOCK_QUOTE_PREFIX)} \[\[!QUOTE\]\]" r"\s*(?P<quote>[^\n]*)(?:\n(?P<attribution>.*))?",
    regex.DOTALL,
)
"""Compiled regex matching and decomposing a Roam ``[[>]] [[!QUOTE]]`` pull-quote block string.

Structurally the same as :data:`CALLOUT_RE` (marker + first line + rest), but keyed to the
``QUOTE`` marker and named for its pull-quote roles.  Named groups:

- ``quote`` — the quotation: the remainder of the first line after the marker (may be empty).
- ``attribution`` — everything after the first newline (the attribution line(s)); ``None`` when the
  string contains no newline.  ``regex.DOTALL`` is set so ``.`` matches embedded newlines.
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
def parse_pull_quote(block_string: str) -> tuple[str, str | None] | None:
    """Parse a ``[[>]] [[!QUOTE]]`` pull quote into its ``(quote, attribution)``, or ``None``.

    Returns ``None`` when *block_string* is not a ``[[>]] [[!QUOTE]]`` block (see
    :data:`PULL_QUOTE_RE`).  The quotation is the first line after the marker; the attribution is
    everything after the first newline, or ``None`` when the block has no further lines.

    Args:
        block_string: The raw block string to parse.

    Returns:
        A ``(quote, attribution)`` tuple when *block_string* is a pull quote — ``attribution`` is
        ``None`` when absent — or ``None`` when it is not a pull quote.
    """
    match: Final[regex.Match[str] | None] = PULL_QUOTE_RE.match(block_string)
    if match is None:
        return None
    attribution: Final[str | None] = match.group("attribution")
    return (match.group("quote"), attribution if attribution else None)


@validate_call
def is_quote_block(block_string: str) -> bool:
    """Return ``True`` if *block_string* is any of the three Roam quote-block forms.

    Recognises:

    - **Standard Markdown block quote**: *block_string* starts with :data:`MD_BLOCK_QUOTE_PREFIX`
      (``>``).
    - **Roam-native block quote**: *block_string* starts with :data:`ROAM_BLOCK_QUOTE_PREFIX`
      (``[[>]]``) and is not a typed callout (does not match :data:`CALLOUT_RE`).
    - **Pull quote**: ``[[>]] [[!QUOTE]]`` — included by the same test, since ``QUOTE`` is not a
      :class:`CalloutType` and so does not match :data:`CALLOUT_RE`.

    A typed callout (``[[>]] [[!INFO]]`` …) returns ``False``.  The three quote forms all map to a
    single ``QUOTE_BLOCK`` node type; the pull quote is distinguished later via
    :func:`parse_pull_quote`.

    Args:
        block_string: The string to test.

    Returns:
        ``True`` when *block_string* is a standard, Roam-native, or pull quote block.
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
        block_string: A block-quote string as recognised by :func:`is_quote_block`.

    Returns:
        The content of the block quote with the leading marker and any intervening
        whitespace removed.

    Raises:
        ValueError: If *block_string* is not a block quote according to
            :func:`is_quote_block`.
    """
    if not is_quote_block(block_string):
        raise ValueError(f"string is not a block quote: {block_string!r}")
    prefix: Final[str] = (
        ROAM_BLOCK_QUOTE_PREFIX if block_string.startswith(ROAM_BLOCK_QUOTE_PREFIX) else MD_BLOCK_QUOTE_PREFIX
    )
    return block_string[len(prefix) :].lstrip()
