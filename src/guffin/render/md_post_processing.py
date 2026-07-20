"""Markdown post-processing: text rewrites applied to Pandoc's GFM output.

One pass operates on the finished GFM string, before it is written to disk:

- **List-separator comment removal.**  Pandoc's GFM writer emits an empty ``<!-- -->`` HTML
  comment between two adjacent lists to keep them from merging when the Markdown is re-parsed.
  Guffin's sibling blocks are intentionally a single continuous outline, and some Markdown
  renderers (e.g. Typora) show the comment literally, so :func:`strip_list_separator_comments`
  removes it — letting the adjacent lists merge.

Public symbols:

- **Functions**: :func:`strip_list_separator_comments` — remove Pandoc's empty ``<!-- -->``
  list-separator comments from a GFM string.
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
