"""Markdown post-processing: text rewrites applied to Pandoc's GFM output.

Each pass operates on the finished GFM string, before it is written to disk:

- **List-separator comment removal.**  Pandoc's GFM writer emits an empty ``<!-- -->`` HTML
  comment between two adjacent lists to keep them from merging when the Markdown is re-parsed.
  Guffin's sibling blocks are intentionally a single continuous outline, and some Markdown
  renderers (e.g. Typora) show the comment literally, so :func:`strip_list_separator_comments`
  removes it — letting the adjacent lists merge.
- **Fenced blank-line indentation.**  Pandoc's GFM writer indents a fenced code block nested in a
  list item, but writes the code's blank lines as completely empty lines.  Per CommonMark the
  fence still holds together — blank lines inside a fenced block are fence content — but lax
  renderers (e.g. Typora) end the list-item context at the empty line, splitting one listing into
  a code block per blank-line-separated section, so :func:`indent_fenced_blank_lines` pads each
  blank line to the fence's own indentation.  A conformant parser strips that indentation back
  off (it never exceeds the container's), so the code content is unchanged.

Public symbols:

- **Functions**: :func:`strip_list_separator_comments` — remove Pandoc's empty ``<!-- -->``
  list-separator comments from a GFM string; :func:`indent_fenced_blank_lines` — pad the blank
  lines inside each fenced code block to the fence's indentation.
"""

from typing import Final

import regex
from pydantic import validate_call

_LIST_SEPARATOR_COMMENT_RE: Final[regex.Pattern[str]] = regex.compile(r"\n\n[ \t]*<!-- -->[ \t]*\n\n")
"""Matches Pandoc's empty ``<!-- -->`` list-separator comment (on its own line, blank-line padded).

The GFM writer emits this between two adjacent lists to keep them from merging on re-parse.  Our
sibling blocks are intentionally a single continuous outline, and some renderers (e.g. Typora) show
the comment literally, so it is stripped from the output — letting the adjacent lists merge.
"""

_FENCE_OPEN_RE: Final[regex.Pattern[str]] = regex.compile(r"^([ \t]*)(`{3,}|~{3,})")
"""Matches a line opening a fenced code block: leading indentation, then the fence marker."""


@validate_call
def strip_list_separator_comments(gfm: str) -> str:
    """Return *gfm* with Pandoc's empty ``<!-- -->`` list-separator comments removed.

    Each blank-line-padded ``<!-- -->`` comment the GFM writer inserts between two adjacent lists
    is collapsed back to a single paragraph break, letting the lists merge into one continuous
    outline.  A string carrying no such comment is returned unchanged.

    Args:
        gfm: The GFM text produced by Pandoc.

    Returns:
        The GFM text with every list-separator comment removed.
    """
    return _LIST_SEPARATOR_COMMENT_RE.sub("\n\n", gfm)


def _closing_fence_pattern(opening_marker: str) -> regex.Pattern[str]:
    """Return the pattern matching the line that closes a fence opened with *opening_marker*.

    A closing fence repeats the opening marker's character at least as many times, with nothing
    but whitespace around it.
    """
    return regex.compile(rf"^[ \t]*{regex.escape(opening_marker[0])}{{{len(opening_marker)},}}[ \t]*$")


@validate_call
def indent_fenced_blank_lines(gfm: str) -> str:
    """Return *gfm* with each fenced code block's blank lines padded to the fence's indentation.

    A completely empty line between a fence's opening and closing markers becomes the opening
    fence's leading indentation; every other line — fence content with text, whitespace-only code
    lines, and everything outside a fence — is untouched.  For an unindented fence the padding is
    the empty string, so the text is unchanged.  A conformant CommonMark parser strips the added
    indentation back off (it never exceeds the enclosing container's), so the parsed code content
    is identical; the padding only keeps lax renderers from ending a list item at the empty line
    and splitting the fence.

    Args:
        gfm: The GFM text produced by Pandoc.

    Returns:
        The GFM text with every in-fence blank line carrying its fence's indentation.
    """
    padded: Final[list[str]] = []
    fence: tuple[str, regex.Pattern[str]] | None = None
    for line in gfm.split("\n"):
        if fence is None:
            opening: regex.Match[str] | None = _FENCE_OPEN_RE.match(line)
            if opening is not None:
                fence = (opening.group(1), _closing_fence_pattern(opening.group(2)))
            padded.append(line)
            continue
        fence_indent, closing_re = fence
        if closing_re.match(line) is not None:
            fence = None
            padded.append(line)
            continue
        padded.append(fence_indent if line == "" else line)
    return "\n".join(padded)
