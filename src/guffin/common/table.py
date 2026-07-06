"""Table data model and view/styling model.

Public symbols:

- :class:`Table` — 2D data model for a table with optional row and column headers.
- :class:`HAlign` — horizontal alignment options for table cell content.
- :class:`CellStyle` — visual styling for a single table cell.
- :class:`TableStyle` — view/display/styling overlay for a :class:`Table`.
"""

import enum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator, validate_call


class Table(BaseModel):
    """2D data model for a table with optional row and column headers.

    Cells are stored as a rectangular grid of strings.  All rows must have the
    same number of columns; this invariant is enforced at construction time.
    Pydantic coerces lists to tuples on input, so
    ``Table(rows=[["a", "b"], ["c", "d"]])`` is valid.

    Attributes:
        rows: Rectangular grid of cell-content strings, indexed first by row
            then by column.
        has_row_header: When ``True``, the first row is treated as a
            column-header row whose cells name each column.
        has_col_header: When ``True``, the first column is treated as a
            row-header column whose cells name each row.
    """

    model_config = ConfigDict(frozen=True)

    rows: tuple[tuple[str, ...], ...] = Field(
        ..., description="Rectangular grid of cell-content strings, indexed row-first."
    )
    has_row_header: bool = Field(default=False, description="First row is a column-header row.")
    has_col_header: bool = Field(default=False, description="First column is a row-header column.")

    @model_validator(mode="after")
    def _validate_rectangular(self) -> Table:
        if not self.rows:
            raise ValueError("rows must be non-empty")
        col_count: Final[int] = len(self.rows[0])
        ragged: Final[list[str]] = [
            f"row {idx} has {len(row)}" for idx, row in enumerate(self.rows[1:], start=1) if len(row) != col_count
        ]
        if ragged:
            raise ValueError(
                f"all rows must have the same column count; row 0 has {col_count} column(s) but " + "; ".join(ragged)
            )
        return self

    @property
    def num_rows(self) -> int:
        """Total number of rows, including the row header if present."""
        return len(self.rows)

    @property
    def num_cols(self) -> int:
        """Total number of columns, including the column header if present."""
        return len(self.rows[0])


class HAlign(enum.StrEnum):
    """Horizontal alignment of content within a table cell."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class CellStyle(BaseModel):
    """Visual styling for a single table cell.

    All fields default to neutral/unstyled values so a :class:`CellStyle` can
    serve as a partial override: fields at their default carry no intentional
    style and may be superseded by a lower-priority style in the rendering pass.

    Attributes:
        color: Foreground color as a CSS/Rich color string (e.g. ``"red"``,
            ``"#ff0000"``); ``None`` means inherit from context.
        background: Background color as a CSS/Rich color string; ``None`` means
            inherit from context.
        align: Horizontal alignment of cell content.
    """

    model_config = ConfigDict(frozen=True)

    color: str | None = Field(default=None, description="Foreground color string; None means inherit.")
    background: str | None = Field(default=None, description="Background color string; None means inherit.")
    align: HAlign = Field(default=HAlign.LEFT, description="Horizontal alignment of cell content.")


def _empty_cell_styles() -> dict[tuple[int, int], CellStyle]:
    return {}


class TableStyle(BaseModel):
    """View/display/styling overlay for a :class:`Table`.

    Styling is applied in priority order (highest to lowest):

    1. Per-cell override from :attr:`cell_styles`.
    2. Header-row style from :attr:`header_row_style` (cells in the first row
       when :attr:`~Table.has_row_header` is ``True``).
    3. Header-column style from :attr:`header_col_style` (cells in the first
       column when :attr:`~Table.has_col_header` is ``True``).
    4. Default cell style from :attr:`default_cell_style`.
    5. A bare :class:`CellStyle` (all defaults) when no rule matches.

    Attributes:
        cell_styles: Per-cell style overrides keyed by zero-based
            ``(row_index, col_index)`` coordinate.
        column_widths: Per-column explicit widths in characters; ``None`` at a
            position means auto-size that column.  An empty tuple means all
            columns are auto-sized.
        header_row_style: Style applied to every cell in the header row.
        header_col_style: Style applied to every cell in the header column.
        default_cell_style: Fallback style for cells not matched by a
            higher-priority rule.
    """

    model_config = ConfigDict(frozen=True)

    cell_styles: dict[tuple[int, int], CellStyle] = Field(
        default_factory=_empty_cell_styles,
        description="Per-cell style overrides keyed by (row_index, col_index).",
    )
    column_widths: tuple[int | None, ...] = Field(
        default=(),
        description="Per-column widths in characters; None means auto-size; empty means all auto.",
    )
    header_row_style: CellStyle | None = Field(
        default=None, description="Style applied to every cell in the header row."
    )
    header_col_style: CellStyle | None = Field(
        default=None, description="Style applied to every cell in the header column."
    )
    default_cell_style: CellStyle | None = Field(
        default=None, description="Fallback style for cells not matched by a higher-priority rule."
    )

    @validate_call
    def style_for(self, row_index: int, col_index: int, table: Table) -> CellStyle:
        """Return the effective :class:`CellStyle` for the cell at (*row_index*, *col_index*).

        Applies the priority cascade described in the class docstring.

        Args:
            row_index: Zero-based row index of the target cell.
            col_index: Zero-based column index of the target cell.
            table: The :class:`Table` this style is overlaid on; used to
                determine whether the cell falls within a header row or column.

        Returns:
            The highest-priority :class:`CellStyle` that applies to the cell,
            falling back to an all-default :class:`CellStyle` when no rule matches.
        """
        override: Final[CellStyle | None] = self.cell_styles.get((row_index, col_index))
        if override is not None:
            return override
        if table.has_row_header and row_index == 0 and self.header_row_style is not None:
            return self.header_row_style
        if table.has_col_header and col_index == 0 and self.header_col_style is not None:
            return self.header_col_style
        if self.default_cell_style is not None:
            return self.default_cell_style
        return CellStyle()
