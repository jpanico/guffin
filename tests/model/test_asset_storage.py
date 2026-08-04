"""Tests for the guffin.model.asset_storage module."""

import pytest
from pydantic import HttpUrl, ValidationError

from guffin.model.asset_storage import AssetStorage, StoreType

_LOCATION: str = (
    "https://firebasestorage.googleapis.com/v0/b/test.appspot.com" "/o/imgs%2Fphoto.jpeg?alt=media&token=abc123"
)


class TestStoreType:
    """StoreType enumerates the storage services an asset binary can be hosted in."""

    def test_exactly_one_member(self) -> None:
        """StoreType has exactly one member."""
        assert set(StoreType) == {StoreType.FIREBASE_STORAGE}

    def test_is_str_enum(self) -> None:
        """Members are string-valued for clean serialization."""
        assert isinstance(StoreType.FIREBASE_STORAGE, str)
        assert StoreType.FIREBASE_STORAGE.value == "firebase-storage"

    def test_resolves_by_value(self) -> None:
        """A stored identifier resolves by plain value lookup."""
        assert StoreType("firebase-storage") is StoreType.FIREBASE_STORAGE


class TestAssetStorage:
    """AssetStorage holds a validated (location, store type, encryption state) triple."""

    def test_constructs_from_legal_fields(self) -> None:
        """A URL string, a StoreType, and a bool construct a frozen value."""
        storage = AssetStorage(location=_LOCATION, store_type=StoreType.FIREBASE_STORAGE, is_encrypted=True)
        assert storage.location == HttpUrl(_LOCATION)
        assert storage.store_type is StoreType.FIREBASE_STORAGE
        assert storage.is_encrypted is True

    def test_is_frozen(self) -> None:
        """A constructed value cannot be mutated."""
        storage = AssetStorage(location=_LOCATION, store_type=StoreType.FIREBASE_STORAGE, is_encrypted=False)
        with pytest.raises(ValidationError):
            storage.is_encrypted = True  # type: ignore[misc]

    def test_rejects_non_url_location(self) -> None:
        """A location that is not a URL is rejected at construction."""
        with pytest.raises(ValidationError, match="URL"):
            AssetStorage(location="not a url", store_type=StoreType.FIREBASE_STORAGE, is_encrypted=False)

    def test_rejects_unrecognized_store_type(self) -> None:
        """A store type outside the StoreType vocabulary is rejected at construction."""
        with pytest.raises(ValidationError, match="store_type"):
            AssetStorage(location=_LOCATION, store_type="s3", is_encrypted=False)  # type: ignore[arg-type]

    def test_serializes_with_kebab_case_aliases(self) -> None:
        """The store type and encryption fields serialize under their kebab-case aliases."""
        storage = AssetStorage(location=_LOCATION, store_type=StoreType.FIREBASE_STORAGE, is_encrypted=True)
        dumped = storage.model_dump(by_alias=True)
        assert dumped["store-type"] == StoreType.FIREBASE_STORAGE
        assert dumped["is-encrypted"] is True

    def test_validates_from_raw_dict(self) -> None:
        """A raw dict with field names and string values validates to the typed model."""
        storage = AssetStorage.model_validate(
            {"location": _LOCATION, "store_type": "firebase-storage", "is_encrypted": True}
        )
        assert storage.store_type is StoreType.FIREBASE_STORAGE
        assert storage.is_encrypted is True
