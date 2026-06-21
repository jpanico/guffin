# guffin

Python 3.14 toolkit for exporting Roam Research graph sub-trees to self-contained documents. Supports two output formats:

- **Markdown** — renders to Github Flavored Markdown (GFM) and optionally bundles Roam-hosted (Cloud Firestore) images into a self-contained `.mdbundle` directory.
- **PDF** — builds a Pandoc object model directly from a graph sub-tree via [Panflute](https://github.com/sergiocorreia/panflute), fetches and embeds Roam-hosted (Cloud Firestore) images, and produces a PDF via [Pandoc](https://pandoc.org) + [Typst](https://typst.app).

## Development Setup

### Prerequisites

- Python 3.14 or higher
- Git
- [Pandoc](https://pandoc.org/installing.html) — required for all export formats (`brew install pandoc`)
- [Typst](https://typst.app) — PDF engine used by Pandoc (`brew install typst`)
- **Noto Sans** and **Noto Sans Mono** (static, not variable) _fonts_ — required for PDF rendering with the default Bergfink template; install the static variants from Google Fonts via Font Book, or override the fonts in `src/guffin/templates/user_cfg.typ`

### Initial Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/jpanico/guffin.git
   cd guffin
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install the package in editable mode with development dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```

   This installs the `guffin` package in editable mode (changes to code are immediately reflected),
   along with all runtime and development dependencies declared in [`pyproject.toml`](pyproject.toml).

### Running Tests

Once the development environment is set up, run the full check pipeline (format, lint, type check, and tests) with a single command:

```bash
hatch run check
```

This runs, in order: `pydocstringformatter`, `black`, `ruff check --fix`, `pyright`, and `pytest`.

To run only the test suite:

```bash
pytest
```

To run tests with verbose output:
```bash
pytest -v
```

To run a specific test file:
```bash
pytest tests/test_roam_asset_fetch.py
```

#### Live Integration Tests

Some tests require the Roam Desktop app to be running locally. These are marked with `@pytest.mark.live` and are skipped by default. To enable them:

```bash
GUFFIN_LIVE_TESTS=1 GUFFIN_ROAM_LOCAL_API_PORT=3333 GUFFIN_ROAM_GRAPH_NAME=<graph> GUFFIN_ROAM_API_TOKEN=<token> pytest -m live -v
```

### Code Formatting

This project uses [Black](https://black.readthedocs.io/) for code formatting (line length: 120):

```bash
black .
```

To check formatting without making changes:
```bash
black --check .
```

### Docstring Formatting and Linting

Docstrings are enforced at two levels:

**1. PEP 257 reflow — [`pydocstringformatter`](https://github.com/DanielNoord/pydocstringformatter)**

Reformats docstring content: line wrapping, blank-line structure, capitalisation, closing-quote placement.

```bash
pydocstringformatter --write src/
```

To preview without writing:
```bash
pydocstringformatter src/
```

**2. Google-style lint — `ruff check`**

Enforces Google docstring convention and auto-fixes violations.

```bash
ruff check src/ tests/
ruff check --fix src/ tests/
```

Recommended order: `pydocstringformatter` → `black` → `ruff check --fix`.

### Type Checking

[Pyright](https://github.com/microsoft/pyright) is configured in **strict** mode for `src/`:

```bash
pyright
```

All production code under `src/guffin/` must be fully annotated with no `Any` types. Test modules (`tests/`) are excluded from pyright via `pyproject.toml` and are not type-checked.

### Regular Expressions

This project uses the third-party [`regex`](https://pypi.org/project/regex/) package **exclusively** — the Python stdlib `re` module is not used anywhere. `regex` is a drop-in superset of `re` (it defaults to `re`-compatible behaviour) and additionally supports recursive patterns, which are required for matching balanced, nestable Roam page references (`[[ … [[ … ]] … ]]`).

Always `import regex` (never `import re`) and use `regex.compile`, `regex.Pattern[str]`, `regex.Match[str]`, and the `regex.*` flags. The `types-regex` stub package (a dev dependency) provides type information for Pyright's strict mode.

## Project Structure

```
guffin/
├── src/
│   └── guffin/                        # Main package
│       ├── vertex.py                    # Vertex union + eight concrete types (PageVertex,
│       │                                #   HeadingVertex, TextVertex, ImageVertex, CalloutVertex,
│       │                                #   CodeBlockVertex, BlockQuoteVertex, TableVertex);
│       │                                #   VertexType, VertexChildren, VertexRefs, vertex_adapter
│       ├── vertex_tree.py               # VertexTree (tree_vertices, ref_vertices, uid_map),
│       │                                #   VertexTreeDFSIterator, root_vertex(), map_vertices();
│       │                                #   filter helpers (page_vertices, image_vertices, …)
│       ├── link.py                      # x-guffin inter-vertex link scheme; VertexLinkKind,
│       │                                #   VertexLink, vertex_link_url(), parse_vertex_link(),
│       │                                #   is_vertex_link()
│       ├── roam_tree_to_vertex_tree.py  # Transcribe NodeTree → VertexTree; applies to_pandoc_md()
│       ├── roam_md_to_pandoc_md.py      # Convert Roam-flavored Markdown strings to Pandoc Markdown
│       │
│       ├── cli/                         # CLI entry points and supporting infrastructure
│       │   ├── dump_roam_tree.py          # dump-roam-tree: render Roam subtree as a Rich tree
│       │   ├── export_roam_tree.py        # export-roam-tree: export to Markdown or PDF
│       │   ├── fetch_roam_tree.py         # Shared tree-loading pipeline (fetch_roam_trees)
│       │   └── logging_config.py          # Colorized logging; reads LOG_LEVEL env var
│       │
│       ├── common/                      # Cross-cutting helpers (no guffin dependencies)
│       │   ├── code_language.py           # CodeLanguage StrEnum of programming-language identifiers
│       │   ├── filenames.py               # POSIX filename normalization (shell_safe_filename)
│       │   ├── geometry.py                # Generic 2D geometry types (ImageSize)
│       │   ├── markdown.py                # HeadingLevel; CommonMark fenced code block utilities
│       │   │                              #   (is_fenced_code_block, FencedCodeBlock,
│       │   │                              #   parse_fenced_code_block); MD_BLOCK_QUOTE_PREFIX
│       │   ├── media_type.py              # MediaType enum; MIME type detection from filenames
│       │   ├── table.py                   # Table, TableStyle, HAlign — 2-D cell grid model
│       │   └── validation.py              # Generic accumulator-pipeline validation framework
│       │
│       ├── render/                      # Rendering pipeline modules
│       │   ├── image_fetch.py             # Pandoc-free image asset fetching; ImageRef (UID + path +
│       │   │                              #   ImageSize); fetch_images() → {uid: ImageRef};
│       │   │                              #   fetch_and_enrich_images() → (VertexTree, {uid: ImageRef})
│       │   ├── pandoc_rendering.py        # Shared Pandoc/Panflute utilities; vertex_tree_to_pandoc()
│       │   │                              #   builds a Panflute Doc; VertexLinkResolver type alias and
│       │   │                              #   resolve_vertex_links() replace x-guffin links in-place
│       │   ├── md_rendering.py            # VertexTree → GFM Markdown; writes .mdbundle or plain .md
│       │   ├── pdf_rendering.py           # VertexTree → PDF via Pandoc + Typst
│       │   ├── rich_rendering.py          # Rich panel/tree rendering for NodeTree and VertexTree
│       │   ├── gfm_callout.lua            # Lua filter: callout Div → GFM alert blockquote
│       │   ├── gfm_color_span.lua         # Lua filter: bg-color Span/Div → GFM HTML span
│       │   ├── gfm_image.lua              # Lua filter: image sizing attributes → HTML <img>
│       │   ├── gfm_mark.lua               # Lua filter: Underline inline → GFM <mark> highlight
│       │   ├── typst_callout.lua          # Lua filter: callout Div → gentle-clues callout box
│       │   └── typst_color_span.lua       # Lua filter: bg-color Span/Div → Typst highlight
│       │
│       ├── roam/                        # Roam Research data model, API, and processing
│       │   ├── primitives.py              # Foundational type aliases (Uid, Id, Order, PageTitle),
│       │   │                              #   stub models (IdObject, LinkObject), and UID regex
│       │   │                              #   constants (UID_PATTERN/RE, ANCHORED_UID_PATTERN/RE)
│       │   ├── markdown.py                # Roam Markdown constructs: CALLOUT_RE, CalloutType,
│       │   │                              #   RoamCallout, parse_callout, IMAGE_LINK_RE,
│       │   │                              #   block-quote helpers, ROAM_NATIVE_TABLE_MARKER
│       │   ├── schema.py                  # Datomic schema model types (RoamNamespace, …)
│       │   ├── node.py                    # RoamNode, NodeType, node_type, NodesByUid
│       │   ├── node_network.py            # NodeNetwork; validators (all_children_present,
│       │   │                              #   is_acyclic, …) and utilities (all_descendants,
│       │   │                              #   refs_ids, min_effective_heading_level)
│       │   ├── node_tree.py               # NodeTree (build() factory, id_map, page_name_map),
│       │   │                              #   NodeTreeDFSIterator, is_tree
│       │   ├── asset.py                   # Cloud Firestore asset model
│       │   ├── local_api.py               # ApiEndpoint model for the Roam Local API
│       │   ├── node_fetch_result.py       # NodeFetchAnchor, NodeFetchSpec, NodeFetchResult
│       │   ├── node_fetch.py              # Fetch RoamNode records via Local API
│       │   ├── schema_fetch.py            # Fetch Datomic schema via Local API
│       │   └── asset_fetch.py             # Fetch Cloud Firestore assets via Local API
│       │
│       └── templates/                   # Bergfink Typst/Pandoc PDF template (package data)
│           ├── bergfink.typst             # Pandoc template entry point
│           ├── base_cfg.typ               # Default cfg dictionary (all supported keys)
│           ├── user_cfg.typ               # User overrides (checked into repo as a working example)
│           ├── default_styles.typ         # Show/set rules derived from cfg
│           ├── titlepage.typ              # Title page layout partial
│           ├── toc.typ                    # Table of contents partial
│           ├── abstract.typ               # Abstract page partial
│           └── yamltable.typ              # YAML-driven table rendering partial
│
├── tests/                               # pytest test suite
│   ├── conftest.py                        # Shared fixtures and helpers
│   ├── regen_fixtures.py                  # Developer script: regenerate fixture files from live Roam
│   └── fixtures/                          # markdown/, yaml/, images/, json/, mdbundle/, pdf/
│
├── scripts/
│   ├── dump-roam-tree.sh                  # Shell wrapper for dump-roam-tree
│   ├── export-roam-tree.sh                # Shell wrapper for export-roam-tree
│   ├── setup-mdbundle-handler.sh          # Setup .mdbundle auto-open in Typora (macOS)
│   └── refresh-mdbundle-folders.sh        # Refresh existing .mdbundle folders (macOS)
│
├── docs/
│   ├── processing_pipeline.md             # High-level overview of the core data processing pipeline
│   ├── roam-local-api.md                  # Roam Local API (JSON over HTTP) reference
│   ├── roam-md.md                         # Roam-flavored Markdown vs. CommonMark differences
│   ├── roam-querying.md                   # Datalog query language and all queries used in this project
│   ├── roam-schema.md                     # Full Roam attribute schema
│   └── MDBUNDLE_SETUP.md                  # macOS .mdbundle integration guide
│
└── pyproject.toml                         # Project configuration
```

## Usage

The package provides two command-line utilities.

### `export-roam-tree` — Export a Roam page or node subtree

Fetches a Roam `Page` or `Node` subtree via the Local API, normalizes it, and writes the result in one of two formats controlled by `--format`. The positional argument is interpreted as a **node UID** if it matches `^[A-Za-z0-9_-]{9}$` (exactly 9 alphanumeric/dash/underscore characters); otherwise it is treated as a **page title**.

```bash
export-roam-tree <page_title_or_node_uid> --port <port> --graph <graph> --token <token> --output-dir <output_dir> \
  [--format markdown|pdf] [--bundle|--no-bundle] [--cache-dir <dir>]
```

#### Markdown output (default)

By default (`--format markdown`) it creates a `.mdbundle` directory containing the Github Flavored Markdown (GFM) document and any downloaded Cloud Firestore images. Pass `--no-bundle` to write a plain `.md` file instead.

```bash
# Bundled (default) — creates ~/docs/Test Article.mdbundle/
export-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token --output-dir ~/docs

# Plain .md — creates ~/docs/Test Article.md
export-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token --output-dir ~/docs --no-bundle

# Export by node UID
export-roam-tree wdMgyBiP9 --port 3333 --graph SCFH --token your-bearer-token --output-dir ~/docs
```

#### PDF output

`--format pdf` builds a Pandoc object model directly from the vertex tree via Panflute, fetches and embeds Cloud Firestore images, and produces a PDF via Pandoc + Typst. Requires `typst` on `PATH`.

```bash
# Creates ~/docs/Test Article.pdf
export-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token --output-dir ~/docs --format pdf
```

The `--bundle/--no-bundle` flags are ignored with `--format pdf`. The `--cache-dir` option works with both formats.

#### Environment variables

All options can be supplied via environment variables:

```bash
export GUFFIN_ROAM_LOCAL_API_PORT=3333
export GUFFIN_ROAM_GRAPH_NAME=SCFH
export GUFFIN_ROAM_API_TOKEN=<your-bearer-token>
export GUFFIN_EXPORT_DIR=~/docs
export GUFFIN_CACHE_DIR=~/.cache/roam   # optional: skip re-downloading unchanged images

export-roam-tree "Test Article"                      # Markdown bundle (default)
export-roam-tree "Test Article" --format pdf         # PDF
```

To change the log level (default: `INFO`), set `LOG_LEVEL`:

```bash
LOG_LEVEL=DEBUG export-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token --output-dir ~/docs
```

### `dump-roam-tree` — Inspect a Roam page or node subtree as a Rich tree

Fetches a Roam `Page` or `Node` subtree via the Local API, and renders it as a colorized tree in the terminal. Useful for inspecting the `RoamNode` structure or the normalized `Vertex`/`VertexTree` structures. The positional argument follows the same page-title-vs-node-UID inference as `export-roam-tree`.

```bash
dump-roam-tree <page_title_or_node_uid> --port <port> --graph <graph> --token <token> \
  [--vertex-tree] [--node-tree] [--raw-results] [--include-refs] \
  [--node-props <props>] [--vertex-props <props>]
```

Flags (all are boolean toggles with a `--no-*` / uppercase-letter inverse):

| Flag | Short | Default | Effect |
|---|---|---|---|
| `--vertex-tree` | `-v/-V` | **on** | Render the normalized vertex tree |
| `--node-tree` | `-n/-N` | off | Render the raw node tree |
| `--raw-results` | `-r/-R` | off | Print the raw Datalog query results |
| `--include-refs` | `-i/-I` | **on** | Also fetch nodes referenced via `:block/refs` and their descendants |

`--node-props heading,parents` selects which `RoamNode` fields appear for each node in the node-tree output (defaults to `heading,order,children,parents,page`).

`--vertex-props vertex_type.value,children,refs` selects which `Vertex` fields appear for each vertex in the vertex-tree output (defaults to `vertex_type.value,children,refs`).

Examples:
```bash
# Default: vertex tree + refs included
dump-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token

# Node tree + vertex tree, with custom node props
dump-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token --node-tree --vertex-tree --node-props heading,parents

# Raw Datalog results only, no refs
dump-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token --raw-results --no-vertex-tree --no-include-refs

# Fetch by node UID
dump-roam-tree wdMgyBiP9 --port 3333 --graph SCFH --token your-bearer-token
```

### macOS Integration: Auto-Open in Typora

To configure macOS to automatically open `.mdbundle` folders in Typora when double-clicked:

1. **Run the setup script:**
   ```bash
   ./scripts/setup-mdbundle-handler.sh
   ```

   This creates and registers `OpenMDBundle.app` which handles `.mdbundle` folders.

2. **Refresh existing .mdbundle folders (if any):**
   ```bash
   ./scripts/refresh-mdbundle-folders.sh ~/wip
   ```

   This updates the metadata for existing `.mdbundle` folders so macOS recognizes them properly.

3. **Done!** Double-clicking any `.mdbundle` folder will now open the markdown file in Typora

See [docs/MDBUNDLE_SETUP.md](docs/MDBUNDLE_SETUP.md) for detailed instructions and troubleshooting.

## Documentation

- [docs/processing_pipeline.md](docs/processing_pipeline.md) — High-level overview of the core data processing pipeline
- [docs/roam-local-api.md](docs/roam-local-api.md) — Roam Local API reference (JSON over HTTP)
- [docs/roam-md.md](docs/roam-md.md) — Roam-flavored Markdown vs. CommonMark differences
- [docs/roam-querying.md](docs/roam-querying.md) — Datalog query language, query structure, and all queries used in this project
- [docs/roam-schema.md](docs/roam-schema.md) — Full Roam attribute schema (kept in sync with `RoamAttribute` enum)
- [docs/MDBUNDLE_SETUP.md](docs/MDBUNDLE_SETUP.md) — macOS `.mdbundle` integration guide

## License

[MIT](LICENSE)
