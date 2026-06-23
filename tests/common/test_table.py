"""Unit tests for guffin.common.table."""

import pytest

from guffin.common.table import CellStyle, HAlign, Table, TableStyle


class TestTable:
    """Tests for Table — rectangular grid construction and access."""

    def test_basic_construction(self) -> None:
        """Test that a Table can be constructed from a nested tuple."""
        table = Table(rows=(("a", "b"), ("c", "d")))
        assert table.rows == (("a", "b"), ("c", "d"))

    def test_list_input_coerced_to_tuple(self) -> None:
        """Test that Pydantic coerces list-of-lists to tuple-of-tuples."""
        table = Table(rows=[["a", "b"], ["c", "d"]])  # type: ignore[arg-type]
        assert isinstance(table.rows, tuple)
        assert isinstance(table.rows[0], tuple)

    def test_cell_access(self) -> None:
        """Test direct tuple indexing to retrieve a cell value."""
        table = Table(rows=(("x", "y", "z"), ("1", "2", "3"), ("a", "b", "c")))
        assert table.rows[2][2] == "c"

    def test_num_rows(self) -> None:
        """Test that num_rows reports the correct row count."""
        table = Table(rows=(("a", "b"), ("c", "d"), ("e", "f")))
        assert table.num_rows == 3

    def test_num_cols(self) -> None:
        """Test that num_cols reports the correct column count."""
        table = Table(rows=(("a", "b", "c"), ("d", "e", "f")))
        assert table.num_cols == 3

    def test_header_flags_default_false(self) -> None:
        """Test that has_row_header and has_col_header default to False."""
        table = Table(rows=(("a",),))
        assert table.has_row_header is False
        assert table.has_col_header is False

    def test_header_flags_set(self) -> None:
        """Test that header flags can be set to True."""
        table = Table(rows=(("h", "a"), ("b", "c")), has_row_header=True, has_col_header=True)
        assert table.has_row_header is True
        assert table.has_col_header is True

    def test_empty_rows_raises(self) -> None:
        """Test that an empty rows tuple raises a validation error."""
        with pytest.raises(Exception):
            Table(rows=())

    def test_jagged_rows_raises(self) -> None:
        """Test that rows with differing column counts raise a validation error."""
        with pytest.raises(Exception):
            Table(rows=(("a", "b"), ("c",)))

    def test_immutable_rows(self) -> None:
        """Test that attempting to replace the rows attribute raises an error."""
        table = Table(rows=(("a", "b"),))
        with pytest.raises(Exception):
            table.rows = (("x", "y"),)  # type: ignore[misc]


class TestTableStyle:
    """Tests for TableStyle — style resolution priority cascade."""

    def _3x3(self, *, row_header: bool = False, col_header: bool = False) -> Table:
        return Table(
            rows=(("h1", "h2", "h3"), ("a", "b", "c"), ("d", "e", "f")),
            has_row_header=row_header,
            has_col_header=col_header,
        )

    def test_no_rules_returns_default_cell_style(self) -> None:
        """Test that a TableStyle with no rules returns a bare CellStyle."""
        style = TableStyle()
        result = style.style_for(1, 1, self._3x3())
        assert result == CellStyle()

    def test_default_cell_style_applied(self) -> None:
        """Test that default_cell_style is returned when no higher-priority rule matches."""
        default = CellStyle(align=HAlign.CENTER)
        style = TableStyle(default_cell_style=default)
        assert style.style_for(1, 1, self._3x3()) == default

    def test_per_cell_override_wins_over_default(self) -> None:
        """Test that a per-cell entry in cell_styles beats default_cell_style."""
        default = CellStyle(align=HAlign.CENTER)
        override = CellStyle(align=HAlign.RIGHT, color="red")
        style = TableStyle(cell_styles={(1, 2): override}, default_cell_style=default)
        assert style.style_for(1, 2, self._3x3()) == override

    def test_per_cell_override_wins_over_header_row(self) -> None:
        """Test that a per-cell entry beats header_row_style even for a header cell."""
        header_style = CellStyle(align=HAlign.CENTER)
        override = CellStyle(color="blue")
        style = TableStyle(cell_styles={(0, 1): override}, header_row_style=header_style)
        table = self._3x3(row_header=True)
        assert style.style_for(0, 1, table) == override

    def test_header_row_style_applied_to_first_row(self) -> None:
        """Test that header_row_style is returned for cells in row 0 when has_row_header is True."""
        header_style = CellStyle(align=HAlign.CENTER)
        style = TableStyle(header_row_style=header_style)
        table = self._3x3(row_header=True)
        assert style.style_for(0, 0, table) == header_style
        assert style.style_for(0, 2, table) == header_style

    def test_header_row_style_not_applied_without_flag(self) -> None:
        """Test that header_row_style is ignored when has_row_header is False."""
        header_style = CellStyle(align=HAlign.CENTER)
        style = TableStyle(header_row_style=header_style)
        assert style.style_for(0, 0, self._3x3(row_header=False)) == CellStyle()

    def test_header_col_style_applied_to_first_col(self) -> None:
        """Test that header_col_style is returned for cells in col 0 when has_col_header is True."""
        col_style = CellStyle(background="#eeeeee")
        style = TableStyle(header_col_style=col_style)
        table = self._3x3(col_header=True)
        assert style.style_for(1, 0, table) == col_style
        assert style.style_for(2, 0, table) == col_style

    def test_header_row_beats_header_col_at_corner(self) -> None:
        """Test that header_row_style takes priority over header_col_style at (0, 0)."""
        row_style = CellStyle(align=HAlign.CENTER)
        col_style = CellStyle(background="gray")
        style = TableStyle(header_row_style=row_style, header_col_style=col_style)
        table = self._3x3(row_header=True, col_header=True)
        assert style.style_for(0, 0, table) == row_style

    def test_non_header_cell_falls_through_to_default(self) -> None:
        """Test that a non-header body cell falls through to default_cell_style."""
        default = CellStyle(color="green")
        style = TableStyle(
            header_row_style=CellStyle(align=HAlign.CENTER),
            header_col_style=CellStyle(background="gray"),
            default_cell_style=default,
        )
        table = self._3x3(row_header=True, col_header=True)
        assert style.style_for(1, 1, table) == default
