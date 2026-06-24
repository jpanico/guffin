"""Tests for guffin.model.view."""

import pytest

from guffin.model.view import DEFAULT_CHILDREN_LAYOUT, ChildrenLayout, VertexView


class TestChildrenLayout:
    """Tests for the ChildrenLayout enum."""

    def test_values(self) -> None:
        """Test the three layout string values."""
        assert ChildrenLayout.BULLET == "bullet"
        assert ChildrenLayout.DOCUMENT == "document"
        assert ChildrenLayout.NUMBERED == "numbered"

    def test_exactly_three_members(self) -> None:
        """Test that ChildrenLayout has exactly three members."""
        assert len(ChildrenLayout) == 3

    def test_default_is_bullet(self) -> None:
        """Test that DEFAULT_CHILDREN_LAYOUT is BULLET (matching Roam's default view-type)."""
        assert DEFAULT_CHILDREN_LAYOUT is ChildrenLayout.BULLET


class TestVertexView:
    """Tests for the VertexView model."""

    def test_defaults_to_default_layout(self) -> None:
        """Test that children_layout defaults to DEFAULT_CHILDREN_LAYOUT."""
        assert VertexView().children_layout is DEFAULT_CHILDREN_LAYOUT

    def test_holds_explicit_layout(self) -> None:
        """Test that an explicit children_layout is stored."""
        assert VertexView(children_layout=ChildrenLayout.NUMBERED).children_layout is ChildrenLayout.NUMBERED

    def test_is_frozen(self) -> None:
        """Test that VertexView is immutable."""
        view = VertexView()
        with pytest.raises(Exception):
            view.children_layout = ChildrenLayout.BULLET  # type: ignore[misc]
