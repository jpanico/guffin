"""Custom ``x-guffin`` URL scheme for links between vertices.

Inline content can point at a vertex using a URL in the ``x-guffin`` scheme.
Three link kinds are distinguished by the URL path stem:

- **Reference** — ``x-guffin:vertex/<uid>``.  The anchor carries only the
  destination's UID; the rest of the destination is obtained by *following* the
  link.  These are the semantics of an HTTP hyperlink, or of a source graph's
  page and block references.
- **Embed** — ``x-guffin:vertex-embed/<uid>``.  The destination's contents are
  included/substituted at the anchor point, like a ``#include``.  These are the
  semantics of a source graph's block embed (transclusion).
- **Note** — ``x-guffin:vertex-note/<uid>``.  The link's display text is the
  *lead-in* of a note: a phrase of the running text that the destination vertex
  annotates.  The destination is the note, set apart from the running text; the
  display text stays in the running text.

Public symbols:

- :data:`GUFFIN_SCHEME` — the ``x-guffin`` URL scheme literal.
- :data:`ALIAS_CLASS` — the class marking a vertex link whose display is the author's own
  words (an alias) rather than the destination's content.
- :class:`VertexLinkKind` — the three link kinds and the URL path stems encoding
  them.
- :class:`VertexLink` — a parsed ``x-guffin`` link: its kind and destination
  UID.
- :func:`vertex_link_url` — build an ``x-guffin`` URL from a UID and kind.
- :func:`parse_vertex_link` — parse an ``x-guffin`` URL into a
  :class:`VertexLink`, or ``None`` when the string is not such a URL.
- :func:`is_vertex_link` — whether a string is an ``x-guffin`` vertex-link URL.
- :func:`parse_standalone_vertex_link` — parse a text that is a *standalone*
  Pandoc-Markdown-form vertex link (``[<display>](<x-guffin-url>)`` as the text's
  entire content) into its :class:`VertexLink`, or ``None`` when the text is
  anything else.
- :func:`vertex_links_in_text` — every Pandoc-Markdown-form vertex link anywhere in a
  text, as ``(display, VertexLink)`` pairs in text order.
- :func:`vertex_link_spans` — the same links, each with the character range it occupies, so a
  text can be rewritten around them.
"""

import enum
from typing import Final, NamedTuple

import regex
from pydantic import validate_call

from guffin.model.primitives import UID_PATTERN, Uid

GUFFIN_SCHEME: Final[str] = "x-guffin"
"""The custom URL scheme identifying a link to a guffin vertex."""

ALIAS_CLASS: Final[str] = "vertex-alias"
"""The class marking a vertex link whose display is the author's own words — an alias.

A reference ordinarily displays its destination's content; an alias displays words the author
chose for it instead (``see figure``, ``the diagram above``), and keeps them.  The Pandoc-Markdown
form carries the class after the link: ``[<display>](<x-guffin-url>){.vertex-alias}``.  The
trailing class also keeps an alias from ever being a *standalone* vertex link
(:func:`parse_standalone_vertex_link`): an alias is words in the running text, never a display of
its destination, whereas :func:`vertex_links_in_text` still finds it.
"""


class VertexLinkKind(enum.StrEnum):
    """A guffin vertex-link kind, whose value is the URL path stem that encodes it.

    Attributes:
        REFERENCE: A pointer that must be *followed* to resolve the destination
            (``vertex`` path stem); hyperlink / page-reference / block-reference
            semantics.
        EMBED: A pointer whose destination contents are substituted at the
            anchor point (``vertex-embed`` path stem); block-embed
            (transclusion) semantics.
        NOTE: A pointer from a lead-in phrase of the running text to the note
            annotating it (``vertex-note`` path stem); the display text is the
            lead-in and stays in the running text, the destination is the note.
    """

    REFERENCE = "vertex"
    EMBED = "vertex-embed"
    NOTE = "vertex-note"

    @classmethod
    def by_path_stem(cls, stem: str) -> VertexLinkKind | None:
        """Return the kind whose URL path stem is *stem*, or ``None`` if unknown.

        The inverse of :attr:`value`: maps a URL path stem back to its kind.

        Args:
            stem: A URL path stem (e.g. ``vertex``).

        Returns:
            The :class:`VertexLinkKind` whose value is *stem*, or ``None`` when
            no kind uses *stem* as its path stem.
        """
        try:
            return cls(stem)
        except ValueError:
            return None


