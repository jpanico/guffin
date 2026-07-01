# guffin

Python 3.14 toolkit for exporting Roam Research graph sub-trees to self-contained documents. Supports three output formats:

- **Markdown** — renders to Github Flavored Markdown (GFM) and optionally bundles Roam-hosted (Cloud Firestore) images into a self-contained `.mdbundle` directory.
- **PDF** — builds a Pandoc object model directly from a graph sub-tree via [Panflute](https://github.com/sergiocorreia/panflute), fetches and embeds Roam-hosted (Cloud Firestore) images, and produces a PDF via [Pandoc](https://pandoc.org) + [Typst](https://typst.app).
- **EPUB** — builds the same Panflute object model and embeds Roam-hosted images into the package, then produces an EPUB 3 e-book via [Pandoc](https://pandoc.org) (no Typst required); top-level headings become chapters.

Every export is shaped by a **project type** (`--type default|book|manuscript`) that selects a structural profile: where the document divides (sections vs. chapters vs. parts), whether sections are numbered, and whether a title page is emitted. A `book`, for example, starts each top-level heading on a new chapter page, numbers its sections, and renders a title page; a `default` article does none of these. Bibliographic **metadata** — title, authors, date, identifier — is sourced from a `guffin-meta::` block on the root page and mapped to each format's native metadata (the PDF/EPUB title page and the EPUB `dc:*` fields); a `title` attribute there overrides the Roam page title.

It also includes `dump-roam-tree`, a companion tool that renders a graph sub-tree as a colorized tree in the terminal for interactive inspection.

## Development Setup

### Prerequisites

- Python 3.14 or higher
- Git
- [Pandoc](https://pandoc.org/installing.html) — required for all export formats (`brew install pandoc`)
- [Typst](https://typst.app) — PDF engine used by Pandoc (`brew install typst`)
- **Noto Sans** and **Noto Sans Mono** (static, not variable) _fonts_ — required for PDF rendering with the default Bergfink template; install the static variants from Google Fonts via Font Book, or override the fonts in `src/guffin/render/typst_resources/user_cfg.typ`

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
│       ├── cli/                         # CLI entry points and supporting infrastructure
│       │   ├── common.py                  # Shared tree-loading pipeline (fetch_roam_trees);
│       │   │                              #   deduce_out_file_stem()
│       │   ├── dump_roam_tree.py          # dump-roam-tree: render Roam subtree as a Rich tree
│       │   ├── export_roam_tree.py        # export-roam-tree: export to Markdown, PDF, or EPUB
│       │   ├── logging_config.py          # Colorized logging; reads LOG_LEVEL env var
│       │   └── params.py                  # Shared Typer Argument/Option declarations (TargetArgument,
│       │                                  #   PortOption, GraphOption, TokenOption)
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
│       ├── model/                       # Core Guffin normalized-graph model (depends only on common/)
│       │   ├── primitives.py              # Uid type alias; SYNTHETIC/DAILY_NOTE/UID_PATTERN(/RE),
│       │   │                              #   ANCHORED_UID_PATTERN(/RE), is_daily_note_uid()
│       │   ├── vertex_type.py             # VertexType StrEnum (PAGE/TEXT/HEADING/IMAGE/…); leaf module
│       │   │                              #   so vertex.py and guffin_semantics.py share it acyclically
│       │   ├── vertex.py                  # Vertex union + nine concrete types (PageVertex,
│       │   │                              #   HeadingVertex, TextVertex, ImageVertex, CalloutVertex,
│       │   │                              #   CodeBlockVertex, BlockQuoteVertex, TableVertex,
│       │   │                              #   BlockEmbedVertex); _BaseVertex.attribute_assignments;
│       │   │                              #   find_attribute_assignment/find_guffin_attribute;
│       │   │                              #   VertexChildren, VertexRefs, vertex_adapter (re-exports VertexType)
│       │   ├── vertex_tree.py             # VertexTree (tree_vertices, ref_vertices, uid_map),
│       │   │                              #   VertexTreeDFSIterator, root_vertex(), map_vertices(),
│       │   │                              #   drop_attribute_assignments(); filter helpers
│       │   │                              #   (page_vertices, image_vertices, …)
│       │   ├── view.py                    # Presentation overlay: ChildrenLayout, VertexView, ViewMap,
│       │   │                              #   DEFAULT_CHILDREN_LAYOUT
│       │   ├── render_bundle.py           # RenderBundle: VertexTree content + ViewMap presentation
│       │   ├── link.py                    # x-guffin inter-vertex link scheme; VertexLinkKind,
│       │   │                              #   VertexLink, vertex_link_url(), parse_vertex_link(),
│       │   │                              #   is_vertex_link()
│       │   ├── attribute.py               # Roam attribute-assignment model: Attribute (graph-independent
│       │   │                              #   identity: name + AttributeDomain), AttributeInstance (graph-
│       │   │                              #   bound: Attribute + VertexLink), AttributeDomain, LiteralValue,
│       │   │                              #   ReferenceValue, AttributeValue, AttributeAssignment
│       │   └── guffin_semantics.py        # Guffin's format-independent, publishing-standard vocabulary:
│       │                                  #   Anchor (PAGE/HEADING, carries its VertexType), Matter
│       │                                  #   (front/body/back-matter), GuffinAttribute (Attribute pinned
│       │                                  #   to guffin domain + Anchor), GuffinSemantics (enum of
│       │                                  #   GuffinAttribute: TITLE/AUTHORS/DATE/IDENTIFIER + the
│       │                                  #   ELEMENT_TYPE & MATTER heading tags), StructuralElement (book
│       │                                  #   parts COVER…COLOPHON, each w/ Matter), element_type_of()/matter_of()
│       │
│       ├── transcribe/                  # Source → model bridge: transcription + normalization (shared)
│       │   ├── roam_md_to_pandoc_md.py    # Convert Roam-flavored Markdown strings to Pandoc Markdown
│       │   └── roam_tree_to_guffin.py     # NodeTree → guffin render model: transcribe() (VertexTree),
│       │                                  #   build_view_map() (ViewMap), to_render_bundle()
│       │
│       ├── render/                      # Output rendering: model → output (export + terminal) + config
│       │   ├── render_options.py          # OutputFormat (markdown/pdf/epub) discriminator; RenderOptions
│       │   │                              #   base + MarkdownRenderOptions/PdfRenderOptions/EpubRenderOptions
│       │   ├── project.py                 # ProjectType (default/book/manuscript), ProjectProfile +
│       │   │                              #   subclasses, StructuralPolicy (modeled on Quarto project:type:)
│       │   ├── image_fetch.py             # Pandoc-free image asset fetching; ImageRef (UID + path +
│       │   │                              #   ImageSize); fetch_images() → {uid: ImageRef};
│       │   │                              #   fetch_and_enrich_images() → (VertexTree, {uid: ImageRef})
│       │   ├── pandoc_rendering.py        # Shared Pandoc/Panflute utilities; vertex_tree_to_pandoc()
│       │   │                              #   builds a Panflute Doc; VertexLinkResolver type alias and
│       │   │                              #   resolve_vertex_links() replace x-guffin links in-place
│       │   ├── md_rendering.py            # VertexTree → GFM Markdown; writes .mdbundle or plain .md
│       │   ├── pdf_rendering.py           # VertexTree → PDF via Pandoc + Typst
│       │   ├── epub_rendering.py          # VertexTree → EPUB 3 via Pandoc (title → dc:title,
│       │   │                              #   headings → chapters, images embedded)
│       │   ├── epub_semantics.py          # EPUB structural semantics: EpubDivision, EpubType (epub:type
│       │   │                              #   terms + division), epub_type_for() (StructuralElement→EpubType)
│       │   ├── rich_rendering.py          # Rich panel/tree rendering for NodeTree and VertexTree (dump)
│       │   ├── gfm_resources/             # GFM Pandoc Lua filters (package data): gfm_callout,
│       │   │                              #   gfm_color_span, gfm_image, gfm_mark
│       │   ├── typst_resources/           # Bergfink Typst template + typst_*.lua filters
│       │   │                              #   (package data; see typst_resources/README.md)
│       │   ├── epub_resources/            # EPUB package data: epub_*.lua filters (callout, color-span,
│       │   │                              #   mark, number-lines) + epub.css default stylesheet
│       │   └── callout_icons/             # Shared SVG callout badge icons (info, memo, …) used by
│       │                                  #   both PDF and EPUB; see callout_icons/README.md
│       │
│       └── roam/                        # Roam Research data model, API, and processing
│           ├── primitives.py              # Foundational type aliases (Uid, Id, Order, PageTitle),
│           │                              #   stub models (IdObject, LinkObject), ChildrenViewType,
│           │                              #   UID regex (SYNTHETIC/DAILY_NOTE/UID_PATTERN,
│           │                              #   ANCHORED_UID_PATTERN), is_daily_note_uid()
│           ├── markdown.py                # Roam Markdown constructs: CALLOUT_RE, CalloutType,
│           │                              #   RoamCallout, parse_callout, IMAGE_LINK_RE, image-link
│           │                              #   accessors, block-quote helpers, ROAM_NATIVE_TABLE_MARKER
│           ├── schema.py                  # Datomic schema model types (SchemaNamespace, SchemaAttribute)
│           ├── node.py                    # RoamNode, NodeType, node_type, NodesByUid
│           ├── node_network.py            # NodeNetwork; validators (all_children_present,
│           │                              #   is_acyclic, …) and utilities (all_descendants,
│           │                              #   refs_ids, min_effective_heading_level)
│           ├── node_tree.py               # NodeTree (build() factory, id_map, page_name_map),
│           │                              #   NodeTreeDFSIterator, is_tree
│           ├── asset.py                   # Cloud Firestore asset model
│           ├── local_api.py               # ApiEndpoint model for the Roam Local API
│           ├── node_fetch_result.py       # NodeFetchAnchor, NodeFetchSpec, NodeFetchResult
│           ├── node_fetch.py              # Fetch RoamNode records via Local API
│           ├── schema_fetch.py            # Fetch Datomic schema via Local API
│           └── asset_fetch.py             # Fetch Cloud Firestore assets via Local API
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
│   ├── processing_pipeline.md             # High-level overview of the whole pipeline (fetch → transcribe → render)
│   ├── render-pipeline.md                 # Render layer (model → output) + the project-type model
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

Fetches a Roam `Page` or `Node` subtree via the Local API, normalizes it, and writes the result in one of three formats controlled by `--format`. The positional argument is interpreted as a **node UID** when wrapped in `(( ))` or when it matches an anchored UID pattern (a 9-character synthetic UID or an `MM-DD-YYYY` Daily Note UID); otherwise it is treated as a **page title** (any `[[ ]]` wrapper is stripped).

```bash
export-roam-tree <page_title_or_node_uid> --port <port> --graph <graph> --token <token> --output-dir <output_dir> \
  [--format markdown|pdf|epub] [--type default|book|manuscript] [--bundle|--no-bundle] [--cache-dir <dir>] [--template-dir <dir>] [--suppress-attributes] [--colophon|--no-colophon]
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

Pass `--template-dir <dir>` (a directory containing a `user_cfg.typ`) to override the bundled Bergfink Typst styling.

#### EPUB output

`--format epub` builds a Pandoc object model directly from the vertex tree via Panflute, fetches and embeds Cloud Firestore images, and produces an EPUB 3 e-book via Pandoc. The page title becomes the EPUB `dc:title` and top-level headings become the e-book's chapters. Requires `pandoc` on `PATH` (no Typst).

```bash
# Creates ~/docs/Test Article.epub
export-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token --output-dir ~/docs --format epub
```

#### Cross-format options

`--bundle/--no-bundle` applies only to Markdown and `--template-dir` only to PDF; each is ignored by the other formats. `--cache-dir` (cache downloaded images across runs) and `--suppress-attributes` (omit Roam attribute assignments from the output) apply to all three formats. `--colophon/--no-colophon` (on by default) controls whether a provenance colophon — the source git commit (hash + commit time, marked `-dirty` for uncommitted changes) and the export time — is embedded in the output, so any generated document can be traced back to the exact source that produced it. It applies to all three formats; PDF renders it on a line below the page footer, while Markdown and EPUB carry it as an end-of-document line.

`--type default|book|manuscript` (default `default`) selects the **project profile** — the kind of work being produced — independently of `--format` (see [docs/render-pipeline.md](docs/render-pipeline.md)). The selected type is appended to the output filename stem as a `.<type>` segment (e.g. `Foo.default.epub`, `Foo.book.pdf`), so the same target exported under different types lands in distinct files. The profile is plumbed through to every renderer. So far it applies `top_level_division` in both formats — for `--type book`, EPUB splits each chapter into its own content file while PDF opens each chapter on a new page, and both number headings hierarchically from level 1 — plus `number_sections`. The remaining structural effect (title page) is not yet applied to the output.

#### Environment variables

The connection and path options can be supplied via environment variables (the `--format`, `--type`, `--bundle/--no-bundle`, and `--suppress-attributes` flags are not env-backed and must be passed on the command line):

```bash
export GUFFIN_ROAM_LOCAL_API_PORT=3333
export GUFFIN_ROAM_GRAPH_NAME=SCFH
export GUFFIN_ROAM_API_TOKEN=<your-bearer-token>
export GUFFIN_EXPORT_DIR=~/docs
export GUFFIN_CACHE_DIR=~/.cache/roam        # optional: skip re-downloading unchanged images
export GUFFIN_PDF_TEMPLATE_DIR=~/mytheme     # optional: user_cfg.typ override for --format pdf
export GUFFIN_DUMP_PANDOC_AST=1              # optional: dump the Pandoc JSON AST before conversion (debug)
export GUFFIN_EMIT_COLOPHON=0                # optional: omit the provenance colophon (backs --no-colophon)

export-roam-tree "Test Article"                      # Markdown bundle (default)
export-roam-tree "Test Article" --format pdf         # PDF
export-roam-tree "Test Article" --format epub        # EPUB
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

- [docs/processing_pipeline.md](docs/processing_pipeline.md) — High-level overview of the whole pipeline (fetch → transcribe → render) as a directional flow across sub-packages
- [docs/render-pipeline.md](docs/render-pipeline.md) — The render layer (model → output two-stage pipeline) and the project-type model (`ProjectType`/`ProjectProfile`/`StructuralPolicy`)
- [docs/roam-local-api.md](docs/roam-local-api.md) — Roam Local API reference (JSON over HTTP)
- [docs/roam-md.md](docs/roam-md.md) — Roam-flavored Markdown vs. CommonMark differences
- [docs/roam-querying.md](docs/roam-querying.md) — Datalog query language, query structure, and all queries used in this project
- [docs/roam-schema.md](docs/roam-schema.md) — Full Roam attribute schema (kept in sync with `RoamAttribute` enum)
- [docs/MDBUNDLE_SETUP.md](docs/MDBUNDLE_SETUP.md) — macOS `.mdbundle` integration guide

## License

[MIT](LICENSE)
