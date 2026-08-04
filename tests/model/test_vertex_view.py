"""Tests for guffin.model.vertex_view."""

import pytest

from guffin.model.vertex_view import DEFAULT_CHILDREN_LAYOUT, ChildrenLayout, Semantic, SourceChannel, VertexView


class TestChildrenLayout:
    """Tests for the ChildrenLayout enum."""

    def test_exactly_three_members(self) -> None:
        """Test that ChildrenLayout has exactly three members."""
        assert len(ChildrenLayout) == 3

    def test_default_is_bullet(self) -> None:
        """Test that DEFAULT_CHILDREN_LAYOUT is BULLET (the conventional outliner default)."""
        assert DEFAULT_CHILDREN_LAYOUT is ChildrenLayout.BULLET


class TestSemantic:
    """Tests for the Semantic enum."""

    def test_exactly_the_declared_kinds(self) -> None:
        """Semantic holds exactly the declared kinds of thinking."""
        assert {member.value for member in Semantic} == {
            "definition",
            "leads-to",
            "result",
            "question",
            "idea",
            "corollary",
            "warning",
            "contrast",
            "evidence",
            "conclusion",
            "hypothesis",
            "depends-on",
            "decision",
            "reference",
            "process",
        }

    def test_value_lookup(self) -> None:
        """A kind resolves from its string value."""
        assert Semantic("leads-to") is Semantic.LEADS_TO


class TestSourceChannel:
    """Tests for the SourceChannel enum."""

    def test_exactly_the_declared_channels(self) -> None:
        """SourceChannel holds exactly the declared source channels."""
        assert {member.value for member in SourceChannel} == {
            "calendar-event",
            "email",
            "voice-call",
            "chat-message",
            "postal-mail",
            "slack",
        }

    def test_value_lookup(self) -> None:
        """A channel resolves from its string value."""
        assert SourceChannel("voice-call") is SourceChannel.VOICE_CALL


class TestVertexView:
    """Tests for the VertexView model."""

    def test_every_field_defaults_to_unset(self) -> None:
        """An empty view asserts nothing: every field defaults to None."""
        view = VertexView()
        assert view.children_layout is None
        assert view.semantic is None
        assert view.source_channel is None

    def test_explicit_fields_are_carried(self) -> None:
        """Explicitly set fields are carried as given."""
        view = VertexView(
            children_layout=ChildrenLayout.DOCUMENT,
            semantic=Semantic.QUESTION,
            source_channel=SourceChannel.EMAIL,
        )
        assert view.children_layout is ChildrenLayout.DOCUMENT
        assert view.semantic is Semantic.QUESTION
        assert view.source_channel is SourceChannel.EMAIL

    def test_is_frozen(self) -> None:
        """Test that VertexView is immutable."""
        view = VertexView()
        with pytest.raises(Exception):
            view.children_layout = ChildrenLayout.BULLET  # type: ignore[misc]
