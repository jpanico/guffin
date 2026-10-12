"""Unit tests for guffin.model.alternative."""

import pytest
from pydantic import ValidationError

from guffin.model.alternative import Alternative


class TestAlternative:
    """Tests for the Alternative value."""

    def test_construction(self) -> None:
        """An alternative is a uid and a text."""
        alternative = Alternative(uid="altuid001", text="another wording")
        assert alternative.uid == "altuid001"
        assert alternative.text == "another wording"

    def test_frozen(self) -> None:
        """An alternative is immutable."""
        alternative = Alternative(uid="altuid001", text="another wording")
        with pytest.raises(ValidationError):
            alternative.text = "changed"  # type: ignore[misc]

    def test_uid_must_be_well_formed(self) -> None:
        """The uid is a model Uid, so a malformed one is rejected."""
        with pytest.raises(ValidationError):
            Alternative(uid="not a uid!", text="x")

    def test_equality_is_by_value(self) -> None:
        """Two alternatives with the same uid and text are equal."""
        assert Alternative(uid="altuid001", text="x") == Alternative(uid="altuid001", text="x")
        assert Alternative(uid="altuid001", text="x") != Alternative(uid="altuid001", text="y")

    def test_round_trips_through_json(self) -> None:
        """An alternative serializes to and from its two-field JSON form."""
        alternative = Alternative(uid="altuid001", text="another wording")
        dumped = alternative.model_dump(mode="json")
        assert dumped == {"uid": "altuid001", "text": "another wording"}
        assert Alternative.model_validate(dumped) == alternative
