"""Tests for guffin.model.render_bundle."""

from datetime import UTC, datetime
from typing import Final

from guffin.common.provenance import Provenance
from guffin.common.revision import Revision
from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex import PageVertex
from guffin.model.vertex_tree import VertexTree


def _bundle() -> RenderBundle:
    """Build a minimal provenance-free RenderBundle."""
    return RenderBundle(content=VertexTree(tree_vertices=[PageVertex(uid="page00001", title="Doc")]))


class TestWithProvenance:
    """:meth:`RenderBundle.with_provenance` returns a stamped copy, leaving the original untouched."""

    def test_stamps_provenance_on_a_new_copy(self) -> None:
        """A non-None provenance is recorded on a new bundle; content carries over; original unchanged."""
        base: Final[RenderBundle] = _bundle()
        provenance: Final[Provenance] = Provenance(commit="abc123", exported_at=datetime(2026, 6, 29, tzinfo=UTC))
        stamped: Final[RenderBundle] = base.with_provenance(provenance)
        assert stamped is not base
        assert stamped.provenance == provenance
        assert stamped.content is base.content  # content carried over by reference
        assert base.provenance is None  # the original (immutable) bundle is untouched

    def test_none_returns_self_unchanged(self) -> None:
        """A ``None`` provenance leaves the bundle as-is (same object)."""
        base: Final[RenderBundle] = _bundle()
        assert base.with_provenance(None) is base


class TestWithRevision:
    """:meth:`RenderBundle.with_revision` returns a stamped copy, leaving the original untouched."""

    def test_stamps_revision_on_a_new_copy(self) -> None:
        """A non-None revision is recorded on a new bundle; content carries over; original unchanged."""
        base: Final[RenderBundle] = _bundle()
        revision: Final[Revision] = Revision(content_hash="d8666f090982", label="draft-3")
        stamped: Final[RenderBundle] = base.with_revision(revision)
        assert stamped is not base
        assert stamped.revision == revision
        assert stamped.content is base.content
        assert base.revision is None

    def test_none_returns_self_unchanged(self) -> None:
        """A ``None`` revision leaves the bundle as-is (same object)."""
        base: Final[RenderBundle] = _bundle()
        assert base.with_revision(None) is base
