"""Tests for the roam_asset_fetch module."""

import base64
import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import HttpUrl, ValidationError

from guffin.roam.asset import RoamAsset
from guffin.roam.asset_fetch import FetchRoamAsset, fetch_and_cache_asset
from guffin.roam.local_api import ApiEndpoint, ApiEndpointURL
from guffin.common.media_type import MediaType

from conftest import FIXTURES_IMAGES_DIR

logger = logging.getLogger(__name__)


class TestRoamAsset:
    """Tests for the RoamAsset Pydantic model (defined in guffin.roam.asset)."""

    def test_valid_initialization(self) -> None:
        """Test creating RoamAsset with valid parameters."""
        test_datetime: datetime = datetime(2024, 1, 15, 10, 30, 0)
        test_contents: bytes = b"test file content"

        roam_asset: RoamAsset = RoamAsset(
            file_name="test.jpeg",
            last_modified=test_datetime,
            media_type=MediaType.JPEG,
            contents=test_contents,
        )

        assert roam_asset.file_name == "test.jpeg"
        assert roam_asset.last_modified == test_datetime
        assert roam_asset.media_type == "image/jpeg"
        assert roam_asset.contents == test_contents

    def test_empty_filename_raises_validation_error(self) -> None:
        """Test that empty file_name raises a validation error."""
        with pytest.raises(Exception):  # Pydantic raises ValidationError
            RoamAsset(
                file_name="",  # Empty string
                last_modified=datetime.now(),
                media_type=MediaType.JPEG,
                contents=b"data",
            )

    def test_invalid_media_type_raises_validation_error(self) -> None:
        """Test that invalid media_type format raises a validation error."""
        with pytest.raises(Exception):  # Pydantic raises ValidationError
            RoamAsset(
                file_name="test.txt",
                last_modified=datetime.now(),
                media_type="invalid",  # type: ignore[arg-type]  # deliberately invalid
                contents=b"data",
            )

    def test_valid_media_types(self) -> None:
        """Test that all MediaType enum members are accepted."""
        for media_type in MediaType:
            roam_asset: RoamAsset = RoamAsset(
                file_name="test.file",
                last_modified=datetime.now(),
                media_type=media_type,
                contents=b"data",
            )
            assert roam_asset.media_type == media_type

    def test_unknown_media_type_raises_validation_error(self) -> None:
        """Test that a MIME type not in the MediaType enum raises a validation error."""
        with pytest.raises(Exception):
            RoamAsset(
                file_name="test.txt",
                last_modified=datetime.now(),
                media_type="text/plain",  # type: ignore[arg-type]  # deliberately not in MediaType enum
                contents=b"data",
            )

    def test_missing_required_fields_raises_validation_error(self) -> None:
        """Test that missing required fields raise validation errors."""
        # Missing file_name
        with pytest.raises(Exception):
            RoamAsset(last_modified=datetime.now(), media_type=MediaType.JPEG, contents=b"data")  # type: ignore[call-arg]

        # Missing last_modified
        with pytest.raises(Exception):
            RoamAsset(file_name="test.jpeg", media_type=MediaType.JPEG, contents=b"data")  # type: ignore[call-arg]

        # Missing media_type
        with pytest.raises(Exception):
            RoamAsset(file_name="test.jpeg", last_modified=datetime.now(), contents=b"data")  # type: ignore[call-arg]

        # Missing contents
        with pytest.raises(Exception):
            RoamAsset(file_name="test.jpeg", last_modified=datetime.now(), media_type=MediaType.JPEG)  # type: ignore[call-arg]

    def test_bytes_contents_validation(self) -> None:
        """Test that contents must be bytes."""
        roam_asset: RoamAsset = RoamAsset(
            file_name="test.png", last_modified=datetime.now(), media_type=MediaType.PNG, contents=b"binary data"
        )
        assert isinstance(roam_asset.contents, bytes)

    def test_different_file_types(self) -> None:
        """Test RoamAsset with different image MIME types."""
        test_cases: list[tuple[str, MediaType, bytes]] = [
            ("image.jpeg", MediaType.JPEG, b"\xff\xd8\xff\xe0"),  # JPEG magic bytes
            ("photo.png", MediaType.PNG, b"\x89PNG"),  # PNG signature
            ("animation.gif", MediaType.GIF, b"GIF89a"),  # GIF header
            ("icon.bmp", MediaType.BMP, b"BM"),  # BMP magic bytes
        ]

        for file_name, media_type, contents in test_cases:
            roam_asset: RoamAsset = RoamAsset(
                file_name=file_name, last_modified=datetime.now(), media_type=media_type, contents=contents
            )
            assert roam_asset.file_name == file_name
            assert roam_asset.media_type == media_type
            assert roam_asset.contents == contents

    def test_datetime_coercion_from_string(self) -> None:
        """Test that last_modified coerces string to datetime."""
        # ISO 8601 format string
        roam_asset: RoamAsset = RoamAsset(
            file_name="test.jpeg",
            last_modified="2024-01-15T10:30:00",  # type: ignore[arg-type]
            media_type=MediaType.JPEG,
            contents=b"data",
        )
        assert isinstance(roam_asset.last_modified, datetime)
        assert roam_asset.last_modified.year == 2024
        assert roam_asset.last_modified.month == 1
        assert roam_asset.last_modified.day == 15
        assert roam_asset.last_modified.hour == 10
        assert roam_asset.last_modified.minute == 30

    def test_immutability(self) -> None:
        """Test that RoamAsset is immutable."""
        roam_asset: RoamAsset = RoamAsset(
            file_name="test.jpeg", last_modified=datetime.now(), media_type=MediaType.JPEG, contents=b"data"
        )
        with pytest.raises(Exception):  # Pydantic raises ValidationError for frozen models
            roam_asset.file_name = "changed.txt"  # type: ignore[misc]


