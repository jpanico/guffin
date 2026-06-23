"""Tests for guffin.common.filenames."""

from guffin.common.filenames import shell_safe_filename


class TestShellSafeFilename:
    """Tests for shell_safe_filename()."""

    def test_replaces_spaces_with_underscores(self) -> None:
        """Test that spaces are replaced with underscores."""
        assert shell_safe_filename("hello world test") == "hello_world_test"

    def test_removes_special_characters(self) -> None:
        """Test that special characters are removed."""
        assert shell_safe_filename("hello@world!test#file.txt") == "helloworldtestfile.txt"

    def test_preserves_safe_characters(self) -> None:
        """Test that safe characters (alphanumeric, underscore, hyphen, period) are preserved."""
        assert shell_safe_filename("file_name-123.txt") == "file_name-123.txt"

    def test_handles_unicode_characters(self) -> None:
        """Test that Unicode characters are converted to ASCII equivalents."""
        assert shell_safe_filename("café résumé naïve") == "cafe_resume_naive"

    def test_handles_empty_string(self) -> None:
        """Test handling of empty string."""
        assert shell_safe_filename("") == ""

    def test_handles_only_special_characters(self) -> None:
        """Test handling of string with only special characters."""
        assert shell_safe_filename("@#$%^&*()") == ""

    def test_handles_parentheses_and_brackets(self) -> None:
        """Test that parentheses and brackets are removed."""
        assert shell_safe_filename("My Document (2024) [Draft].txt") == "My_Document_2024_Draft.txt"

    def test_handles_mixed_case(self) -> None:
        """Test that mixed case is preserved."""
        assert shell_safe_filename("MyDocumentFile.TXT") == "MyDocumentFile.TXT"

    def test_handles_multiple_spaces(self) -> None:
        """Test that multiple consecutive spaces become a single underscore."""
        assert shell_safe_filename("hello    world") == "hello_world"

    def test_handles_email_addresses(self) -> None:
        """Test normalization of email-like strings."""
        assert shell_safe_filename("user@example.com") == "userexample.com"

    def test_handles_urls(self) -> None:
        """Test normalization of URL-like strings."""
        assert shell_safe_filename("https://example.com/path") == "httpsexample.compath"

    def test_preserves_file_extensions(self) -> None:
        """Test that file extensions with periods are preserved."""
        assert shell_safe_filename("document.backup.tar.gz") == "document.backup.tar.gz"

    def test_handles_accented_characters(self) -> None:
        """Test that accented characters are transliterated; non-Latin scripts are dropped."""
        assert shell_safe_filename("Zürich Москва 北京") == "Zurich"

    def test_handles_leading_trailing_special_chars(self) -> None:
        """Test that leading and trailing special characters are stripped."""
        assert shell_safe_filename("!!!filename###.txt") == "filename.txt"
