"""Tests for the media_type module."""

from guffin.common.media_type import MediaType, is_image_type


class TestMediaTypeFromFileName:
    """Tests for MediaType.from_file_name classmethod."""

    def test_jpeg_extension_variant(self) -> None:
        """.jpeg resolves to JPEG even though the canonical extension is .jpg."""
        assert MediaType.from_file_name("photo.jpeg") == MediaType.JPEG

    def test_jpg_extension(self) -> None:
        """.jpg resolves to JPEG."""
        assert MediaType.from_file_name("photo.jpg") == MediaType.JPEG

    def test_png(self) -> None:
        """.png resolves to PNG."""
        assert MediaType.from_file_name("image.png") == MediaType.PNG

    def test_unknown_extension_returns_none(self) -> None:
        """An unrecognized extension returns None."""
        assert MediaType.from_file_name("file.xyz") is None


class TestMediaTypeExtension:
    """Tests for MediaType.extension property and MediaType.from_extension classmethod."""

    def test_jpeg(self) -> None:
        """MediaType.JPEG.extension returns .jpg."""
        assert MediaType.JPEG.extension == ".jpg"

    def test_png(self) -> None:
        """MediaType.PNG.extension returns .png."""
        assert MediaType.PNG.extension == ".png"

    def test_gif(self) -> None:
        """MediaType.GIF.extension returns .gif."""
        assert MediaType.GIF.extension == ".gif"

    def test_webp(self) -> None:
        """MediaType.WEBP.extension returns .webp."""
        assert MediaType.WEBP.extension == ".webp"

    def test_svg(self) -> None:
        """MediaType.SVG.extension returns .svg."""
        assert MediaType.SVG.extension == ".svg"

    def test_from_extension_unknown_returns_none(self) -> None:
        """An unrecognized file extension returns None from from_extension."""
        assert MediaType.from_extension(".xyz") is None


class TestIsImageType:
    """Tests for is_image_type."""

    def test_jpeg_is_image(self) -> None:
        """JPEG is an image type."""
        assert is_image_type(MediaType.JPEG) is True

    def test_png_is_image(self) -> None:
        """PNG is an image type."""
        assert is_image_type(MediaType.PNG) is True

    def test_svg_is_image(self) -> None:
        """SVG is an image type."""
        assert is_image_type(MediaType.SVG) is True

    def test_pdf_is_not_image(self) -> None:
        """PDF is not an image type."""
        assert is_image_type(MediaType.PDF) is False

    def test_mp4_is_not_image(self) -> None:
        """MP4 is not an image type."""
        assert is_image_type(MediaType.MP4) is False

    def test_mov_is_not_image(self) -> None:
        """MOV is not an image type."""
        assert is_image_type(MediaType.MOV) is False
