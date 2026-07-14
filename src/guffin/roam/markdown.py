"""Roam Research Markdown constructs: inline and block-level pattern constants and accessors.

Public symbols:

- **Pattern constants**: :data:`IMAGE_LINK_RE` — compiled regex matching a Roam markdown image
  link whose URL is a Cloud Firestore storage URL; :data:`PDF_EMBED_RE` — compiled regex matching
  a Roam PDF component ``{{pdf: <url>}}`` (or ``{{[[pdf]]: <url>}}``) whose URL is a Cloud
  Firestore storage URL; :data:`PAGE_REF_RE` — compiled regex matching
  a Roam page reference ``[[<page_name>]]``; :data:`TAG_RE` — compiled regex matching a Roam tag
  in either page-reference (``#[[…]]``) or bare-word (``#word``) form; :data:`ATTRIBUTE_ASSIGNMENT_RE`
  — compiled regex matching a line-anchored Roam attribute assignment ``attribute:: value, …``;
  :data:`BLOCK_REF_RE` — compiled regex matching a
  Roam block reference ``((<uid>))``; :data:`BLOCK_EMBED_RE` — compiled regex matching a Roam
  block embed ``{{embed: ((<uid>))}}`` (or ``{{[[embed]]: ((<uid>))}}``); :data:`PAGE_EMBED_RE` —
  compiled regex matching a Roam page embed ``{{embed: [[<page_name>]]}}`` (or
  ``{{[[embed]]: [[<page_name>]]}}``); :data:`PAGE_LINK_ALIAS_RE` — compiled regex matching a
  Roam aliased page link ``[display]([[Page Name]])``; :data:`ITALIC_RE` — compiled regex
  matching Roam italic syntax ``__text__``; :data:`HIGHLIGHT_RE` — compiled regex matching Roam
  highlight syntax ``^^text^^``; :data:`COLOR_BOLD_RE`, :data:`COLOR_HIGHLIGHT_RE`,
  :data:`COLOR_UNDERLINE_RE`, :data:`COLOR_BOX_RE`, :data:`BG_COLOR_LINE_RE` — compiled regexes
  for the five Color Highlighter inline and block-level color constructs.
- **Pattern fragments**: :data:`SLUG` — a short restricted token (letters, digits, underscore,
  hyphen, em-dash), reused as a building block of larger patterns such as :data:`TAG_RE`.
- **Image-link accessors**: :func:`image_link_url`, :func:`image_link_alt_text` — extract the Cloud
  Firestore URL and the alt text from the first image link in a block string;
  :func:`firestore_url_file_name` — decode the original filename from a Firestore storage URL.
- **PDF-embed accessor**: :func:`pdf_embed_url` — extract the Cloud Firestore URL from the first
  PDF component in a block string.
- **Table marker**: :data:`ROAM_NATIVE_TABLE_MARKER` — the canonical block string identifying a Roam
  native table block; :data:`ROAM_NATIVE_TABLE_MARKERS` — every recognised spelling of the marker
  (``{{table}}`` and ``{{[[table]]}}``).
"""

from typing import Final
from urllib.parse import unquote, urlparse

import regex
from pydantic import validate_call

from guffin.roam.primitives import SYNTHETIC_UID_PATTERN

ROAM_NATIVE_TABLE_MARKER: Final[str] = "{{table}}"
"""The canonical block string identifying a Roam native table block.

A block whose :attr:`~guffin.roam.node.RoamNode.string` (after stripping surrounding
whitespace) is one of :data:`ROAM_NATIVE_TABLE_MARKERS` is a Roam native table container;
its child blocks form the rows, and each child's children are the cells.
"""

ROAM_NATIVE_TABLE_MARKERS: Final[frozenset[str]] = frozenset({ROAM_NATIVE_TABLE_MARKER, "{{[[table]]}}"})
"""Every recognised spelling of the Roam native table marker.

Roam writes the component as either the bare :data:`ROAM_NATIVE_TABLE_MARKER` form
(``{{table}}``) or the page-reference form (``{{[[table]]}}``); the two are equivalent.
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


PDF_EMBED_RE: Final[regex.Pattern[str]] = regex.compile(
    r"\{\{(?:pdf|\[\[pdf\]\]): (?P<url>https://firebasestorage\.googleapis\.com/[^\}\s]+)\}\}"
)
"""Compiled regex matching a Roam PDF component whose URL is a Cloud Firestore storage URL.

Roam writes the component as either the bare form (``{{pdf: <url>}}``) or the page-reference
form (``{{[[pdf]]: <url>}}``); the two are equivalent.  Exactly one space follows the colon,
mirroring the block-embed component (:data:`BLOCK_EMBED_RE`).

Named group:

- ``url`` — the Cloud Firestore storage URL between the colon and the closing ``}}``.

