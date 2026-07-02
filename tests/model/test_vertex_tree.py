"""Tests for guffin.vertex_tree — map_vertices and related helpers."""

import logging
from typing import Final

import pytest
from pydantic import HttpUrl

from guffin.common.geometry import ImageSize
from guffin.common.media_type import MediaType
from guffin.model.attribute import Attribute, AttributeAssignment, AttributeDomain, AttributeInstance, LiteralValue
from guffin.model.link import VertexLink, VertexLinkKind
from guffin.model.vertex import HeadingVertex, ImageVertex, PageVertex, TextVertex, Vertex
from guffin.model.vertex_tree import (
    VertexTree,
    drop_attribute_assignments,
    drop_root_preamble,
    enrich_image_original_sizes,
    has_parts,
    map_vertices,
)

logger = logging.getLogger(__name__)


def _make_text_tree(uid_text_pairs: list[tuple[str, str]]) -> VertexTree:
    return VertexTree(tree_vertices=[TextVertex(uid=uid, text=text) for uid, text in uid_text_pairs])


_IMAGE_SOURCE: Final[HttpUrl] = HttpUrl("https://example.com/img.jpg")


def _make_image_vertex(uid: str) -> ImageVertex:
    return ImageVertex(
        uid=uid,
        source=_IMAGE_SOURCE,
        media_type=MediaType.JPEG,
        scaled_image_size=ImageSize(width=100, height=100),
    )


class TestMapVertices:
    """Tests for map_vertices()."""

    def test_returns_new_tree_instance(self) -> None:
        """Identity fn produces a distinct VertexTree object, not the original."""
        tree: Final[VertexTree] = _make_text_tree([("aaaaaaaaa", "hello")])
        result: Final[VertexTree] = map_vertices(tree, lambda v: v)
        assert result is not tree

    def test_fn_applied_to_all_vertices(self) -> None:
        """Fn is invoked exactly once for every vertex in the tree."""
        tree: Final[VertexTree] = _make_text_tree([("aaaaaaaaa", "hello"), ("bbbbbbbbb", "world")])
        seen_uids: Final[list[str]] = []

        def _record(vtx: Vertex) -> Vertex:
            seen_uids.append(vtx.uid)
            return vtx

        map_vertices(tree, _record)
        assert sorted(seen_uids) == ["aaaaaaaaa", "bbbbbbbbb"]

    def test_fn_transforms_vertex_fields(self) -> None:
        """Fn's return values appear verbatim in the result tree."""
        tree: Final[VertexTree] = _make_text_tree([("aaaaaaaaa", "hello"), ("bbbbbbbbb", "world")])

        def _upcase(vtx: Vertex) -> Vertex:
            if isinstance(vtx, TextVertex):
                return vtx.model_copy(update={"text": vtx.text.upper()})
            return vtx

        result: Final[VertexTree] = map_vertices(tree, _upcase)
        texts: Final[list[str]] = [vtx.text for vtx in result.tree_vertices if isinstance(vtx, TextVertex)]
        assert texts == ["HELLO", "WORLD"]

    def test_unmatched_vertices_pass_through_unchanged(self) -> None:
        """Vertices not modified by fn are returned as-is."""
        tree: Final[VertexTree] = _make_text_tree([("aaaaaaaaa", "hello"), ("bbbbbbbbb", "world")])

        def _transform_first_only(vtx: Vertex) -> Vertex:
            if isinstance(vtx, TextVertex) and vtx.uid == "aaaaaaaaa":
                return vtx.model_copy(update={"text": "changed"})
            return vtx

        result: Final[VertexTree] = map_vertices(tree, _transform_first_only)
        texts: Final[list[str]] = [vtx.text for vtx in result.tree_vertices if isinstance(vtx, TextVertex)]
        assert texts == ["changed", "world"]


