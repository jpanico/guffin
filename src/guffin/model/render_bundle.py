"""The Guffin render bundle: a VertexTree paired with its presentation ViewMap.

Public symbols:

- :class:`RenderBundle` — bundles a :class:`~guffin.model.vertex_tree.VertexTree` (content) with
  its :data:`~guffin.model.view.ViewMap` (presentation).  The two are held as separate fields so
  content and presentation stay decoupled while travelling together as one bundle.
"""

from pydantic import BaseModel, ConfigDict, Field

from guffin.model.vertex_tree import VertexTree
from guffin.model.view import ViewMap


class RenderBundle(BaseModel):
    """A normalized content tree paired with its presentation view map.

    Attributes:
        content: The normalized content tree (:class:`~guffin.model.vertex.Vertex` graph).
        view: Presentation/layout state keyed by vertex uid; sparse, defaulting to empty.
    """

    model_config = ConfigDict(frozen=True)

    content: VertexTree = Field(..., description="The normalized content tree.")
    view: ViewMap = Field(default_factory=dict, description="Presentation/layout state keyed by vertex uid.")
