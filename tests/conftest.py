"""Shared pytest configuration and test infrastructure for the guffin test suite."""

import os
import pathlib
from typing import Final

import pytest
import yaml

from guffin.model.vertex import vertex_adapter
from guffin.model.vertex_tree import VertexTree
from guffin.roam.local_api import ApiEndpoint, ApiEndpointURL
from guffin.roam.node import NodeType, RoamNode, node_type
from guffin.roam.node_tree import NodeTree

FIXTURES_YAML_DIR: pathlib.Path = pathlib.Path(__file__).parent / "fixtures" / "yaml"
"""Absolute path to the ``tests/fixtures/yaml/`` directory."""

FIXTURES_JSON_DIR: pathlib.Path = pathlib.Path(__file__).parent / "fixtures" / "json"
"""Absolute path to the ``tests/fixtures/json/`` directory."""

FIXTURES_IMAGES_DIR: pathlib.Path = pathlib.Path(__file__).parent / "fixtures" / "images"
"""Absolute path to the ``tests/fixtures/images/`` directory."""

FIXTURES_MD_DIR: pathlib.Path = pathlib.Path(__file__).parent / "fixtures" / "markdown"
"""Absolute path to the ``tests/fixtures/markdown/`` directory."""

FIXTURES_PDF_DIR: pathlib.Path = pathlib.Path(__file__).parent / "fixtures" / "pdf"
"""Absolute path to the ``tests/fixtures/pdf/`` directory."""

FIXTURES_MDBUNDLE_DIR: pathlib.Path = pathlib.Path(__file__).parent / "fixtures" / "mdbundle"
"""Absolute path to the ``tests/fixtures/mdbundle/`` directory."""

PDF_CREATION_TIMESTAMP: int = 1704067200
"""Fixed UNIX timestamp (2024-01-01T00:00:00Z) pinned via ``GUFFIN_PDF_CREATION_TIMESTAMP`` so PDF.

export is byte-reproducible; shared by the live PDF fixture test and ``regen_fixtures.py --pdf``.
"""


@pytest.fixture(autouse=True)
def _neutralize_render_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the render-shaping environment variables for every test.

    The colophon embeds the live export time and source commit, which would vary every run and per
    commit — breaking the byte-for-byte fixture comparisons (offline mdbundle, live PDF).  Tests that
    exercise the colophon opt in explicitly (by passing a :class:`~guffin.common.provenance.Provenance`
    or re-enabling ``GUFFIN_EMIT_COLOPHON``).

    The tri-state flag overrides (``GUFFIN_INCLUDE_PREAMBLE``, ``GUFFIN_NUMBER_SECTIONS``) are
    removed so CLI-invoking tests always exercise the defer-to-profile default, regardless of
    what the developer's shell exports.
    """
    monkeypatch.setenv("GUFFIN_EMIT_COLOPHON", "0")
    monkeypatch.delenv("GUFFIN_INCLUDE_PREAMBLE", raising=False)
    monkeypatch.delenv("GUFFIN_NUMBER_SECTIONS", raising=False)


@pytest.fixture
def api_endpoint() -> ApiEndpoint:
    """Return a minimal :class:`~guffin.roam.local_api.ApiEndpoint` for unit tests."""
    return ApiEndpoint(
        url=ApiEndpointURL(local_api_port=3333, graph_name="test-graph"),
        bearer_token="test-token",
    )


@pytest.fixture
def live_api_endpoint() -> ApiEndpoint:
    """Return a live :class:`~guffin.roam.local_api.ApiEndpoint` built from env vars.

    Requires ``GUFFIN_ROAM_LOCAL_API_PORT``, ``GUFFIN_ROAM_GRAPH_NAME``, and ``GUFFIN_ROAM_API_TOKEN``
    to be set in the environment.  Intended for use in tests marked ``@pytest.mark.live``.
    """
    return ApiEndpoint.from_parts(
        local_api_port=int(os.environ["GUFFIN_ROAM_LOCAL_API_PORT"]),
        graph_name=os.environ["GUFFIN_ROAM_GRAPH_NAME"],
        bearer_token=os.environ["GUFFIN_ROAM_API_TOKEN"],
    )


@pytest.fixture
def live_cache_dir() -> pathlib.Path:
    """Return the asset cache directory from ``GUFFIN_CACHE_DIR`` for live tests.

    Requires ``GUFFIN_CACHE_DIR`` to be set in the environment.  Intended for use in
    tests marked ``@pytest.mark.live``.
    """
    return pathlib.Path(os.environ["GUFFIN_CACHE_DIR"])


def article1_node_tree() -> NodeTree:
    """Load and return the ``[[Test Article]] 1`` :class:`~guffin.roam.node_tree.NodeTree` from its YAML fixture.

    Loads all nodes from ``test_article_1_nodes_by_uid.yaml`` (anchor subtree plus
    referenced pages) so that :attr:`~guffin.roam.node_tree.NodeTree.refs_by_id` is
    populated and page references resolve to ``x-guffin`` vertex links during
    transcription.
    """
    raw_by_uid: Final[dict[str, dict[str, object]]] = yaml.safe_load(
        (FIXTURES_YAML_DIR / "test_article_1_nodes_by_uid.yaml").read_text()
    )
    all_nodes: Final[list[RoamNode]] = [RoamNode.model_validate(r) for r in raw_by_uid.values()]
    root_node: Final[RoamNode] = next(
        n for n in all_nodes if node_type(n) == NodeType.PAGE and n.title == "[[Test Article]] 1"
    )
    return NodeTree.build(super_network=all_nodes, root_node=root_node)


def article1_vertex_tree() -> VertexTree:
    """Load and return the ``[[Test Article]] 1`` :class:`~guffin.vertex_tree.VertexTree` from its YAML fixture."""
    raw: Final[list[dict[str, object]]] = yaml.safe_load(
        (FIXTURES_YAML_DIR / "test_article_1_vertices.yaml").read_text()
    )
    return VertexTree(tree_vertices=[vertex_adapter.validate_python(r) for r in raw])


def article5_node_tree() -> NodeTree:
    """Load and return the ``[[Test Article]] 5`` :class:`~guffin.roam.node_tree.NodeTree` from its YAML fixture.

    Loads all nodes from ``test_article_5_nodes_by_uid.yaml`` (anchor subtree plus referenced pages)
    so that :attr:`~guffin.roam.node_tree.NodeTree.page_name_map` is populated and attribute/tag page
    references resolve to ``x-guffin`` vertex links during transcription.
    """
    raw_by_uid: Final[dict[str, dict[str, object]]] = yaml.safe_load(
        (FIXTURES_YAML_DIR / "test_article_5_nodes_by_uid.yaml").read_text()
    )
    all_nodes: Final[list[RoamNode]] = [RoamNode.model_validate(r) for r in raw_by_uid.values()]
    root_node: Final[RoamNode] = next(
        n for n in all_nodes if node_type(n) == NodeType.PAGE and n.title == "[[Test Article]] 5"
    )
    return NodeTree.build(super_network=all_nodes, root_node=root_node)
