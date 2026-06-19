"""Normalize Roam flavored Markdown to Pandoc Markdown.

Roam Research uses a Markdown dialect ("Roamdown") that diverges from standard
Markdown in several ways.  This module transforms a single Roam block string into
a Pandoc Markdown-compatible string.  See ``docs/roam-md.md`` for a full
description of the differences.

The conversion functions operate on plain Python strings (one block string at a
time) and are stateless and side-effect-free.  They are designed to be composed
via :func:`to_pandoc_md`, which applies every transformation in a defined,
stable order.

Constructs intentionally left verbatim for future expansion:

- Block references — ``((block-uid))``
- Block embeds — ``{{embed: ((block-uid))}}``
- Other Roam components — ``{{TODO}}``, ``{{DONE}}``, ``{{query: ...}}``, etc.

Public symbols:

- :func:`to_pandoc_md` — apply all conversions to a Roam block string and
  return the Pandoc Markdown result.
- :func:`convert_color_bold` — convert Color Highlighter ``#c:COLOR **text**``
  spans → ``[**text**]{color="color"}`` bracketed spans.
- :func:`convert_code_blocks` — reposition Roam fenced code blocks so the
  opening and closing ```` ``` ```` fences each sit on their own line.
- :func:`convert_italics` — convert ``__italic__`` → ``*italic*``.
- :func:`convert_highlights` — convert ``^^text^^`` → ``[text]{.mark}``.
- :func:`convert_page_link_aliases` — convert ``[display]([[Page Name]])``
  → ``[display](Page Name)``.
- :func:`strip_double_brackets` — remove ``[[`` and ``]]`` delimiters, leaving
  the inner text (e.g. ``[[Page Name]]`` → ``Page Name``).
"""

import re

from pydantic import validate_call

# ---------------------------------------------------------------------------
# Module-level compiled patterns
# ---------------------------------------------------------------------------

# Roam fenced code block: ```lang\ncode``` where the opening fence (with its
# optional language tag) and the closing fence may share a line with adjacent
# content.  Group 1 captures the language/info string on the opening line;
# group 2 captures the code body up to the closing fence.
_CODE_BLOCK_RE: re.Pattern[str] = re.compile(r"```([^\n]*)\n(.*?)```", re.DOTALL)

# Roam italic: __text__ (double underscores).  Must not match bold (**text**).
# Negative look-behind/ahead prevents matching inside bold markers.
_ITALIC_RE: re.Pattern[str] = re.compile(r"(?<!\w)__(?!\s)(.+?)(?<!\s)__(?!\w)", re.DOTALL)

# Roam highlight: ^^text^^.  Converted to a Pandoc bracketed span with class
# "mark" via the bracketed_spans extension (enabled by default in Pandoc Markdown).
_HIGHLIGHT_RE: re.Pattern[str] = re.compile(r"\^\^(.+?)\^\^", re.DOTALL)

# Roam alias to a page link: [display text]([[Page Name]]).  Capture group 1 is
# the display text (no square brackets); group 2 is the page name (no square
# brackets).  Must be applied before strip_double_brackets so the [[...]] target
# can be identified and converted to a plain Pandoc Markdown link destination.
_PAGE_LINK_ALIAS_RE: re.Pattern[str] = re.compile(r"\[([^\[\]]+)\]\(\[\[([^\[\]]*)\]\]\)")

# Double-bracket delimiters used by Roam for page links ([[Page Name]]) and
# hashtag page links (#[[multi-word tag]]).  Matched and removed independently
# to handle arbitrarily nested page links (e.g. [[nested [[pages]]]]).
_DOUBLE_OPEN_RE: re.Pattern[str] = re.compile(r"\[\[")
_DOUBLE_CLOSE_RE: re.Pattern[str] = re.compile(r"\]\]")

# Color Highlighter extension: #c:COLOR **bold text**.  Group 1 is the color
# name (e.g. ORANGE); group 2 is the bold content between the ** delimiters.
_COLOR_BOLD_RE: re.Pattern[str] = re.compile(r"#c:([A-Za-z]+) \*\*(.+?)\*\*")

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@validate_call
def to_pandoc_md(roam_string: str) -> str:
    """Convert a Roam block string to Pandoc Markdown by applying all transformations.

    Transformations are applied in a fixed order designed to avoid
    double-substitution artefacts.  Each individual conversion is also
    available as a standalone function for testing or selective use.

    The following Roam constructs are intentionally left verbatim for future
    expansion: block references ``((uid))``, block embeds
    ``{{embed: ((uid))}}``, and other ``{{…}}`` components.

    Args:
        roam_string: A single Roam block string (the raw ``string`` field from a
            :class:`~guffin.roam.node.RoamNode`).

    Returns:
        The Pandoc Markdown string.
    """
    result: str = roam_string
    result = convert_color_bold(result)
    result = convert_code_blocks(result)
    result = convert_page_link_aliases(result)
    result = strip_double_brackets(result)
    result = convert_italics(result)
    result = convert_highlights(result)
    return result


