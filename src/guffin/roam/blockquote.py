"""Roam Research quote-block constructs: the ``[[>]]`` marker, its callout, pull-quote, and epigraph subtypes.

In Roam's Markdown model ``[[>]]`` is the block-quote marker.  A **callout** is a styled subtype
whose marker is ``[[>]] [[!<TYPE>]]`` (``<TYPE>`` one of the eleven callout keywords).  Two further
markers of that shape are treated separately, as quotations rather than callouts: ``[[>]] [[!QUOTE]]``
is a **pull quote** — a passage of the work's own text promoted for display — and
``[[>]] [[!EPIGRAPH]]`` is an **epigraph** — a quotation set at the opening of a work or one of its
divisions.  Roam renders any ``[[!<TYPE>]]`` keyword as a callout box, so both display as callouts
in Roam itself.

A plain block quote (``>`` or ``[[>]]``) or an epigraph reproduces another source's words, so it
may carry an **attribution**: the source line conventionally set beneath the quotation.  It is
written as the quote's final paragraph — after a blank line — led by an em dash (``—``) or en dash
(``–``).  A pull quote never carries one: its source is the work itself, so all its text is
quotation.

Public symbols:

- **Pattern constants**: :data:`ROAM_BLOCK_QUOTE_PREFIX` — string prefix for a Roam block
  quote (and callout / pull quote); :data:`CALLOUT_RE` — compiled regex that matches and decomposes
  a full callout block string; :data:`PULL_QUOTE_RE` — compiled regex that matches a
  ``[[>]] [[!QUOTE]]`` pull-quote block string and captures its quotation; :data:`EPIGRAPH_RE` —
  compiled regex that matches a ``[[>]] [[!EPIGRAPH]]`` epigraph block string and captures its
  content; :data:`ATTRIBUTION_DASHES` — the dashes that may lead a quotation's attribution;
  :data:`BLOCK_QUOTE_ATTRIBUTION_RE` — compiled regex splitting a quotation's content into its
  quotation and attribution.
- **Enumerations**: :class:`CalloutType` — the eleven Roam callout type keywords.
- **Models**: :class:`RoamCallout` — parsed decomposition of a callout block string;
  :class:`RoamBlockQuote` — parsed decomposition of an attributable quotation string (a plain block
  quote or an epigraph).
- **Parsers**: :func:`parse_callout` — parse a raw block string as a :class:`RoamCallout`;
  :func:`parse_pull_quote` — the quotation of a ``[[>]] [[!QUOTE]]`` block string;
  :func:`parse_epigraph` — parse a ``[[>]] [[!EPIGRAPH]]`` block string as a :class:`RoamBlockQuote`;
  :func:`parse_block_quote` — parse a plain block-quote string as a :class:`RoamBlockQuote`.
- **Quote-block predicate**: :func:`is_quote_block` — return ``True`` when a string is any of the
  four quote-block forms (standard ``>``, Roam-native ``[[>]]``, ``[[>]] [[!QUOTE]]`` pull quote, or
  ``[[>]] [[!EPIGRAPH]]`` epigraph).
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

    Note ``QUOTE`` and ``EPIGRAPH`` are deliberately absent: ``[[>]] [[!QUOTE]]`` is a pull quote
    (see :data:`PULL_QUOTE_RE`) and ``[[>]] [[!EPIGRAPH]]`` an epigraph (see :data:`EPIGRAPH_RE`),
    quotations rather than callouts.
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
    rf"{regex.escape(ROAM_BLOCK_QUOTE_PREFIX)} \[\[!QUOTE\]\]" r"\s*(?P<quote>.*)",
    regex.DOTALL,
)
"""Compiled regex matching a Roam ``[[>]] [[!QUOTE]]`` pull-quote block string.

A pull quote promotes a passage of the work's own text, so it carries no attribution: everything
after the marker is quotation.  Named group:

- ``quote`` — the quotation: everything after the marker and any intervening whitespace, every
  line of it (may be empty).  ``regex.DOTALL`` is set so ``.`` matches embedded newlines.
"""

EPIGRAPH_RE: Final[regex.Pattern[str]] = regex.compile(
    rf"{regex.escape(ROAM_BLOCK_QUOTE_PREFIX)} \[\[!EPIGRAPH\]\]" r"\s*(?P<content>.*)",
    regex.DOTALL,
)
"""Compiled regex matching a Roam ``[[>]] [[!EPIGRAPH]]`` epigraph block string.

Structurally the same as :data:`PULL_QUOTE_RE`, keyed to the ``EPIGRAPH`` marker.  An epigraph quotes
another source, so its content may end in an attribution, split off by
:data:`BLOCK_QUOTE_ATTRIBUTION_RE`.  Named group:

- ``content`` — everything after the marker and any intervening whitespace, every line of it (may
  be empty).  ``regex.DOTALL`` is set so ``.`` matches embedded newlines.
"""

ATTRIBUTION_DASHES: Final[frozenset[str]] = frozenset({"—", "–"})
"""The dashes that may lead a quotation's attribution paragraph: the em dash (``—``, U+2014).

and the en dash (``–``, U+2013).
"""

BLOCK_QUOTE_ATTRIBUTION_RE: Final[regex.Pattern[str]] = regex.compile(
    r"(?P<quote>.*\S)\n[ \t]*\n[ \t]*"
    rf"[{''.join(sorted(ATTRIBUTION_DASHES))}]"
    r"[ \t]*(?P<attribution>(?:[^\n]|\n(?![ \t]*\n))*\S)\s*",
    regex.DOTALL,
)
"""Compiled regex splitting a quotation's content into its quotation and attribution.

Matches content (the marker already stripped) whose **final paragraph** — the run after its last
blank line — is led by one of the :data:`ATTRIBUTION_DASHES`.  The required blank line keeps a
dash-led line *inside* the quotation (verse, dialogue) from being taken for a credit.  Use with
``fullmatch``.  Named groups:

- ``quote`` — the quotation: everything before that blank line (never empty).
- ``attribution`` — the final paragraph's text after its leading dash and spacing (one or more
  lines, never containing a blank line, never empty).
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


class RoamBlockQuote(BaseModel):
    """Parsed decomposition of an attributable quotation string: a plain block quote or an epigraph.

    A plain block quote is ``>`` or ``[[>]]``; an epigraph is ``[[>]] [[!EPIGRAPH]]``.  A pull quote is
    neither, since it carries no attribution.

    Attributes:
        quote: The quotation — the content after the marker, less any attribution paragraph.
        attribution: The source line's text, after its leading dash — the quote's final
            paragraph, when it follows a blank line and is led by one of the
            :data:`ATTRIBUTION_DASHES` — or ``None`` when the quote carries none.
    """

    model_config = ConfigDict(frozen=True)

    quote: str = Field(..., description="The quotation — the content after the marker, less any attribution.")
    attribution: str | None = Field(
        default=None, description="The source line's text after its leading dash; None when absent."
    )


@validate_call
def parse_pull_quote(block_string: str) -> str | None:
    """Return the quotation of a ``[[>]] [[!QUOTE]]`` pull quote, or ``None``.

    Returns ``None`` when *block_string* is not a ``[[>]] [[!QUOTE]]`` block (see
    :data:`PULL_QUOTE_RE`).  A pull quote carries no attribution, so the quotation is everything
    after the marker, every line of it.

    Args:
        block_string: The raw block string to parse.

    Returns:
        The quotation when *block_string* is a pull quote, else ``None``.
    """
    match: Final[regex.Match[str] | None] = PULL_QUOTE_RE.match(block_string)
    return match.group("quote") if match is not None else None