class TestFetchRoamAssetResponsePayloadResult:
    """Tests for FetchRoamAsset.Response.Payload.Result — the model that parses raw ``file.get`` result dicts."""

    def test_null_raises_validation_error(self) -> None:
        """Test that None raises ValidationError."""
        with pytest.raises(ValidationError):
            FetchRoamAsset.Response.Payload.Result.model_validate(None)

    def test_valid_result_parses_correctly(self) -> None:
        """Test that a valid result dict parses into a Result with decoded contents."""
        file_content: bytes = b"test file content"
        encoded_content: str = base64.b64encode(file_content).decode("utf-8")
        raw: dict[str, str] = {"base64": encoded_content, "filename": "test_file.jpeg", "mimetype": "image/jpeg"}

        parsed: FetchRoamAsset.Response.Payload.Result = FetchRoamAsset.Response.Payload.Result.model_validate(raw)

        assert parsed.file_name == "test_file.jpeg"
        assert parsed.content == file_content
        assert parsed.media_type == "image/jpeg"

    def test_base64_decoding(self) -> None:
        """Test that the ``base64`` field is decoded to bytes by Base64Bytes."""
        test_content: bytes = b"Hello, Roam Research!"
        encoded: str = base64.b64encode(test_content).decode("utf-8")
        raw: dict[str, str] = {"base64": encoded, "filename": "test.jpeg", "mimetype": "image/jpeg"}

        parsed: FetchRoamAsset.Response.Payload.Result = FetchRoamAsset.Response.Payload.Result.model_validate(raw)

        assert parsed.content == test_content
        assert parsed.file_name == "test.jpeg"
        assert parsed.media_type == "image/jpeg"

    def test_different_file_types(self) -> None:
        """Test parsing result dicts with different file types."""
        test_cases: list[tuple[str, bytes, str]] = [
            ("image.jpeg", b"\xff\xd8\xff\xe0", "image/jpeg"),  # JPEG magic bytes
            ("animation.gif", b"GIF89a", "image/gif"),  # GIF header
            ("photo.png", b"\x89PNG", "image/png"),  # PNG signature
        ]

        for filename, content, media_type in test_cases:
            encoded: str = base64.b64encode(content).decode("utf-8")
            raw: dict[str, str] = {"base64": encoded, "filename": filename, "mimetype": media_type}

            parsed: FetchRoamAsset.Response.Payload.Result = FetchRoamAsset.Response.Payload.Result.model_validate(raw)

            assert parsed.file_name == filename
            assert parsed.content == content
            assert parsed.media_type == media_type

    def test_missing_base64_key_raises_error(self) -> None:
        """Test that a missing ``base64`` key raises ValidationError."""
        with pytest.raises(ValidationError):
            FetchRoamAsset.Response.Payload.Result.model_validate({"filename": "test.jpeg", "mimetype": "image/jpeg"})

    def test_missing_filename_key_raises_error(self) -> None:
        """Test that a missing ``filename`` key raises ValidationError."""
        encoded: str = base64.b64encode(b"data").decode("utf-8")
        with pytest.raises(ValidationError):
            FetchRoamAsset.Response.Payload.Result.model_validate({"base64": encoded, "mimetype": "text/plain"})


