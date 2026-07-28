"""View/presentation state for the Guffin normalized-graph model.

Holds presentation/layout state associated with a
:class:`~guffin.model.vertex_tree.VertexTree`, kept strictly separate from its content:
:class:`~guffin.model.vertex.Vertex` stores only content/semantics, while this module
stores how that content is laid out when rendered.

Public symbols:

- :class:`ChildrenLayout` — ``StrEnum`` of child-layout modes (``BULLET``, ``DOCUMENT``, ``NUMBERED``).
- :class:`Semantic` — ``StrEnum`` of the kinds of thinking a vertex's content can represent.
- :class:`SourceChannel` — ``StrEnum`` of the source channels a vertex's content can originate from.
- :data:`DEFAULT_CHILDREN_LAYOUT` — the layout at the root of effective-layout resolution.
- :class:`VertexView` — per-vertex presentation state (children layout, semantic, source
  channel; every field optional).
- :data:`ViewMap` — ``dict`` mapping a vertex ``uid`` to its :class:`VertexView`.
"""

import enum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from guffin.model.primitives import Uid


class ChildrenLayout(enum.StrEnum):
    """How a vertex's children are laid out when rendered.

    - **BULLET**: children rendered as a bulleted list.
    - **DOCUMENT**: children rendered as a flowing document, with no list markers.
    - **NUMBERED**: children rendered as a numbered list.
    """

    BULLET = "bullet"
    DOCUMENT = "document"
    NUMBERED = "numbered"


class Semantic(enum.StrEnum):
    """The kind of thinking a vertex's content represents.

    Classifies the act of thought a piece of content performs — the role it plays in the
    surrounding reasoning — independently of any markup or extension vocabulary that may have
    declared it.

    Attributes:
        DEFINITION: An equality or definition.
        LEADS_TO: A leads-to progression.
        RESULT: A result or consequence.
        QUESTION: A question.
        IDEA: An idea or addition.
        COROLLARY: A subproof or corollary — a result established from the one it hangs under.
        CONTRAST: A contrast or objection.
        EVIDENCE: Evidence or support.
        CONCLUSION: A conclusion or synthesis drawn from what precedes it.
        HYPOTHESIS: A tentative claim, advanced to be tested rather than asserted.
        DEPENDS_ON: A dependency or prerequisite — the inverse of :attr:`LEADS_TO`.
        WARNING: An important point or warning.
        DECISION: A decision or choice.
        REFERENCE: A pointer to related material.
        PROCESS: A process or ongoing work.
    """

    DEFINITION = "definition"
    LEADS_TO = "leads-to"
    RESULT = "result"
    QUESTION = "question"
    IDEA = "idea"
    COROLLARY = "corollary"
    CONTRAST = "contrast"
    EVIDENCE = "evidence"
    CONCLUSION = "conclusion"
    HYPOTHESIS = "hypothesis"
    DEPENDS_ON = "depends-on"
    WARNING = "warning"
    DECISION = "decision"
    REFERENCE = "reference"
    PROCESS = "process"


class SourceChannel(enum.StrEnum):
    """The source channel a vertex's content originates from.

    Names the medium through which the recorded material arrived — a communication or capture
    channel, not an author or a location.

    Attributes:
        CALENDAR_EVENT: Captured from a calendar event.
        EMAIL: Captured from an email message.
        VOICE_CALL: Captured from a voice call.
        CHAT_MESSAGE: Captured from a chat message.
        POSTAL_MAIL: Captured from postal mail.
        SLACK: Captured from a Slack conversation.
    """

    CALENDAR_EVENT = "calendar-event"
    EMAIL = "email"
    VOICE_CALL = "voice-call"
    CHAT_MESSAGE = "chat-message"
    POSTAL_MAIL = "postal-mail"
    SLACK = "slack"


DEFAULT_CHILDREN_LAYOUT: Final[ChildrenLayout] = ChildrenLayout.BULLET
"""The layout at the root of effective-layout resolution.

A vertex with no explicitly recorded layout — no :class:`VertexView` at all, or one whose
:attr:`~VertexView.children_layout` is unset — inherits its parent's effective layout rather
than this default; the default seeds the resolution only at a parentless root (the tri-state
effective-layout rules; see ``docs/render-pipeline.md``, *Children layout*).
"""


class VertexView(BaseModel):
    """Presentation/view state for a single vertex.

    Carries no content — only how the vertex is presented and classified — so that
    :class:`~guffin.model.vertex.Vertex` can remain content-only.  Every field is optional: an
    unset field asserts nothing about the vertex, leaving each consumer's own resolution rules
    (inheritance, defaults) to apply.

    Attributes:
        children_layout: How this vertex's children are laid out when rendered; ``None``
            when unset.
        semantic: The kind of thinking this vertex's content represents; ``None`` when
            undeclared.
        source_channel: The source channel this vertex's content originates from; ``None``
            when undeclared.
    """

    model_config = ConfigDict(frozen=True)

    children_layout: ChildrenLayout | None = Field(
        default=None,
        description="How this vertex's children are laid out when rendered; None when unset.",
    )
    semantic: Semantic | None = Field(
        default=None,
        description="The kind of thinking this vertex's content represents; None when undeclared.",
    )
    source_channel: SourceChannel | None = Field(
        default=None,
        description="The source channel this vertex's content originates from; None when undeclared.",
    )


type ViewMap = dict[Uid, VertexView]
"""``dict`` mapping a vertex :data:`~guffin.model.primitives.Uid` to its :class:`VertexView`.

Sparse: only explicitly authored views are recorded.  A uid absent from the map has no view
of its own — its effective layout is inherited from its parent's, with
:data:`DEFAULT_CHILDREN_LAYOUT` seeding the resolution only at a parentless root (the
tri-state effective-layout rules; see ``docs/render-pipeline.md``, *Children layout*).
"""
