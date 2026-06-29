# CLAUDE.md

## Project Overview
Python 3.14 toolkit for exporting Roam Research pages to self-contained
documents.  Supports two output formats:

- **Markdown** — renders to GFM and optionally bundles Cloud
  Firestore-hosted images into a self-contained `.mdbundle` directory.
- **PDF** — builds a Pandoc object model directly from the `VertexTree`
  via Panflute, fetches and embeds Cloud Firestore images, and produces a
  PDF via Pandoc + Typst.

## Setup
```bash
source .venv/bin/activate
pip install -e ".[dev]"
```

## Key Commands
```bash
dump-roam-tree <page_title_or_node_uid> -p <port> -g <graph> -t <token> [-v/-V] [-n/-N] [-r/-R] [--node-props <props>]
export-roam-tree <page_title_or_node_uid> -p <port> -g <graph> -t <token> -o <output_dir> [--format markdown|pdf|epub] [--type default|book|manuscript] [--bundle|--no-bundle] [--cache-dir <dir>] [--template-dir <dir>] [--suppress-attributes]
# output filename stem embeds the project type: <target>.<type>.<ext> (e.g. Foo.default.epub, Foo.book.pdf)
# --format markdown (default): writes <target>.<type>.mdbundle/ (--bundle) or <target>.<type>.md (--no-bundle)
# --format pdf: writes <target>.<type>.pdf via Pandoc + Typst; requires typst on PATH
# --format epub: writes <target>.<type>.epub (EPUB 3) via Pandoc; requires pandoc on PATH (no typst)
# --type (-T): project profile (default/book/manuscript); appended to the output filename stem; plumbed to all renderers (applied so far: EPUB split-level from top_level_division, and number_sections in both EPUB and PDF; remaining structural/metadata effects not yet applied)
# --template-dir: directory containing user_cfg.typ overrides for PDF styling (pdf only)

# Run the full check pipeline (format + lint + type check + tests) in one shot:
hatch run check

# Individual steps (run in this order):
pydocstringformatter --write src/ # reflow docstring content (PEP 257)
black .                           # format code
ruff check --fix src/ tests/      # lint + fix docstring style (Google convention)
pyright                           # type check (strict)
pytest                            # run tests (excludes live tests)

# Live tests — NOT part of the check pipeline; must be explicitly requested:
GUFFIN_LIVE_TESTS=1 pytest -m live -v  # requires Roam Desktop running locally
```