class VertexLink(NamedTuple):
    """A parsed ``x-guffin`` vertex link.

    Attributes:
        kind: Whether the link is a reference, an embed, or a note.
        uid: The destination vertex's UID.
    """

    kind: VertexLinkKind
    uid: Uid


_VERTEX_LINK_URL_RE: Final[regex.Pattern[str]] = regex.compile(
    rf"{regex.escape(GUFFIN_SCHEME)}:(?P<stem>[^/]+)/(?P<uid>{UID_PATTERN})"
)
"""The URL encoding of a :class:`VertexLink` — the string :func:`vertex_link_url` emits.

The scheme literal, a path stem (any non-slash run, validated against
:meth:`VertexLinkKind.by_path_stem` by the caller), a slash, and a UID.  Named groups:
``stem`` and ``uid``.  Used with ``fullmatch``, so no anchors are needed.
"""


_STANDALONE_VERTEX_LINK_MD_RE: Final[regex.Pattern[str]] = regex.compile(
    rf"\A\[(?P<display>.*)\]\((?P<url>{_VERTEX_LINK_URL_RE.pattern})\)\Z", regex.DOTALL
)
"""A text that is a *standalone* Pandoc-Markdown-form vertex link: nothing but the link.

**Standalone** means the link is the text's entire content — the ``\\A``/``\\Z`` anchors
encode that, so the pattern's language is standalone-link texts regardless of how it is
matched.  The
``[<display>](<x-guffin-url>)`` form is what a solo source reference (a lone block or
page reference) transcribes to; the URL chunk is :data:`_VERTEX_LINK_URL_RE` itself, so the two
encodings cannot drift (shape only — the stem still needs
:meth:`VertexLinkKind.by_path_stem` validation, the parse function's job).  The display
is matched with DOTALL because a reference's display reproduces the destination's whole
raw string, which may span paragraphs.
"""


_IN_TEXT_VERTEX_LINK_MD_RE: Final[regex.Pattern[str]] = regex.compile(
    rf"\[(?P<display>[^\[\]]*)\]\((?P<url>{_VERTEX_LINK_URL_RE.pattern})\)"
)
"""A Pandoc-Markdown-form vertex link anywhere in a text, its display free of square brackets.

The in-text sibling of :data:`_STANDALONE_VERTEX_LINK_MD_RE`: the same ``[<display>](<x-guffin-url>)``
form with :data:`_VERTEX_LINK_URL_RE` as its URL chunk, so the encodings cannot drift (shape only —
the stem still needs :meth:`VertexLinkKind.by_path_stem` validation).  Unanchored, so it finds
every link in a text.  A link whose display contains square brackets (such as a reference whose
display reproduces a destination's raw text) is not matched.
"""


@validate_call
def vertex_link_url(uid: Uid, kind: VertexLinkKind) -> str:
    """Build an ``x-guffin`` URL pointing at the vertex identified by *uid*.

    Args:
        uid: The destination vertex's UID.
        kind: Whether to build a reference, an embed, or a note link.

    Returns:
        The ``x-guffin`` URL — ``x-guffin:vertex/<uid>`` for a reference,
        ``x-guffin:vertex-embed/<uid>`` for an embed, or ``x-guffin:vertex-note/<uid>``
        for a note.
    """
    return f"{GUFFIN_SCHEME}:{kind.value}/{uid}"


@validate_call
def parse_vertex_link(url: str) -> VertexLink | None:
    """Parse an ``x-guffin`` vertex-link URL into its kind and destination UID.

    Args:
        url: The string to parse.

    Returns:
        A :class:`VertexLink` when *url* is a well-formed ``x-guffin`` vertex
        link — the ``x-guffin`` scheme, a recognised path stem, and a valid
        UID (synthetic or daily-note) — and ``None`` otherwise.
    """
    match: Final[regex.Match[str] | None] = _VERTEX_LINK_URL_RE.fullmatch(url)
    if match is None:
        return None
    kind: Final[VertexLinkKind | None] = VertexLinkKind.by_path_stem(match.group("stem"))
    if kind is None:
        return None
    return VertexLink(kind=kind, uid=match.group("uid"))


