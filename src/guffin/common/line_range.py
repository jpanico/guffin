"""An inclusive 1-based line range within a text, and its selection operation — with no domain coupling.

Public symbols:

- :class:`LineRange` — an inclusive 1-based line range within a text.
- :func:`sliced_line_range` — the lines of a text that a range selects.
"""

from typing import Final, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator, validate_call


class LineRange(BaseModel):
    """An inclusive 1-based line range within a text.

    A single line is the degenerate range whose ``start`` equals its ``end``.

    Attributes:
        start: First line of the range, 1-based.
        end: Last line of the range, inclusive; never before ``start``.
    """

    model_config = ConfigDict(frozen=True)

    start: int = Field(..., ge=1)
    end: int = Field(..., ge=1)

    @model_validator(mode="after")
    def _end_not_before_start(self) -> Self:
        """Reject a range whose ``end`` precedes its ``start``."""
        if self.end < self.start:
            raise ValueError(f"line range end {self.end} precedes start {self.start}")
        return self


@validate_call
def sliced_line_range(text: str, line_range: LineRange | None) -> str:
    """Return the lines of *text* that *line_range* selects.

    Deliberately strict about overflow: a range reaching beyond the text's last line raises
    rather than silently truncating, so a stale range cannot masquerade as a shorter
    selection.  A lenient consumer should clamp the range before calling.

    Args:
        text: The text to slice.
        line_range: The inclusive 1-based range to select, or ``None`` for all of *text*.

    Returns:
        The selected lines, newline-joined; *text* unchanged when *line_range* is ``None``.

    Raises:
        ValueError: If *line_range* ends beyond the last line of *text*.
    """
    if line_range is None:
        return text
    lines: Final[list[str]] = text.split("\n")
    if line_range.end > len(lines):
        raise ValueError(f"line range L{line_range.start}-L{line_range.end} exceeds the file's {len(lines)} lines")
    return "\n".join(lines[line_range.start - 1 : line_range.end])
