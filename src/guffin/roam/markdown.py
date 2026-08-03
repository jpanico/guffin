"""Roam Research Markdown constructs: inline and block-level pattern constants and accessors.

Public symbols:

- **Pattern constants**: :data:`FIRESTORE_URL_RE` — compiled regex matching a Cloud Firestore
  storage URL, the single URL form of every Roam-managed asset; :data:`IMAGE_LINK_RE` — compiled
  regex matching a Roam markdown image link whose URL is a Cloud Firestore storage URL;
  :data:`PDF_EMBED_RE` — compiled regex matching
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
- **Pattern fragments**: :data:`FIRESTORE_URL_PATTERN` — the canonical Cloud Firestore storage
  URL form, the building block of every asset-bearing construct pattern (:data:`IMAGE_LINK_RE`,
  :data:`PDF_EMBED_RE`); :data:`SLUG` — a short restricted token (letters, digits, underscore,
  hyphen, em-dash), reused as a building block of larger patterns such as :data:`TAG_RE`;
  :data:`COLOR_TAG_PATTERN` — a Color Highlighter color tag ``#c:COLOR``, the building block of
  the ``COLOR_*_RE`` span patterns; :data:`INLINE_STYLE_DELIMITER_PATTERN` — any one Roam
  inline-styling delimiter, derived from :data:`INLINE_STYLE_DELIMITERS`.
- **Delimiter constants**: :data:`BOLD_DELIMITER` / :data:`ITALIC_DELIMITER` /
  :data:`HIGHLIGHT_DELIMITER` / :data:`STRIKETHROUGH_DELIMITER` — Roam's four inline-styling
  delimiters, declared once and composed into every pattern that spells them;
  :data:`INLINE_STYLE_DELIMITERS` — the four in one tuple.
- **Image-link accessors**: :func:`image_link_url`, :func:`image_link_alt_text` — extract the Cloud
  Firestore URL and the alt text from the first image link in a block string.
- **PDF-embed accessor**: :func:`pdf_embed_url` — extract the Cloud Firestore URL from the first
  PDF component in a block string.
- **Table marker**: :data:`ROAM_NATIVE_TABLE_RAW_MARKER` — the canonical block string identifying a Roam
  native table block; :data:`ROAM_NATIVE_TABLE_REF_MARKER` — the page-reference spelling of the marker;
  :data:`ROAM_NATIVE_TABLE_MARKERS` — every recognised spelling of the marker
  (``{{table}}`` and ``{{[[table]]}}``).
"""

from typing import Final

import regex
from pydantic import validate_call

from guffin.roam.primitives import SYNTHETIC_UID_PATTERN

ROAM_NATIVE_TABLE_RAW_MARKER: Final[str] = "{{table}}"
"""The canonical block string identifying a Roam native table block.

A block whose :attr:`~guffin.roam.node.RoamNode.string` (after stripping surrounding
whitespace) is one of :data:`ROAM_NATIVE_TABLE_MARKERS` is a Roam native table container;
its child blocks form the rows, and each child's children are the cells.
"""

ROAM_NATIVE_TABLE_REF_MARKER: Final[str] = "{{[[table]]}}"
"""The page-reference spelling of the Roam native table marker.

Equivalent to :data:`ROAM_NATIVE_TABLE_RAW_MARKER`, with the component name written as a Roam
page reference (``[[table]]``) rather than bare text.
"""

ROAM_NATIVE_TABLE_MARKERS: Final[frozenset[str]] = frozenset(
    {ROAM_NATIVE_TABLE_RAW_MARKER, ROAM_NATIVE_TABLE_REF_MARKER}
)
"""Every recognised spelling of the Roam native table marker.

Roam writes the component as either the bare :data:`ROAM_NATIVE_TABLE_RAW_MARKER` form
(``{{table}}``) or the page-reference :data:`ROAM_NATIVE_TABLE_REF_MARKER` form
(``{{[[table]]}}``); the two are equivalent.
"""

