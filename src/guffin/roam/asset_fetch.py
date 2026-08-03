"""Roam Research asset fetching via the Local API.

Public symbols:

- :class:`FetchRoamAsset` — stateless utility class that fetches a Roam asset
  (image or file) by its Firebase Storage URL via the Local API's ``file.get``
  action.
- :func:`fetch_and_cache_asset` — fetch a Firebase Storage asset, using a local
  cache directory to avoid re-downloading unchanged assets.
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Final, Literal, Self, final

from pydantic import Base64Bytes, BaseModel, ConfigDict, Field, HttpUrl, validate_call

from guffin.common.media_type import MediaType
from guffin.roam.asset import RoamAsset
from guffin.roam.local_api import (
    ApiEndpoint,
    invoke_action,
)
from guffin.roam.local_api import (
    Request as LocalApiRequest,
)
from guffin.roam.local_api import (
    Response as LocalApiResponse,
)

logger = logging.getLogger(__name__)


@final
class FetchRoamAsset:
    """Stateless utility class for fetching Roam assets through the Roam Research Local API.

    Executes a ``file.get`` action via the Local API, which proxies
    ``roamAlphaAPI.file.get`` through the Roam Desktop app's local HTTP server.
    The decoded asset is returned as a :class:`~guffin.roam.asset.RoamAsset`.

    Delegates HTTP transport to :func:`~guffin.roam.local_api.invoke_action`,
    which handles header construction and error raising.
    """

    def __init__(self) -> None:
        """Prevent instantiation of this stateless utility class."""
        raise TypeError("FetchRoamAsset is a stateless utility class and cannot be instantiated")

    class Request:
        """Namespace for ``file.get`` request types."""

        class Payload(LocalApiRequest.Payload):
            """``file.get`` specialisation of :class:`roam_local_api.Request.Payload`.

            Inherits ``action: str`` and ``args: list[object]`` from the parent.
            Instances must be constructed via :meth:`with_url`, which sets
            ``action`` to ``"file.get"`` and wraps the Firebase Storage URL in a
            single :class:`Arg`.

            Once created, instances cannot be modified (frozen).
            """

            model_config = ConfigDict(frozen=True)

            class Arg(BaseModel):
                """A single positional argument in a ``file.get`` request.

                Attributes:
                    url: Firebase Storage URL of the asset to fetch.
                    format: Encoding format for the response; always ``'base64'``.
                """

                model_config = ConfigDict(frozen=True)

                url: HttpUrl
                format: Literal["base64"] = Field(default="base64")

            @classmethod
            def with_url(cls, url: HttpUrl) -> Self:
                """Construct a ``file.get`` payload for the given Firebase Storage URL.

                Args:
                    url: Firebase Storage URL of the asset to fetch.

                Returns:
                    A frozen :class:`Payload` with ``action`` set to ``"file.get"``
                    and ``args`` containing a single :class:`Arg` for ``url``.
                """
                return cls(action="file.get", args=[cls.Arg(url=url)])

    class Response:
        """Namespace for ``file.get`` response types."""

        class Payload(BaseModel):
            """Parsed ``file.get`` response payload."""

            model_config = ConfigDict(frozen=True)

            success: bool
            result: Result

            class Result(BaseModel):
                """Decoded asset data returned by the ``file.get`` action."""

                model_config = ConfigDict(frozen=True)

                file_name: str = Field(alias="filename")
                media_type: MediaType = Field(alias="mimetype")
                content: Base64Bytes = Field(alias="base64")

    @staticmethod
    @validate_call
    def fetch(firebase_url: HttpUrl, api_endpoint: ApiEndpoint) -> RoamAsset:
        """Fetch an asset from Firebase Storage via the Roam Research Local API.

        Builds a ``file.get`` request payload and delegates the HTTP call to
        :func:`~guffin.roam.local_api.invoke_action`. The Roam Desktop app must be
        running and the user must be logged into the graph at the time this method is
        called.

        Args:
            firebase_url: The Firebase Storage URL of the asset, as it appears in the
                Roam graph's Markdown.
            api_endpoint: The API endpoint (URL + bearer token) for the target Roam graph.

        Returns:
            An immutable :class:`~guffin.roam.asset.RoamAsset` with the decoded
            binary contents, file name, media type, and a ``last_modified``
            timestamp of now.

        Raises:
            ValidationError: If ``firebase_url`` or ``api_endpoint`` is ``None`` or invalid.
            requests.exceptions.ConnectionError: If the Local API is unreachable.
            requests.exceptions.HTTPError: If the Local API returns a non-200 status.
        """
        logger.debug("api_endpoint: %s, firebase_url: %s", api_endpoint, firebase_url)

        request_payload: FetchRoamAsset.Request.Payload = FetchRoamAsset.Request.Payload.with_url(firebase_url)
        local_api_response_payload: LocalApiResponse.Payload = invoke_action(request_payload, api_endpoint)
        logger.debug("local_api_response_payload: %s", local_api_response_payload)
        fetch_asset_response_payload: FetchRoamAsset.Response.Payload = FetchRoamAsset.Response.Payload.model_validate(
            local_api_response_payload.model_dump(mode="json")
        )
        logger.debug("fetch_asset_response_payload: %s", fetch_asset_response_payload)

        result: FetchRoamAsset.Response.Payload.Result = fetch_asset_response_payload.result
        return RoamAsset(
            file_name=result.file_name,
            last_modified=datetime.now(),
            media_type=result.media_type,
            contents=result.content,
            original_file_name=result.file_name,
        )


_SIDECAR_SUFFIX: Final[str] = ".meta.json"
"""Filename suffix of the per-asset cache sidecar carrying metadata the cached bytes cannot."""


def _read_sidecar_original_file_name(sidecar_path: Path) -> str | None:
    """Return the original filename recorded in the sidecar at *sidecar_path*, or ``None``.

    ``None`` when the sidecar does not record an original filename.
    """
    raw: Final[dict[str, str | None]] = json.loads(sidecar_path.read_text(encoding="utf-8"))
    return raw.get("original_file_name")


def _cached_asset(cache_dir: Path | None, cache_key: str, firebase_url: HttpUrl) -> RoamAsset | None:
    """Return the cached asset for *cache_key*, or ``None`` when the cache cannot serve it.

    ``None`` when *cache_dir* is ``None`` (no cache configured) or holds no
    file for *cache_key*.  A cache entry is a ``<cache_key>.<ext>`` file
    paired with its metadata sidecar; entries are assumed coherent, so a
    present cached file is always served together with the original filename
    its sidecar records.

    Args:
        cache_dir: Directory holding cached asset files and their sidecars,
            or ``None`` when caching is disabled.
        cache_key: The SHA-256 hex digest keying the asset's cache entry.
        firebase_url: The asset's Firebase Storage URL, for logging only.

    Returns:
        The cached :class:`~guffin.roam.asset.RoamAsset`, or ``None`` when
        the cache cannot serve the asset.

    Raises:
        ValueError: If multiple cache files exist for *cache_key*, or the
            cached file has an unrecognized extension.
    """
    if cache_dir is None:
        return None
    cached_files: Final[list[Path]] = [
        path for path in cache_dir.glob(f"{cache_key}.*") if not path.name.endswith(_SIDECAR_SUFFIX)
    ]
    if len(cached_files) > 1:
        raise ValueError(f"Multiple cache files found for key {cache_key!r}: {cached_files}")
    if not cached_files:
        return None
    cached_path: Final[Path] = cached_files[0]
    cached_media_type: Final[MediaType | None] = MediaType.from_file_name(cached_path.name)
    if cached_media_type is None:
        raise ValueError(f"Cached file has unrecognized extension: {cached_path.name!r}")
    logger.info("Cache hit: %s -> %s", firebase_url, cached_path.name)
    return RoamAsset.create(
        file_name=cached_path.name,
        last_modified=datetime.now(),
        media_type=cached_media_type,
        contents=cached_path.read_bytes(),
        original_file_name=_read_sidecar_original_file_name(cache_dir / f"{cache_key}{_SIDECAR_SUFFIX}"),
    )


def _encache_asset(cache_dir: Path | None, cache_key: str, asset: RoamAsset, firebase_url: HttpUrl) -> None:
    """Write *asset* into the cache as the entry for *cache_key*.

    A no-op when *cache_dir* is ``None`` (no cache configured).  A cache
    entry is a ``<cache_key>.<ext>`` file paired with its metadata sidecar;
    both are written together, keeping the entry coherent.  *cache_dir* is
    created if absent.

    Args:
        cache_dir: Directory holding cached asset files and their sidecars,
            or ``None`` when caching is disabled.
        cache_key: The SHA-256 hex digest keying the asset's cache entry.
        asset: The fetched asset to cache.
        firebase_url: The asset's Firebase Storage URL, for logging only.
    """
    if cache_dir is None:
        return
    file_name: Final[str] = f"{cache_key}{asset.media_type.extension}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / file_name).write_bytes(asset.contents)
    (cache_dir / f"{cache_key}{_SIDECAR_SUFFIX}").write_text(
        json.dumps({"original_file_name": asset.original_file_name}), encoding="utf-8"
    )
    logger.info("Cached asset: %s -> %s", firebase_url, file_name)


@validate_call
def fetch_and_cache_asset(
    firebase_url: HttpUrl,
    api_endpoint: ApiEndpoint,
    cache_dir: Path | None = None,
) -> RoamAsset:
    """Fetch a Firebase Storage asset, using *cache_dir* as a read/write cache.

    The cache key is the SHA-256 hex digest of the URL string.  Cached files
    are stored as ``<sha256>.<ext>`` where the extension is derived from the
    MIME type (e.g. ``.jpg`` for ``image/jpeg``).  The same naming convention
    is applied to the :attr:`~guffin.roam.asset.RoamAsset.file_name` of the
    returned asset, ensuring a consistent, deterministic filename regardless
    of whether the result came from cache or a fresh API call.  The asset's
    original upload filename is preserved in a ``<sha256>.meta.json`` sidecar
    next to the cached file, so
    :attr:`~guffin.roam.asset.RoamAsset.original_file_name` is populated on
    cache hits too.

    Args:
        firebase_url: The Firebase Storage URL of the asset to fetch.
        api_endpoint: The Roam Local API endpoint (URL + bearer token).
        cache_dir: Optional directory for caching fetched assets across runs.
            On a cache hit the asset is read from disk; on a cache miss the
            fetched asset is written to *cache_dir* for future runs.

    Returns:
        A :class:`~guffin.roam.asset.RoamAsset` with decoded binary contents,
        a MIME-type-derived ``file_name``, the asset's ``media_type``, its
        ``original_file_name`` when known, and a ``last_modified`` timestamp
        of now.

    Raises:
        ValidationError: If ``firebase_url`` or ``api_endpoint`` is ``None`` or invalid.
        requests.exceptions.ConnectionError: If the Local API is unreachable.
        requests.exceptions.HTTPError: If the Local API returns a non-200 status.
    """
    cache_key: Final[str] = hashlib.sha256(str(firebase_url).encode()).hexdigest()
    cached: Final[RoamAsset | None] = _cached_asset(cache_dir, cache_key, firebase_url)
    if cached is not None:
        return cached

    asset: Final[RoamAsset] = FetchRoamAsset.fetch(firebase_url=firebase_url, api_endpoint=api_endpoint)
    _encache_asset(cache_dir, cache_key, asset, firebase_url)

    return RoamAsset.create(
        file_name=f"{cache_key}{asset.media_type.extension}",
        last_modified=asset.last_modified,
        media_type=asset.media_type,
        contents=asset.contents,
        original_file_name=asset.original_file_name,
    )
