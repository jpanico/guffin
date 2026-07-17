"""Tests for guffin.roam.code_language."""

from guffin.common.programming_language import CANONICAL_LANGUAGE_IDS
from guffin.roam.code_language import CodeLanguage, canonical_id_for


class TestCanonicalIdFor:
    """canonical_id_for() maps every Roam code-block language into the canonical vocabulary."""

    def test_mapping_is_total(self) -> None:
        """Every CodeLanguage member resolves to a canonical language id."""
        for member in CodeLanguage:
            assert canonical_id_for(member) in CANONICAL_LANGUAGE_IDS

    def test_same_spelling_passes_through(self) -> None:
        """A member whose value is already a vocabulary name resolves to itself."""
        assert canonical_id_for(CodeLanguage.PYTHON) == "python"

    def test_alias_spelling_resolves(self) -> None:
        """A member whose value is a vocabulary alias resolves to the canonical id."""
        assert canonical_id_for(CodeLanguage.PLAIN_TEXT) == "text"
        assert canonical_id_for(CodeLanguage.LATEX) == "tex"

    def test_divergent_spellings_bridged(self) -> None:
        """The members with no vocabulary name/alias carry explicit overrides."""
        assert canonical_id_for(CodeLanguage.COMMON_LISP) == "common lisp"
        assert canonical_id_for(CodeLanguage.JSON_LD) == "jsonld"
        assert canonical_id_for(CodeLanguage.JSX) == "javascript"
        assert canonical_id_for(CodeLanguage.VB) == "visual basic .net"