class TestFetchRoamAssetRequestPayload:
    """Tests for FetchRoamAsset.Request.Payload."""

    def test_with_url_is_json_serializable(self) -> None:
        """Test that a payload built with with_url round-trips through JSON correctly."""
        url: HttpUrl = HttpUrl("https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/file.jpeg")
        payload: FetchRoamAsset.Request.Payload = FetchRoamAsset.Request.Payload.with_url(url)

        json_str: str = payload.model_dump_json()
        parsed: dict[str, object] = json.loads(json_str)

        assert parsed["action"] == "file.get"
        assert isinstance(parsed["args"], list)
        args: list[object] = parsed["args"]  # type: ignore[assignment]
        assert len(args) == 1
        arg = args[0]
        assert isinstance(arg, dict)
        assert "url" in arg
        assert arg["format"] == "base64"


class TestFetchRoamAssetFetch:
    """Tests for the FetchRoamAsset.fetch static method."""

    def test_null_api_endpoint_raises_validation_error(self) -> None:
        """Test that None api_endpoint raises ValidationError."""
        with pytest.raises(ValidationError):
            FetchRoamAsset.fetch(api_endpoint=None, firebase_url="https://example.com/file.jpeg")  # type: ignore[arg-type]

    def test_null_firebase_url_raises_validation_error(self) -> None:
        """Test that None firebase_url raises ValidationError."""
        endpoint: ApiEndpoint = ApiEndpoint(
            url=ApiEndpointURL(local_api_port=3333, graph_name="test-graph"),
            bearer_token="test-token",
        )
        with pytest.raises(ValidationError):
            FetchRoamAsset.fetch(api_endpoint=endpoint, firebase_url=None)  # type: ignore[arg-type]

    @pytest.mark.live
    @pytest.mark.skipif(not os.getenv("GUFFIN_LIVE_TESTS"), reason="requires Roam Desktop app running locally")
    def test_live(self, live_api_endpoint: ApiEndpoint) -> None:
        """Fetch a Cloud Firestore asset and verify the returned RoamAsset is well-formed."""
        url: HttpUrl = HttpUrl(
            "https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2F-9owRBegJ8.jpeg.enc?alt=media&token=9b673aae-8089-4a91-84df-9dac152a7f94"
        )
        roam_asset: RoamAsset = FetchRoamAsset.fetch(api_endpoint=live_api_endpoint, firebase_url=url)
        logger.debug(f"roam_asset: {roam_asset}")

        # Read the expected JPEG file
        with open(FIXTURES_IMAGES_DIR / "flower.jpeg", "rb") as f:
            expected_contents: bytes = f.read()

        # Assert the fetched file matches the expected file
        assert roam_asset.file_name == "flower.jpeg"
        assert roam_asset.contents == expected_contents
        assert roam_asset.media_type == "image/jpeg"
        assert isinstance(roam_asset.last_modified, datetime)


class TestFetchAndCacheAsset:
    """Tests for fetch_and_cache_asset()."""

    def test_cache_hit_with_jpeg_extension_variant(self, tmp_path: Path) -> None:
        """Cache files with .jpeg extension are served correctly.

        Regression test: an older version of the code wrote cache files with the
        platform-dependent extension returned by mimetypes.guess_extension (e.g.
        '.jpeg' on macOS). fetch_and_cache_asset must handle these via
        MediaType.from_file_name, which resolves extension variants through
        mimetypes.guess_type, rather than MediaType.from_extension, which only
        knows the canonical '.jpg'.
        """
        firebase_url: HttpUrl = HttpUrl("https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/photo.jpeg")
        cache_key: str = hashlib.sha256(str(firebase_url).encode()).hexdigest()
        cached_file: Path = tmp_path / f"{cache_key}.jpeg"
        cached_file.write_bytes(b"\xff\xd8\xff\xe0")

        endpoint: ApiEndpoint = ApiEndpoint(
            url=ApiEndpointURL(local_api_port=3333, graph_name="test-graph"),
            bearer_token="test-token",
        )

        asset: RoamAsset = fetch_and_cache_asset(firebase_url, endpoint, cache_dir=tmp_path)

        assert asset.media_type == MediaType.JPEG
        assert asset.contents == b"\xff\xd8\xff\xe0"
        assert asset.file_name == cached_file.name
