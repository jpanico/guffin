"""The visual design language's tokens — the single source of the values every format styles to.

The language (``docs/visual-design-language.md``) gives every element a *colour family* with three
members — a light *fill* for its background, a *stroke* for its outline, and a dark *ink* for the
text that names it — plus a heavier *emphasis* stroke for the one element of its kind being pointed
at, and sizes its radii, strokes, and padding in ems of the surrounding text so they scale with it.
Those tokens are declared once here, and each output format derives its own expression of them: a
stylesheet for the EPUB, a configuration dictionary for the PDF's Typst template.  Change a token
here and every format follows.

Public symbols:

- **Type aliases**: :data:`HexColor` — a ``#rrggbb`` colour string.
- **Enums**: :class:`DesignFamily` — the colour families, each carrying the meaning it stands for.
- **Models**: :class:`ColorFamily` — a family's fill, stroke, emphasis, and ink; :class:`TableTheme`
  — a table's tokens, as a card of one family.
- **Constants**: :data:`FAMILY_PALETTE` — the ``DesignFamily`` → ``ColorFamily`` map (covers every
  member); :data:`TEXT_INK` / :data:`LABEL_INK` / :data:`MUTED_INK` — the neutral inks for titles,
  labels, and descriptions; :data:`TABLE_THEME` — the table tokens in force.
- **Functions**: :func:`table_css` — the EPUB stylesheet rules styling a table to its theme;
  :func:`typst_table_tokens` — the Bergfink ``cfg`` entries styling a PDF table to its theme, as a
  Typst dictionary literal.
"""

import enum
from typing import Annotated, Final

from pydantic import BaseModel, Field, validate_call

type HexColor = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
"""A ``#rrggbb`` colour string."""

TEXT_INK: Final[str] = "#161A22"
"""The ink of titles and names."""

LABEL_INK: Final[str] = "#3D4250"
"""The ink of labels, arrows, and a neutral panel's name."""

MUTED_INK: Final[str] = "#5A6170"
"""The ink of descriptions."""


class DesignFamily(enum.StrEnum):
    """A colour family of the design language, named for its hue and carrying its meaning.

    An element takes the family whose meaning it has, so the hue alone tells a reader what kind of
    thing it is looking at.
    """

    BLUE = "blue"
    NEUTRAL = "neutral"
    AMBER = "amber"
    TEAL = "teal"

    @property
    def meaning(self) -> str:
        """What an element of this family is: the kind of thing the hue stands for."""
        return _MEANING_BY_FAMILY[self]


_MEANING_BY_FAMILY: Final[dict[DesignFamily, str]] = {
    DesignFamily.BLUE: "the processor: whatever acts",
    DesignFamily.NEUTRAL: "the container: whatever holds other things",
    DesignFamily.AMBER: "instructions and code: the program as text",
    DesignFamily.TEAL: "data: the values a program reads and writes",
}


class ColorFamily(BaseModel, frozen=True):
    """The members of one colour family.

    Attributes:
        fill: The light background of an element of the family.
        stroke: The hairline outline of such an element.
        emphasis: The heavier, darker outline of the one element being pointed at, when the family
            has one; ``None`` for a family nothing is ever emphasised in.
        ink: The dark colour of the text that names the element.
    """

    fill: HexColor
    stroke: HexColor
    emphasis: HexColor | None
    ink: HexColor


FAMILY_PALETTE: Final[dict[DesignFamily, ColorFamily]] = {
    DesignFamily.BLUE: ColorFamily(fill="#EDF2FA", stroke="#C8D5EA", emphasis="#AFC0DC", ink="#234279"),
    DesignFamily.NEUTRAL: ColorFamily(fill="#F5F5F3", stroke="#DADAD5", emphasis=None, ink="#3D4250"),
    DesignFamily.AMBER: ColorFamily(fill="#FBEEE1", stroke="#EDD3B8", emphasis="#C96F2A", ink="#8E4A12"),
    DesignFamily.TEAL: ColorFamily(fill="#E6F2EF", stroke="#BFDCD5", emphasis=None, ink="#1E5F54"),
}
"""The colours of every ``DesignFamily``."""


