#!/usr/bin/env python3
"""Regenerate all fixture files for a given Roam page title or node UID.

All fixtures are produced from a single ``include_refs=True`` fetch so that
referenced-page nodes are available in ``refs_by_id`` and page references in
vertex text fields resolve to ``x-guffin`` vertex links.

Writes to tests/fixtures/yaml/ and tests/fixtures/markdown/:

    <prefix>_nodes.yaml         — anchor-subtree RoamNodes (serialised)
    <prefix>_vertices.yaml      — VertexTree (serialised)
    <prefix>_expected.md        — rendered GFM
    <prefix>_raw_result.yaml    — raw Datalog wire response
    <prefix>_anchor_tree.yaml   — serialised NodeTree (anchor subtree + refs)
    <prefix>_nodes_by_uid.yaml  — all fetched nodes keyed by UID

  Optional (--pdf), to tests/fixtures/pdf/:
    <shell-safe-title>.pdf      — byte-reproducible baseline PDF (requires Typst on PATH)

  Optional (--mdbundle), to tests/fixtures/mdbundle/:
    <shell-safe-title>.mdbundle/  — baseline mdbundle directory

Run from the project root with the venv active, one invocation per TestArticle
member (qualifier → --prefix):

  python tests/regen_fixtures.py "<article.qualifier>" --prefix <article.prefix>

Credentials are read from CLI flags first, then env vars, then hard-coded defaults:
  --port   $GUFFIN_ROAM_LOCAL_API_PORT  (default 3333)
  --graph  $GUFFIN_ROAM_GRAPH_NAME      (default SCFH)
  --token  $GUFFIN_ROAM_API_TOKEN
"""

import argparse
import enum
import os
import pathlib
import sys
import tempfile
from typing import Final

import yaml

from guffin.cli.common import deduce_out_file_stem
from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex import vertex_adapter
from guffin.model.vertex_tree import VertexTree
from guffin.cli.logging_config import configure_logging
from guffin.pipeline.md_rendering import render
from guffin.pipeline.pdf_rendering import render as render_pdf
from guffin.pipeline.render_options import MarkdownRenderOptions, PdfRenderOptions
from guffin.roam.local_api import ApiEndpoint
from guffin.roam.node import RoamNode
from guffin.roam.node_fetch import FetchRoamNodes
from guffin.roam.node_fetch_result import NodeFetchAnchor, NodeFetchResult
from guffin.pipeline.roam_tree_to_guffin import build_view_map, transcribe
from guffin.roam.node_tree import NodeTree

from conftest import PDF_CREATION_TIMESTAMP

configure_logging()


class TestArticle(enum.Enum):
    """Identity of a live-Roam test article: Roam page title and fixture filename prefix."""

    qualifier: str
    prefix: str

    ARTICLE_0 = ("[[Test Article]] 0", "test_article_0")
    ARTICLE_1 = ("[[Test Article]] 1", "test_article_1")
    ARTICLE_2 = ("[[Test Article]] 2", "test_article_2")
    ARTICLE_3 = ("[[Test Article]] 3", "test_article_3")
    ARTICLE_4 = ("[[Test Article]] 4", "test_article_4")
    ARTICLE_5 = ("[[Test Article]] 5", "test_article_5")

    def __init__(self, qualifier: str, prefix: str) -> None:
        """Set qualifier and prefix from the tuple member value."""
        self.qualifier = qualifier
        self.prefix = prefix


FIXTURES_YAML: Final[pathlib.Path] = pathlib.Path("tests/fixtures/yaml")
FIXTURES_MD: Final[pathlib.Path] = pathlib.Path("tests/fixtures/markdown")
FIXTURES_PDF: Final[pathlib.Path] = pathlib.Path("tests/fixtures/pdf")
FIXTURES_MDBUNDLE: Final[pathlib.Path] = pathlib.Path("tests/fixtures/mdbundle")
README_PATH: Final[pathlib.Path] = pathlib.Path("tests/fixtures/README.md")

_TRANSIENT_FIELDS: Final[frozenset[str]] = frozenset({"open"})

_DEFAULT_PORT: Final[str] = "3333"
_DEFAULT_GRAPH: Final[str] = "SCFH"
_DEFAULT_TOKEN: Final[str] = "roam-graph-local-token-OR3s0AcJn5rwxPJ6MYaqnIyjNi7ai"

_CALLOUT_MARKER: Final[str] = "[[>]] [[!INFO]] THIS PAGE IS USED FOR TESTING [GUFFIN]("
_PROPERTIES_MARKER: Final[str] = "Features:"


def _extract_features(callout_string: str) -> str | None:
    """Return the feature bullet list that follows 'Features:' in a callout node string.

    Lines starting with '-- ' are Roam's convention for sub-list items; they are
    converted to GFM indented bullets ('  - ').
    """
    idx: Final[int] = callout_string.find(_PROPERTIES_MARKER)
    if idx == -1:
        return None
    raw: Final[str] = callout_string[idx + len(_PROPERTIES_MARKER) :].strip()
    normalized: Final[list[str]] = ["  - " + line[3:] if line.startswith("-- ") else line for line in raw.splitlines()]
    return "\n".join(normalized)