@validate_call
def convert_code_blocks(roam_string: str) -> str:
    r"""Reposition Roam fenced code blocks so each fence sits on its own line.

    Roam stores a fenced code block as ```` ```lang\ncode``` ````, where the
    opening fence (with its language tag) can share a line with preceding text
    and the closing fence trails the final code line.  Pandoc only recognises a
    fenced code block when both the opening and closing ```` ``` ```` fences
    begin their own lines, so this function inserts the newlines needed to
    isolate them:

    - a newline is inserted before the opening fence unless it already starts
      the string or follows a newline;
    - the closing fence is moved onto its own line directly after the code body;
    - a newline is inserted after the closing fence when trailing content
      follows it on the same line.

    The language/info string on the opening fence is preserved verbatim.

    Args:
        roam_string: A Roam block string, possibly containing fenced code blocks.

    Returns:
        The string with every fenced code block repositioned onto isolated
        fence lines.
    """

    def _reposition(match: re.Match[str]) -> str:
        language: str = match.group(1)
        body: str = match.group(2).rstrip("\n")
        prefix: str = "" if match.start() == 0 or match.string[match.start() - 1] == "\n" else "\n"
        suffix: str = "" if match.end() == len(match.string) or match.string[match.end()] == "\n" else "\n"
        return f"{prefix}```{language}\n{body}\n```{suffix}"

    return _CODE_BLOCK_RE.sub(_reposition, roam_string)


@validate_call
def convert_italics(roam_string: str) -> str:
    """Convert Roam italic syntax to Pandoc Markdown italic syntax.

    Roam uses ``__double underscores__`` for italics; Pandoc Markdown uses
    ``*single asterisks*``.  This function replaces every ``__text__`` span
    with ``*text*``.

    Args:
        roam_string: A Roam block string, possibly containing ``__italic__`` spans.

    Returns:
        The string with all ``__italic__`` spans replaced by ``*italic*``.
    """
    return _ITALIC_RE.sub(r"*\1*", roam_string)


@validate_call
def convert_highlights(roam_string: str) -> str:
    """Convert Roam highlight syntax to a Pandoc Markdown bracketed span.

    Roam uses ``^^text^^`` for background highlights.  Pandoc Markdown
    represents this as ``[text]{.mark}`` via the ``bracketed_spans`` extension
    (enabled by default in Pandoc Markdown), which maps to a ``Span`` AST node
    with class ``mark``.

    Args:
        roam_string: A Roam block string, possibly containing ``^^highlight^^`` spans.

    Returns:
        The string with all ``^^text^^`` spans replaced by ``[text]{.mark}``.
    """
    return _HIGHLIGHT_RE.sub(r"[\1]{.mark}", roam_string)


@validate_call
def convert_color_bold(roam_string: str) -> str:
    """Convert Color Highlighter colorized bold spans to Pandoc bracketed spans.

    The Color Highlighter Roam extension uses ``#c:COLOR **bold text**`` to
    render bold text in a named color.  Each such span is converted to a Pandoc
    bracketed span with a ``color`` attribute:
    ``[**bold text**]{color="orange"}``.  The color name is lowercased for
    CSS compatibility.  Must run before other conversions so that any Roam
    constructs inside the bold content are still available for subsequent steps.

    Args:
        roam_string: A Roam block string, possibly containing
            ``#c:COLOR **text**`` spans.

    Returns:
        The string with all ``#c:COLOR **text**`` spans replaced by
        ``[**text**]{color="color"}`` bracketed spans.
    """
    return _COLOR_BOLD_RE.sub(
        lambda match: f'[**{match.group(2)}**]{{color="{match.group(1).lower()}"}}',
        roam_string,
    )


@validate_call
def convert_page_link_aliases(roam_string: str) -> str:
    """Convert Roam page-link aliases to Pandoc Markdown inline links.

    Roam supports ``[display text]([[Page Name]])`` to create an aliased link
    to a page.  This function converts each such construct to the Pandoc
    Markdown inline link ``[display text](Page Name)``, removing the
    ``[[``/``]]`` delimiters and using the page name as the link destination.

    Must be applied before :func:`strip_double_brackets` so that the ``[[…]]``
    target is identified and converted rather than blindly stripped.

    Args:
        roam_string: A Roam block string, possibly containing alias patterns.

    Returns:
        The string with all ``[display]([[Page Name]])`` patterns replaced by
        ``[display](Page Name)``.
    """
    return _PAGE_LINK_ALIAS_RE.sub(r"[\1](\2)", roam_string)


@validate_call
def strip_double_brackets(roam_string: str) -> str:
    """Remove ``[[`` and ``]]`` delimiters from *roam_string*, leaving inner text.

    Handles Roam page links (``[[Page Name]]``), hashtag page links
    (``#[[multi-word tag]]``), and arbitrarily nested page links
    (``[[nested [[pages]]]]``) by independently removing all ``[[`` and ``]]``
    occurrences.  Single square brackets ``[`` and ``]`` are intentionally
    preserved, as they carry meaning in Pandoc Markdown (link labels, bracketed
    spans, etc.).

    Examples::

        strip_double_brackets("[[Page Name]]")         # → "Page Name"
        strip_double_brackets("[[nested [[pages]]]]")  # → "nested pages"
        strip_double_brackets("#[[multi-word tag]]")   # → "#multi-word tag"
        strip_double_brackets("[text]")                # → "[text]"

    Args:
        roam_string: A Roam block string, possibly containing ``[[…]]`` constructs.

    Returns:
        The string with all ``[[`` and ``]]`` occurrences removed.
    """
    result: str = _DOUBLE_OPEN_RE.sub("", roam_string)
    result = _DOUBLE_CLOSE_RE.sub("", result)
    return result