def _assignment() -> AttributeAssignment:
    return AttributeAssignment(
        attribute=AttributeInstance(
            definition=Attribute(name="tags"), link=VertexLink(kind=VertexLinkKind.REFERENCE, uid="pageaaaaa")
        ),
        values=(LiteralValue(value="x"),),
    )


class TestDropAttributeAssignments:
    """Tests for drop_attribute_assignments()."""

    def test_clears_attribute_assignments_and_preserves_other_fields(self) -> None:
        """A vertex's attribute_assignments are cleared to None; its other fields are untouched."""
        root: Final[TextVertex] = TextVertex(
            uid="root00001", text="root", children=["keep00001"], attribute_assignments=[_assignment()]
        )
        keep: Final[TextVertex] = TextVertex(uid="keep00001", text="keep")
        tree: Final[VertexTree] = VertexTree(tree_vertices=[root, keep])
        result: Final[VertexTree] = drop_attribute_assignments(tree)
        assert [v.uid for v in result.tree_vertices] == ["root00001", "keep00001"]
        new_root: Final[Vertex] = next(v for v in result.tree_vertices if v.uid == "root00001")
        assert new_root.attribute_assignments is None
        assert new_root.children == ["keep00001"]
        assert isinstance(new_root, TextVertex) and new_root.text == "root"

    def test_tree_without_attributes_unchanged(self) -> None:
        """A tree with no attribute assignments passes every vertex through unchanged."""
        tree: Final[VertexTree] = _make_text_tree([("aaaaaaaaa", "hello"), ("bbbbbbbbb", "world")])
        result: Final[VertexTree] = drop_attribute_assignments(tree)
        assert [v.uid for v in result.tree_vertices] == ["aaaaaaaaa", "bbbbbbbbb"]
        assert all(v.attribute_assignments is None for v in result.tree_vertices)

    def test_returns_new_tree_instance(self) -> None:
        """The original tree is not mutated; a distinct VertexTree is returned."""
        tree: Final[VertexTree] = _make_text_tree([("aaaaaaaaa", "hello")])
        result: Final[VertexTree] = drop_attribute_assignments(tree)
        assert result is not tree


def _element_type_assignment(value: str) -> AttributeAssignment:
    """Build a guffin-domain ``element-type`` assignment carrying *value*."""
    return AttributeAssignment(
        attribute=AttributeInstance(
            definition=Attribute(name="element-type", domain=AttributeDomain.GUFFIN),
            link=VertexLink(kind=VertexLinkKind.REFERENCE, uid="pageaaaaa"),
        ),
        values=(LiteralValue(value=value),),
    )


def _tagged_heading_tree(heading_level: int, element_type: str | None) -> VertexTree:
    """A page with one heading at *heading_level*, optionally tagged ``element-type:: <value>``."""
    page: Final[PageVertex] = PageVertex(uid="pageroot1", title="Doc", children=["head00001"])
    heading: Final[HeadingVertex] = HeadingVertex(
        uid="head00001",
        text="A Heading",
        heading_level=heading_level,
        attribute_assignments=[_element_type_assignment(element_type)] if element_type is not None else None,
    )
    return VertexTree(tree_vertices=[page, heading])


class TestHasParts:
    """Tests for has_parts()."""

    def test_level_1_part_heading_detected(self) -> None:
        """A level-1 heading tagged element-type:: part makes the tree a parts tree."""
        assert has_parts(_tagged_heading_tree(1, "part")) is True

    def test_level_1_non_part_element_type_is_not_parts(self) -> None:
        """A level-1 heading tagged with a different element type does not."""
        assert has_parts(_tagged_heading_tree(1, "chapter")) is False

    def test_part_tag_below_level_1_is_not_parts(self) -> None:
        """A part tag on a deeper heading does not make the tree a parts tree."""
        assert has_parts(_tagged_heading_tree(2, "part")) is False

    def test_untagged_headings_are_not_parts(self) -> None:
        """Headings without element-type tags leave the tree partless."""
        assert has_parts(_tagged_heading_tree(1, None)) is False

    def test_unrecognised_element_type_ignored_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """A junk element-type value is ignored (warned), not raised."""
        with caplog.at_level(logging.WARNING, logger="guffin.model.vertex_tree"):
            assert has_parts(_tagged_heading_tree(1, "not-an-element")) is False
        assert "ignoring element-type" in caplog.text


