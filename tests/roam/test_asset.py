"""Tests for guffin.roam.asset — RoamAsset and RoamImageAsset models."""

import base64
import logging
from datetime import datetime
from typing import Final

import pytest

from guffin.common.media_type import MediaType
from guffin.roam.asset import RoamAsset, RoamImageAsset

logger = logging.getLogger(__name__)

# Minimal valid images constructed from the PNG/JPEG format specs.
# Dimensions verified with imagesize at generation time.
_PNG_1x1: Final[bytes] = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgYGAAAAAEAAH2FzhVAAAAAElFTkSuQmCC"
)
_PNG_3x7: Final[bytes] = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAMAAAAHCAIAAABC22D+AAAADElEQVR4nGNgoAYAAABGAAEXyV8TAAAAAElFTkSuQmCC"
)
_JPEG_1x1: Final[bytes] = base64.b64decode("/9j/4AAQSkZJRgABAQAAAQABAAD/wAALCAABAAEBAREA/9k=")
_JPEG_5x9: Final[bytes] = base64.b64decode("/9j/4AAQSkZJRgABAQAAAQABAAD/wAALCAAJAAUBAREA/9k=")

_LAST_MODIFIED: Final[datetime] = datetime(2024, 6, 1, 12, 0, 0)


class TestRoamAssetCreate:
    """Tests for RoamAsset.create() factory classmethod."""

    @pytest.mark.parametrize(
        "media_type,contents,expected_w,expected_h",
        [
            (MediaType.JPEG, _JPEG_1x1, 1, 1),
            (MediaType.JPEG, _JPEG_5x9, 5, 9),
            (MediaType.PNG, _PNG_1x1, 1, 1),
            (MediaType.PNG, _PNG_3x7, 3, 7),
        ],
    )
    def test_image_type_returns_roam_image_asset_with_correct_dimensions(
        self,
        media_type: MediaType,
        contents: bytes,
        expected_w: int,
        expected_h: int,
    ) -> None:
        """Image media types produce a RoamImageAsset with dimensions extracted from contents."""
        result: Final[RoamAsset] = RoamAsset.create(
            file_name="image.jpg",
            last_modified=_LAST_MODIFIED,
            media_type=media_type,
            contents=contents,
        )
        assert isinstance(result, RoamImageAsset)
        assert result.image_size.width == expected_w
        assert result.image_size.height == expected_h

    @pytest.mark.parametrize("media_type", [MediaType.PDF, MediaType.MP4, MediaType.MOV])
    def test_non_image_type_returns_plain_roam_asset(self, media_type: MediaType) -> None:
        """Non-image media types produce a plain RoamAsset, never a RoamImageAsset."""
        result: Final[RoamAsset] = RoamAsset.create(
            file_name="doc.pdf",
            last_modified=_LAST_MODIFIED,
            media_type=media_type,
            contents=b"not an image",
        )
        assert type(result) is RoamAsset

    def test_unparseable_image_bytes_yield_none_dimensions(self, caplog: pytest.LogCaptureFixture) -> None:
        """An image media_type with unrecognizable bytes produces image_size(None, None) and logs an ERROR."""
        with caplog.at_level(logging.ERROR, logger="guffin.roam.asset"):
            result: Final[RoamAsset] = RoamAsset.create(
                file_name="bad.jpg",
                last_modified=_LAST_MODIFIED,
                media_type=MediaType.JPEG,
                contents=b"\x00\x00\x00",
            )
        assert isinstance(result, RoamImageAsset)
        assert result.image_size.width is None
        assert result.image_size.height is None
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_all_fields_propagated(self) -> None:
        """create() faithfully copies all base fields onto the returned instance."""
        contents: Final[bytes] = _PNG_1x1
        result: Final[RoamAsset] = RoamAsset.create(
            file_name="photo.png",
            last_modified=_LAST_MODIFIED,
            media_type=MediaType.PNG,
            contents=contents,
        )
        assert result.file_name == "photo.png"
        assert result.last_modified == _LAST_MODIFIED
        assert result.media_type == MediaType.PNG
        assert result.contents == contents
