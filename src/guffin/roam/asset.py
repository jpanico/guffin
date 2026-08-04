"""Roam Research asset data model.

Public symbols:

- :class:`RoamAsset` — immutable representation of an asset fetched from Firebase Storage
  through the Roam API; :meth:`~RoamAsset.create` is the factory entry point.
- :class:`RoamImageAsset` — :class:`RoamAsset` subclass for image assets; adds
  :attr:`~RoamImageAsset.image_size`.
"""

import io
import logging
from datetime import datetime
from typing import Final

import imagesize  # pyright: ignore[reportMissingTypeStubs]
from pydantic import BaseModel, ConfigDict, Field

from guffin.common.geometry import ImageSize
from guffin.common.media_type import MediaType, is_image_type

logger = logging.getLogger(__name__)


def _imagesize_get(data: bytes) -> tuple[int, int]:
    result: Final[tuple[int, int]] = imagesize.get(io.BytesIO(data))  # type: ignore[no-untyped-call, assignment]
    if result == (-1, -1):
        logger.error("imagesize could not parse image contents (len=%d bytes)", len(data))
    return result


class RoamAsset(BaseModel):
    """Immutable representation of an asset fetched from Firebase Storage through the Roam API.

    Roam uploads all user assets (files, media) to Firebase Storage, and stores only
    Firebase Storage locators (URLs) within the Roam graph DB itself (nodes).

    Use :meth:`create` to construct instances — it dispatches to the appropriate subclass based
    on *media_type*.

    Once created, instances cannot be modified (frozen). All fields are required
    and validated at construction time.
    """

    model_config = ConfigDict(frozen=True)

    file_name: str = Field(..., min_length=1, description="Name of the file")
    last_modified: datetime = Field(..., description="Last modification timestamp")
    media_type: MediaType | None = Field(
        ..., description="MIME type (e.g., 'image/jpeg'); None for an asset of unrecognized kind"
    )
    contents: bytes = Field(..., description="Binary file contents")
    original_file_name: str | None = Field(
        default=None,
        description="The filename the asset was originally uploaded under, when known.",
    )

    @classmethod
    def create(
        cls,
        file_name: str,
        last_modified: datetime,
        media_type: MediaType | None,
        contents: bytes,
        original_file_name: str | None = None,
    ) -> RoamAsset:
        """Construct a :class:`RoamAsset` or the appropriate subclass for *media_type*.

        For image media types, pixel dimensions are extracted from *contents* via
        ``imagesize`` and a :class:`RoamImageAsset` is returned.  For all other types —
        an unrecognized kind (``None``) included — a plain :class:`RoamAsset` is
        returned.

        Args:
            file_name: Name of the file.
            last_modified: Last modification timestamp.
            media_type: IANA media type of the asset, or ``None`` when unrecognized.
            contents: Binary file contents.
            original_file_name: The filename the asset was originally uploaded under,
                when known.

        Returns:
            A :class:`RoamImageAsset` when *media_type* is an image type; a
            :class:`RoamAsset` otherwise.
        """
        if media_type is not None and is_image_type(media_type):
            raw_size: Final[tuple[int, int]] = _imagesize_get(contents)
            image_size: Final[ImageSize] = ImageSize(
                width=raw_size[0] if raw_size[0] != -1 else None,
                height=raw_size[1] if raw_size[1] != -1 else None,
            )
            return RoamImageAsset(
                file_name=file_name,
                last_modified=last_modified,
                media_type=media_type,
                contents=contents,
                original_file_name=original_file_name,
                image_size=image_size,
            )
        return RoamAsset(
            file_name=file_name,
            last_modified=last_modified,
            media_type=media_type,
            contents=contents,
            original_file_name=original_file_name,
        )


class RoamImageAsset(RoamAsset):
    """Immutable representation of an image asset fetched from Firebase Storage through the Roam API.

    Extends :class:`RoamAsset` with pixel dimensions extracted from the image file contents.

    Attributes:
        image_size: Pixel dimensions of the image.
    """

    image_size: ImageSize = Field(..., description="Pixel dimensions of the image.")