def _make_preamble_tree() -> VertexTree:
    """A page whose leading children (one with a nested subtree) precede its first heading."""
    page: Final[PageVertex] = PageVertex(
        uid="pageroot1", title="Doc", children=["pre000001", "pre000002", "chap00001", "trail0001"]
    )
    pre1: Final[TextVertex] = TextVertex(uid="pre000001", text="loose callout", children=["pre1child"])
    pre1_child: Final[TextVertex] = TextVertex(uid="pre1child", text="nested under preamble")
    pre2: Final[TextVertex] = TextVertex(uid="pre000002", text="more preamble")
    chap: Final[HeadingVertex] = HeadingVertex(uid="chap00001", text="Chapter One", heading_level=1)
    trail: Final[TextVertex] = TextVertex(uid="trail0001", text="after the heading")
    return VertexTree(tree_vertices=[page, pre1, pre1_child, pre2, chap, trail])


class TestDropRootPreamble:
    """Tests for drop_root_preamble()."""

    def test_drops_leading_children_and_their_subtrees(self) -> None:
        """Children ahead of the first heading — and their descendants — are removed."""
        result: Final[VertexTree] = drop_root_preamble(_make_preamble_tree())
        assert sorted(v.uid for v in result.tree_vertices) == ["chap00001", "pageroot1", "trail0001"]
        new_root: Final[Vertex] = next(v for v in result.tree_vertices if v.uid == "pageroot1")
        assert new_root.children == ["chap00001", "trail0001"]

    def test_retains_loose_content_after_first_heading(self) -> None:
        """Only the leading run is preamble; loose children after the heading survive."""
        result: Final[VertexTree] = drop_root_preamble(_make_preamble_tree())
        assert "trail0001" in result.uid_map

    def test_original_tree_unmodified(self) -> None:
        """The prune is copy-on-write; the source tree keeps its preamble."""
        tree: Final[VertexTree] = _make_preamble_tree()
        drop_root_preamble(tree)
        assert "pre000001" in tree.uid_map
        root: Final[Vertex] = next(v for v in tree.tree_vertices if v.uid == "pageroot1")
        assert root.children == ["pre000001", "pre000002", "chap00001", "trail0001"]

    def test_noop_when_first_child_is_heading(self) -> None:
        """A page with no preamble passes through as the same tree object."""
        page: Final[PageVertex] = PageVertex(uid="pageroot1", title="Doc", children=["chap00001"])
        chap: Final[HeadingVertex] = HeadingVertex(uid="chap00001", text="Chapter One", heading_level=1)
        tree: Final[VertexTree] = VertexTree(tree_vertices=[page, chap])
        assert drop_root_preamble(tree) is tree

    def test_noop_for_non_page_root(self) -> None:
        """A subtree export rooted at a non-page vertex passes through unchanged."""
        root: Final[TextVertex] = TextVertex(uid="root00001", text="block root", children=["child0001"])
        child: Final[TextVertex] = TextVertex(uid="child0001", text="child")
        tree: Final[VertexTree] = VertexTree(tree_vertices=[root, child])
        assert drop_root_preamble(tree) is tree

    def test_warns_and_retains_when_no_heading_children(self, caplog: pytest.LogCaptureFixture) -> None:
        """A page with no heading children keeps all content and logs a warning."""
        page: Final[PageVertex] = PageVertex(uid="pageroot1", title="Doc", children=["text00001"])
        text: Final[TextVertex] = TextVertex(uid="text00001", text="only loose content")
        tree: Final[VertexTree] = VertexTree(tree_vertices=[page, text])
        with caplog.at_level(logging.WARNING, logger="guffin.model.vertex_tree"):
            result: Final[VertexTree] = drop_root_preamble(tree)
        assert result is tree
        assert "no heading children" in caplog.text

    def test_ref_vertices_preserved(self) -> None:
        """Stub ref vertices are untouched by the prune."""
        tree: Final[VertexTree] = _make_preamble_tree()
        stub: Final[TextVertex] = TextVertex(uid="refstub01", text="referenced elsewhere")
        with_refs: Final[VertexTree] = VertexTree(tree_vertices=tree.tree_vertices, ref_vertices=[stub])
        result: Final[VertexTree] = drop_root_preamble(with_refs)
        assert [v.uid for v in result.ref_vertices] == ["refstub01"]