def _split_attribution(content: str) -> RoamBlockQuote:
    """Return *content* split into its quotation and its attribution, per :data:`BLOCK_QUOTE_ATTRIBUTION_RE`.

    Content with no dash-led final paragraph after a blank line is all quotation.
    """
    match: Final[regex.Match[str] | None] = BLOCK_QUOTE_ATTRIBUTION_RE.fullmatch(content)
    if match is None:
        return RoamBlockQuote(quote=content)
    return RoamBlockQuote(quote=match.group("quote"), attribution=match.group("attribution"))


@validate_call
def parse_epigraph(block_string: str) -> RoamBlockQuote | None:
    """Parse a ``[[>]] [[!EPIGRAPH]]`` epigraph as a :class:`RoamBlockQuote`, or return ``None``.

    Returns ``None`` when *block_string* is not a ``[[>]] [[!EPIGRAPH]]`` block (see
    :data:`EPIGRAPH_RE`).  Otherwise everything after the marker is the epigraph's content, from which
    the attribution is split off exactly as from a plain block quote's: the content's final paragraph,
    when it follows a blank line and is led by one of the :data:`ATTRIBUTION_DASHES`.

    Args:
        block_string: The raw block string to parse.

    Returns:
        The :class:`RoamBlockQuote` when *block_string* is an epigraph, else ``None``.
    """
    match: Final[regex.Match[str] | None] = EPIGRAPH_RE.match(block_string)
    return _split_attribution(match.group("content")) if match is not None else None


@validate_call
def parse_block_quote(block_string: str) -> RoamBlockQuote | None:
    """Parse a plain block-quote string as a :class:`RoamBlockQuote`, or return ``None``.

    Returns ``None`` when *block_string* is not a plain block quote — not a quote block at all
    (:func:`is_quote_block`), a pull quote (:func:`parse_pull_quote`), or an epigraph
    (:func:`parse_epigraph`).  Otherwise strips the marker (:func:`strip_block_quote_marker`) and
    splits off the attribution: the content's final paragraph, when it follows a blank line and is led
    by one of the :data:`ATTRIBUTION_DASHES` (:data:`BLOCK_QUOTE_ATTRIBUTION_RE`).  Content with no
    such paragraph is all quotation.

    Args:
        block_string: The raw block string to parse.

    Returns:
        The :class:`RoamBlockQuote` when *block_string* is a plain block quote, else ``None``.
    """
    if (
        not is_quote_block(block_string)
        or parse_pull_quote(block_string) is not None
        or EPIGRAPH_RE.match(block_string) is not None
    ):
        return None
    return _split_attribution(strip_block_quote_marker(block_string))


@validate_call
def is_quote_block(block_string: str) -> bool:
    """Return ``True`` if *block_string* is any of the four Roam quote-block forms.

    Recognises:

    - **Standard Markdown block quote**: *block_string* starts with :data:`MD_BLOCK_QUOTE_PREFIX`
      (``>``).
    - **Roam-native block quote**: *block_string* starts with :data:`ROAM_BLOCK_QUOTE_PREFIX`
      (``[[>]]``) and is not a typed callout (does not match :data:`CALLOUT_RE`).
    - **Pull quote**: ``[[>]] [[!QUOTE]]`` — included by the same test, since ``QUOTE`` is not a
      :class:`CalloutType` and so does not match :data:`CALLOUT_RE`.
    - **Epigraph**: ``[[>]] [[!EPIGRAPH]]`` — likewise included, ``EPIGRAPH`` not being a
      :class:`CalloutType` either.

    A typed callout (``[[>]] [[!INFO]]`` …) returns ``False``.  The four quote forms all map to a
    single ``QUOTE_BLOCK`` node type; the pull quote is distinguished later via
    :func:`parse_pull_quote`, the epigraph via :func:`parse_epigraph`, and a plain block quote's parts
    via :func:`parse_block_quote`.

    Args:
        block_string: The string to test.

    Returns:
        ``True`` when *block_string* is a standard, Roam-native, pull quote, or epigraph block.
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