def _update_readme_article_features(qualifier: str, features: str) -> None:
    """Replace the body of the '#### `<qualifier>`' subsection in README_PATH with features."""
    text: Final[str] = README_PATH.read_text(encoding="utf-8")
    lines: Final[list[str]] = text.splitlines(keepends=True)
    heading: Final[str] = f"#### `{qualifier}`"
    start_idx: int | None = None
    end_idx: int | None = None
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n").rstrip()
        if stripped == heading:
            start_idx = i
        elif start_idx is not None and i > start_idx + 1:
            if stripped.startswith("####") or stripped.startswith("###") or stripped.startswith("##"):
                end_idx = i
                break
    if start_idx is None:
        print(f"  WARNING: '#### `{qualifier}`' not found in {README_PATH}; skipping README update")
        return
    if end_idx is None:
        end_idx = len(lines)
    new_content: Final[str] = f"{heading}\n\n{features}\n\n"
    new_lines: Final[list[str]] = lines[:start_idx] + [new_content] + lines[end_idx:]
    README_PATH.write_text("".join(new_lines), encoding="utf-8")
    print(f"  updated {README_PATH} (#### `{qualifier}` features)")


def _stub_node_dict(node: RoamNode) -> dict[str, object]:
    """Serialise *node* with transient fields omitted for fixture storage."""
    d: Final[dict[str, object]] = node.model_dump(mode="json")
    for key in _TRANSIENT_FIELDS:
        d.pop(key, None)
    return d