class TestEnrichImageOriginalSizes:
    """Tests for enrich_image_original_sizes()."""

    def test_matched_uid_sets_original_image_size(self) -> None:
        """ImageVertex whose UID is in sizes receives original_image_size."""
        vertex: Final[ImageVertex] = _make_image_vertex("img000001")
        tree: Final[VertexTree] = VertexTree(tree_vertices=[vertex])
        size: Final[ImageSize] = ImageSize(width=320, height=240)
        result: Final[VertexTree] = enrich_image_original_sizes(tree, {"img000001": size})
        enriched: Final[ImageVertex] = next(v for v in result.tree_vertices if isinstance(v, ImageVertex))
        assert enriched.original_image_size == size

    def test_unmatched_image_vertex_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """ImageVertex absent from sizes map logs a WARNING and keeps original_image_size as None."""
        vertex: Final[ImageVertex] = _make_image_vertex("img000002")
        tree: Final[VertexTree] = VertexTree(tree_vertices=[vertex])
        with caplog.at_level(logging.WARNING, logger="guffin.vertex_tree"):
            result: Final[VertexTree] = enrich_image_original_sizes(tree, {})
        unmatched: Final[ImageVertex] = next(v for v in result.tree_vertices if isinstance(v, ImageVertex))
        assert unmatched.original_image_size is None
        assert any("absent from sizes map" in r.message for r in caplog.records)

    def test_non_image_vertices_pass_through(self) -> None:
        """TextVertex is returned unchanged regardless of the sizes map."""
        tree: Final[VertexTree] = _make_text_tree([("aaaaaaaaa", "hello")])
        result: Final[VertexTree] = enrich_image_original_sizes(tree, {})
        texts: Final[list[str]] = [v.text for v in result.tree_vertices if isinstance(v, TextVertex)]
        assert texts == ["hello"]

    def test_mixed_tree_partial_match(self) -> None:
        """Matched image gets size; unmatched image stays None; text vertex passes through unchanged."""
        img_matched: Final[ImageVertex] = _make_image_vertex("img000003")
        img_unmatched: Final[ImageVertex] = _make_image_vertex("img000004")
        text: Final[TextVertex] = TextVertex(uid="aaaaaaaaa", text="hello")
        tree: Final[VertexTree] = VertexTree(tree_vertices=[img_matched, img_unmatched, text])
        size: Final[ImageSize] = ImageSize(width=800, height=600)
        result: Final[VertexTree] = enrich_image_original_sizes(tree, {"img000003": size})
        result_by_uid: Final[dict[str, Vertex]] = {v.uid: v for v in result.tree_vertices}
        matched_result: Final[Vertex] = result_by_uid["img000003"]
        unmatched_result: Final[Vertex] = result_by_uid["img000004"]
        assert isinstance(matched_result, ImageVertex)
        assert isinstance(unmatched_result, ImageVertex)
        assert matched_result.original_image_size == size
        assert unmatched_result.original_image_size is None
        assert isinstance(result_by_uid["aaaaaaaaa"], TextVertex)
