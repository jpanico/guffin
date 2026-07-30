"""Unit tests for guffin.server.console_export."""

from guffin.server.console_export import (
    CONSOLE_MEDIA_TYPE,
    ConsoleFormat,
    console_environment,
    exported_console,
)


class TestConsoleMediaType:
    """Tests for the representation→media-type mapping."""

    def test_total_over_the_format_enum(self) -> None:
        """Every representation has a media type."""
        assert set(CONSOLE_MEDIA_TYPE) == set(ConsoleFormat)


class TestConsoleEnvironment:
    """Tests for console_environment."""

    def test_plain_text_disables_color_and_pins_width(self) -> None:
        """A plain text capture runs colorless at the requested width."""
        environment = console_environment(ConsoleFormat.TEXT, 97, ansi=False)
        assert environment["COLUMNS"] == "97"
        assert environment["NO_COLOR"] == "1"
        assert environment["FORCE_COLOR"] is None

    def test_ansi_text_forces_color(self) -> None:
        """A text capture keeping ANSI escapes runs colored."""
        environment = console_environment(ConsoleFormat.TEXT, 120, ansi=True)
        assert environment["FORCE_COLOR"] == "1"
        assert environment["NO_COLOR"] is None

    def test_rich_representations_always_capture_colored(self) -> None:
        """HTML and SVG captures run colored regardless of the ansi field."""
        for console_format in (ConsoleFormat.HTML, ConsoleFormat.SVG):
            environment = console_environment(console_format, 120, ansi=False)
            assert environment["FORCE_COLOR"] == "1"
            assert environment["NO_COLOR"] is None


class TestExportedConsole:
    """Tests for exported_console."""

    def test_text_passes_the_capture_through(self) -> None:
        """The text representation is the capture itself, verbatim."""
        captured = "plain rendering\nsecond line\n"
        assert exported_console(captured, ConsoleFormat.TEXT, 80) == captured

    def test_html_re_renders_into_a_standalone_document(self) -> None:
        """The HTML representation is a full document carrying the capture's text."""
        captured = "\x1b[1mBold Words\x1b[0m and plain\n"
        html = exported_console(captured, ConsoleFormat.HTML, 80)
        assert "<html" in html
        assert "Bold Words" in html

    def test_svg_re_renders_into_an_svg_document(self) -> None:
        """The SVG representation is an SVG image carrying the capture's text."""
        captured = "\x1b[1mBold Words\x1b[0m and plain\n"
        svg = exported_console(captured, ConsoleFormat.SVG, 80)
        assert "<svg" in svg
        assert "Bold" in svg
