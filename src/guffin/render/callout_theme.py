"""The callout look: which colour family each callout type is a card of, and each format's expression of it.

A callout box is a *card* of the visual design language (:mod:`~guffin.render.design_language`),
and its type chooses the card's colour family: an informational note is the blue family, a plain
note the neutral one, a warning the amber, a success the green, a danger the red, and so on.  The
family's fill, emphasis stroke, and ink then make the box's title band, frame, and title text, in
every output format alike, and the family's meaning is what the colour says.  The choice is
declared once here, for every :class:`~guffin.roam.blockquote.CalloutType`, and each format
derives its own expression of the resulting tokens: stylesheet rules for the EPUB, a Typst
configuration dictionary for the PDF template.

Public symbols:

- **Constants**: :data:`CALLOUT_FAMILY` — the ``CalloutType`` → ``DesignFamily`` map (covers every
  member).
- **Functions**: :func:`callout_colors` — the colour family of a callout type; :func:`callout_css` —
  the EPUB stylesheet rules styling every callout to its theme; :func:`typst_callout_tokens` — the
  Bergfink ``cfg`` entries styling the PDF's callouts, as a Typst dictionary literal.
"""

from typing import Final

from pydantic import validate_call

from guffin.render.design_language import (
    CALLOUT_THEME,
    FAMILY_PALETTE,
    CalloutTheme,
    ColorFamily,
    DesignFamily,
    typst_dictionary,
    typst_rgb,
)
from guffin.roam.blockquote import CalloutType

CALLOUT_FAMILY: Final[dict[CalloutType, DesignFamily]] = {
    CalloutType.INFO: DesignFamily.BLUE,
    CalloutType.NOTE: DesignFamily.NEUTRAL,
    CalloutType.EXAMPLE: DesignFamily.VIOLET,
    CalloutType.SUMMARY: DesignFamily.TEAL,
    CalloutType.QUESTION: DesignFamily.AMBER,
    CalloutType.TIP: DesignFamily.GREEN,
    CalloutType.SUCCESS: DesignFamily.GREEN,
    CalloutType.WARNING: DesignFamily.AMBER,
    CalloutType.DANGER: DesignFamily.RED,
    CalloutType.FAILURE: DesignFamily.RED,
    CalloutType.BUG: DesignFamily.RED,
}
"""The colour family each callout type is a card of; covers every ``CalloutType`` member."""


@validate_call
def callout_colors(callout_type: CalloutType) -> ColorFamily:
    """Return the colours of the family *callout_type* is a card of."""
    return FAMILY_PALETTE[CALLOUT_FAMILY[callout_type]]


def _css_class(callout_type: CalloutType) -> str:
    """Return the class a callout of *callout_type* carries in the rendered document."""
    return f"callout-{callout_type.value.lower()}"


@validate_call
def callout_css(theme: CalloutTheme = CALLOUT_THEME) -> str:
    """Return the stylesheet rules that style every ``div.callout`` to *theme*.

    Written for the markup the shared document build emits — ``div.callout.callout-<type>`` holding
    a ``div.callout-title`` (the icon and the title) and the body blocks, with ``callout-no-body``
    marking a title-only callout — and for reading systems: the frame is the box's own border with
    a radius, and the title band, spanning the box through negative margins, rounds its own top
    corners (and, without a body, its bottom ones), since a block's background is never clipped to
    its parent's radius.  The icon, an inline SVG drawn in ``currentColor``, takes the band's text
    colour.  One rule per callout type gives the box its family's colours.

    Args:
        theme: The callout tokens to express.

    Returns:
        The CSS text, ending in a newline.
    """
    radius: Final[str] = f"{theme.radius_em}em"
    rules: Final[list[str]] = [
        "/* Callouts: a card of the design language (guffin/render/callout_theme.py). */",
        "div.callout {",
        f"  border: {theme.frame_width_em}em solid;",
        f"  border-radius: {radius};",
        f"  padding: 0 {theme.body_inset_x_em}em {theme.body_inset_y_em}em;",
        "}",
        "div.callout-title {",
        f"  padding: {theme.header_inset_y_em}em {theme.header_inset_x_em}em;",
        f"  margin: 0 -{theme.body_inset_x_em}em;",
        f"  font-weight: {theme.title_weight};",
        f"  border-bottom: {theme.frame_width_em}em solid;",
        f"  border-top-left-radius: {radius};",
        f"  border-top-right-radius: {radius};",
        "}",
        f"div.callout-title + * {{ margin-top: {theme.body_inset_y_em}em; }}",
        "div.callout.callout-no-body > div.callout-title {",
        f"  border-bottom-left-radius: {radius};",
        f"  border-bottom-right-radius: {radius};",
        "}",
        f"div.callout-title svg {{ width: {theme.icon_size_em}em; height: {theme.icon_size_em}em; }}",
    ]
    for callout_type in CalloutType:
        colors: ColorFamily = callout_colors(callout_type)
        selector: str = f"div.{_css_class(callout_type)}"
        rules.append(f"{selector} {{ border-color: {colors.emphasis}; }}")
        rules.append(
            f"{selector} > div.callout-title {{ background-color: {colors.fill}; color: {colors.ink}; "
            f"border-bottom-color: {colors.emphasis}; }}"
        )
    return "\n".join(rules) + "\n"


@validate_call
def typst_callout_tokens(theme: CalloutTheme = CALLOUT_THEME) -> str:
    """Return the Bergfink ``cfg`` entries that style the PDF's callouts to *theme*, as a Typst dictionary literal.

    The measures (``callout-radius``, ``callout-frame-width``, the insets, the title weight, the
    icon size) and ``callout-colors``, a dictionary keyed by callout type name (``info``, ``note``,
    …) of each type's ``fill``, ``frame`` (the family's emphasis stroke), and ``ink``.

    Args:
        theme: The callout tokens to express.

    Returns:
        A ``(key: value, …)`` Typst dictionary literal, for the template to join onto its ``cfg``.
    """
    colors_by_type: Final[dict[str, str]] = {
        callout_type.value.lower(): typst_dictionary(
            {
                "fill": typst_rgb(callout_colors(callout_type).fill),
                "frame": typst_rgb(callout_colors(callout_type).emphasis),
                "ink": typst_rgb(callout_colors(callout_type).ink),
            }
        )
        for callout_type in CalloutType
    }
    return typst_dictionary(
        {
            "callout-radius": f"{theme.radius_em}em",
            "callout-frame-width": f"{theme.frame_width_em}em",
            "callout-header-inset": f"(x: {theme.header_inset_x_em}em, y: {theme.header_inset_y_em}em)",
            "callout-body-inset": f"(x: {theme.body_inset_x_em}em, y: {theme.body_inset_y_em}em)",
            "callout-title-weight": str(theme.title_weight),
            "callout-icon-size": f"{theme.icon_size_em}em",
            "callout-colors": typst_dictionary(colors_by_type),
        }
    )
