"""Roam Research Markdown constructs: block-quote and callout parsing.

Public symbols:

- **Pattern constants**: :data:`ROAM_BLOCK_QUOTE_PREFIX` — string prefix for a Roam block
  quote (and callout); :data:`CALLOUT_RE` — compiled regex that matches and decomposes a full
  callout block string; :data:`IMAGE_LINK_RE` — compiled regex matching a Roam markdown image
  link whose URL is a Cloud Firestore storage URL; :data:`PAGE_REF_RE` — compiled regex matching
  a Roam page reference ``[[<page_name>]]``; :data:`BLOCK_REF_RE` — compiled regex matching a
  Roam block reference ``((<uid>))``; :data:`BLOCK_EMBED_RE` — compiled regex matching a Roam
  block embed ``{{embed: ((<uid>))}}``; :data:`PAGE_LINK_ALIAS_RE` — compiled regex matching a
  Roam aliased page link ``[display]([[Page Name]])``; :data:`ITALIC_RE` — compiled regex
  matching Roam italic syntax ``__text__``; :data:`HIGHLIGHT_RE` — compiled regex matching Roam
  highlight syntax ``^^text^^``; :data:`COLOR_BOLD_RE`, :data:`COLOR_HIGHLIGHT_RE`,
  :data:`COLOR_UNDERLINE_RE`, :data:`COLOR_BOX_RE`, :data:`BG_COLOR_LINE_RE` — compiled regexes
  for the five Color Highlighter inline and block-level color constructs.
- **Enumerations**: :class:`CalloutType` — the twelve Roam callout type keywords.
- **Callout model**: :class:`RoamCallout` — parsed decomposition of a callout block string.
- **Callout parser**: :func:`parse_callout` — parse a raw block string as a :class:`RoamCallout`.
- **Block-quote predicate**: :func:`is_roam_block_quote` — return ``True`` when a string is a
  Roam or standard Markdown block quote.
- **Block-quote marker stripper**: :func:`strip_block_quote_marker` — strip the leading block-quote
  marker from a block-quote string and return the remaining content.
- **Image-link accessors**: :func:`image_link_url`, :func:`image_link_alt_text` — extract the Cloud
  Firestore URL and the alt text from the first image link in a block string;
  :func:`firestore_url_file_name` — decode the original filename from a Firestore storage URL.
- **Table marker**: :data:`ROAM_NATIVE_TABLE_MARKER` — the block string that identifies a Roam
  native table block.
"""

import enum
from typing import Final
from urllib.parse import unquote, urlparse

import regex
from pydantic import BaseModel, ConfigDict, Field, validate_call

from guffin.common.markdown import MD_BLOCK_QUOTE_PREFIX
from guffin.roam.primitives import SYNTHETIC_UID_PATTERN


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


ROAM_BLOCK_QUOTE_PREFIX: Final[str] = "[[>]]"
"""String prefix for a Roam block quote (and by extension, a Roam callout).

In Roam's Markdown model ``[[>]]`` is the block-quote marker; callouts are a
styled subtype of block quote whose marker is ``[[>]] [[!<TYPE>]]``.  Used as
a fast pre-filter before applying :data:`CALLOUT_RE` and by
:func:`is_roam_block_quote`.
"""

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


ROAM_NATIVE_TABLE_MARKER: Final[str] = "{{table}}"
"""Block string that identifies a Roam native table block.

A block whose :attr:`~guffin.roam.node.RoamNode.string` (after stripping surrounding
whitespace) equals this marker is a Roam native table container; its child blocks
form the rows, and each child's children are the cells.
"""

IMAGE_LINK_RE: Final[regex.Pattern[str]] = regex.compile(
    r"!\[(?P<alt>(?:[^\]]|\n)*?)\]\((?P<url>https://firebasestorage\.googleapis\.com/[^\)]+)\)"
)
"""Compiled regex matching a Roam markdown image link whose URL is a Cloud Firestore storage URL.

Named groups:

- ``alt`` — the alt-text content between ``[`` and ``]`` (may be empty or multi-line).
- ``url`` — the Cloud Firestore storage URL between ``(`` and ``)``.

Example match on ``![my photo](https://firebasestorage.googleapis.com/v0/b/...)``:

- ``match.group(0)`` — the full ``![...](..)`` string.
- ``match.group("url")`` — just the URL.
- ``match.group("alt")`` — just the alt text.
"""


