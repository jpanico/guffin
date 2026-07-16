"""Custom ``x-guffin`` URL scheme for links between vertices.

Inline content can point at a vertex using a URL in the ``x-guffin`` scheme.
Two link kinds are distinguished by the URL path stem:

- **Reference** — ``x-guffin:vertex/<uid>``.  The anchor carries only the
  destination's UID; the rest of the destination is obtained by *following* the
  link.  These are the semantics of an HTTP hyperlink, a Roam page reference, or
  a Roam block reference.
- **Embed** — ``x-guffin:vertex-embed/<uid>``.  The destination's contents are
  included/substituted at the anchor point, like a ``#include``.  These are the
  semantics of a Roam block embed.

Public symbols:

- :data:`GUFFIN_SCHEME` — the ``x-guffin`` URL scheme literal.
- :class:`VertexLinkKind` — the two link kinds and the URL path stems encoding
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
"""

import enum
from typing import Final, NamedTuple

import regex
from pydantic import validate_call

from guffin.model.primitives import UID_PATTERN, Uid

GUFFIN_SCHEME: Final[str] = "x-guffin"
"""The custom URL scheme identifying a link to a guffin vertex."""


class VertexLinkKind(enum.StrEnum):
    """A guffin vertex-link kind, whose value is the URL path stem that encodes it.

    Attributes:
        REFERENCE: A pointer that must be *followed* to resolve the destination
            (``vertex`` path stem); HTTP / Roam page-ref / Roam block-ref
            semantics.
        EMBED: A pointer whose destination contents are substituted at the
            anchor point (``vertex-embed`` path stem); Roam block-embed
            semantics.
    """

    REFERENCE = "vertex"
    EMBED = "vertex-embed"

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
        kind: Whether the link is a reference or an embed.
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
``[<display>](<x-guffin-url>)`` form is what a solo Roam ``((uid))`` / ``[[Page]]``
reference transcribes to; the URL chunk is :data:`_VERTEX_LINK_URL_RE` itself, so the two
encodings cannot drift (shape only — the stem still needs
:meth:`VertexLinkKind.by_path_stem` validation, the parse function's job).  The display
is matched with DOTALL because a reference's display reproduces the destination's whole
raw string, which may span paragraphs.
"""


@validate_call
def vertex_link_url(uid: Uid, kind: VertexLinkKind) -> str:
    """Build an ``x-guffin`` URL pointing at the vertex identified by *uid*.

    Args:
        uid: The destination vertex's UID.
        kind: Whether to build a reference or an embed link.

    Returns:
        The ``x-guffin`` URL — ``x-guffin:vertex/<uid>`` for a reference or
        ``x-guffin:vertex-embed/<uid>`` for an embed.
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
    canonical text encoding of a :class:`VertexLink` — the form a Roam reference or embed
    transcribes to.  Recognition is **structural**, from that shape
    (:data:`_STANDALONE_VERTEX_LINK_MD_RE`), rather than by a Markdown inline parse: a link
    whose display reproduces a multi-paragraph destination cannot be parsed as a single
    Markdown inline, but is still exactly one vertex link.

    A matched text whose display contains a further ``x-guffin`` URL is rejected — not as
    part of the *standalone* definition, but as an ambiguity guard: a display reproduces its
    destination's raw text, so one carrying a vertex-link URL is structurally
    indistinguishable from a mis-bracketed match whose greedy display swallowed the real
    link, and the parse cannot be trusted.

    Args:
        text: The text to parse.

    Returns:
        The :class:`VertexLink` when *text* is a standalone well-formed vertex link — nothing
        before or after it, a valid ``x-guffin`` URL (per :func:`parse_vertex_link`), and no
        further ``x-guffin`` URL inside the display text; ``None`` in every other case,
        including a link mixed with surrounding text.
    """
    match: Final[regex.Match[str] | None] = _STANDALONE_VERTEX_LINK_MD_RE.fullmatch(text)
    if match is None or f"{GUFFIN_SCHEME}:" in match.group("display"):
        return None
    return parse_vertex_link(match.group("url"))
