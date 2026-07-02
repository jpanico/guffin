"""Roam Research asset fetching via the Local API.

Public symbols:

- :class:`FetchRoamAsset` — stateless utility class that fetches a Roam asset
  (image or file) by its Cloud Firestore URL via the Local API's ``file.get``
  action.
- :func:`fetch_and_cache_asset` — fetch a Cloud Firestore asset, using a local
  cache directory to avoid re-downloading unchanged assets.
"""

import hashlib
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
            ``action`` to ``"file.get"`` and wraps the Cloud Firestore URL in a
            single :class:`Arg`.

            Once created, instances cannot be modified (frozen).
            """

            model_config = ConfigDict(frozen=True)

            class Arg(BaseModel):
                """A single positional argument in a ``file.get`` request.

                Attributes:
                    url: Cloud Firestore URL of the asset to fetch.
                    format: Encoding format for the response; always ``'base64'``.
                """

                model_config = ConfigDict(frozen=True)

                url: HttpUrl
                format: Literal["base64"] = Field(default="base64")

            @classmethod
            def with_url(cls, url: HttpUrl) -> Self:
                """Construct a ``file.get`` payload for the given Cloud Firestore URL.

                Args:
                    url: Cloud Firestore URL of the asset to fetch.

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
        """Fetch an asset from Cloud Firestore via the Roam Research Local API.

        Builds a ``file.get`` request payload and delegates the HTTP call to
        :func:`~guffin.roam.local_api.invoke_action`. The Roam Desktop app must be
        running and the user must be logged into the graph at the time this method is
        called.

        Args:
            firebase_url: The Cloud Firestore URL of the asset, as it appears in the
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
        )


@validate_call
def fetch_and_cache_asset(
    firebase_url: HttpUrl,
    api_endpoint: ApiEndpoint,
    cache_dir: Path | None = None,
) -> RoamAsset:
    """Fetch a Cloud Firestore asset, using *cache_dir* as a read/write cache.

    The cache key is the SHA-256 hex digest of the URL string.  Cached files
    are stored as ``<sha256>.<ext>`` where the extension is derived from the
    MIME type (e.g. ``.jpg`` for ``image/jpeg``).  The same naming convention
    is applied to the :attr:`~guffin.roam.asset.RoamAsset.file_name` of the
    returned asset, ensuring a consistent, deterministic filename regardless
    of whether the result came from cache or a fresh API call.

    Args:
        firebase_url: The Cloud Firestore URL of the asset to fetch.
        api_endpoint: The Roam Local API endpoint (URL + bearer token).
        cache_dir: Optional directory for caching fetched assets across runs.
            On a cache hit the asset is read from disk; on a cache miss the
            fetched asset is written to *cache_dir* for future runs.

    Returns:
        A :class:`~guffin.roam.asset.RoamAsset` with decoded binary contents,
        a MIME-type-derived ``file_name``, the asset's ``media_type``, and a
        ``last_modified`` timestamp of now.

    Raises:
        ValidationError: If ``firebase_url`` or ``api_endpoint`` is ``None`` or invalid.
        requests.exceptions.ConnectionError: If the Local API is unreachable.
        requests.exceptions.HTTPError: If the Local API returns a non-200 status.
    """
    cache_key: Final[str] = hashlib.sha256(str(firebase_url).encode()).hexdigest()

    if cache_dir is not None:
        cached_files: Final[list[Path]] = list(cache_dir.glob(f"{cache_key}.*"))
        if len(cached_files) > 1:
            raise ValueError(f"Multiple cache files found for key {cache_key!r}: {cached_files}")
        if cached_files:
            cached_path: Final[Path] = cached_files[0]
            cached_media_type: Final[MediaType | None] = MediaType.from_file_name(cached_path.name)
            if cached_media_type is None:
                raise ValueError(f"Cached file has unrecognized extension: {cached_path.name!r}")
            logger.info("Cache hit: %s -> %s", firebase_url, cached_path.name)
            cached_contents: Final[bytes] = cached_path.read_bytes()
            return RoamAsset.create(
                file_name=cached_path.name,
                last_modified=datetime.now(),
                media_type=cached_media_type,
                contents=cached_contents,
            )

    asset: Final[RoamAsset] = FetchRoamAsset.fetch(firebase_url=firebase_url, api_endpoint=api_endpoint)
    ext: Final[str] = asset.media_type.extension
    file_name: Final[str] = f"{cache_key}{ext}"

    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / file_name).write_bytes(asset.contents)
        logger.info("Cached asset: %s -> %s", firebase_url, file_name)

    return RoamAsset.create(
        file_name=file_name,
        last_modified=asset.last_modified,
        media_type=asset.media_type,
        contents=asset.contents,
    )