@validate_call
def image_link_url(string: str) -> str | None:
    """Return the Cloud Firestore storage URL embedded in *string*, or ``None`` if absent.

    Args:
        string: A raw block string that may contain a Roam markdown image link.

    Returns:
        The URL string captured from the first Firestore image link, or ``None``.
    """
    m: Final[regex.Match[str] | None] = IMAGE_LINK_RE.search(string)
    return m.group("url") if m else None


@validate_call
def image_link_alt_text(string: str) -> str | None:
    """Return the alt text from the first Firestore image link in *string*, or ``None``.

    The captured alt text is stripped of leading and trailing whitespace.  Returns ``None`` when no
    Firestore image link is found or the alt text is empty after stripping.

    Args:
        string: A raw block string that may contain a Roam markdown image link.

    Returns:
        The stripped alt text string, or ``None``.
    """
    m: Final[regex.Match[str] | None] = IMAGE_LINK_RE.search(string)
    if m is None:
        return None
    alt: Final[str] = m.group("alt").strip()
    return alt if alt else None


@validate_call
def firestore_url_file_name(firestore_url: str) -> str | None:
    """Return the original filename encoded in a Firestore URL, or ``None`` on failure.

    Firestore URLs encode the object path after ``/o/`` using percent-encoding.  The filename is the
    last path segment after URL-decoding.

    Args:
        firestore_url: A ``https://firebasestorage.googleapis.com/...`` URL string.

    Returns:
        The decoded filename (e.g. ``"image.png"``), or ``None`` if extraction fails.
    """
    try:
        path: Final[str] = urlparse(firestore_url).path
        parts: Final[list[str]] = path.split("/o/", maxsplit=1)
        if len(parts) == 2:
            return unquote(parts[1]).split("/")[-1]
    except Exception:
        pass
    return None


PAGE_REF_RE: Final[regex.Pattern[str]] = regex.compile(r"\[\[(?P<page_name>(?:[^\[\]\n]++|(?R))+)\]\]")
"""Compiled regex matching a Roam page reference ``[[<page_name>]]``.

A page name may itself contain nested page references, so the pattern is
recursive: it matches a balanced ``[[`` … ``]]`` pair using the third-party
:mod:`regex` module's ``(?R)`` whole-pattern recursion (stdlib :mod:`re` cannot
match balanced nesting).

Named group:

- ``page_name`` — the content between the *outermost* balanced ``[[`` and ``]]``
  delimiters; non-empty, and itself possibly containing further ``[[…]]``
  references.  It may span spaces and punctuation but not a newline, since a Roam
  page title is single-line.

Adjacent references are matched separately; use :meth:`regex.Pattern.finditer`
to enumerate every top-level reference.

Example matches:

- ``[[Test Article]]`` → ``page_name`` is ``Test Article``.
- ``[[0.2 Introduction [[v01]]]]`` → ``page_name`` is ``0.2 Introduction [[v01]]``.
- ``[[[[[[Illustration]] Brief]] -- Draft]]`` → ``page_name`` is
  ``[[[[Illustration]] Brief]] -- Draft``.
"""

BLOCK_REF_RE: Final[regex.Pattern[str]] = regex.compile(rf"\(\((?P<uid>{SYNTHETIC_UID_PATTERN})\)\)")
"""Compiled regex matching a Roam block reference ``((<uid>))``.

Block references embed a synthetic 9-character Roam UID between ``((`` and ``))`` — they target
blocks, which always have synthetic UIDs (daily-note pages are referenced by title, not ``((...))``).
Unlike page references, block refs cannot nest other references, so no recursive matching is required.

Named group:

- ``uid`` — the synthetic UID (matching :data:`~guffin.roam.primitives.SYNTHETIC_UID_PATTERN`)
  between the outer ``((`` and ``))`` delimiters.

Adjacent references are matched separately; use :meth:`regex.Pattern.finditer`
to enumerate every reference in a string.

Example match on ``((wdMgyBiP9))``:

- ``match.group(0)`` — the full ``((wdMgyBiP9))`` string.
- ``match.group("uid")`` — just ``wdMgyBiP9``.
"""