class TableTheme(BaseModel, frozen=True):
    """A table's tokens: a *card* of one family.

    A table is white, framed by the family's emphasis stroke on a rounded outline, with its header
    row a band of the family's fill carrying the family's ink in a semibold weight, and its body rows
    parted by hairline rules in the family's stroke.  Columns are parted by their padding alone.
    Every length is in ems of the table's text, so the look scales with the type.

    Attributes:
        family: The colour family the table is a card of.
        frame_width_em: The thickness of the frame and of the rule under the header: the emphasis
            weight (1.5 px against the language's 15 px text).
        rule_width_em: The thickness of the rules between body rows: the hairline weight (1 px).
        radius_em: The corner radius of the frame: the card radius.
        inset_x_em: The padding at either side of a cell's content.
        inset_y_em: The padding above and below a cell's content.
        header_weight: The font weight of the header row's text, as a CSS weight number.
    """

    family: DesignFamily = DesignFamily.BLUE
    frame_width_em: float = 0.1
    rule_width_em: float = 0.07
    radius_em: float = 0.625
    inset_x_em: float = 0.9
    inset_y_em: float = 0.55
    header_weight: int = 600

    @property
    def colors(self) -> ColorFamily:
        """The table's colour family."""
        return FAMILY_PALETTE[self.family]

    @property
    def frame_color(self) -> str:
        """The colour of the frame and of the rule under the header: the family's emphasis stroke."""
        emphasis: Final[str | None] = self.colors.emphasis
        if emphasis is None:
            raise ValueError(f"a table cannot be a card of the {self.family} family, which has no emphasis stroke")
        return emphasis


TABLE_THEME: Final[TableTheme] = TableTheme()
"""The table tokens in force."""


@validate_call
def table_css(theme: TableTheme = TABLE_THEME) -> str:
    """Return the stylesheet rules that style a ``<table>`` to *theme*.

    Written for the markup Pandoc emits (``table`` > ``thead``/``tbody`` > ``tr`` > ``th``/``td``) and
    for the reading systems EPUBs are read in: separate borders, so the frame is the table's own
    border with a radius; the two top corner cells rounded to match, since a cell's background is
    never clipped to its table's radius; the body's rules as each row's top border from the second
    row on.  A system that lacks ``:last-child`` or ``border-radius`` shows a squarer table and
    nothing worse.

    Args:
        theme: The table tokens to express.

    Returns:
        The CSS text, ending in a newline.
    """
    colors: Final[ColorFamily] = theme.colors
    frame: Final[str] = f"{theme.frame_width_em}em solid {theme.frame_color}"
    rule: Final[str] = f"{theme.rule_width_em}em solid {colors.stroke}"
    radius: Final[str] = f"{theme.radius_em}em"
    rules: Final[list[str]] = [
        "/* Tables: a card of the design language (guffin/render/design_language.py). */",
        "table {",
        "  border-collapse: separate;",
        "  border-spacing: 0;",
        f"  border: {frame};",
        f"  border-radius: {radius};",
        "  margin: 1em 0;",
        "}",
        "th, td {",
        "  border: 0;",
        f"  padding: {theme.inset_y_em}em {theme.inset_x_em}em;",
        "}",
        "thead th {",
        f"  background-color: {colors.fill};",
        f"  color: {colors.ink};",
        f"  font-weight: {theme.header_weight};",
        f"  border-bottom: {frame};",
        "}",
        f"thead th:first-child {{ border-top-left-radius: {radius}; }}",
        f"thead th:last-child {{ border-top-right-radius: {radius}; }}",
        f"tbody tr + tr td {{ border-top: {rule}; }}",
    ]
    return "\n".join(rules) + "\n"


def _typst_stroke(width_em: float, color: str) -> str:
    """Return the Typst stroke expression for a *width_em* line in *color*."""
    return f'{width_em}em + rgb("{color}")'


@validate_call
def typst_table_tokens(theme: TableTheme = TABLE_THEME) -> str:
    """Return the Bergfink ``cfg`` entries that style a PDF table to *theme*, as a Typst dictionary literal.

    The keys are the template's table keys (``base_cfg.typ``): the frame and radius, the header
    row's fill, ink, and weight, the strokes between rows, and the cell inset.  The cell border
    strokes are ``none``, the frame drawing the outline, and so are the vertical strokes.  The
    striped fill, used by YAML-driven tables alone, is the neutral family's fill.

    Args:
        theme: The table tokens to express.

    Returns:
        A ``(key: value, …)`` Typst dictionary literal, for the template to join onto its ``cfg``.
    """
    colors: Final[ColorFamily] = theme.colors
    frame: Final[str] = _typst_stroke(theme.frame_width_em, theme.frame_color)
    entries: Final[dict[str, str]] = {
        "table-header-bg": f'rgb("{colors.fill}")',
        "table-header-ink": f'rgb("{colors.ink}")',
        "table-header-weight": str(theme.header_weight),
        "table-striped-bg": f'rgb("{FAMILY_PALETTE[DesignFamily.NEUTRAL].fill}")',
        "table-stroke-border-x": "none",
        "table-stroke-border-y": "none",
        "table-stroke-header-b": frame,
        "table-stroke-vertical": "none",
        "table-stroke-horizontal": _typst_stroke(theme.rule_width_em, colors.stroke),
        "table-frame-stroke": frame,
        "table-radius": f"{theme.radius_em}em",
        "table-inset": f"(x: {theme.inset_x_em}em, y: {theme.inset_y_em}em)",
    }
    body: Final[str] = ", ".join(f"{key}: {value}" for key, value in entries.items())
    return f"({body})"
