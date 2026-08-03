"""Filename utilities.

Public symbols:

- :func:`shell_safe_filename` — normalize a string to be safe for POSIX
  filenames without shell escaping.
- :func:`url_file_name` — the filename encoded in a URL's path, or ``None``.
"""

import unicodedata
from typing import Final
from urllib.parse import unquote

import regex
from pydantic import HttpUrl, validate_call


@validate_call
def shell_safe_filename(text: str) -> str:
    """Normalize a string to be safe for POSIX filenames without shell escaping.

    Converts the string to use only characters that are safe in POSIX filenames
    and don't require escaping in standard Unix shells (bash, zsh, etc.).

    Safe characters: a-z, A-Z, 0-9, underscore (_), hyphen (-), period (.)

    Args:
        text: The string to normalize.

    Returns:
        A normalized string safe for use as a POSIX filename.

    Raises:
        ValidationError: If ``text`` is ``None`` or invalid.
    """
    result: Final[str] = unicodedata.normalize("NFKD", text)
    ascii_result: Final[str] = result.encode("ascii", "ignore").decode("ascii")
    no_spaces: Final[str] = regex.sub(r" +", "_", ascii_result)
    safe_chars: Final[str] = regex.sub(r"[^a-zA-Z0-9._-]", "", no_spaces)
    collapsed: Final[str] = regex.sub(r"_+", "_", safe_chars)
    return collapsed.lstrip("_")


@validate_call
def url_file_name(url: HttpUrl) -> str | None:
    """Return the filename encoded in *url*'s path, or ``None``.

    The filename is the basename of the URL path's percent-decoded last segment: the
    segment is decoded first, so a segment that percent-encodes a whole path (``%2F``
    for ``/``) still yields only its final name.  The query string and fragment never
    contribute.

    Args:
        url: The URL to read.

    Returns:
        The decoded filename (e.g. ``"image.png"``), or ``None`` when the URL's path
        ends in a separator or has no path at all.
    """
    last_segment: Final[str] = (url.path or "").rsplit("/", 1)[-1]
    file_name: Final[str] = unquote(last_segment).rsplit("/", 1)[-1]
    return file_name if file_name else None
