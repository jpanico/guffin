"""Tests for guffin.render.rich_rendering (raw-results table + view-map tree rendering)."""

import io

from conftest import article0_node_tree, article1_node_tree
from rich.cells import cell_len
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.tree import Tree as RichTree

from guffin.model.vertex import HeadingVertex, PageVertex, TextVertex
from guffin.model.vertex_tree import VertexTree
from guffin.model.vertex_view import ChildrenLayout, VertexView, ViewMap
from guffin.render.rich_rendering import (
    SELECTED_VERSION_MARKER,
    UNSELECTED_VERSION_MARKER,
    VERSION_GROUP_GLYPH,
    build_node_panel,
    build_rich_node_tree,
    build_rich_raw_table,
    build_rich_version_groups_box,
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
    """build_view_panel titles a vertex like its content panel and dims connector-only panels."""

    def test_entry_title_matches_vertex_panel(self) -> None:
        """An entry-bearing view panel reuses the same title string as the vertex's content panel."""
        vertex = HeadingVertex(uid="chap00001", text="Chapter One", heading_level=1)
        entry = build_view_panel(vertex, VertexView(children_layout=ChildrenLayout.DOCUMENT))
        assert entry.title == build_vertex_panel(vertex).title
        assert entry.border_style == "none"

    def test_connector_panel_is_dimmed(self) -> None:
        """A connector panel (no view entry) dims its border and wraps the content title in ``[dim]``."""
        vertex = HeadingVertex(uid="chap00001", text="Chapter One", heading_level=1)
        connector = build_view_panel(vertex, None)
        assert connector.border_style == "dim"
        assert connector.title == f"[dim]{build_vertex_panel(vertex).title}[/dim]"


def _rendered(renderable: RenderableType) -> str:
    """Render *renderable* to plain text at a width wide enough that nothing wraps away."""
    buffer = io.StringIO()
    Console(file=buffer, width=240, force_terminal=False, color_system=None).print(renderable)
    return buffer.getvalue()


class TestBuildRichVersionGroupsBox:
    """Tests for build_rich_version_groups_box."""

    def test_tree_without_version_groups_yields_none(self) -> None:
        """A tree with no version groups renders no box at all."""
        assert build_rich_version_groups_box(article1_node_tree()) is None

    def test_article0_box_lists_every_version_and_marks_the_selected_one(self) -> None:
        """The [[Test Article]] 0 tree's one group renders with all three versions, the third marked selected."""
        box = build_rich_version_groups_box(article0_node_tree(), truncate=False)
        assert isinstance(box, Panel)
        text = _rendered(box)
        assert "version groups" in text
        assert f"{VERSION_GROUP_GLYPH} version group e9j_vHjGQ" in text
        assert "members: 3" in text
        for version in ("version 1", "version 2", "version 3"):
            assert f"This is {version}" in text or f"This is __{version}__" in text or f"This is **{version}**" in text
        assert text.count(SELECTED_VERSION_MARKER) == 1
        assert text.count(UNSELECTED_VERSION_MARKER) == 2

    def test_selected_marker_sits_beside_the_selected_version(self) -> None:
        """The member marked ◉ is the one the group's selected_id names; the others are marked ○."""
        tree = article0_node_tree()
        box = build_rich_version_groups_box(tree, truncate=False)
        assert box is not None
        group = next(iter(tree.version_groups.values()))
        selected_string = tree.version_members_by_id[group.selected_id].string
        assert selected_string is not None
        lines = _rendered(box).splitlines()
        selected_lines = [line for line in lines if SELECTED_VERSION_MARKER in line]
        assert len(selected_lines) == 1
        assert selected_string in selected_lines[0]
        unselected_lines = [line for line in lines if UNSELECTED_VERSION_MARKER in line]
        assert len(unselected_lines) == 2
        assert all(selected_string not in line for line in unselected_lines)

    def test_markers_are_single_width_so_the_grid_stays_aligned(self) -> None:
        """Every glyph is one terminal cell wide, keeping the marker column and panel edges aligned."""
        assert cell_len(VERSION_GROUP_GLYPH) == 1
        assert cell_len(SELECTED_VERSION_MARKER) == 1
        assert cell_len(UNSELECTED_VERSION_MARKER) == 1

    def test_every_member_panel_carries_the_versioning_glyph(self) -> None:
        """Each member's panel title leads with ⎇, as does the group's: four in the Test Article 0 box."""
        box = build_rich_version_groups_box(article0_node_tree(), truncate=False)
        assert box is not None
        assert _rendered(box).count(VERSION_GROUP_GLYPH) == 4


class TestVersionedNodePanels:
    """A node that has versions carries the orange ⎇ before its panel title, wherever its panel appears."""

    def test_panel_is_unmarked_by_default(self) -> None:
        """Without the versioned flag a node panel's title has no glyph."""
        tree = article1_node_tree()
        assert VERSION_GROUP_GLYPH not in _rendered(build_node_panel(tree.root_node))

    def test_versioned_panel_leads_with_the_glyph_in_orange(self) -> None:
        """With the flag the glyph leads the title, styled orange."""
        tree = article1_node_tree()
        panel = build_node_panel(tree.root_node, versioned=True)
        plain = _rendered(panel)
        assert VERSION_GROUP_GLYPH in plain
        assert plain.index(VERSION_GROUP_GLYPH) < plain.index("<roam/page>")
        buffer = io.StringIO()
        Console(file=buffer, width=240, force_terminal=True, color_system="256").print(panel)
        assert f"\x1b[38;5;214m{VERSION_GROUP_GLYPH}" in buffer.getvalue()  # orange1 is ANSI 256-colour 214

    def test_node_tree_marks_only_the_versioned_node(self) -> None:
        """In the Test Article 0 node tree exactly one panel, the selected version's, carries the glyph."""
        tree = article0_node_tree()
        group = next(iter(tree.version_groups.values()))
        selected_string = tree.version_members_by_id[group.selected_id].string
        assert selected_string is not None
        lines = _rendered(build_rich_node_tree(tree, truncate=False)).splitlines()
        marked = [line for line in lines if VERSION_GROUP_GLYPH in line]
        assert len(marked) == 1
        assert selected_string in marked[0]

    def test_unversioned_tree_has_no_glyph(self) -> None:
        """A tree with no version groups renders no glyph anywhere."""
        assert VERSION_GROUP_GLYPH not in _rendered(build_rich_node_tree(article1_node_tree()))
