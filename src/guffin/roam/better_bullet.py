"""Better Bullets: the marker→bullet vocabulary of the Better Bullets Roam extension.

The **Better Bullets** Roam extension (``mlava/better-bullets``) restyles a block's bullet
when the block's text leads with a recognized marker token: the plain-text *marker* the
author types is displayed as the extension's *bullet* glyph, conveying the block's
rhetorical role (definition, consequence, question, …).  A block can also be badged with
its *provenance* — the source channel its content arrived through (a calendar event, an
email, …) — declared the same way, by a leading marker.

Public symbols:

- **Enumerations**: :class:`BetterBulletType` — the recognized Better Bullets kinds, each
  member carrying its human-readable meaning, its authored marker token, and the bullet
  glyph the extension renders; :class:`BetterBulletProvenance` — the recognized provenance
  kinds, each member carrying its human-readable source, its default marker token, and the
  badge glyph the extension renders.
"""

import enum
from typing import Self


class BetterBulletType(enum.StrEnum):
    """A Better Bullets kind: an authored marker token and the bullet glyph it renders as.

    Each member's string value is its short :attr:`id` — the identifier the extension
    itself persists on a block (the ``type`` entry of the block's property map), so a
    stored identifier resolves to its member by plain value lookup.  The member carries
    the human-readable *meaning* the bullet conveys, the plain-text *marker* token an
    author types at the head of a block, and the *bullet* glyph the extension displays in
    the bullet's place.  A marker and its bullet may coincide (e.g. ``=`` and ``?``),
    where the authored token already is the display glyph.

    Attributes:
        meaning: The human-readable role the bullet conveys.
        marker: The plain-text token an author types to request the bullet.
        bullet: The glyph the extension renders as the block's bullet.
        EQUAL: Equality or a definition; ``=`` renders as ``=``.
        LEADS_TO: A leads-to relation; ``->`` renders as ``→`` (persisted id ``arrow``).
        RESULT: A result or consequence; ``=>`` renders as ``⇒`` (persisted id ``doubleArrow``).
        QUESTION: A question; ``?`` renders as ``?``.
        IMPORTANT: An important point or warning; ``!`` renders as ``!``.
        IDEA: An idea or addition; ``+`` renders as ``+`` (persisted id ``plus``).
        CONTRAST: A contrast or however; ``~`` renders as ``≠``.
        EVIDENCE: Evidence or support; ``^`` renders as ``▸``.
        DECISION: A decision or choice; ``|`` renders as ``⎇``.
        REFERENCE: A reference to related material; ``@`` renders as ``↗``.
        PROCESS: A process or ongoing work; ``...`` renders as ``↻``.
    """

    def __new__(cls, value: str, meaning: str, marker: str, bullet: str) -> Self:
        """Create a member whose string value is *value*, carrying meaning, marker, and bullet."""
        member = str.__new__(cls, value)
        member._value_ = value
        member.meaning = meaning
        member.marker = marker
        member.bullet = bullet
        return member

    meaning: str
    marker: str
    bullet: str

    @property
    def id(self) -> str:
        """The kind's short identifier — the member's string value."""
        return self.value

    EQUAL = ("equal", "Equal / definition", "=", "=")
    LEADS_TO = ("arrow", "Leads to", "->", "→")
    RESULT = ("doubleArrow", "Result", "=>", "⇒")
    QUESTION = ("question", "Question", "?", "?")
    IMPORTANT = ("important", "Important / warning", "!", "!")
    IDEA = ("plus", "Idea / addition", "+", "+")
    CONTRAST = ("contrast", "Contrast / however", "~", "≠")
    EVIDENCE = ("evidence", "Evidence / support", "^", "▸")
    DECISION = ("decision", "Decision / choice", "|", "⎇")
    REFERENCE = ("reference", "Reference / related", "@", "↗")
    PROCESS = ("process", "Process / ongoing", "...", "↻")


class BetterBulletProvenance(enum.StrEnum):
    """A provenance kind: the source channel a block's content arrived through, and its badge.

    Each member's string value is its short :attr:`id` — the identifier the extension
    persists on a block (the ``provenance`` entry of the block's property map), so a stored
    identifier resolves to its member by plain value lookup.  The member carries the
    human-readable *source* the badge conveys, the *default marker* token an author types at
    the head of a block, and the *badge* glyph the extension displays.  A marker and its
    badge may coincide (the pictographic markers), where the authored token already is the
    display glyph.

    Attributes:
        source: The human-readable source channel the badge conveys.
        default_marker: The token an author types, by default, to request the badge.
        badge: The glyph the extension renders as the block's badge.
        CALENDAR_EVENT: A calendar event; ``📅`` renders as ``📅``.
        EMAIL: An email message; ``📨`` renders as ``📨``.
        PHONE_CALL: A phone call; ``📞`` renders as ``📞``.
        CHAT_MESSAGE: A chat message; ``💬`` renders as ``💬``.
        SCANNED_POST: Scanned post; ``📪`` renders as ``📪`` (persisted id ``mail``).
        SLACK: A Slack conversation; ``%`` renders as ``＃``.
    """

    def __new__(cls, value: str, source: str, default_marker: str, badge: str) -> Self:
        """Create a member whose string value is *value*, carrying source, marker, and badge."""
        member = str.__new__(cls, value)
        member._value_ = value
        member.source = source
        member.default_marker = default_marker
        member.badge = badge
        return member

    source: str
    default_marker: str
    badge: str

    @property
    def id(self) -> str:
        """The kind's short identifier — the member's string value."""
        return self.value

    CALENDAR_EVENT = ("calendar", "Calendar event", "📅", "📅")
    EMAIL = ("email", "Email", "📨", "📨")
    PHONE_CALL = ("phone", "Phone call", "📞", "📞")
    CHAT_MESSAGE = ("chat", "Chat message", "💬", "💬")
    SCANNED_POST = ("mail", "Scanned post", "📪", "📪")
    SLACK = ("slack", "Slack", "%", "＃")
