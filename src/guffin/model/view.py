"""View/presentation state for the Guffin normalized-graph model.

Holds presentation/layout state associated with a
:class:`~guffin.model.vertex_tree.VertexTree`, kept strictly separate from its content:
:class:`~guffin.model.vertex.Vertex` stores only content/semantics, while this module
stores how that content is laid out when rendered.

Public symbols:

- :class:`ChildrenLayout` — ``StrEnum`` of child-layout modes (``BULLET``, ``DOCUMENT``, ``NUMBERED``).
- :data:`DEFAULT_CHILDREN_LAYOUT` — the layout assumed for a vertex with no recorded view.
- :class:`VertexView` — per-vertex presentation state (currently just the children layout).
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


DEFAULT_CHILDREN_LAYOUT: Final[ChildrenLayout] = ChildrenLayout.BULLET
"""Layout assumed for a vertex with no recorded :class:`VertexView`."""


class VertexView(BaseModel):
    """Presentation/view state for a single vertex's subtree.

    Carries no content — only how the vertex's children are presented — so that
    :class:`~guffin.model.vertex.Vertex` can remain content-only.

    Attributes:
        children_layout: How this vertex's children are laid out when rendered.
    """

    model_config = ConfigDict(frozen=True)

    children_layout: ChildrenLayout = Field(
        default=DEFAULT_CHILDREN_LAYOUT,
        description="How this vertex's children are laid out when rendered.",
    )


type ViewMap = dict[Uid, VertexView]
"""``dict`` mapping a vertex :data:`~guffin.model.primitives.Uid` to its :class:`VertexView`.

Sparse: a uid absent from the map takes :data:`DEFAULT_CHILDREN_LAYOUT`.
"""