FIRESTORE_URL_PATTERN: Final[str] = (
    r"https://firebasestorage\.googleapis\.com"
    r"/v0/b/(?P<bucket>[\w.-]+)"
    r"/o/(?P<object_path>[\w%.-]+)"
    r"\?(?P<query>[\w=&%.-]+)"
)
"""Pattern: the canonical form of a Cloud Firestore storage URL — the single URL form of every Roam-managed asset.

Roam stores every managed asset binary (image, PDF, or any other uploaded file) in Cloud
Firestore and addresses it with one URL shape::

    https://firebasestorage.googleapis.com/v0/b/<bucket>/o/<object_path>?<query>

- ``bucket`` — the storage bucket (host-like: word characters, dots, hyphens).
- ``object_path`` — the percent-encoded object path.  Roam generates the path segments itself
  (e.g. ``imgs%2Fapp%2F<graph>%2F<uid>.<ext>[.enc]``), so the charset is deliberately tight:
  word characters, percent escapes, dots, and hyphens.  The decoded path's last segment is the
  asset's stored filename.
- ``query`` — the access parameters (``alt=media&token=<uuid>``).

The tight charsets make the pattern **self-terminating**: it never overruns a Markdown or Roam
component delimiter (``)``, ``}}``, whitespace), so host patterns embed it verbatim with no
context-specific exclusions — the asset-bearing constructs (:data:`IMAGE_LINK_RE`,
:data:`PDF_EMBED_RE`) differ only in the chrome wrapped around this one fragment.  Compiled
standalone as :data:`FIRESTORE_URL_RE`.

Named groups: ``bucket``, ``object_path``, ``query``.
"""

FIRESTORE_URL_RE: Final[regex.Pattern[str]] = regex.compile(FIRESTORE_URL_PATTERN)
"""Compiled regex matching a Cloud Firestore storage URL (:data:`FIRESTORE_URL_PATTERN`).

Named groups:

- ``bucket`` — the storage bucket.
- ``object_path`` — the percent-encoded object path after ``/o/``.
- ``query`` — the query string after ``?``.

Example match on
``https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2Fabc.jpeg?alt=media&token=…``:

- ``match.group(0)`` — the full URL.
- ``match.group("object_path")`` — ``imgs%2Fapp%2FSCFH%2Fabc.jpeg``.
"""

IMAGE_LINK_RE: Final[regex.Pattern[str]] = regex.compile(
    rf"!\[(?P<alt>(?:[^\]]|\n)*?)\]\((?P<url>{FIRESTORE_URL_PATTERN})\)"
)
"""Compiled regex matching a Roam markdown image link whose URL is a Cloud Firestore storage URL.

A standard Markdown image reference (``![<alt>](<url>)``) whose URL is the canonical
:data:`FIRESTORE_URL_PATTERN` — an image is ordinary Markdown chrome around the one Roam
asset-URL form.

Named groups:

- ``alt`` — the alt-text content between ``[`` and ``]`` (may be empty or multi-line).
- ``url`` — the Cloud Firestore storage URL between ``(`` and ``)`` (plus the pattern's own
  ``bucket``/``object_path``/``query`` groups).

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


PDF_EMBED_RE: Final[regex.Pattern[str]] = regex.compile(
    rf"\{{\{{(?:pdf|\[\[pdf\]\]): (?P<url>{FIRESTORE_URL_PATTERN})\}}\}}"
)
"""Compiled regex matching a Roam PDF component whose URL is a Cloud Firestore storage URL.

PDF-specific chrome around the canonical :data:`FIRESTORE_URL_PATTERN`: Roam writes the
component as either the bare form (``{{pdf: <url>}}``) or the page-reference form
(``{{[[pdf]]: <url>}}``); the two are equivalent.  Exactly one space follows the colon,
mirroring the block-embed component (:data:`BLOCK_EMBED_RE`).

Named group:

