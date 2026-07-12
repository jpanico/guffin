"""The Guffin render bundle: a VertexTree paired with its presentation ViewMap.

Public symbols:

- :class:`RenderBundle` — bundles a :class:`~guffin.model.vertex_tree.VertexTree` (content) with
  its :data:`~guffin.model.vertex_view.ViewMap` (presentation), plus optional
  :class:`~guffin.common.provenance.Provenance` recording the software that produced the bundle's
  data and optional :class:`~guffin.common.revision.Revision` recording the content snapshot it
  was produced from.  Content and presentation are held as separate fields so they stay decoupled
  while travelling together as one bundle.  :meth:`RenderBundle.with_provenance` /
  :meth:`RenderBundle.with_revision` return copies stamped with the given record.
"""

from pydantic import BaseModel, ConfigDict, Field

from guffin.common.provenance import Provenance
from guffin.common.revision import Revision
from guffin.model.vertex_tree import VertexTree
from guffin.model.vertex_view import ViewMap


class RenderBundle(BaseModel):
    """A normalized content tree paired with its presentation view map.

    Attributes:
        content: The normalized content tree (:class:`~guffin.model.vertex.Vertex` graph).
        view: Presentation/layout state keyed by vertex uid; sparse, defaulting to empty.
        provenance: Optional record of the software (source commit + timestamps) that produced this
            bundle's data; ``None`` when not captured.  Carried as origin metadata so a renderer can
            stamp it as a colophon when asked (see
            :attr:`~guffin.render.render_options.RenderOptions.emit_colophon`).
        revision: Optional record of the content snapshot (snapshot hash + timestamps + authored
            revision name) this bundle was produced from; ``None`` when not captured.  Carried as origin
            metadata alongside :attr:`provenance` and stamped into the same colophon.
    """

    model_config = ConfigDict(frozen=True)

    content: VertexTree = Field(..., description="The normalized content tree.")
    view: ViewMap = Field(default_factory=dict, description="Presentation/layout state keyed by vertex uid.")
    provenance: Provenance | None = Field(
        default=None, description="Software (commit + timestamps) that produced this bundle's data."
    )
    revision: Revision | None = Field(
        default=None, description="Content snapshot (hash + timestamps + revision name) this bundle was produced from."
    )

    def with_provenance(self, provenance: Provenance | None) -> RenderBundle:
        """Return a copy of this bundle stamped with *provenance*, or ``self`` unchanged when ``None``.

        A pure enrichment helper: the bundle's producer captures provenance separately (e.g. via
        :func:`~guffin.common.provenance.gather_provenance`) and attaches it here, keeping this model
        free of any runtime-capture side effects.

        Args:
            provenance: The provenance to record on the returned bundle, or ``None`` to leave the
                bundle unchanged.

        Returns:
            A new :class:`RenderBundle` carrying *provenance*, or ``self`` when *provenance* is ``None``.
        """
        if provenance is None:
            return self
        return self.model_copy(update={"provenance": provenance})

    def with_revision(self, revision: Revision | None) -> RenderBundle:
        """Return a copy of this bundle stamped with *revision*, or ``self`` unchanged when ``None``.

        A pure enrichment helper, the content-side twin of :meth:`with_provenance`: the bundle's
        producer captures the revision separately (e.g. via
        :func:`~guffin.roam.revision.gather_revision`) and attaches it here, keeping this model
        free of any runtime-capture side effects.

        Args:
            revision: The revision to record on the returned bundle, or ``None`` to leave the
                bundle unchanged.

        Returns:
            A new :class:`RenderBundle` carrying *revision*, or ``self`` when *revision* is ``None``.
        """
        if revision is None:
            return self
        return self.model_copy(update={"revision": revision})