@validate_call
def is_vertex_link(url: str) -> bool:
    """Return whether *url* is a well-formed ``x-guffin`` vertex-link URL.

    Args:
        url: The string to test.

    Returns:
        ``True`` if *url* parses as a :class:`VertexLink` (see
        :func:`parse_vertex_link`); ``False`` otherwise.
    """
    return parse_vertex_link(url) is not None


@validate_call
def parse_standalone_vertex_link(text: str) -> VertexLink | None:
    """Parse a text that is a *standalone* Pandoc-Markdown-form vertex link.

    **Standalone** means the link is the text's entire content — the text displays nothing
    but the link.  The Pandoc-Markdown link form ``[<display>](<x-guffin-url>)`` is the
    canonical text encoding of a :class:`VertexLink` — the form a source reference or embed
    transcribes to.  Recognition is **structural**, from that shape
    (:data:`_STANDALONE_VERTEX_LINK_MD_RE`), rather than by a Markdown inline parse: a link
    whose display reproduces a multi-paragraph destination cannot be parsed as a single
    Markdown inline, but is still exactly one vertex link.

    A matched text whose display contains a further ``x-guffin`` URL is rejected — not as
    part of the *standalone* definition, but as an ambiguity guard: a display reproduces its
    destination's raw text, so one carrying a vertex-link URL is structurally
    indistinguishable from a mis-bracketed match whose greedy display swallowed the real
    link, and the parse cannot be trusted.  So is a text whose opening ``[`` closes before the
    link's own ``](`` — a bracketed span followed by more text and a link at the end, such as
    ``[label]{color="red"} see [figure](<x-guffin-url>)``: the link is inline there, not the
    text's entire content.

    Args:
        text: The text to parse.

    Returns:
        The :class:`VertexLink` when *text* is a standalone well-formed vertex link — nothing
        before or after it, a valid ``x-guffin`` URL (per :func:`parse_vertex_link`), no
        further ``x-guffin`` URL inside the display text, and an opening bracket that stays
        open to the link's end; ``None`` in every other case, including a link mixed with
        surrounding text.
    """
    match: Final[regex.Match[str] | None] = _STANDALONE_VERTEX_LINK_MD_RE.fullmatch(text)
    if match is None or f"{GUFFIN_SCHEME}:" in match.group("display"):
        return None
    if not _display_stays_open(match.group("display")):
        return None
    return parse_vertex_link(match.group("url"))


def _display_stays_open(display: str) -> bool:
    """Return whether the text's opening ``[`` is still open everywhere in *display*.

    The standalone pattern takes the text's first ``[`` as the link's opening bracket and its
    last ``](`` as the closing one.  That holds only when no ``]`` inside *display* closes the
    opening bracket early: a text such as ``[styled label]{attrs} see [word](url)`` has a
    bracketed span first and a link at its end, and its greedy display swallows the span's
    closing bracket.  A bracket escaped with a backslash is literal text and counts for nothing.
    """
    depth: int = 0
    escaped: bool = False
    for char in display:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth < 0:
                return False
    return True


@validate_call
def vertex_links_in_text(text: str) -> list[tuple[str, VertexLink]]:
    """Return every Pandoc-Markdown-form vertex link in *text*, with its display text, in text order.

    Finds each ``[<display>](<x-guffin-url>)`` link wherever it sits in *text*, keeping those whose
    URL parses as a :class:`VertexLink` (per :func:`parse_vertex_link`).  A link whose display
    contains square brackets is not found.

    Args:
        text: The text to search.

    Returns:
        One ``(display, link)`` pair per vertex link; empty when *text* has none.
    """
    return [(display, link) for _start, _end, display, link in vertex_link_spans(text)]


@validate_call
def vertex_link_spans(text: str) -> list[tuple[int, int, str, VertexLink]]:
    """Return every Pandoc-Markdown-form vertex link in *text* with where it lies, in text order.

    The located counterpart of :func:`vertex_links_in_text`: the same links, each with the half-open
    range ``[start, end)`` of characters its ``[<display>](<x-guffin-url>)`` form occupies in *text*.

    Args:
        text: The text to search.

    Returns:
        One ``(start, end, display, link)`` tuple per vertex link; empty when *text* has none.
    """
    return [
        (match.start(), match.end(), match.group("display"), link)
        for match in _IN_TEXT_VERTEX_LINK_MD_RE.finditer(text)
        if (link := parse_vertex_link(match.group("url"))) is not None
    ]
