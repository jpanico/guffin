"""Canonical classification glyphs — the single source of truth for semantic and badge glyphs across formats.

A vertex classified by the :class:`~guffin.model.vertex_view.VertexView` overlay renders its
classification as a glyph, declared once here per member: a
:class:`~guffin.model.vertex_view.Semantic` renders as a *bullet glyph* shown in place of the
list marker, and a :class:`~guffin.model.vertex_view.SourceChannel` renders as a *badge glyph*
leading the content.  Every output format draws on these declarations, so a given
classification looks the same everywhere.

Public symbols:

- **Constants**: :data:`BULLET_GLYPH_BY_SEMANTIC` — the canonical ``Semantic`` → bullet-glyph
  map (covers every member); :data:`BADGE_GLYPH_BY_SOURCE_CHANNEL` — the canonical
  ``SourceChannel`` → badge-glyph map (covers every member); :data:`DEFAULT_BULLET_GLYPH` — the
  plain bullet glyph for an unclassified item listed among classified ones.
"""

from collections.abc import Mapping
from typing import Final

from guffin.model.vertex_view import Semantic, SourceChannel

BULLET_GLYPH_BY_SEMANTIC: Final[Mapping[Semantic, str]] = {
    Semantic.DEFINITION: "=",
    Semantic.LEADS_TO: "→",
    Semantic.RESULT: "⇒",
    Semantic.QUESTION: "?",
    Semantic.IDEA: "+",
    Semantic.COROLLARY: "⤷",
    Semantic.WARNING: "!",
    Semantic.CONTRAST: "≠",
    Semantic.EVIDENCE: "▸",
    Semantic.CONCLUSION: "∴",
    Semantic.HYPOTHESIS: "◊",
    Semantic.DEPENDS_ON: "↤",
    Semantic.DECISION: "⎇",
    Semantic.REFERENCE: "↗",
    Semantic.PROCESS: "↻",
}
"""Canonical bullet glyph per :class:`~guffin.model.vertex_view.Semantic`; covers every member.

The glyph renders in place of a classified list item's marker.
"""

BADGE_GLYPH_BY_SOURCE_CHANNEL: Final[Mapping[SourceChannel, str]] = {
    SourceChannel.CALENDAR_EVENT: "📅",
    SourceChannel.EMAIL: "📨",
    SourceChannel.VOICE_CALL: "📞",
    SourceChannel.CHAT_MESSAGE: "💬",
    SourceChannel.POSTAL_MAIL: "📪",
    SourceChannel.SLACK: "＃",
}
"""Canonical badge glyph per :class:`~guffin.model.vertex_view.SourceChannel`; covers every member.

The glyph leads a classified item's content, decorating it rather than replacing its marker.
"""

DEFAULT_BULLET_GLYPH: Final[str] = "•"
"""The plain bullet glyph for an unclassified item listed among classified siblings.

A format that replaces a classified list's native markers with explicit glyphs (so a
:data:`BULLET_GLYPH_BY_SEMANTIC` glyph can stand where the marker was) renders unclassified
items in the same list with this glyph, keeping the run visually one uniform list.
"""
