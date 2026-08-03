"""Unit tests for guffin.roam.todo."""

import pytest
from pydantic import ValidationError

from guffin.roam.todo import TODO_MARKER_RE, RoamTodo, TodoState, parse_todo, todo_state

# ---------------------------------------------------------------------------
# TestTodoState
# ---------------------------------------------------------------------------


class TestTodoState:
    """Tests for the TodoState enum."""

    def test_exactly_two_members(self) -> None:
        """Test that TodoState has exactly two members."""
        assert set(TodoState) == {TodoState.TODO, TodoState.DONE}

    def test_values_are_the_marker_keywords(self) -> None:
        """Test that each member's value is the keyword spelled inside the marker."""
        assert TodoState.TODO.value == "TODO"
        assert TodoState.DONE.value == "DONE"

    def test_captured_keyword_resolves_by_value_lookup(self) -> None:
        """Test that a keyword string resolves to its member by plain value lookup."""
        assert TodoState("TODO") is TodoState.TODO
        assert TodoState("DONE") is TodoState.DONE


# ---------------------------------------------------------------------------
# TestTodoMarkerRe
# ---------------------------------------------------------------------------


class TestTodoMarkerRe:
    """Tests for the TODO_MARKER_RE pattern."""

    def test_matches_the_todo_marker(self) -> None:
        """Test that {{[[TODO]]}} matches with the state group capturing TODO."""
        matched = TODO_MARKER_RE.match("{{[[TODO]]}} an open item")
        assert matched is not None
        assert matched.group("state") == "TODO"

    def test_matches_the_done_marker(self) -> None:
        """Test that {{[[DONE]]}} matches with the state group capturing DONE."""
        matched = TODO_MARKER_RE.match("{{[[DONE]]}} a completed item")
        assert matched is not None
        assert matched.group("state") == "DONE"

    def test_rejects_the_raw_spelling(self) -> None:
        """Test that the bare {{TODO}} spelling, unhandled by the Roam UI, does not match."""
        assert TODO_MARKER_RE.match("{{TODO}} an open item") is None

    def test_rejects_other_keywords(self) -> None:
        """Test that a page-reference component with a non-state keyword does not match."""
        assert TODO_MARKER_RE.match("{{[[LATER]]}} an item") is None

    def test_rejects_lowercase_keywords(self) -> None:
        """Test that the marker keywords are case-sensitive."""
        assert TODO_MARKER_RE.match("{{[[todo]]}} an item") is None


# ---------------------------------------------------------------------------
# TestParseTodo
# ---------------------------------------------------------------------------


class TestParseTodo:
    """Tests for the parse_todo() decomposition."""

    def test_plain_marker_decomposes(self) -> None:
        """Test that a marker-led string decomposes into its state and marker-free text."""
        assert parse_todo("{{[[TODO]]}} an open item") == RoamTodo(state=TodoState.TODO, text="an open item")

    def test_marker_alone_yields_empty_text(self) -> None:
        """Test that a string that is exactly the marker yields an empty text."""
        assert parse_todo("{{[[DONE]]}}") == RoamTodo(state=TodoState.DONE, text="")

    def test_marker_inside_color_bold_markup_is_recognized(self) -> None:
        """Test that a marker wrapped by a color tag and bold opener is recognized, Roam-faithfully."""
        parsed = parse_todo("#c:FUCHSIA **{{[[TODO]]}} a bold fuchsia item**")
        assert parsed == RoamTodo(state=TodoState.TODO, text="#c:FUCHSIA **a bold fuchsia item**")

    def test_marker_inside_bold_markup_is_recognized(self) -> None:
        """Test that a marker wrapped by a bare bold opener is recognized and excised in place."""
        parsed = parse_todo("**{{[[DONE]]}} a bold item**")
        assert parsed == RoamTodo(state=TodoState.DONE, text="**a bold item**")

    def test_marker_inside_highlight_markup_is_recognized(self) -> None:
        """Test that a marker wrapped by a highlight opener is recognized and excised in place."""
        parsed = parse_todo("^^{{[[TODO]]}} a highlighted item^^")
        assert parsed == RoamTodo(state=TodoState.TODO, text="^^a highlighted item^^")

    def test_text_before_marker_disqualifies(self) -> None:
        """Test that ordinary text ahead of the marker keeps the string from being a TODO item."""
        assert parse_todo("see {{[[TODO]]}} here") is None

    def test_closed_emphasis_before_marker_disqualifies(self) -> None:
        """Test that a completed emphasis span ahead of the marker is content, not leading markup."""
        assert parse_todo("**bold** {{[[TODO]]}} an item") is None

    def test_raw_spelling_yields_none(self) -> None:
        """Test that the bare {{TODO}} spelling yields None."""
        assert parse_todo("{{TODO}} an open item") is None

    def test_plain_text_yields_none(self) -> None:
        """Test that a string with no marker yields None."""
        assert parse_todo("just a plain block") is None


# ---------------------------------------------------------------------------
# TestTodoState function
# ---------------------------------------------------------------------------


class TestTodoStateFunction:
    """Tests for the todo_state() function."""

    def test_todo_marker_yields_todo(self) -> None:
        """Test that a {{[[TODO]]}}-led string yields TodoState.TODO."""
        assert todo_state("{{[[TODO]]}} an open item") is TodoState.TODO

    def test_done_marker_yields_done(self) -> None:
        """Test that a {{[[DONE]]}}-led string yields TodoState.DONE."""
        assert todo_state("{{[[DONE]]}} a completed item") is TodoState.DONE

    def test_marker_alone_yields_its_state(self) -> None:
        """Test that a string that is exactly the marker yields its state."""
        assert todo_state("{{[[TODO]]}}") is TodoState.TODO

    def test_surrounding_whitespace_is_tolerated(self) -> None:
        """Test that whitespace around the marker-led string is stripped before matching."""
        assert todo_state("  {{[[DONE]]}} a completed item  ") is TodoState.DONE

    def test_raw_spelling_yields_none(self) -> None:
        """Test that the bare {{TODO}} spelling yields None."""
        assert todo_state("{{TODO}} an open item") is None

    def test_marker_amid_text_yields_none(self) -> None:
        """Test that a marker appearing amid the text, not leading it, yields None."""
        assert todo_state("see {{[[TODO]]}} here") is None

    def test_plain_text_yields_none(self) -> None:
        """Test that a string with no marker yields None."""
        assert todo_state("just a plain block") is None

    def test_null_string_raises_validation_error(self) -> None:
        """Test that passing None raises a ValidationError."""
        with pytest.raises(ValidationError):
            todo_state(None)  # type: ignore[arg-type]
