"""An alternative — one of the other wordings a vertex's content could have.

A vertex that supports alternatives carries, beside its own text, the other texts its
content was written as: coexisting peers of one piece of content, of which the vertex's own
text is the selected one.  An alternative is a wording only — it has no children, no
attributes, and no identity in the tree beyond the vertex it belongs to — so choosing
another alternative changes what the vertex says and nothing else.

These are not revisions.  A revision is a successive state of one thing over time; an
alternative is a peer that exists at the same time, side by side with the selected text.

Public symbols:

- :class:`Alternative` — one alternative wording: its source identifier and its text.
"""

from pydantic import BaseModel, ConfigDict, Field

from guffin.model.primitives import Uid


class Alternative(BaseModel):
    """One alternative wording of a vertex's content.

    Attributes:
        uid: The stable identifier the alternative carries in its source, so it can be named
            — for instance to select it — without ambiguity.
        text: The alternative's text, normalized exactly as the vertex's own text is.
    """

    model_config = ConfigDict(frozen=True)

    uid: Uid = Field(description="The alternative's stable source identifier.")
    text: str = Field(description="The alternative wording, normalized like the vertex's own text.")
