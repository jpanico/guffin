"""Tests for guffin.common.programming_language."""

import pytest
from pydantic import BaseModel, ValidationError

from guffin.common.programming_language import (
    CANONICAL_LANGUAGE_IDS,
    CodeLanguageId,
    canonical_language_id,
    verified_code_language_id,
)


class TestCanonicalLanguageId:
    """canonical_language_id() resolves names and aliases, case-insensitively."""

    def test_name_resolves_to_id(self) -> None:
        """A language name resolves to its lowercased-name id."""
        assert canonical_language_id("Fortran") == "fortran"

    def test_id_resolves_to_itself(self) -> None:
        """A canonical id resolves to itself."""
        assert canonical_language_id("python") == "python"

    def test_alias_resolves_to_id(self) -> None:
        """An alias resolves to the language's canonical id."""
        assert canonical_language_id("plain text") == "text"

    def test_case_insensitive(self) -> None:
        """Matching ignores case."""
        assert canonical_language_id("FORTRAN") == "fortran"

    def test_surrounding_whitespace_ignored(self) -> None:
        """Matching ignores surrounding whitespace."""
        assert canonical_language_id("  fortran ") == "fortran"

    def test_unknown_language_is_none(self) -> None:
        """A name outside the vocabulary resolves to None."""
        assert canonical_language_id("edsac") is None

    def test_symbolic_names_survive(self) -> None:
        """Names with symbols (C++, C#) are ids too."""
        assert canonical_language_id("C++") == "c++"
        assert canonical_language_id("c#") == "c#"


class TestVerifiedCodeLanguageId:
    """verified_code_language_id() accepts exactly the canonical ids."""

    def test_canonical_id_accepted(self) -> None:
        """A canonical id passes through unchanged."""
        assert verified_code_language_id("fortran") == "fortran"

    def test_alias_rejected(self) -> None:
        """An alias is not an id; the id form is exact."""
        with pytest.raises(ValueError):
            verified_code_language_id("plain text")

    def test_wrong_case_rejected(self) -> None:
        """A differently-cased name is not an id."""
        with pytest.raises(ValueError):
            verified_code_language_id("Fortran")

    def test_unknown_rejected(self) -> None:
        """A string outside the vocabulary is rejected."""
        with pytest.raises(ValueError):
            verified_code_language_id("edsac")


class TestCodeLanguageIdAnnotation:
    """The CodeLanguageId annotation enforces membership wherever it appears."""

    class _Holder(BaseModel):
        language: CodeLanguageId

    def test_valid_id_accepted(self) -> None:
        """A model field typed CodeLanguageId accepts a canonical id."""
        assert self._Holder(language="fortran").language == "fortran"

    def test_invalid_id_rejected(self) -> None:
        """A model field typed CodeLanguageId rejects a non-canonical string."""
        with pytest.raises(ValidationError):
            self._Holder(language="edsac")


class TestVocabularyContent:
    """Sanity checks on the generated vocabulary."""

    def test_vocabulary_is_large(self) -> None:
        """The Linguist registry carries hundreds of languages."""
        assert len(CANONICAL_LANGUAGE_IDS) > 500

    def test_practically_important_languages_present(self) -> None:
        """The languages that motivated the vocabulary are present."""
        for language_id in ("fortran", "python", "c++", "assembly", "text", "cobol", "ada"):
            assert language_id in CANONICAL_LANGUAGE_IDS
