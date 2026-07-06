"""Tests for guffin.render.rich_rendering (raw-results table transient-column toggle)."""

from guffin.render.rich_rendering import build_rich_raw_table
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
