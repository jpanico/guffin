"""The storage holding a hosted asset's binary: its address, the storing service, and its encryption state.

Public symbols:

- :class:`StoreType` — ``StrEnum`` of the storage services an asset binary can be hosted in
  (``FIREBASE_STORAGE``).
- :class:`AssetStorage` — the storage of one hosted asset: where the binary lives
  (``location``), which service holds it (``store_type``), and whether the stored bytes
  are encrypted (``is_encrypted``).

A pure value model near the bottom of the ``model/`` conceptual stack: depends only on
third-party packages, so any ``model/`` module may depend on it.
"""

import enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class StoreType(enum.StrEnum):
    """The kind of storage service holding an asset binary.

    Attributes:
        FIREBASE_STORAGE: Firebase Storage (officially *Cloud Storage for Firebase*) —
            Firebase's BLOB file store, distinct from *Cloud Firestore*, Firebase's
            document database.
    """

    FIREBASE_STORAGE = "firebase-storage"


class AssetStorage(BaseModel):
    """The storage of one hosted asset.

    The three facts locating an asset's binary: the address it is retrievable from
    (``location``), the kind of service that address belongs to (``store_type``), and
    whether the bytes stored there are encrypted (``is_encrypted``) — an encrypted
    binary is unreadable as fetched, so the address alone does not yield usable content.

    Attributes:
        location: The URL the asset binary is retrievable from — the complete,
            self-sufficient address of the stored object.
        store_type: The :class:`StoreType` of the service holding the binary
            (serialized as ``store-type``).
        is_encrypted: Whether the stored bytes are encrypted at rest, so that fetching
            *location* yields ciphertext rather than the asset's usable content
            (serialized as ``is-encrypted``).
    """

    model_config = ConfigDict(frozen=True, validate_by_name=True)

    location: HttpUrl = Field(..., description="URL the asset binary is retrievable from.")
    store_type: StoreType = Field(
        ...,
        serialization_alias="store-type",
        description="The kind of storage service holding the binary (serialized as 'store-type').",
    )
    is_encrypted: bool = Field(
        ...,
        serialization_alias="is-encrypted",
        description="Whether the stored bytes are encrypted at rest (serialized as 'is-encrypted').",
    )