- ``url`` — the Cloud Firestore storage URL between the colon and the closing ``}}`` (plus the
  pattern's own ``bucket``/``object_path``/``query`` groups).

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

BOLD_DELIMITER: Final[str] = "**"
"""Roam's bold delimiter: ``**text**``."""

ITALIC_DELIMITER: Final[str] = "__"
"""Roam's italic delimiter: ``__text__`` (double underscores, not single)."""

HIGHLIGHT_DELIMITER: Final[str] = "^^"
"""Roam's highlight delimiter: ``^^text^^``."""

STRIKETHROUGH_DELIMITER: Final[str] = "~~"
"""Roam's strikethrough delimiter: ``~~text~~``."""

INLINE_STYLE_DELIMITERS: Final[tuple[str, ...]] = (
    BOLD_DELIMITER,
    ITALIC_DELIMITER,
    HIGHLIGHT_DELIMITER,
    STRIKETHROUGH_DELIMITER,
)
"""Every Roam inline-styling delimiter, in one tuple."""

INLINE_STYLE_DELIMITER_PATTERN: Final[str] = "|".join(regex.escape(delimiter) for delimiter in INLINE_STYLE_DELIMITERS)
"""Regex pattern matching any one Roam inline-styling delimiter.

An alternation derived from :data:`INLINE_STYLE_DELIMITERS`, each member regex-escaped.
"""

COLOR_TAG_PATTERN: Final[str] = r"#c:([A-Za-z]+)"
"""Regex pattern matching a Color Highlighter color tag ``#c:COLOR``.

Numbered group (no named groups):

- Group 1 — the color name (e.g. ``ORANGE``); ASCII letters only.
"""

_BOLD: Final[str] = regex.escape(BOLD_DELIMITER)
_ITALIC: Final[str] = regex.escape(ITALIC_DELIMITER)
_HIGHLIGHT: Final[str] = regex.escape(HIGHLIGHT_DELIMITER)
_STRIKETHROUGH: Final[str] = regex.escape(STRIKETHROUGH_DELIMITER)

ITALIC_RE: Final[regex.Pattern[str]] = regex.compile(
    rf"(?<!\w){_ITALIC}(?!\s)(.+?)(?<!\s){_ITALIC}(?!\w)", regex.DOTALL
)
"""Compiled regex matching Roam italic syntax ``__text__``.

Roam uses double underscores for italics.  Negative look-behind and look-ahead
prevent matching adjacent to word characters, and look-ahead/behind on the
inner boundary prevent matching when the delimited content begins or ends with
whitespace.

Numbered group (no named groups):

- Group 1 — the italic content between the ``__`` delimiters; may span newlines
  (:data:`regex.DOTALL` is set).
"""

HIGHLIGHT_RE: Final[regex.Pattern[str]] = regex.compile(rf"{_HIGHLIGHT}(.+?){_HIGHLIGHT}", regex.DOTALL)
"""Compiled regex matching Roam highlight syntax ``^^text^^``.

Numbered group (no named groups):

- Group 1 — the highlighted content between the ``^^`` delimiters; may span
  newlines (:data:`regex.DOTALL` is set).
"""

COLOR_BOLD_RE: Final[regex.Pattern[str]] = regex.compile(rf"{COLOR_TAG_PATTERN} ( *){_BOLD}(.+?){_BOLD}")
"""Compiled regex matching a Color Highlighter bold span ``#c:COLOR **text**``.

The first space after the color name is the tag separator; a longer whitespace run still
matches, with the additional spaces captured separately (group 2).

Numbered groups (no named groups):

- Group 1 — the color name (e.g. ``ORANGE``); ASCII letters only.
- Group 2 — any spaces beyond the single separator space (may be empty).
- Group 3 — the bold content between the ``**`` delimiters.
"""

COLOR_HIGHLIGHT_RE: Final[regex.Pattern[str]] = regex.compile(rf"{COLOR_TAG_PATTERN} ( *){_HIGHLIGHT}(.+?){_HIGHLIGHT}")
"""Compiled regex matching a Color Highlighter highlight span ``#c:COLOR ^^text^^``.

The first space after the color name is the tag separator; a longer whitespace run still
matches, with the additional spaces captured separately (group 2).

Numbered groups (no named groups):

- Group 1 — the color name (e.g. ``ORANGE``); ASCII letters only.
- Group 2 — any spaces beyond the single separator space (may be empty).
- Group 3 — the highlighted content between the ``^^`` delimiters.
"""

COLOR_UNDERLINE_RE: Final[regex.Pattern[str]] = regex.compile(rf"{COLOR_TAG_PATTERN} ( *){_ITALIC}(.+?){_ITALIC}")
"""Compiled regex matching a Color Highlighter underline span ``#c:COLOR __text__``.

The first space after the color name is the tag separator; a longer whitespace run still
matches, with the additional spaces captured separately (group 2).

Numbered groups (no named groups):

- Group 1 — the color name (e.g. ``ORANGE``); ASCII letters only.
- Group 2 — any spaces beyond the single separator space (may be empty).
- Group 3 — the underlined content between the ``__`` delimiters.
"""

COLOR_BOX_RE: Final[regex.Pattern[str]] = regex.compile(
    rf"{COLOR_TAG_PATTERN} ( *){_STRIKETHROUGH}(.+?){_STRIKETHROUGH}"
)
"""Compiled regex matching a Color Highlighter box span ``#c:COLOR ~~text~~``.

The first space after the color name is the tag separator; a longer whitespace run still
matches, with the additional spaces captured separately (group 2).

Numbered groups (no named groups):

- Group 1 — the color name (e.g. ``ORANGE``); ASCII letters only.
- Group 2 — any spaces beyond the single separator space (may be empty).
- Group 3 — the boxed content between the ``~~`` delimiters.
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