Example match on ``{{pdf: https://firebasestorage.googleapis.com/v0/b/...}}``:

- ``match.group(0)`` — the full ``{{pdf: ...}}`` component.
- ``match.group("url")`` — just the URL.
"""


@validate_call
def pdf_embed_url(string: str) -> str | None:
    """Return the Cloud Firestore storage URL from the first PDF component in *string*, or ``None``.

    Args:
        string: A raw block string that may contain a Roam PDF component
            (``{{pdf: <url>}}`` / ``{{[[pdf]]: <url>}}``).

    Returns:
        The URL string captured from the first Firestore PDF component, or ``None``.
    """
    m: Final[regex.Match[str] | None] = PDF_EMBED_RE.search(string)
    return m.group("url") if m else None


_PAGE_REF_BODY: Final[str] = r"(?:[^\[\]\n]++|(?&page_ref))+"
"""The content between a page reference's ``[[`` and ``]]`` delimiters: a non-empty run of bracket-free.

text interleaved with nested page references.

Recurses the enclosing ``page_ref`` group via ``(?&page_ref)``, so it only resolves inside a pattern
that defines a ``page_ref`` group wrapping it (see :data:`_PAGE_REF` and :data:`ATTRIBUTE_ASSIGNMENT_RE`).
The non-bracket run uses a possessive ``++`` quantifier, which keeps matching linear on long
unterminated input.
"""

_PAGE_REF: Final[str] = rf"(?P<page_ref>\[\[(?P<page_name>{_PAGE_REF_BODY})\]\])"
"""Reusable pattern fragment for a Roam page reference ``[[<page_name>]]``.

Inside the ``[[`` … ``]]`` delimiters a page name is **permissive**: it may contain any characters
except the bracket delimiters and a newline, and it may nest further references.  The whole ``[[…]]``
reference is captured by the named group ``page_ref`` and its inner name (:data:`_PAGE_REF_BODY`) by
``page_name``.

Nesting is expressed by recursing the ``page_ref`` subpattern via ``(?&page_ref)`` — a *named*-group
recursion rather than ``(?R)`` whole-pattern recursion — so the fragment composes correctly when
embedded in a larger pattern such as :data:`TAG_RE` (where ``(?R)`` would wrongly recurse the host
pattern).  Compiled standalone as :data:`PAGE_REF_RE`.
"""

PAGE_REF_RE: Final[regex.Pattern[str]] = regex.compile(_PAGE_REF)
"""Compiled regex matching a Roam page reference ``[[<page_name>]]``.

A page name may itself contain nested page references, so the pattern is recursive: it matches a
balanced ``[[`` … ``]]`` pair via the named-group recursion of :data:`_PAGE_REF` (stdlib :mod:`re`
cannot match balanced nesting).  Within the brackets the name is unrestricted apart from the bracket
delimiters and newlines.

Named groups:

- ``page_ref`` — the full ``[[…]]`` reference; equal to the whole match (``match.group(0)``).
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

SLUG: Final[str] = r"[\p{L}\p{N}_—-]{1,45}"  # letters, digits, underscore, hyphen, em-dash
"""Pattern: a slug — a short, restricted token of 1 to 45 characters.

A slug contains no whitespace and (almost) no punctuation: a run of Unicode letters and digits plus
the three connectors underscore (``_``), hyphen (``-``), and em-dash (``—``).  The 1-to-45-character
upper bound is a Guffin policy limit.
"""

TAG_RE: Final[regex.Pattern[str]] = regex.compile(rf"#(?:{_PAGE_REF}|(?P<bare_page_name>{SLUG}))")
"""Compiled regex matching a Roam tag, in either of its two forms.

A tag opens with ``#`` and is immediately followed by exactly one of:

1. **Bracketed page reference** — a full :data:`PAGE_REF_RE` ``[[…]]`` reference (possibly
   compound/nested, with an unrestricted page name), contributing the ``page_ref`` and ``page_name``
   groups (e.g. ``#[[Better Bullets]]``, ``#[[a [[b]] c]]``, ``#[[Chapter 7: intro]]``).
2. **Bare page name** — the compact bracket-less form, a :data:`SLUG` (letters, digits, underscore,
   hyphen, and em-dash; no whitespace and no other punctuation), captured by the ``bare_page_name``
   group (e.g. ``#Guffin``, ``#some-tag``).

Both forms reference a page; they differ only in how permissive the page name may be.  For a bracketed
tag the ``bare_page_name`` group is ``None``; for a bare tag the ``page_ref`` and ``page_name`` groups
are ``None``.  In both forms ``match.group(0)`` includes the leading ``#``.

Because the bare form admits no whitespace or other punctuation, ``#Guffin,more`` captures only
``Guffin`` (it stops at the comma) and ``#a.b`` captures only ``a`` (it stops at the dot).

Named groups:

- ``page_ref`` — the full ``[[…]]`` reference (form 1); ``None`` for a bare tag.
- ``page_name`` — the referenced page name (form 1); ``None`` for a bare tag.
- ``bare_page_name`` — the bracket-less page name following ``#`` (form 2); ``None`` for a bracketed tag.

Adjacent tags are matched separately; use :meth:`regex.Pattern.finditer` to enumerate every tag in
a string.
"""

_ATTRIBUTE_VALUE: Final[str] = rf"(?P<value>#(?:(?&page_ref)|{SLUG})|{SLUG})"
"""Pattern fragment for one attribute-assignment value, captured by the repeated ``value`` group.

A value is either a tag — ``#`` followed by a page reference or a :data:`SLUG` — or a bare
:data:`SLUG`.  The page reference is reached via ``(?&page_ref)``, so this fragment resolves only
inside a pattern that defines that subroutine (it is embedded solely in :data:`ATTRIBUTE_ASSIGNMENT_RE`).
"""

ATTRIBUTE_ASSIGNMENT_RE: Final[regex.Pattern[str]] = regex.compile(
    rf"(?(DEFINE)(?P<page_ref>\[\[{_PAGE_REF_BODY}\]\]))"
    rf"^(?P<attribute>{SLUG})::[ \t]*"
    rf"(?P<values>{_ATTRIBUTE_VALUE}(?:[ \t]*,[ \t]*{_ATTRIBUTE_VALUE})*)",
    regex.MULTILINE,
)
"""Compiled regex matching a Roam attribute assignment ``<attribute>:: <value>[, <value>]…``.

The assignment is anchored to the start of a line (:data:`regex.MULTILINE` is set so the ``^`` anchor
matches at the start of any line within a multi-line block string).  Structure:

- The **attribute** is a single :data:`SLUG`, terminated by the ``::`` separator.
- The **values** are a comma-separated list of one or more elements, each either a Roam tag (``#`` plus
  a page reference or a :data:`SLUG`, per :data:`TAG_RE`) or a bare :data:`SLUG`.  Whitespace around the
  commas and after ``::`` is permitted and not captured.

A capture-free, recursive page-reference subroutine is defined up front via ``(?(DEFINE)…)`` (sharing
:data:`_PAGE_REF_BODY` with :data:`_PAGE_REF`) and invoked from each value with ``(?&page_ref)``; a
``DEFINE`` subroutine is needed because the per-value page reference recurs in a repeated context, where
the named groups of :data:`_PAGE_REF` could not be duplicated.

Named groups:

- ``attribute`` — the attribute name preceding ``::``.
- ``values`` — the whole comma-separated value list following ``::`` (leading whitespace after ``::``
  excluded), including the intervening separators.
- ``value`` — repeated once per list element; enumerate the elements with ``match.captures("value")``.

Example matches:

- ``attribute1:: 5, #[[callouts demo]], #v01`` → ``attribute`` is ``attribute1``; ``captures("value")``
  is ``["5", "#[[callouts demo]]", "#v01"]``.
- ``tags:: #Guffin,#[[Better Bullets]]`` → ``attribute`` is ``tags``; ``captures("value")`` is
  ``["#Guffin", "#[[Better Bullets]]"]``.
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

BLOCK_EMBED_RE: Final[regex.Pattern[str]] = regex.compile(
    rf"\{{\{{(?:embed|\[\[embed\]\]): {BLOCK_REF_RE.pattern}\}}\}}"
)
"""Compiled regex matching a Roam block embed ``{{embed: ((<uid>))}}``.

Wraps a :data:`BLOCK_REF_RE` block reference in the literal ``{{embed: `` and ``}}``
delimiters (note the single space after ``embed:``).  Roam writes the component as either
the bare form (``{{embed: ((<uid>))}}``) or the page-reference form
(``{{[[embed]]: ((<uid>))}}``); the two are equivalent.  The embedded reference's ``uid``
named group is carried through, so the referenced node UID is available on a match.

Named group:

- ``uid`` — the 9-character UID of the embedded block.

Example match on ``{{embed: ((LfXmNr-tV))}}``:

- ``match.group(0)`` — the full ``{{embed: ((LfXmNr-tV))}}`` string.
- ``match.group("uid")`` — just ``LfXmNr-tV``.
"""

PAGE_EMBED_RE: Final[regex.Pattern[str]] = regex.compile(rf"\{{\{{(?:embed|\[\[embed\]\]): {PAGE_REF_RE.pattern}\}}\}}")
"""Compiled regex matching a Roam page embed ``{{embed: [[<page_name>]]}}``.

The page-embed sibling of :data:`BLOCK_EMBED_RE`: it wraps a :data:`PAGE_REF_RE` page reference in
the literal ``{{embed: `` and ``}}`` delimiters (note the single space after ``embed:``) instead of a
block reference.  Roam writes the component as either the bare form (``{{embed: [[<page_name>]]}}``)
or the page-reference form (``{{[[embed]]: [[<page_name>]]}}``); the two are equivalent.  The
embedded reference's ``page_name`` named group is carried through, so the referenced page title is
available on a match (including nested ``[[…]]`` inside the name, via the recursion in
:data:`PAGE_REF_RE`).

Named group:

- ``page_name`` — the title of the embedded page.

Example match on ``{{embed: [[CHAPTER XXXVI. Account of the City of Juju.]]}}``:

- ``match.group(0)`` — the full ``{{embed: [[CHAPTER XXXVI. Account of the City of Juju.]]}}`` string.
- ``match.group("page_name")`` — just ``CHAPTER XXXVI. Account of the City of Juju.``.
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