def main() -> None:
    """Parse arguments and regenerate all six fixture files."""
    parser = argparse.ArgumentParser(
        description="Regenerate all six test fixture files for a Roam page or node.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
        + "".join(f'  python tests/regen_fixtures.py "{a.qualifier}" --prefix {a.prefix}\n' for a in TestArticle),
    )
    parser.add_argument("qualifier", help="Roam page title or 9-char node UID.")
    parser.add_argument(
        "--prefix",
        required=True,
        metavar="PREFIX",
        help="Output file name prefix, e.g. 'test_article_1'.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("GUFFIN_ROAM_LOCAL_API_PORT", _DEFAULT_PORT)),
        help="Roam Local API port (default: $GUFFIN_ROAM_LOCAL_API_PORT or %(default)s).",
    )
    parser.add_argument(
        "--graph",
        default=os.getenv("GUFFIN_ROAM_GRAPH_NAME", _DEFAULT_GRAPH),
        help="Roam graph name (default: $GUFFIN_ROAM_GRAPH_NAME or %(default)s).",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("GUFFIN_ROAM_API_TOKEN", _DEFAULT_TOKEN),
        help="Roam Local API bearer token (default: $GUFFIN_ROAM_API_TOKEN).",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="Also render a byte-reproducible baseline PDF to tests/fixtures/pdf/ (requires Typst on PATH).",
    )
    parser.add_argument(
        "--mdbundle",
        action="store_true",
        help="Also render a baseline .mdbundle to tests/fixtures/mdbundle/.",
    )
    args = parser.parse_args()

    qualifier: Final[str] = args.qualifier
    prefix: Final[str] = args.prefix
    endpoint: Final[ApiEndpoint] = ApiEndpoint.from_parts(
        local_api_port=args.port,
        graph_name=args.graph,
        bearer_token=args.token,
    )
    anchor: Final[NodeFetchAnchor] = NodeFetchAnchor(qualifier=qualifier)

    # Single fetch with include_refs=True — used for all fixtures
    print(f"Fetching '{qualifier}' (include_refs=True) …")
    result: Final[NodeFetchResult] = FetchRoamNodes.fetch_roam_nodes(
        anchor=anchor, api_endpoint=endpoint, include_refs=True
    )
    assert result.anchor_tree is not None
    anchor_tree: Final[NodeTree] = result.anchor_tree
    nodes: Final[list[RoamNode]] = list(anchor_tree.tree_network)
    vertex_tree: Final[VertexTree] = transcribe(anchor_tree)
    render_bundle: Final[RenderBundle] = RenderBundle(content=vertex_tree, view=build_view_map(anchor_tree))
    out_stem: Final[str] = deduce_out_file_stem(vertex_tree)
    print(f"  fetched {len(result.network)} node(s) total, {len(nodes)} anchor node(s)")
    print(f"  transcribed {len(vertex_tree.tree_vertices)} vertex/vertices")

    # Fixture 1: nodes YAML
    nodes_path: Final[pathlib.Path] = FIXTURES_YAML / f"{prefix}_nodes.yaml"
    node_dicts: Final[list[dict[str, object]]] = [_stub_node_dict(n) for n in nodes]
    nodes_header: Final[str] = (
        f"# YAML fixture for '{qualifier}' NodeNetwork.\n"
        "# Regenerated by tests/regen_fixtures.py.\n"
        "# Serialised with model_dump(mode='json') and yaml.dump(\n"
        "#   default_flow_style=False, allow_unicode=True, sort_keys=False).\n"
        "#\n"
        "# The transient 'open' field is excluded from live-test comparisons and is\n"
        "# omitted entirely here so it defaults to None on model_validate.\n"
    )
    nodes_path.write_text(
        nodes_header + yaml.dump(node_dicts, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"  wrote {nodes_path}")

    # Fixture 2: vertices YAML
    vertices_path: Final[pathlib.Path] = FIXTURES_YAML / f"{prefix}_vertices.yaml"
    vertices_header: Final[str] = (
        f"# YAML fixture for '{qualifier}' VertexTree.\n"
        "# Regenerated by tests/regen_fixtures.py.\n"
        "# Serialised with model_dump(mode='json', exclude_none=True) and yaml.dump(\n"
        "#   default_flow_style=False, allow_unicode=True, sort_keys=False).\n"
    )
    vertices_path.write_text(
        vertices_header
        + yaml.dump(
            [vertex_adapter.dump_python(v, mode="json", exclude_none=True) for v in vertex_tree.tree_vertices],
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    print(f"  wrote {vertices_path}")

    # Fixture 3: expected markdown
    md_path: Final[pathlib.Path] = FIXTURES_MD / f"{prefix}_expected.md"
    with tempfile.TemporaryDirectory() as tmp_dir:
        render(
            render_bundle,
            filename_stem=out_stem,
            api_endpoint=endpoint,
            options=MarkdownRenderOptions(output_dir=pathlib.Path(tmp_dir), bundle=False),
        )
        rendered: Final[str] = (pathlib.Path(tmp_dir) / f"{out_stem}.md").read_text(encoding="utf-8")
    md_path.write_text(rendered, encoding="utf-8")
    print(f"  wrote {md_path}")

    # Update README Article Features section from callout node
    callout_node: Final[RoamNode | None] = next(
        (n for n in nodes if n.string is not None and n.string.startswith(_CALLOUT_MARKER)),
        None,
    )
    if callout_node is None or callout_node.string is None:
        print(f"  WARNING: callout node not found for '{qualifier}'; skipping README update")
    else:
        features_text: Final[str | None] = _extract_features(callout_node.string)
        if features_text is None:
            print(f"  WARNING: '{_PROPERTIES_MARKER}' not found in callout node; skipping README update")
        else:
            _update_readme_article_features(qualifier, features_text)

    # Fixture 4: raw_result YAML
    raw_result_path: Final[pathlib.Path] = FIXTURES_YAML / f"{prefix}_raw_result.yaml"
    raw_result_path.write_text(
        yaml.dump(result.raw_result, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"  wrote {raw_result_path}")

    # Fixture 5: anchor_tree YAML
    anchor_tree_path: Final[pathlib.Path] = FIXTURES_YAML / f"{prefix}_anchor_tree.yaml"
    anchor_tree_path.write_text(
        yaml.dump(
            anchor_tree.model_dump(mode="json"),
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    print(f"  wrote {anchor_tree_path}")

    # Fixture 6: nodes_by_uid YAML
    nodes_by_uid_path: Final[pathlib.Path] = FIXTURES_YAML / f"{prefix}_nodes_by_uid.yaml"
    assert result.nodes_by_uid is not None
    nodes_by_uid_path.write_text(
        yaml.dump(
            {uid: node.model_dump(mode="json") for uid, node in result.nodes_by_uid.items()},
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    print(f"  wrote {nodes_by_uid_path}")

    # Fixture 7 (optional, --pdf): byte-reproducible baseline PDF under tests/fixtures/pdf/
    if args.pdf:
        FIXTURES_PDF.mkdir(parents=True, exist_ok=True)
        os.environ["GUFFIN_PDF_CREATION_TIMESTAMP"] = str(PDF_CREATION_TIMESTAMP)
        render_pdf(
            render_bundle,
            filename_stem=out_stem,
            api_endpoint=endpoint,
            options=PdfRenderOptions(output_dir=FIXTURES_PDF),
        )
        pdf_path: Final[pathlib.Path] = FIXTURES_PDF / f"{out_stem}.pdf"
        print(f"  wrote {pdf_path}")

    # Fixture 8 (optional, --mdbundle): baseline .mdbundle under tests/fixtures/mdbundle/
    if args.mdbundle:
        FIXTURES_MDBUNDLE.mkdir(parents=True, exist_ok=True)
        render(
            render_bundle,
            filename_stem=out_stem,
            api_endpoint=endpoint,
            options=MarkdownRenderOptions(output_dir=FIXTURES_MDBUNDLE, bundle=True),
        )
        mdbundle_path: Final[pathlib.Path] = FIXTURES_MDBUNDLE / f"{out_stem}.mdbundle"
        print(f"  wrote {mdbundle_path}")

    print("Done.")


if __name__ == "__main__":
    main()
    sys.exit(0)
