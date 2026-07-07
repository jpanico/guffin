"""Tests for guffin.render.rich_rendering (raw-results table + view-map tree rendering)."""

import io

from rich.console import Console
from rich.tree import Tree as RichTree

from guffin.model.vertex import HeadingVertex, PageVertex, TextVertex
from guffin.model.vertex_tree import VertexTree
from guffin.model.vertex_view import ChildrenLayout, VertexView, ViewMap
from guffin.render.rich_rendering import (
    build_rich_raw_table,
    build_rich_view_map_tree,
    build_vertex_panel,
    build_view_panel,
)
from guffin.roam.node_fetch_result import NodeFetchAnchor, NodeFetchResult, NodeFetchSpec


def _fetch_result(raw_block: dict[str, object]) -> NodeFetchResult:
    """Build a raw-only NodeFetchResult whose single pull-block is *raw_block*."""
    spec = NodeFetchSpec(anchor=NodeFetchAnchor(qualifier="Some Page"), include_refs=False)
    return NodeFetchResult.from_raw_result(spec, [[raw_block]])


_BLOCK: dict[str, object] = {
    "id": 1,
    "uid": "abc123xyz",
    "string": "hi",
    "open": True,
    "edit-time": 1700000000000,
    "sidebar": [],
}


class TestRawResultsTransientColumns:
    """build_rich_raw_table hides transient columns by default and shows them on request."""

    def test_transient_columns_hidden_by_default(self) -> None:
        """Transient attribute columns are absent; structural columns remain."""
        headers = {column.header for column in build_rich_raw_table(_fetch_result(_BLOCK)).columns}
        assert "open" not in headers
        assert "edit-time" not in headers
        assert "sidebar" not in headers
        assert {"uid", "string"} <= headers

    def test_transient_columns_shown_when_requested(self) -> None:
        """With show_transient, the transient attribute columns appear alongside structural ones."""
        headers = {column.header for column in build_rich_raw_table(_fetch_result(_BLOCK), show_transient=True).columns}
        assert {"open", "edit-time", "sidebar"} <= headers
        assert {"uid", "string"} <= headers

    def test_bookkeeping_columns_hidden_even_when_showing_transient(self) -> None:
        """Lookup and attrs stay hidden regardless of show_transient."""
        block: dict[str, object] = {"id": 1, "uid": "abc123xyz", "lookup": [1], "attrs": []}
        headers = {column.header for column in build_rich_raw_table(_fetch_result(block), show_transient=True).columns}
        assert "lookup" not in headers
        assert "attrs" not in headers


def _render(tree: RichTree) -> str:
    """Render *tree* to plain (uncolored) text through a wide Console for content assertions."""
    console = Console(width=400, file=io.StringIO(), no_color=True)
    console.print(tree)
    return console.file.getvalue()  # type: ignore[attr-defined]


def _nested_tree() -> VertexTree:
    """Build a page → chapter → section → text tree plus a loose sibling of the chapter.

    Structure (uids)::

        pageroot1 (page)
        ├── chap00001 (H1)
        │   └── sect00001 (H2)
        │       └── deep00001 (text)   ← the only vertex given a view entry
        └── other0001 (text)           ← sibling with no view entry
    """
    page = PageVertex(uid="pageroot1", title="Doc", children=["chap00001", "other0001"])
    chap = HeadingVertex(uid="chap00001", text="Chapter One", heading_level=1, children=["sect00001"])
    sect = HeadingVertex(uid="sect00001", text="Section", heading_level=2, children=["deep00001"])
    deep = TextVertex(uid="deep00001", text="deep leaf")
    other = TextVertex(uid="other0001", text="loose sibling")
    return VertexTree(tree_vertices=[page, chap, sect, deep, other])


class TestBuildRichViewMapTree:
    """build_rich_view_map_tree prunes to view entries plus their connecting ancestors."""

    def test_entry_ancestors_and_root_shown_others_pruned(self) -> None:
        """A deep entry pulls in its ancestors and the root; unrelated siblings are omitted."""
        view_map: ViewMap = {"deep00001": VertexView(children_layout=ChildrenLayout.DOCUMENT)}
        out = _render(build_rich_view_map_tree(_nested_tree(), view_map))
        assert "pageroot1" in out  # root always shown
        assert "chap00001" in out  # connector ancestor
        assert "sect00001" in out  # connector ancestor
        assert "deep00001" in out  # the entry itself
        assert "other0001" not in out  # unrelated sibling pruned

    def test_entry_body_shows_view_fields_connectors_show_placeholder(self) -> None:
        """The entry panel lists its VertexView fields; connector/root panels show a placeholder."""
        view_map: ViewMap = {"deep00001": VertexView(children_layout=ChildrenLayout.DOCUMENT)}
        out = _render(build_rich_view_map_tree(_nested_tree(), view_map))
        assert "children_layout=document" in out
        assert "(no view entry)" in out  # root + connectors carry no entry

    def test_empty_view_map_shows_only_root(self) -> None:
        """With no entries the tree is just the root panel, marked as carrying no view entry."""
        out = _render(build_rich_view_map_tree(_nested_tree(), {}))
        assert "pageroot1" in out
        assert "(no view entry)" in out
        for pruned in ("chap00001", "sect00001", "deep00001", "other0001"):
            assert pruned not in out


class TestBuildViewPanel:
    """build_view_panel titles a vertex identically to its content panel."""

    def test_title_matches_vertex_panel(self) -> None:
        """A view panel reuses the same title string as the vertex's content panel."""
        vertex = HeadingVertex(uid="chap00001", text="Chapter One", heading_level=1)
        assert build_view_panel(vertex, None).title == build_vertex_panel(vertex).title
