"""Better Bullets: the marker→bullet vocabulary of the Better Bullets Roam extension.

The **Better Bullets** Roam extension (``mlava/better-bullets``) restyles a block's bullet
when the block's text leads with a recognized marker token: the plain-text *marker* the
author types is displayed as the extension's *bullet* glyph, conveying the block's
rhetorical role (definition, consequence, question, …).

Public symbols:

- **Enumerations**: :class:`BetterBulletType` — the recognized Better Bullets kinds, each
  member carrying its human-readable meaning, its authored marker token, and the bullet
  glyph the extension renders.
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
        ARROW: A leads-to relation; ``->`` renders as ``→``.
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
    ARROW = ("arrow", "Leads to", "->", "→")
    RESULT = ("doubleArrow", "Result", "=>", "⇒")
    QUESTION = ("question", "Question", "?", "?")
    IMPORTANT = ("important", "Important / warning", "!", "!")
    IDEA = ("plus", "Idea / addition", "+", "+")
    CONTRAST = ("contrast", "Contrast / however", "~", "≠")
    EVIDENCE = ("evidence", "Evidence / support", "^", "▸")
    DECISION = ("decision", "Decision / choice", "|", "⎇")
    REFERENCE = ("reference", "Reference / related", "@", "↗")
    PROCESS = ("process", "Process / ongoing", "...", "↻")
