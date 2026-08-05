# guffin

Python 3.14 toolkit for exporting Roam Research graph sub-trees to self-contained documents. Supports three output formats:

- **Markdown** — renders to Github Flavored Markdown (GFM) and optionally bundles Roam-hosted (Firebase Storage) images, PDFs, and bare assets into a self-contained `.mdbundle` directory.
- **PDF** — builds a Pandoc object model directly from a graph sub-tree via [Panflute](https://github.com/sergiocorreia/panflute), fetches and embeds Roam-hosted (Firebase Storage) images, and produces a PDF via [Pandoc](https://pandoc.org) + [Typst](https://typst.app) (the bundled Bergfink template). PDF assets are not embedded as files, but an embed tagged `pdf-render:: inline-native` renders all of its pages into the document flow, and one tagged `appendix-native` renders them in a generated back-matter appendix linked from the embed.
- **EPUB** — builds the same Panflute object model and embeds Roam-hosted images into the package, then produces an EPUB 3 e-book via [Pandoc](https://pandoc.org) (no Typst required); top-level headings become chapters. A PDF embed tagged `pdf-render:: appendix-image` has its pages rasterised and reproduced in a generated back-matter appendix.

Orthogonal to the format, a **project type** (`--type article|book|manuscript`) says what *kind* of work is being produced. Its structural profile drives where the document divides (sections vs. chapters vs. parts), whether headings are numbered, whether a title page and table of contents are emitted, whether the root's loose preamble is kept, and whether authored `page-break:: before` tags are honored. A `book`, for example, opens each chapter on a new page (or file, for EPUB), numbers its headings, emits a linked ToC and a title page, and drops the preamble; an `article` does none of these. A book also **auto-detects parts** from its content: any level-1 heading tagged `element-type:: part` switches it to a part/chapter structure.

Document structure and bibliographic **metadata** are declared in the Roam content itself, through the format-independent `guffin`-domain attribute vocabulary. A `guffin-meta::` block on the root page carries the bibliographic metadata — title, subtitle, authors, illustrators, date, publisher, rights, identifier, language, description, revision, and cover image — which each renderer maps to its format's native conventions (the PDF/EPUB title page, the EPUB `dc:*` fields, the Markdown YAML front matter); `element-type::`/`matter::` heading tags, a per-block `publish:: false` tag, a per-embed `pdf-render::` placement tag (see [docs/pdf-render.md](docs/pdf-render.md)), and a per-code-block `code-source::` provenance tag (verified against GitHub on every export, unless `--no-verify-code-sources`) drive the rest.

It also includes `dump-roam-tree`, a companion tool that renders a graph sub-tree as a colorized tree in the terminal for interactive inspection.

Both commands are also servable remotely: **server mode** (`guffin-server`) exposes them as HTTP command endpoints — the JSON Request mirrors the CLI arguments, and the response carries the exported document (streamed, integrity-headed) or the captured dump rendering — so any machine can request work from the one running Roam Desktop, the only host the Roam Local API answers on. See [docs/server-mode.md](docs/server-mode.md).

## Development Setup

### Prerequisites

- Python 3.14 or higher
- Git
- [Pandoc](https://pandoc.org/installing.html) — required for all export formats (`brew install pandoc`)
- [Typst](https://typst.app) — PDF engine used by Pandoc; **≥ 0.14** required for inline PDF-page rendering (`brew install typst`)
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

This runs, in order: `pydocstringformatter`, `black`, `ruff check --fix`, `pyright`, and `test-heavy` (the full suite, live tests included — requires Roam Desktop running locally).

The suite is organized into tiers (hatch scripts), lightest to heaviest:

```bash
hatch run test-light    # skips the pandoc-subprocess integration tests; the fast inner loop
hatch run test-medium   # the full offline suite
hatch run test-heavy    # everything, live tests included (requires Roam Desktop running locally)
```

To run the plain offline suite directly:

```bash
pytest
```

The `tests/` tree mirrors `src/guffin/` — each test module lives in the sub-package of the module it covers (e.g. `tests/roam/test_asset_fetch.py` covers `guffin/roam/asset_fetch.py`). To run one file:

```bash
pytest tests/roam/test_asset_fetch.py
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
│   └── guffin/                          # Main package
│       ├── cli/                           # CLI entry points and supporting infrastructure
│       │   ├── code_source_verification.py  # Verify code-source:: code blocks against GitHub
│       │   ├── common.py                    # Shared tree-loading pipeline (fetch_roam_trees,
│       │   │                                #   resolve_profile); output-filename derivation
│       │   ├── dump_roam_tree.py            # dump-roam-tree: render Roam subtree as a Rich tree
│       │   ├── export_roam_tree.py          # export-roam-tree: export to Markdown, PDF, or EPUB
│       │   ├── logging_config.py            # Colorized logging; reads LOG_LEVEL env var
│       │   ├── params.py                    # Shared Typer Argument/Option declarations
│       │   └── serve.py                     # guffin-server: launch the HTTP server front end
│       │
│       ├── server/                        # HTTP server front end: remote RPC-like invocation
│       │   ├── app.py                       # FastAPI ASGI app: POST /v1/export, POST /v1/dump,
│       │   │                                #   GET /v1/health; RFC 9457 problem+json errors
│       │   ├── request_derivation.py        # Typer signature → request model + argv translation
│       │   ├── request_models.py            # The derived ExportRequest / DumpRequest models
│       │   ├── invocation.py                # In-process CliRunner invocation, structured capture
│       │   ├── console_export.py            # Dump representations: text / HTML / SVG (Rich export)
│       │   ├── export_artifact.py           # Artifact resolution, .mdbundle zipping, Content-Digest
│       │   ├── cors.py                      # Opt-in CORS browser-admission grants (--allow-origin)
│       │   └── problem_details.py           # RFC 9457 application/problem+json responses
│       │
│       ├── common/                        # Cross-cutting helpers (no guffin dependencies)
│       │   ├── date.py                      # English month names, ordinal suffixes, UTC timestamps
│       │   ├── filenames.py                 # POSIX filename normalization (shell_safe_filename)
│       │   ├── geometry.py                  # Generic 2D geometry types (ImageSize)
│       │   ├── github_fetch.py              # GitHub ref resolution + commit-pinned file retrieval
│       │   ├── github_file_ref.py           # GitHubFileRef: file addressing + blob/raw URL encodings
│       │   ├── json_value.py                # JsonValue recursive type alias
│       │   ├── line_range.py                # LineRange: inclusive 1-based line range + slicing
│       │   ├── markdown.py                  # CommonMark fenced-code-block and hard-break utilities
│       │   ├── media_type.py                # MediaType enum; MIME type detection from filenames
│       │   ├── programming_language.py      # Canonical language vocabulary (vendored GitHub Linguist);
│       │   │                                #   programming_language_data.py holds the generated data
│       │   ├── provenance.py                # Export provenance (source git commit + timestamps)
│       │   ├── revision.py                  # Content revision (snapshot hash + edit/fetch bookkeeping)
│       │   ├── table.py                     # Table, TableStyle — 2-D cell grid model
│       │   ├── validation.py                # Generic accumulator-pipeline validation framework
│       │   ├── w3cdtf_date.py               # W3CDTF reduced-precision date (YYYY[-MM[-DD]])
│       │   └── whitespace.py                # Unicode space-separator normalization (normalize_spaces)
│       │
│       ├── model/                         # Core normalized-graph model (depends only on common/)
│       │   ├── primitives.py                # Uid + UID regex primitives; is_daily_note_uid()
│       │   ├── vertex.py                    # VertexType StrEnum; Vertex union + thirteen concrete types
│       │   │                                #   (Page/Heading/Text/Todo/Image/Pdf/Asset/Callout/CodeBlock/
│       │   │                                #   QuoteBlock/Table/BlockEmbed/PageEmbed); asset & embed
│       │   │                                #   unions with narrowing predicates
│       │   ├── vertex_tree.py               # VertexTree (tree_vertices, ref_vertices, uid_map),
│       │   │                                #   transcluded_vertices(), assignments_for(), transformers
│       │   ├── vertex_view.py               # Presentation overlay: ChildrenLayout, Semantic,
│       │   │                                #   SourceChannel, VertexView, ViewMap
│       │   ├── render_bundle.py             # RenderBundle: VertexTree + ViewMap + provenance + revision
│       │   ├── vertex_link.py               # x-guffin inter-vertex link scheme
│       │   ├── attribute.py                 # Attribute identity/values (Attribute, AttributeInstance,
│       │   │                                #   AttributeDomain, LiteralValue/ReferenceValue)
│       │   ├── attribute_assignment.py      # A whole `<attribute>:: <value>, …` assignment + readers
│       │   ├── attribute_anchor.py          # Anchoring affordances: TreePosition, AttributeAnchor
│       │   ├── chicago_structure.py         # CMOS taxonomy: Matter, StructuralElement
│       │   ├── element_number.py            # Internal element numbering (a heading's [1.2.3] lead)
│       │   ├── asset_storage.py             # AssetStorage: where a hosted asset's binary lives
│       │   │                                #   (location URL, store type, encryption state)
│       │   ├── code_source.py               # CodeSource: a code block's GitHub provenance
│       │   │                                #   (blob URL + commit SHA + fetch date)
│       │   ├── code_source_diagnosis.py     # Pure verdict of a code block against its source
│       │   │                                #   (drift vs. local modification vs. fetch failure)
│       │   ├── publishing_semantics.py      # Guffin's publishing-standard attribute vocabulary
│       │   │                                #   (PublishingSemantics)
│       │   └── publishing_validation.py     # The vocabulary's validation pass (validate_semantics)
│       │
│       ├── transcribe/                    # Source → model bridge: transcription + normalization
│       │   ├── roam_md_to_pandoc_md.py      # Convert Roam-flavored Markdown strings to Pandoc Markdown
│       │   └── roam_tree_to_guffin.py       # NodeTree → render model: transcribe(), build_view_map(),
│       │                                    #   to_render_bundle()
│       │
│       ├── render/                        # Output rendering: model → output (export + terminal)
│       │   ├── date_format.py               # DateFormat (roam-long/iso/abbrev-month-day) + format_date()
│       │   ├── render_options.py            # OutputFormat discriminator; RenderOptions base + per-format
│       │   ├── project.py                   # ProjectType, ProjectProfile + subclasses, StructuralPolicy
│       │   ├── asset_fetch.py               # Pandoc-free asset fetching; AssetRef; fetch_and_enrich_assets()
│       │   ├── pandoc_ast.py                # Guffin-independent Pandoc AST helpers
│       │   ├── pandoc_server.py             # Persistent pandoc-server for fast Markdown→JSON parses
│       │   ├── pandoc_rendering.py          # Shared model→Pandoc utilities; vertex_tree_to_pandoc();
│       │   │                                #   x-guffin link resolution
│       │   ├── code_language_token.py       # Whitespace-free language token for info strings/classes
│       │   ├── md_rendering.py              # VertexTree → GFM Markdown; writes .mdbundle or plain .md
│       │   ├── md_post_processing.py        # GFM text post-passes (list-separator comment removal)
│       │   ├── pdf_placement.py             # pdf-render policy: supported placements + per-output defaults
│       │   ├── pdf_appendix.py              # The generated back-matter appendix holding appendix-placed PDFs
│       │   ├── pdf_raster.py                # Rasterise PDF pages to PNGs (pypdfium2) for image placements
│       │   ├── pdf_rendering.py             # VertexTree → PDF via Pandoc + Typst
│       │   ├── epub_rendering.py            # VertexTree → EPUB 3 via Pandoc
│       │   ├── epub_semantics.py            # EPUB structural-semantics vocabulary + model→EPUB mappings
│       │   ├── epub_post_processing.py      # EPUB post-passes (matter divisions, colophon, revision)
│       │   ├── rich_rendering.py            # Rich panel/tree rendering for the dump command
│       │   ├── callout_theme.py             # Canonical per-callout-type colour palette (all formats)
│       │   ├── semantic_theme.py            # Canonical bullet/badge glyphs for the classification
│       │   │                                #   overlay (Semantic, SourceChannel) — all formats
│       │   ├── gfm_resources/               # GFM Pandoc Lua filters (package data)
│       │   ├── typst_resources/             # Bergfink Typst template + typst_*.lua filters (package data)
│       │   ├── epub_resources/              # EPUB Lua filters + epub.css (package data)
│       │   └── callout_icons/               # Shared SVG callout badge icons (PDF + EPUB)
│       │
│       └── roam/                          # Roam Research data model, API, and processing
│           ├── primitives.py                # Foundational type aliases, stub models, UID regex
│           ├── better_bullet.py             # Better Bullets extension: marker → bullet vocabulary
│           ├── blockquote.py                # Roam block-quote / callout / pull-quote constructs
│           ├── code_language.py             # Roam's fence-language vocabulary + canonical mapping
│           ├── markdown.py                  # Roam Markdown constructs (image links, PDF embeds, tables)
│           ├── todo.py                      # Roam TODO-item construct: TodoState, parse_todo()
│           ├── schema.py                    # Datomic schema model types
│           ├── node.py                      # RoamNode, NodeType, node_type, NodesByUid
│           ├── node_network.py              # NodeNetwork; network validators and utilities
│           ├── node_tree.py                 # NodeTree (build() factory), NodeTreeDFSIterator, to_table
│           ├── asset.py                     # Firebase Storage asset model
│           ├── local_api.py                 # ApiEndpoint model for the Roam Local API
│           ├── node_fetch_result.py         # NodeFetchAnchor, NodeFetchSpec, NodeFetchResult
│           ├── node_fetch.py                # Fetch RoamNode records via Local API
│           ├── schema_fetch.py              # Fetch Datomic schema via Local API
│           ├── asset_fetch.py               # Fetch Firebase Storage assets via Local API
│           └── revision.py                  # Capture a content Revision from a raw fetch
│
├── tests/                               # pytest test suite; mirrors src/guffin/
│   ├── conftest.py                      # Shared fixtures and helpers
│   ├── regen_fixtures.py                # Developer script: regenerate fixture files from live Roam
│   └── fixtures/                        # markdown/, yaml/, images/, json/, mdbundle/, pdf/, epub/
│
├── scripts/
│   ├── setup-mdbundle-handler.sh        # Setup .mdbundle auto-open in Typora (macOS)
│   └── regen_programming_languages.py   # Regenerate the vendored Linguist language data
│
├── docs/
│   ├── processing_pipeline.md           # High-level overview of the whole pipeline
│   ├── render-pipeline.md               # Render layer (four-phase) + the project-type model
│   ├── publishing-semantics.md          # The PublishingSemantics vocabulary + per-format mapping
│   ├── pdf-render.md                    # The pdf-render placements, format by format
│   ├── server-mode.md                   # Server mode: protocol, API design, and decision log
│   ├── companion-extension-plan.md      # In-Roam companion extension (client of guffin-server)
│   ├── server-packaging-plan.md         # Plan for packaging guffin-server as a desktop app
│   ├── quarto-borrowing-analysis.md     # Design backlog from an examination of Quarto
│   ├── code-source-display-plan.md      # Plan for displaying code-source provenance in Roam
│   ├── roam-local-api.md                # Roam Local API (JSON over HTTP) reference
│   ├── roam-md.md                       # Roam-flavored Markdown vs. CommonMark differences
│   ├── roam-querying.md                 # Datalog query language and all queries used here
│   ├── roam-schema.md                   # Full Roam attribute schema
│   └── MDBUNDLE_SETUP.md                # macOS .mdbundle integration guide
│
├── CLAUDE.md                            # Exhaustive per-module index and project conventions
└── pyproject.toml                       # Project configuration
```

## Usage

The package provides two command-line utilities, plus an HTTP server (`guffin-server`) that serves them both remotely. Every command accepts `--version`, printing the guffin package version and exiting.

### `export-roam-tree` — Export a Roam page or node subtree

Fetches a Roam `Page` or `Node` subtree via the Local API, normalizes it, and writes the result in one of three formats controlled by `--format`. The positional argument is interpreted as a **node UID** when wrapped in `(( ))` or when it matches an anchored UID pattern (a 9-character synthetic UID or an `MM-DD-YYYY` Daily Note UID); otherwise it is treated as a **page title** (any `[[ ]]` wrapper is stripped).

```bash
export-roam-tree <page_title_or_node_uid> --port <port> --graph <graph> --token <token> --output-dir <output_dir> \
  [--format markdown|pdf|epub] [--type article|book|manuscript] [--bundle|--no-bundle] \
  [--cache-dir <dir>] [--template-dir <dir>] [--suppress-attributes] [--colophon|--no-colophon] \
  [--preamble|--no-preamble] [--numbering|--no-numbering] [--element-numbers|--no-element-numbers] \
  [--code-sources|--no-code-sources] [--verify-code-sources|--no-verify-code-sources] \
  [--default-pdf-render <placement>] [--daily-note-format roam-long|iso|abbrev-month-day]
```

The output filename stem embeds the project type: `<target>.<type>.<ext>` (e.g. `Foo.article.epub`, `Foo.book.pdf`), so the same target exported under different types lands in distinct files.

#### Markdown output (default)

By default (`--format markdown`) it creates a `<target>.<type>.mdbundle` directory containing the Github Flavored Markdown (GFM) document and any downloaded Firebase Storage images, PDFs, and bare assets. Pass `--no-bundle` to write a plain `.md` file instead.

```bash
# Bundled (default) — creates ~/docs/Test_Article.article.mdbundle/
export-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token --output-dir ~/docs

# Plain .md — creates ~/docs/Test_Article.article.md
export-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token --output-dir ~/docs --no-bundle

# Export by node UID
export-roam-tree wdMgyBiP9 --port 3333 --graph SCFH --token your-bearer-token --output-dir ~/docs
```

#### PDF output

`--format pdf` builds a Pandoc object model directly from the vertex tree via Panflute, fetches and embeds Firebase Storage images, and produces a PDF via Pandoc + Typst. Requires `typst` on `PATH`. The source PDF asset file is never embedded; where a `{{[[pdf]]: <url>}}` embed's content goes is controlled by its `pdf-render::` tag (a `guffin-meta::` child of the embed block, or of a standalone block reference to it): `inline-native` renders all of the PDF's pages into the document flow (requires Typst ≥ 0.14; the text stays selectable and searchable), `appendix-native` renders them in a generated back-matter appendix linked from the embed, `external-link` links the hosted original, and `name-only` renders the PDF's original filename as plain text. An untagged embed resolves to the output's default placement (overridable via `--default-pdf-render`), and any placement the format cannot honor falls back to `name-only` with a warning — see [docs/pdf-render.md](docs/pdf-render.md) for the full placement × format matrix.

```bash
# Creates ~/docs/Test_Article.article.pdf
export-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token --output-dir ~/docs --format pdf
```

Pass `--template-dir <dir>` (a directory containing a `user_cfg.typ`) to override the bundled Bergfink Typst styling.

#### EPUB output

`--format epub` builds a Pandoc object model directly from the vertex tree via Panflute, fetches and embeds Firebase Storage images, and produces an EPUB 3 e-book via Pandoc. The page title becomes the EPUB `dc:title` and top-level headings become the e-book's chapters. A PDF embed tagged `pdf-render:: appendix-image` has its pages rasterised to PNGs and reproduced in a generated back-matter appendix linked from the embed. Requires `pandoc` on `PATH` (no Typst).

```bash
# Creates ~/docs/Test_Article.article.epub
export-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token --output-dir ~/docs --format epub
```

#### Project types

`--type article|book|manuscript` (default `article`, short `-T`) selects the **project profile** — the kind of work being produced — independently of `--format` (see [docs/render-pipeline.md](docs/render-pipeline.md)). The profile resolves to six structural directives that are applied across the paginated formats:

- **`top_level_division`** — where the work divides. `book` opens each chapter on a new PDF page and splits each chapter into its own EPUB content file, numbering headings hierarchically from level 1. A book whose content tags a level-1 heading `element-type:: part` is auto-promoted to a part/chapter structure.
- **`number_sections`** — whether headings are numbered (book: yes; others: no).
- **`emit_title_page`** — a title page built from the `guffin-meta::` metadata (PDF Bergfink `titlepage`, EPUB `--epub-title-page`); a profile that emits none has the PDF open with the title as an in-flow level-1 heading, and Markdown expresses it as a YAML front-matter block.
- **`emit_toc`** — a navigable table of contents (book default; PDF renders a linked Typst outline, EPUB relies on its always-generated nav document).
- **`drop_preamble`** — whether the export root's loose preamble (children before its first heading) is pruned (book: yes; others: no).
- **`honor_page_breaks`** — whether a heading tagged `page-break:: before` opens on a new page in the paginated formats (article/manuscript: yes; a book's pagination is fixed by its own structure, so a book export drops the tag with a warning).

The `--preamble/--no-preamble` and `--numbering/--no-numbering` flags (PDF/EPUB only) override the profile's `drop_preamble` / `number_sections` decisions for a single export; unset, the `--type` profile decides.

#### Cross-format options

| Option | Short | Formats | Effect |
|---|---|---|---|
| `--bundle/--no-bundle` | | markdown | Bundle images/PDFs into a `.mdbundle` (default) vs. write a plain `.md`. |
| `--template-dir` | | pdf | Directory with a `user_cfg.typ` overriding the Bergfink styling. |
| `--cache-dir` | `-c` | markdown, pdf, epub | Cache downloaded Firebase Storage assets across runs. |
| `--suppress-attributes` | | all | Omit end-user Roam attribute assignments (the rendered pills) from the output. |
| `--colophon/--no-colophon` | | all | Embed a provenance + revision colophon (on by default). |
| `--preamble/--no-preamble` | | pdf, epub | Keep/drop the root's loose preamble; unset defers to the `--type` profile. |
| `--numbering/--no-numbering` | | pdf, epub | Turn heading numbering on/off; unset defers to the `--type` profile. |
| `--element-numbers/--no-element-numbers` | | all | Keep/strip internal element numbers (a heading's `[1.2.3]` lead); stripped by default. |
| `--code-sources/--no-code-sources` | | all | Render/omit each sourced code block's GitHub attribution line (from its `code-source::` tag); omitted by default. |
| `--verify-code-sources/--no-verify-code-sources` | | all | Verify every `code-source::`-tagged code block against GitHub (**on by default**); any drift, local modification, or fetch failure aborts the export with exit 1. `--no-verify-code-sources` is the offline escape hatch. |
| `--default-pdf-render` | | all | Placement an *untagged* PDF embed resolves to (e.g. `external-link`), overriding the built-in format/type default; an embed's own `pdf-render::` tag still wins. |
| `--daily-note-format` | | all | How a daily-note-page reference renders its date: `roam-long` (default), `iso`, `abbrev-month-day`. |

The `--colophon` provenance records the guffin package version, the source git commit (hash + commit time, marked `-dirty` for uncommitted changes), and the export time, plus the content revision (snapshot hash, edit/fetch times, and any authored `revision::` name), so any generated document can be traced back to the exact source and content snapshot that produced it. Placement differs by format: PDF renders it at the foot of the title page (or below the page footer when no title page is emitted); EPUB mirrors that; Markdown carries it as an end-of-document block.

#### Environment variables

The connection and path options, and every long-form toggle, can be supplied via environment variables (`--format`, `--type`, and `--bundle/--no-bundle` are not env-backed and must be passed on the command line):

```bash
export GUFFIN_ROAM_LOCAL_API_PORT=3333
export GUFFIN_ROAM_GRAPH_NAME=SCFH
export GUFFIN_ROAM_API_TOKEN=<your-bearer-token>
export GUFFIN_EXPORT_DIR=~/docs
export GUFFIN_CACHE_DIR=~/.cache/roam        # optional: skip re-downloading unchanged assets
export GUFFIN_PDF_TEMPLATE_DIR=~/mytheme     # optional: user_cfg.typ override for --format pdf
export GUFFIN_EMIT_COLOPHON=0                # optional: omit the colophon (backs --no-colophon)
export GUFFIN_INCLUDE_PREAMBLE=false         # optional: backs --preamble/--no-preamble (pdf/epub)
export GUFFIN_NUMBER_SECTIONS=false          # optional: backs --numbering/--no-numbering (pdf/epub)
export GUFFIN_ELEMENT_NUMBERS=1              # optional: backs --element-numbers (keep the [1.2.3] leads)
export GUFFIN_CODE_SOURCES=1                 # optional: backs --code-sources (render GitHub attribution lines)
export GUFFIN_VERIFY_CODE_SOURCES=0          # optional: backs --no-verify-code-sources (the offline path)
export GUFFIN_GITHUB_TOKEN=<token>           # optional: raises the GitHub API rate limit for verification
export GUFFIN_DAILY_NOTE_FORMAT=iso          # optional: backs --daily-note-format
export GUFFIN_DEFAULT_PDF_RENDER=external-link  # optional: backs --default-pdf-render (untagged PDF embeds)
export GUFFIN_DUMP_PANDOC_AST=1              # optional: dump the Pandoc JSON AST before conversion (debug)
export GUFFIN_DUMP_TYPST=1                   # optional: dump intermediate Typst sources (--format pdf, debug)

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
  [--render-bundle] [--node-tree] [--raw-results] [--include-refs] [--truncate] [--show-transient] \
  [--verify-code-sources|--no-verify-code-sources] \
  [--node-props <props>] [--vertex-props <props>] [--cache-dir <dir>]
```

Flags (all are boolean toggles with a `--no-*` / uppercase-letter inverse):

| Flag | Short | Default | Effect |
|---|---|---|---|
| `--render-bundle` | `-b/-B` | **on** | Render the render bundle: the normalized vertex tree and its view map |
| `--node-tree` | `-n/-N` | off | Render the raw node tree |
| `--raw-results` | `-r/-R` | off | Print the raw Datalog query results |
| `--include-refs` | `-i/-I` | **on** | Also fetch nodes referenced via `:block/refs` and their descendants |
| `--truncate` | | **on** | Shorten long string values with an ellipsis; `--no-truncate` shows them in full |
| `--show-transient` | | off | In the raw-results table, also show the transient session/UI attribute columns (hidden by default) |
| `--verify-code-sources` | | **on** | Verify `code-source::`-tagged code blocks against GitHub; findings are advisory warnings here (the dump always renders), unlike export's abort. `--no-verify-code-sources` skips the network check |

The `--render-bundle` output is an outer **Render Bundle** panel wrapping two sub-panels: a **Vertex Tree** (the content `VertexTree`) followed by a **View Map** (the presentation `ViewMap`). The view-map tree always shows the root and, below it, only the vertices that carry a view entry plus the ancestors needed to connect them to the root; each panel is titled like its vertex-tree counterpart and its body lists the vertex's `VertexView` fields.

`--node-props heading,parents` selects which `RoamNode` fields appear for each node in the node-tree output (defaults to `heading,order,children,parents,page`).

`--vertex-props type,children,text` selects which `Vertex` fields appear for each vertex in the vertex-tree output (defaults to `vertex_type.value,children,refs`).

`--cache-dir <dir>` / `-c` (env `GUFFIN_CACHE_DIR`) caches downloaded Firebase Storage assets across runs. Rendering the render bundle fetches every displayed asset to read each image's native pixel size and each PDF's original filename; without a cache directory, every run re-downloads them.

Examples:
```bash
# Default: render bundle (vertex tree + view map) + refs included
dump-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token

# Node tree + render bundle, with custom node props
dump-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token --node-tree --render-bundle --node-props heading,parents

# Raw Datalog results only, no render bundle, no refs
dump-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token --raw-results --no-render-bundle --no-include-refs

# Fetch by node UID
dump-roam-tree wdMgyBiP9 --port 3333 --graph SCFH --token your-bearer-token
```

### `guffin-server` — Serve the commands over HTTP

Serves `export-roam-tree` and `dump-roam-tree` as HTTP command endpoints for remote, RPC-like invocation (design and decision log: [docs/server-mode.md](docs/server-mode.md)). The server must run on the machine running the Roam Desktop app — the Roam Local API answers only there — and binds `127.0.0.1:8077` by default (`--host` / `--port` `-p`, env `GUFFIN_SERVER_HOST` / `GUFFIN_SERVER_PORT`).

The repeatable `--allow-origin <origin>` (env `GUFFIN_SERVER_ALLOW_ORIGIN`, space-separated; default none) admits browser pages at the named web origins via CORS — e.g. `--allow-origin https://roamresearch.com` lets an in-Roam extension call the server. It is read-side admission only, never authentication; without it the server sends no CORS headers at all (non-browser clients are unaffected either way).

```bash
guffin-server                                            # http://127.0.0.1:8077
guffin-server --allow-origin https://roamresearch.com    # admit an in-Roam browser client via CORS
guffin-server --host 0.0.0.0 -p 9000                     # expose beyond the host — see the security note below
```

| Endpoint | Invokes | Success body |
|---|---|---|
| `POST /v1/export` | `export-roam-tree` | the exported document (binary, streamed); a `.mdbundle` answers as a zip archive |
| `POST /v1/dump` | `dump-roam-tree` | the captured console rendering: plain text (default), HTML, or SVG |
| `GET /v1/health` | — | liveness, package version, and serving-code provenance |

The JSON Request's fields are the command's own parameter names and types — each request model is derived from the CLI signature at import time, so the two vocabularies cannot drift. Every field except `target` is optional: an omitted field defers to the command's own default, including its `GUFFIN_*` env-var fallback resolved in the *server's* environment, so a server whose environment carries the Roam connection settings needs only a `target`. The deliberate divergences from the CLI: `output_dir` is absent (the server exports into a per-request temporary directory and deletes it after the response), the CLI-only `--version` flag is absent from both vocabularies (the health endpoint reports the server's version), and the dump request adds `console_format` (`text`/`html`/`svg`), `console_width`, and `ansi`.

```bash
# Export a book-profile EPUB; -OJ saves it under the Content-Disposition name (Test_Article.book.epub)
curl -fsS -OJ http://127.0.0.1:8077/v1/export \
  -H "Content-Type: application/json" \
  -d '{"target": "Test Article", "output_format": "epub", "project_type": "book"}'

# Dump as a standalone HTML rendering, 100 columns wide
curl -fsS http://127.0.0.1:8077/v1/dump \
  -H "Content-Type: application/json" \
  -d '{"target": "Test Article", "console_format": "html", "console_width": 100}' > dump.html
```

A success response streams the document with `Content-Length`, an RFC 9530 `Content-Digest` (`sha-256`) for end-to-end integrity verification, and a `Content-Disposition` download name — and it begins only after the invocation has fully completed, so the status code is always authoritative. Failures answer `application/problem+json` (RFC 9457): `400` for a malformed or invalid Request, `422` when the invocation itself failed — its `detail` carries the complete captured error text (log records, stderr, any traceback) — and `500` for a serving-layer fault. Invocations execute one at a time, and a render can take minutes, so give the client a generous read timeout.

**Security**: the default bind serves the local host only, and the Roam bearer token rides in request bodies — expose the server beyond the host only over a trusted path (an SSH tunnel, a tailnet, or TLS terminated in front of it).

### macOS Integration: Auto-Open in Typora

To configure macOS to automatically open `.mdbundle` folders in Typora when double-clicked:

1. **Run the setup script:**
   ```bash
   ./scripts/setup-mdbundle-handler.sh
   ```

   This creates and registers `OpenMDBundle.app` which handles `.mdbundle` folders.

2. **Done!** Double-clicking any `.mdbundle` folder will now open the markdown file in Typora

See [docs/MDBUNDLE_SETUP.md](docs/MDBUNDLE_SETUP.md) for detailed instructions and troubleshooting.

## Documentation

- [docs/processing_pipeline.md](docs/processing_pipeline.md) — High-level overview of the whole pipeline (fetch → transcribe → render) as a directional flow across sub-packages
- [docs/render-pipeline.md](docs/render-pipeline.md) — The render layer (model → output four-phase pipeline: prepare → build → convert → post-process) and the project-type model (`ProjectType`/`ProjectProfile`/`StructuralPolicy`)
- [docs/publishing-semantics.md](docs/publishing-semantics.md) — The format-independent `PublishingSemantics` vocabulary and how it maps to each output format (companion to `render-pipeline.md`)
- [docs/pdf-render.md](docs/pdf-render.md) — What each `pdf-render` placement renders in each output format, and whether the PDF file travels with the output
- [docs/server-mode.md](docs/server-mode.md) — Server mode: the ratified HTTP command-endpoint protocol, API design, in-process invocation design, and decision log (Phase 1 implemented)
- [docs/quarto-borrowing-analysis.md](docs/quarto-borrowing-analysis.md) — Design backlog from an examination of Quarto: concepts worth borrowing, and what was deliberately not borrowed
- [docs/roam-local-api.md](docs/roam-local-api.md) — Roam Local API reference (JSON over HTTP)
- [docs/roam-md.md](docs/roam-md.md) — Roam-flavored Markdown vs. CommonMark differences
- [docs/roam-querying.md](docs/roam-querying.md) — Datalog query language, query structure, and all queries used in this project
- [docs/roam-schema.md](docs/roam-schema.md) — Full Roam attribute schema (kept in sync with the `SchemaAttribute` enum)
- [docs/MDBUNDLE_SETUP.md](docs/MDBUNDLE_SETUP.md) — macOS `.mdbundle` integration guide
- [CLAUDE.md](CLAUDE.md) — Exhaustive per-module index, sub-package dependency rules, and coding conventions

## License

[MIT](LICENSE)
