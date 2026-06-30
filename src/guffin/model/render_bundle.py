"""The Guffin render bundle: a VertexTree paired with its presentation ViewMap.

Public symbols:

- :class:`RenderBundle` — bundles a :class:`~guffin.model.vertex_tree.VertexTree` (content) with
  its :data:`~guffin.model.view.ViewMap` (presentation), plus optional
  :class:`~guffin.common.provenance.Provenance` recording the software that produced the bundle's
  data.  Content and presentation are held as separate fields so they stay decoupled while
  travelling together as one bundle.
"""

from pydantic import BaseModel, ConfigDict, Field

from guffin.common.provenance import Provenance
from guffin.model.vertex_tree import VertexTree
from guffin.model.view import ViewMap


class RenderBundle(BaseModel):
    """A normalized content tree paired with its presentation view map.

    Attributes:
        content: The normalized content tree (:class:`~guffin.model.vertex.Vertex` graph).
        view: Presentation/layout state keyed by vertex uid; sparse, defaulting to empty.
        provenance: Optional record of the software (source commit + timestamps) that produced this
            bundle's data; ``None`` when not captured.  Carried as origin metadata so a renderer can
            stamp it as a colophon when asked (see
            :attr:`~guffin.render.render_options.RenderOptions.emit_colophon`).
    """

    model_config = ConfigDict(frozen=True)

    content: VertexTree = Field(..., description="The normalized content tree.")
    view: ViewMap = Field(default_factory=dict, description="Presentation/layout state keyed by vertex uid.")
    provenance: Provenance | None = Field(
        default=None, description="Software (commit + timestamps) that produced this bundle's data."
    )