## Project Structure
- `src/guffin/` — main package
  - **`cli/` sub-package** (`src/guffin/cli/`) — CLI entry points and supporting infrastructure
    - `dump_roam_tree.py` — dumps a Roam page or node subtree as a Rich tree to the terminal; supports `--vertex-tree`/`--node-tree`/`--raw-results` flags (`dump-roam-tree`)
    - `export_roam_tree.py` — exports a Roam page or node subtree; `--format markdown` (default) writes a `.mdbundle` or plain `.md`; `--format pdf` writes a PDF via Panflute + Pandoc + Typst; `--format epub` writes an EPUB 3 e-book via Panflute + Pandoc; target is a page title or node UID (`export-roam-tree`)
    - `logging_config.py` — colorized logging (`configure_logging()`); reads `LOG_LEVEL` env var
    - `common.py` — tree-loading pipeline for CLI commands; `fetch_roam_trees` resolves a target, fetches nodes, and returns a `(NodeFetchResult, VertexTree | None)` pair
  - **`model/` sub-package** (`src/guffin/model/`) — core normalized-graph model: UID primitives, vertex types, tree, presentation overlay, render bundle, and inter-vertex links
    - `primitives.py` — foundational UID primitives for the model: `Uid`, `SYNTHETIC_UID_PATTERN`/`DAILY_NOTE_UID_PATTERN`/`UID_PATTERN`/`UID_RE`, `ANCHORED_UID_PATTERN`/`ANCHORED_UID_RE`, `is_daily_note_uid()` (dependency root)
    - `vertex.py` — `Vertex` union and all ten concrete vertex types (`PageVertex`, `HeadingVertex`, `TextVertex`, `ImageVertex`, `CalloutVertex`, `CodeBlockVertex`, `BlockQuoteVertex`, `TableVertex`, `BlockEmbedVertex`, `AttributeAssignmentVertex`); `VertexType`, `VertexChildren`, `VertexRefs`, `vertex_adapter`
    - `vertex_tree.py` — `VertexTree`, `VertexTreeDFSIterator`, `root_vertex()`; filter helpers `page_vertices()`, `heading_vertices()`, `text_vertices()`, `image_vertices()`, `image_urls()`; transformers `map_vertices()`, `enrich_image_original_sizes()`
    - `view.py` — presentation overlay kept decoupled from content: `ChildrenLayout` StrEnum (bullet/document/numbered), `DEFAULT_CHILDREN_LAYOUT`, `VertexView`, `ViewMap` (sparse `{uid: VertexView}`)
    - `render_bundle.py` — `RenderBundle`: a `VertexTree` (content) paired with its `ViewMap` (presentation), held as separate fields so they travel together while staying decoupled
    - `link.py` — custom `x-guffin` URL scheme for inter-vertex links; `VertexLinkKind`, `VertexLink`, `vertex_link_url()`, `parse_vertex_link()`, `is_vertex_link()`
    - `attribute.py` — normalized model of a Roam attribute assignment (`<attribute>:: <value>, …`): `Attribute` (the named page, carrying a `VertexLink`), the `AttributeValue` discriminated union (`LiteralValue` | `ReferenceValue`, with `AttributeValueKind` and `attribute_value_adapter`), and `AttributeAssignment` pairing an attribute with its ordered values
  - **`transcribe/` sub-package** (`src/guffin/transcribe/`) — the source→model bridge: source-to-model transcription and text normalization (shared by every use — export, dump, future interchange)
    - `roam_md_to_pandoc_md.py` — converts Roam-flavored Markdown strings to Pandoc Markdown; `to_pandoc_md()` is the main entry point
    - `roam_tree_to_guffin.py` — transcribes a `NodeTree` into the guffin render model: `transcribe()` derives the `VertexTree` content (applying `to_pandoc_md()` to all text fields), `build_view_map()` derives the presentation `ViewMap`, and `to_render_bundle()` bundles both into a `RenderBundle`
  - **`render/` sub-package** (`src/guffin/render/`) — output rendering: turns the normalized model into consumable output (document export and terminal display) plus the configuration and bundled resources that drive it
    - `render_options.py` — immutable export settings carried from a front end to a rendering entry point: `OutputFormat` (markdown/pdf/epub enum discriminator), `RenderOptions` (format-independent base: `output_dir`, `cache_dir`, `suppress_attributes`, `dump_pandoc_ast`), and the per-format subclasses `MarkdownRenderOptions` (`bundle`), `PdfRenderOptions` (`template_dir`), and `EpubRenderOptions` (no extra fields yet)
    - `project.py` — the *kind* of work being rendered, modeled on Quarto's `project: type:` (concept only — no Quarto artifacts): `ProjectType` (default/book/manuscript discriminator), `TopLevelDivision` (section/chapter/part), the `ProjectProfile` base + per-type subclasses `DefaultProfile`/`BookProfile`/`ManuscriptProfile`, `StructuralPolicy` (format-independent structural directives a profile resolves to), and `profile_for()` (maps a `ProjectType` to its default-valued profile). Orthogonal to `OutputFormat`; a `profile: ProjectProfile` is plumbed into every render entry point (via the CLI `--type` flag). Two structural effects are applied — EPUB derives `--split-level` from `top_level_division`, and both EPUB and PDF honour `number_sections` — but the remaining structural effects (PDF chapters vs. sections, title page) and all metadata effects are not yet applied to output
    - `image_fetch.py` — Pandoc-free image-asset fetching; `ImageRef` (UID + on-disk path + `ImageSize`) and `fetch_images()` (fetches a `VertexTree`'s Cloud Firestore image assets to a local dir, returning `{uid: ImageRef}`)
    - `pandoc_rendering.py` — shared Pandoc/Panflute rendering utilities; `vertex_tree_to_pandoc()` builds a Panflute `Doc` from a `VertexTree` (batch-parsing inline Pandoc Markdown via a single Pandoc call)
    - `md_rendering.py` — renders a `VertexTree` to Markdown: invokes `pandoc_rendering`, serializes to Pandoc JSON, converts to GFM via Pandoc, writes a plain `.md` or `.mdbundle/` directory
    - `pdf_rendering.py` — renders a `VertexTree` to PDF: invokes `pandoc_rendering`, serializes to Pandoc JSON, converts to PDF via Pandoc + Typst
    - `epub_rendering.py` — renders a `VertexTree` to EPUB 3: invokes `pandoc_rendering`, serializes to Pandoc JSON, converts to EPUB via Pandoc (page title → `dc:title`, top-level headings → chapters, images embedded into the package)
    - `rich_rendering.py` — Rich panel/tree rendering for `NodeTree` and `VertexTree` (the terminal-display renderer used by `dump-roam-tree`)
    - `typst_resources/` — bundled package data for PDF output (consumed only by `pdf_rendering.py`): the Bergfink Typst/Pandoc template (`user_cfg.typ` is the intended customization point; see `src/guffin/render/typst_resources/README.md`) plus the `typst_*.lua` Pandoc filters
    - `gfm_resources/` — bundled package data for Markdown output (consumed only by `md_rendering.py`): the `gfm_*.lua` Pandoc filters (callout, color-span, image, mark; see `src/guffin/render/gfm_resources/README.md`)
    - `epub_resources/` — bundled package data for EPUB output (consumed only by `epub_rendering.py`): the `epub_*.lua` Pandoc filters (callout, color-span, mark, number-lines) emitting inline-styled XHTML, plus `epub.css` (the default stylesheet applied via `--css`; the font-family customization point); see `src/guffin/render/epub_resources/README.md`
    - `callout_icons/` — bundled SVG badge icons (`info.svg`, `memo.svg`, …), one per gentle-clues callout function, **shared** by PDF and EPUB output so both render an identical callout icon set; inlined by `typst_callout.lua` (into the gentle-clues `icon:`) and `epub_callout.lua` (into the callout title header), located via the `GUFFIN_CALLOUT_ICONS_DIR` env var set by the renderer; see `src/guffin/render/callout_icons/README.md`
  - **`common/` sub-package** (`src/guffin/common/`) — cross-cutting helpers shared across the package
    - `code_language.py` — `CodeLanguage` StrEnum of programming-language identifiers for fenced code block info strings
    - `filenames.py` — `shell_safe_filename()` normalizes strings to POSIX-safe filenames
    - `geometry.py` — `ImageSize` Pydantic model for pixel dimensions (width × height) of a 2-D image
    - `markdown.py` — CommonMark fenced code block utilities: `is_fenced_code_block()`, `FencedCodeBlock` NamedTuple, `parse_fenced_code_block()`
    - `media_type.py` — `MediaType` enum; MIME type detection from file names
    - `validation.py` — generic accumulator-pipeline validation framework
  - **`roam/` sub-package** (`src/guffin/roam/`) — all Roam Research data model, API, and processing modules
    - `primitives.py` — foundational type aliases, stub models, `UID_PATTERN`/`UID_RE`, `ANCHORED_UID_PATTERN`/`ANCHORED_UID_RE` (dependency root)
    - `markdown.py` — Roam Markdown constructs: `CALLOUT_RE`, `CalloutType`, `RoamCallout`, `parse_callout`, `IMAGE_LINK_RE`, block-quote helpers (`is_roam_block_quote`, `strip_block_quote_marker`), `ROAM_NATIVE_TABLE_MARKER`
    - `schema.py` — Datomic schema model types (`RoamNamespace`, etc.)
    - `node.py` — `RoamNode`, `NodeType`, `node_type`, `NodesByUid`
    - `node_network.py` — `NodeNetwork` type alias; network validators (`all_children_present`, `all_parents_present`, `has_unique_ids`, `is_acyclic`) and utilities (`all_descendants`, `refs_ids`)
    - `node_tree.py` — `NodeTree` (factory `build()`, fields `root_node`/`tree_network`/`refs_by_id`), `NodeTreeDFSIterator`, `is_tree`, `to_table` (reconstructs a raw-cell `common.Table` from a native-table `NodeTree`)
    - `asset.py` — Cloud Firestore asset model
    - `local_api.py` — `ApiEndpoint` model for the Roam Local API
    - `node_fetch_result.py` — `NodeFetchAnchor`, `NodeFetchSpec`, `NodeFetchResult`; fetch result model and factory methods (`from_raw`, `from_network`); `anchor_node` helper
    - `node_fetch.py` — fetches `RoamNode` records via Local API; `fetch_roam_nodes` dispatches on page title vs. node UID
    - `schema_fetch.py` — fetches Datomic schema via Local API
    - `asset_fetch.py` — fetches Firestore assets via Local API
- `scripts/` — shell wrapper scripts (`dump-roam-tree.sh`, `export-roam-tree.sh`)
- `tests/fixtures/` — sample markdown, images, JSON, YAML, PDF for tests
- `tests/regen_fixtures.py` — developer script; regenerates all six fixture files for a given Roam page title or node UID (see **Test Fixtures** below)

## Test Fixtures

Four live Roam pages serve as the primary test sources: `[[Test Article]] 0`,
`[[Test Article]] 1`, `[[Test Article]] 2`, and `[[Test Article]] 3`.  For each source, `tests/regen_fixtures.py` generates six
fixture files that capture different stages and views of the data pipeline.

### No-refs fixture set (`include_refs=False`) — a linear pipeline

Three fixtures representing successive stages of the export pipeline applied to
the anchor subtree alone, with no referenced pages included:

| Fixture | What it captures |
|---|---|
| `<prefix>_nodes.yaml` | The Roam nodes (page + blocks) as parsed `RoamNode` model objects |
| `<prefix>_vertices.yaml` | The same subtree transcribed into the export model (`VertexTree`) |
| `<prefix>_expected.md` | The fully rendered GFM output |

### With-refs fixture set (`include_refs=True`) — three views of the same fetch

Three fixtures derived from a single API call that pulls the anchor subtree
together with every page and block it references.  Rather than a pipeline, they
are three different lenses on the same underlying data:

| Fixture | What it captures |
|---|---|
| `<prefix>_raw_result.yaml` | The raw Datalog wire response before any `RoamNode` parsing |
| `<prefix>_anchor_tree.yaml` | The `NodeTree` of the anchor subtree itself (within the broader refs fetch) |
| `<prefix>_nodes_by_uid.yaml` | All fetched nodes — anchor subtree plus every referenced page/block — keyed by UID |

To regenerate fixtures from the live Roam graph (requires Roam Desktop running):
```bash
python tests/regen_fixtures.py "[[Test Article]] 0" --prefix test_article_0
python tests/regen_fixtures.py "[[Test Article]] 1" --prefix test_article_1
python tests/regen_fixtures.py "[[Test Article]] 2" --prefix test_article_2
python tests/regen_fixtures.py "[[Test Article]] 3" --prefix test_article_3
```

Pass `--pdf` to additionally record a byte-reproducible baseline PDF under `tests/fixtures/pdf/`
(requires Typst on PATH) for the live PDF export test — e.g.
`python tests/regen_fixtures.py "[[Test Article]] 1" --prefix test_article_1 --pdf`.

## Git
- **Never commit or push without explicit instructions**: do not run `git commit` or `git push` unless the user explicitly asks. This applies even after completing a task — finish the work, then wait for the user to request a commit/push.

## Conventions
- Src layout: package lives under `src/guffin/`
- Line length: 120 chars (Black + Ruff)
- Docstrings: PEP 257 format (pydocstringformatter), Google style convention (Ruff)
- **Dependent-agnostic documentation**: a module, class, or function must document what it offers on its own terms — never how its dependents (importers/callers) consume it. Don't name downstream modules or describe their usage in upstream docstrings or comments (e.g. avoid "X and Y delegate their logic here" or "shared by Z"); describe behaviour through the API's own parameters and contract, so the documentation reads identically regardless of who depends on it.
- **`Public symbols:` docstring is a by-kind index**: the module-docstring `Public symbols:` block is a *categorized index* of the module's public API, grouped by kind (pattern constants → type aliases → enums → models/classes → functions), with related symbols kept contiguous within a group. It is **independent of definition order** — the body's order follows define-before-use and feature cohesion (e.g. a discriminated-union alias must be defined after its members, a Typer `app` before the `main` it decorates), so the index and the body deliberately need not match. Keep the index grouping coherent; do not reorder code to track it.
- **Tests**: pytest, files named `test_*.py`. The `tests/` tree mirrors `src/guffin/`:
  each test module lives in the subpackage of the module it covers
  (`tests/<package>/test_<module>.py`, e.g. `tests/roam/test_markdown.py` for
  `guffin/roam/markdown.py`, `tests/common/test_markdown.py` for `guffin/common/markdown.py`).
  pytest runs in `importlib` import mode (`addopts = "--import-mode=importlib"`), so test
  files need no `__init__.py` and basenames may repeat across packages. `tests/conftest.py`
  and `tests/regen_fixtures.py` stay at the `tests/` root; shared non-fixture helpers are
  imported via `from conftest import ...` (`tests/` is on `pythonpath`).
- **Strong typing**: all Python code must use type annotations throughout; no `Any` types; enforced by pyright in strict mode
- **Regular expressions**: use the third-party `regex` package **exclusively** — never the stdlib `re` module. Import as `import regex` and use `regex.compile`, `regex.Pattern[str]`, `regex.Match[str]`, `regex.DOTALL`, etc. `regex` is a drop-in superset of `re` (it defaults to `re`-compatible behaviour) and additionally supports recursive patterns (e.g. `(?R)` for matching balanced, nestable Roam page references). `types-regex` (a dev dependency) provides the stubs required by pyright strict mode.
- **Bash tool calls**: never chain multiple commands with `&&` in a single Bash tool call; use separate Bash tool calls instead. Never use heredoc embeds (`$(cat <<'EOF'...EOF)`) or ANSI-C quoting (`$'...'`) in Bash tool calls; both embed literal newlines in the command string, which prevents permission-pattern matching. For `git commit` messages that need multiple paragraphs, use repeated `-m` flags instead: `git commit -m "subject" -m "body" -m "Co-Authored-By: ..."` — each `-m` becomes a blank-line-separated paragraph.
- **Logging format**: all `logger.*()` calls must use `%`-style format strings (e.g., `logger.info("x=%s", x)`) — never f-strings (e.g., `logger.info(f"x={x}")`); this enables lazy interpolation and better log aggregation in monitoring tools.
- **`@validate_call`**: decorate every public function and method (non-`_`-prefixed, non-dunder) with `@validate_call`. Exceptions: `@property` methods (technically incompatible), Pydantic model lifecycle methods (`model_*`, field validators, `__init__`), CLI entry-point functions wired by argparse, methods overriding non-Pydantic framework interfaces, generic functions whose type variables cannot be resolved at runtime, and classmethods/staticmethods whose return-type annotation references the class being defined (pydantic eagerly evaluates type hints at decoration time, before the class is added to module globals, causing a `NameError`). For `@staticmethod` and `@classmethod` methods that qualify, `@validate_call` is placed innermost — just above `def`, below the `@staticmethod`/`@classmethod` line. When a function has panflute (or other arbitrary-type) parameters, use `@validate_call(config=ConfigDict(arbitrary_types_allowed=True))` instead of plain `@validate_call`.
- **Immutable bindings**: all local variables and module-level constants must be annotated `Final[T]` by default (e.g., `x: Final[int] = 1`, `MY_CONST: Final[str] = "value"`); only omit `Final` when the binding genuinely needs to be reassigned. Inside Pydantic models, use `ClassVar[T]` for class-level constants (Pydantic excludes these from model fields).
- **Parameter names**: function and method parameter names must be at least 3 characters long; single- and two-character names (e.g. `s`, `fn`, `cb`) are not allowed.

## Architecture
- **CLI isolation**: only modules in the `cli/` sub-package may import or use the Typer package (the entry points `export_roam_tree.py` / `dump_roam_tree.py` and CLI-only support modules such as `cli/params.py`). All modules outside `cli/` must be front-end agnostic so they can be used outside a CLI context without pulling in CLI dependencies. Within `cli/`, keep Typer out of modules that have a non-CLI reason to stay framework-free (e.g. `cli/common.py`, whose helpers are unit-tested directly).
- **Exit-point isolation**: all explicit process-exit calls (`typer.Exit`, `sys.exit`, etc.) must live exclusively in the CLI modules. Library code propagates exceptions; CLIs decide whether and how to exit. This keeps control-flow transparent and makes library code testable without mocking exit behaviour.

### Sub-package dependency rules

| Package | May depend on | May NOT depend on |
|---|---|---|
| `common/` | stdlib, third-party only | any `guffin` package |
| `roam/` | `common/` | `guffin` root modules, `model/`, `transcribe/`, `render/`, `cli/` |
| `model/` | `common/` | `guffin` root modules, `roam/`, `transcribe/`, `render/`, `cli/` |
| `guffin` (root modules) | `roam/`, `common/`, `model/` | `transcribe/`, `render/`, `cli/` |
| `transcribe/` | `common/`, `roam/`, `model/`, `guffin` root modules | `render/`, `cli/` |
| `render/` | `common/`, `roam/`, `model/`, `guffin` root modules | `transcribe/`, `cli/` |
| `cli/` | `common/`, `roam/`, `model/`, `guffin` root modules, `transcribe/`, `render/` | — |

No package may take a dependency on `cli/`.

## Modern Python Requirements (Python 3.14)
All code written or modified by Claude MUST follow these conventions — no exceptions:

- **Built-in generics**: always `list[x]`, `tuple[x, y]`, `dict[k, v]`, `set[x]` — never `List`, `Tuple`, `Dict`, `Set` from `typing`
- **Union syntax**: always `X | Y` and `X | None` — never `Union[X, Y]` or `Optional[X]`
- **Type aliases**: always `type Foo = ...` (PEP 695) — never `Foo: TypeAlias = ...` or bare `Foo = ...`. Exception: a shared **Typer parameter alias** (`Name = Annotated[T, typer.Option(...)]` / `typer.Argument(...)` reused across CLI commands, e.g. in `cli/params.py`) must use a plain assignment, because Typer reads the embedded `Option`/`Argument` metadata off the annotation object and cannot resolve it through a PEP 695 `TypeAliasType` (it raises `RuntimeError: Type not yet supported`).
- **No `from __future__ import annotations`**: not needed in Python 3.14 (PEP 649 deferred evaluation is the default)
- **No string-quoted forward references**: never `"ClassName"` in annotations; if a forward reference is needed, reorder definitions so the referenced name is declared first
- **No `cast()`**: never use `typing.cast()`; fix the type properly instead
- **No `Any`**: never use `typing.Any`; use a precise type or a type variable
- **Enum mixin subclasses**: always use the dedicated single-inheritance mixin — never mix a built-in type with `Enum`/`Flag` directly (Ruff `UP042`):
  - `class Foo(str, Enum)` → `class Foo(enum.StrEnum)`
  - `class Foo(int, Enum)` → `class Foo(enum.IntEnum)`
  - `class Foo(int, Flag)` → `class Foo(enum.IntFlag)`

## Reference Docs
- `docs/roam-md.md` — Roam flavored Markdown vs. CommonMark differences (relevant to normalization work)
- `docs/roam-local-api.md` — Roam Local API reference (endpoints, request/response shapes)
- `docs/roam-querying.md` — Datalog query patterns used to fetch Roam nodes
- `docs/roam-schema.md` — Roam Datomic schema reference (attributes, value types, cardinality)
- `docs/processing_pipeline.md` — high-level overview of the whole pipeline (fetch → transcribe → render) as a directional flow across sub-packages; the render stage is detailed in `render-pipeline.md`
- `docs/render-pipeline.md` — the render layer (model → output two-stage pipeline) and the project-type model (`ProjectType`/`ProjectProfile`/`StructuralPolicy`); where the profile is consumed and why it is separate from `RenderOptions`

## Environment Variables
- `GUFFIN_ROAM_LOCAL_API_PORT` — port for Roam Local API (all CLI tools)
- `GUFFIN_ROAM_GRAPH_NAME` — Roam graph name (all CLI tools)
- `GUFFIN_ROAM_API_TOKEN` — bearer token for auth (all CLI tools)
- `GUFFIN_EXPORT_DIR` — output directory for `export-roam-tree`
- `GUFFIN_CACHE_DIR` — directory for caching downloaded Cloud Firestore assets (`export-roam-tree`)
- `GUFFIN_PDF_TEMPLATE_DIR` — directory containing a `user_cfg.typ` override for PDF styling (`export-roam-tree --format pdf`)
- `GUFFIN_DUMP_PANDOC_AST` — set to any non-empty value to dump the Pandoc JSON AST to `<output-dir>/<target>.pandoc.json` before the Pandoc conversion step (`export-roam-tree`, all formats)
- `GUFFIN_DUMP_TYPST` — set to any non-empty value to dump the intermediate Typst sources `<output-dir>/<target>.body.typ` (bare body) and `<output-dir>/<target>.full.typ` (with template applied) for debugging (`export-roam-tree --format pdf`); no effect on the produced PDF
- `GUFFIN_PDF_CREATION_TIMESTAMP` — UNIX timestamp passed to Typst via Pandoc `--pdf-engine-opt=--creation-timestamp` to pin the PDF creation date for byte-reproducible output (`export-roam-tree --format pdf`); used by the live PDF fixture test
- `GUFFIN_LIVE_TESTS` — set to any non-empty value to enable live tests (e.g. `GUFFIN_LIVE_TESTS=1`); requires Roam Desktop running locally
