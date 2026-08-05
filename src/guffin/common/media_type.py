"""IANA media type (MIME type) enumeration for Roam-hosted asset files.

Public symbols:

- :class:`MediaType` — IANA media type for assets fetched from Firebase Storage.
- :func:`is_image_type` — returns ``True`` if a :class:`MediaType` is an image MIME type.
"""

import enum
import mimetypes

from pydantic import validate_call


class MediaType(enum.StrEnum):
    """IANA media type (MIME type) for Roam-hosted asset files.

    Each member is defined as ``(mime_type, file_extension)``; the enum value
    (used for string comparison and Pydantic validation) is the MIME type string.
    Use :attr:`extension` to get the corresponding file extension, or
    :meth:`from_extension` to look up a member by extension.

    The vocabulary is deliberately confined to IANA-registered types.  A de facto
    vendor type with no IANA registration — e.g. ``application/vnd.apple.pkpass``,
    the unregistered MIME type Apple specifies for ``.pkpass`` Wallet passes — has
    no member, so a file of such a type resolves to ``None`` rather than to an
    unofficial name.
    """

    def __new__(cls, mime: str, ext: str) -> MediaType:
        """Create a new member whose string value is the MIME type."""
        obj = str.__new__(cls, mime)
        obj._value_ = mime
        return obj

    def __init__(self, mime: str, ext: str) -> None:
        """Store the file extension alongside the MIME type value."""
        self._ext: str = ext

    JPEG = "image/jpeg", ".jpg"
    PNG = "image/png", ".png"
    GIF = "image/gif", ".gif"
    WEBP = "image/webp", ".webp"
    SVG = "image/svg+xml", ".svg"
    TIFF = "image/tiff", ".tiff"
    BMP = "image/bmp", ".bmp"
    PDF = "application/pdf", ".pdf"
    MP4 = "video/mp4", ".mp4"
    MOV = "video/quicktime", ".mov"

    @property
    def extension(self) -> str:
        """Return the canonical file extension for this media type (e.g. ``'.jpg'``)."""
        return self._ext

    @classmethod
    def from_extension(cls, ext: str) -> MediaType | None:
        """Return the :class:`MediaType` for *ext*, or ``None`` if unrecognized.

        Args:
            ext: A dotted file extension string (e.g. ``'.jpg'``).

        Returns:
            The matching :class:`MediaType`, or ``None`` if *ext* is not recognized.
        """
        return next((m for m in cls if m._ext == ext), None)

    @classmethod
    def from_file_name(cls, file_name: str) -> MediaType | None:
        """Return the :class:`MediaType` inferred from *file_name*'s extension, or ``None``.

        Uses :func:`mimetypes.guess_type` to resolve the extension to a MIME type
        string, then maps that string to a :class:`MediaType` member.  This handles
        extension variants (e.g. ``'.jpeg'`` and ``'.jpg'`` both resolve to
        :attr:`JPEG`).

        Args:
            file_name: A filename string including extension (e.g. ``'photo.jpeg'``).

        Returns:
            The matching :class:`MediaType`, or ``None`` when the type cannot be
            determined or is not a recognized Roam asset media type.
        """
        guessed, _ = mimetypes.guess_type(file_name)
        if guessed is None:
            return None
        try:
            return cls(guessed)
        except ValueError:
            return None


@validate_call
def is_image_type(media_type: MediaType) -> bool:
    """Return ``True`` if *media_type* is an image MIME type (``image/*``).

    Args:
        media_type: The :class:`MediaType` to test.

    Returns:
        ``True`` if the MIME type starts with ``"image/"``; ``False`` otherwise.
    """
    return str(media_type).startswith("image/")