BLOCK_EMBED_RE: Final[regex.Pattern[str]] = regex.compile(rf"\{{\{{embed: {BLOCK_REF_RE.pattern}\}}\}}")
"""Compiled regex matching a Roam block embed ``{{embed: ((<uid>))}}``.

Wraps a :data:`BLOCK_REF_RE` block reference in the literal ``{{embed: `` and ``}}``
delimiters (note the single space after ``embed:``).  The embedded reference's ``uid``
named group is carried through, so the referenced node UID is available on a match.

Named group:

- ``uid`` — the 9-character UID of the embedded block.

Example match on ``{{embed: ((LfXmNr-tV))}}``:

- ``match.group(0)`` — the full ``{{embed: ((LfXmNr-tV))}}`` string.
- ``match.group("uid")`` — just ``LfXmNr-tV``.
"""

PAGE_LINK_ALIAS_RE: Final[regex.Pattern[str]] = regex.compile(r"\[([^\[\]]+)\]\(\[\[([^\[\]]*)\]\]\)")
"""Compiled regex matching a Roam aliased page link ``[display text]([[Page Name]])``.

Numbered groups (no named groups):

- Group 1 — the display text between the outer ``[`` and ``]``; non-empty,
  no square brackets.
- Group 2 — the page name between the inner ``[[`` and ``]]``; may be empty.
"""

ITALIC_RE: Final[regex.Pattern[str]] = regex.compile(r"(?<!\w)__(?!\s)(.+?)(?<!\s)__(?!\w)", regex.DOTALL)
"""Compiled regex matching Roam italic syntax ``__text__``.

Roam uses double underscores for italics.  Negative look-behind and look-ahead
prevent matching adjacent to word characters, and look-ahead/behind on the
inner boundary prevent matching when the delimited content begins or ends with
whitespace.

Numbered group (no named groups):

- Group 1 — the italic content between the ``__`` delimiters; may span newlines
  (:data:`regex.DOTALL` is set).
"""

HIGHLIGHT_RE: Final[regex.Pattern[str]] = regex.compile(r"\^\^(.+?)\^\^", regex.DOTALL)
"""Compiled regex matching Roam highlight syntax ``^^text^^``.

Numbered group (no named groups):

- Group 1 — the highlighted content between the ``^^`` delimiters; may span
  newlines (:data:`regex.DOTALL` is set).
"""

COLOR_BOLD_RE: Final[regex.Pattern[str]] = regex.compile(r"#c:([A-Za-z]+) \*\*(.+?)\*\*")
"""Compiled regex matching a Color Highlighter bold span ``#c:COLOR **text**``.

Numbered groups (no named groups):

- Group 1 — the color name (e.g. ``ORANGE``); ASCII letters only.
- Group 2 — the bold content between the ``**`` delimiters.
"""

COLOR_HIGHLIGHT_RE: Final[regex.Pattern[str]] = regex.compile(r"#c:([A-Za-z]+) \^\^(.+?)\^\^")
"""Compiled regex matching a Color Highlighter highlight span ``#c:COLOR ^^text^^``.

Numbered groups (no named groups):

- Group 1 — the color name (e.g. ``ORANGE``); ASCII letters only.
- Group 2 — the highlighted content between the ``^^`` delimiters.
"""

COLOR_UNDERLINE_RE: Final[regex.Pattern[str]] = regex.compile(r"#c:([A-Za-z]+) __(.+?)__")
"""Compiled regex matching a Color Highlighter underline span ``#c:COLOR __text__``.

Numbered groups (no named groups):

- Group 1 — the color name (e.g. ``ORANGE``); ASCII letters only.
- Group 2 — the underlined content between the ``__`` delimiters.
"""

COLOR_BOX_RE: Final[regex.Pattern[str]] = regex.compile(r"#c:([A-Za-z]+) ~~(.+?)~~")
"""Compiled regex matching a Color Highlighter box span ``#c:COLOR ~~text~~``.

Numbered groups (no named groups):

- Group 1 — the color name (e.g. ``ORANGE``); ASCII letters only.
- Group 2 — the boxed content between the ``~~`` delimiters.
"""

BG_COLOR_LINE_RE: Final[regex.Pattern[str]] = regex.compile(r"^(.*) #\.bg-([A-Za-z]+)$", regex.DOTALL)
"""Compiled regex matching a Color Highlighter whole-line background span ``text #.bg-COLOR``.

The ``#.bg-COLOR`` suffix appears at the end of a block string to apply a
background color to the entire line.  :data:`regex.DOTALL` is set so that
group 1 can span newlines in multi-line blocks.

Numbered groups (no named groups):

- Group 1 — all content preceding the ``#.bg-COLOR`` suffix.
- Group 2 — the color name (e.g. ``ORANGE``); ASCII letters only.
"""
