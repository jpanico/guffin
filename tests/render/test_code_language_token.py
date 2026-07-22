"""Tests for guffin.render.code_language_token."""

import pytest
from pydantic import ValidationError

from guffin.common.programming_language import CANONICAL_LANGUAGE_IDS
from guffin.common.programming_language_data import LANGUAGE_ID_BY_ALIAS
from guffin.render.code_language_token import _CODE_LANGUAGE_TOKEN_OVERRIDES, code_language_token


class TestCodeLanguageToken:
    """code_language_token respells a canonical language id as a whitespace-free highlighter token."""

    @pytest.mark.parametrize(
        ("language_id", "expected"),
        [
            ("common lisp", "lisp"),
            ("emacs lisp", "elisp"),
            ("visual basic .net", "vbnet"),
        ],
    )
    def test_overridden_id_resolves_to_its_highlighter_alias(self, language_id: str, expected: str) -> None:
        """An id with an explicit override resolves to its highlighter-recognized alias."""
        assert code_language_token(language_id) == expected

    def test_spaced_id_without_override_folds_whitespace_to_hyphens(self) -> None:
        """A space-bearing id with no override folds its whitespace runs to single hyphens."""
        assert code_language_token("standard ml") == "standard-ml"
        assert code_language_token("fortran free form") == "fortran-free-form"

    def test_whitespace_free_id_passes_through_verbatim(self) -> None:
        """An id containing no whitespace is returned unchanged."""
        assert code_language_token("python") == "python"
        assert code_language_token("c++") == "c++"

    def test_non_canonical_id_is_rejected(self) -> None:
        """A string that is not a canonical language id fails validation."""
        with pytest.raises(ValidationError):
            code_language_token("commonlisp")

    def test_every_canonical_id_yields_a_whitespace_free_token(self) -> None:
        """No token — hence no emitted fence info string or class — contains whitespace."""
        for language_id in CANONICAL_LANGUAGE_IDS:
            token = code_language_token(language_id)
            assert not any(char.isspace() for char in token), f"{language_id!r} -> {token!r}"


class TestCodeLanguageTokenOverrides:
    """The override table's coherence with the canonical vocabulary."""

    def test_every_override_key_is_a_canonical_id(self) -> None:
        """Each override respells an id that exists in the canonical vocabulary."""
        for key in _CODE_LANGUAGE_TOKEN_OVERRIDES:
            assert key in CANONICAL_LANGUAGE_IDS

    def test_every_override_value_is_an_alias_of_its_key(self) -> None:
        """Each override token is a Linguist alias resolving back to its key's language."""
        for key, token in _CODE_LANGUAGE_TOKEN_OVERRIDES.items():
            assert LANGUAGE_ID_BY_ALIAS.get(token) == key, f"{token!r} is not an alias of {key!r}"
