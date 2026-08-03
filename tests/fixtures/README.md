# Test Fixtures

This directory contains test data used by the guffin test suite.

## Directory Structure

- `images/` — Test images referenced by live integration tests
- `json/` — Raw Roam Local API response payloads used by unit tests
- `markdown/` — Expected GFM output files and supporting assets
- `yaml/` — Serialized `RoamNode` and `Vertex` trees used by unit tests

## Files

### images/
- `flower.jpeg` — JPEG fixture used in `TestFetchRoamAssetFetch::test_live`
- `test_article_1.png` — Screenshot of the `[[Test Article]] 1` page in Roam (reference only)
- `test_article_2.png` — Screenshot of the `[[Test Article]] 2` page in Roam (reference only)

### json/
- `image_node.json` — Raw Roam node payload for a Firebase Storage image block; used in `TestTranscribeNode::test_transcribes_image_node_from_fixture`

### markdown/
- `descendant_rule.md` — CSS descendant-rule reference snippet used in `TestExportRoamPageNoBundle`
- `flower.jpeg` — Image asset bundled alongside `test_article_1_expected.md` in the no-bundle export test

### yaml/
- *(see **Test Articles**)*

## Test Articles

Nine live Roam pages serve as the primary test sources: `[[Test Article]] 0`,
`[[Test Article]] 1`, `[[Test Article]] 2`, `[[Test Article]] 3`,
`[[Test Article]] 4`, `[[Test Article]] 5`, `[[Test Article]] 6`,
`[[Test Article]] 7`, and `[[Test Article]] 8 has a **bold** word`.

The convention is that a source page's title is `[[Test Article]] N`.  Article 8
relaxes it: when the feature under test is a property of the *title itself*, the
`[[Test Article]] N` form is kept as a prefix and the feature demonstration
follows (here, `**bold**` emphasis on one portion of the page name).

### Article Features

#### `[[Test Article]] 0`

- 3 top-level blocks
- nested blocks
- __italics__ text
- **bold** text
- ~~strikethrough~~
- ^^highlight^^
- `inline-code`
- fenced code mixed with text, block
- isolated fenced code block
- isolated fenced code block whose `plain text` fence language is overridden by a `code-language:: FORTRAN` tag
- Markdown single line block quote
- Markdown multi-line block quote
- Roam-native single line block quote
- Roam-native multi-line block quote
- Roam-native single line pull quote
- Roam-native multi-line pull quote
- Roam-native TODO item (open and done)
- Roam-native table (3x3)
- this INFO `Callout box`, which contains Roam `page references`

#### `[[Test Article]] 1`

- Page is completely self-contained – there are `no Roam embeds` of any kind
- 3 top-level `headers`, all H1
- nested `headers` down to H4, via __Augmented Headings__ extension
- a node, (Ma5KGUH9O) "AI assistant (Claude Opus 4.6):" that has property: BLOCK_HEADING = 0, which is not a valid Markdown level. It seems that this can happen when first a valid level value (1-6) is assigned, and then the heading level is removed altogether through the Roam UI.
- a pair of JPEG `image`s that **have not** been resized through the Roam UI (illustration 1.1)
- a single JPEG `image` that **has** been resized through the Roam UI (illustration 2.1)
- a native `{{table}}` (Section 2.2) whose four cells are each a standalone `block reference` to a JPEG `image` block, so each cell displays its referenced image
- an embedded PDF document that has no special PublishingSemantics Attributes attached
- an embedded PDF document that has `guffin-meta:: pdf-render: "inline"`
- this INFO `Callout box`, which contains Roam `page references`

#### `[[Test Article]] 2`

- **View as** block styling
 - The Page has children_layout=document

#### `[[Test Article]] 3`

- an exhaustive matrix of Roam `refs` and `embeds`: inline vs. standalone × internal (in-page) vs. external (out-of-page) × target kind
- `Feature Content` section holds the reference targets:
  - styled text runs: plain, italics, bold, strikethrough, highlight, inline-code
  - `color spans`: text color, highlight color, underline, box
  - a fenced Python `code block`, a standalone `image`, a Roam `callout`, a native `{{table}}`
  - `block quotes` (Markdown and Roam native, single- and multi-line) and Roam `pull quotes`
- `Internal (in-page) links:` section: inline refs to the styled/colored targets, plus standalone refs to page / block / parent block / header and to every block-level target above, plus a block embed
- `External (out-of-page) links:` section: the same matrix against Test Article 1 and Test Article 2, plus a Daily Notes Page ref, a page embed, a callout embed, and a standalone ref to a Test Article 1 PDF block tagged `guffin-meta:: pdf-render: "inline"` at the reference site (the site's tag drives the PDF format's inline placement)
- this INFO `Callout box`, which contains Roam `page references`

#### `[[Test Article]] 4`

- **Color Highlighter** Roam Extension: [fbgallet/roam-extension-color-highlighter: Highlight with different color and color bold text](https://github.com/fbgallet/roam-extension-color-highlighter)
 - **Better Bullets** Roam Extension: [mlava/better-bullets](https://github.com/mlava/better-bullets)

#### `[[Test Article]] 5`

- **attributes**, in both Roam forms: attribute blocks and `:entity/attrs` structured assertions
- end-user attribute blocks that fold onto their parent and render as `pills`: a `tags::` with reference values and an `attribute1::` mixing a literal value with references
- a `guffin-meta::` block carrying guffin-domain document metadata: `title::` (overrides the page title in every export — this page renders as "Source Code For Humans"), `date::`, `authors::` (two), and `identifier::`
- a guffin-domain `tags::` inside the guffin-meta block that is **not** a recognized PublishingSemantics attribute (folded, never rendered)
- this INFO `Callout box`

#### `[[Test Article]] 6`

- a small **Book** (The Picture of Dorian Gray) whose sections are declared with `element-type::` heading tags: copyright-page, preface, chapter
- full `guffin-meta::` bibliographic metadata: `title::` (overrides the page title in every export), `authors::`, `date::` (reduced-precision year), `publisher::`, `rights::`, `identifier::`, `revision::` (draft-1), and a `cover-image::` block ref
- PublishingSemantics interacting with transclusion: each section's content is a PAGE_EMBED of a different page
- per-embed `children_layout` presentation: the Uncopyright embed set to `document`, the Preface embed unset, the chapter I embed set to `numbered`; the page itself uses `document` children layout
- this INFO `Callout box`

#### `[[Test Article]] 7`

- a very large **parts Book** (The Travels of Marco Polo, ~30 chapters of prose) for scalability and performance testing
- four level-1 `element-type:: part` headings (**Book I–IV**, with bold runs in the heading text) — the content auto-detects the PART division, chapters at level 2
- 30 `element-type:: chapter` headings, plus introduction, acknowledgments, and section tags, and a bespoke `matter:: front-matter` override
- internal element numbers leading the headings — `[0.x]` front matter, `[1.p]` parts, `[1.p.c]` chapters — exercising the numbering validators (well-formedness, matter agreement, uniqueness, ordering, nesting)
- full `guffin-meta::` bibliographic metadata: `title::`, `subtitle::`, `authors::` (two), `date::` (full W3CDTF date), `publisher::`, `rights::`, `identifier::`
- front-matter headings whose text is a page reference (Acknowledgments; Who is this Book for?)
- a chapter whose body is a fenced Python `code block` (Chapter 4: Code Listing)
- this INFO `Callout box`

#### `[[Test Article]] 8 has a **bold** word`

- The Page title/name has Markdown markup in it

### Fixtures

For each source article, `tests/regen_fixtures.py` generates six fixture files that capture different stages and views of the data pipeline.

#### No-refs fixture set (`include_refs=False`) — a linear pipeline

These three fixtures represent successive stages of the export pipeline applied
to the anchor subtree alone, with no referenced pages included:

| Fixture | What it captures |
|---|---|
| `<prefix>_nodes.yaml` | The Roam nodes (page + blocks) as parsed `RoamNode` model objects |
| `<prefix>_vertices.yaml` | The same subtree transcribed into the export model (`VertexTree`) |
| `<prefix>_expected.md` | The fully rendered GFM output |

#### With-refs fixture set (`include_refs=True`) — three views of the same fetch

These three fixtures are all derived from a single API call that pulls the anchor
subtree together with every page and block it references.  Rather than a pipeline,
they are three different lenses on the same underlying data:

| Fixture | What it captures |
|---|---|
| `<prefix>_raw_result.yaml` | The raw Datalog wire response before any `RoamNode` parsing |
| `<prefix>_anchor_tree.yaml` | The `NodeTree` of the anchor subtree itself (within the broader refs fetch) |
| `<prefix>_nodes_by_uid.yaml` | All fetched nodes — anchor subtree plus every referenced page/block — keyed by UID |

## Usage

Fixture paths are resolved via constants defined in `tests/conftest.py`:

```python
from conftest import FIXTURES_IMAGES_DIR, FIXTURES_JSON_DIR, FIXTURES_MD_DIR, FIXTURES_YAML_DIR

data = (FIXTURES_YAML_DIR / "test_article_1_vertices.yaml").read_text()
image = (FIXTURES_IMAGES_DIR / "flower.jpeg").read_bytes()
```

To regenerate fixtures from the live Roam graph:

```bash
source .venv/bin/activate
python tests/regen_fixtures.py "[[Test Article]] 0" --prefix test_article_0
python tests/regen_fixtures.py "[[Test Article]] 1" --prefix test_article_1
python tests/regen_fixtures.py "[[Test Article]] 2" --prefix test_article_2
python tests/regen_fixtures.py "[[Test Article]] 3" --prefix test_article_3
python tests/regen_fixtures.py "[[Test Article]] 4" --prefix test_article_4
python tests/regen_fixtures.py "[[Test Article]] 5" --prefix test_article_5
python tests/regen_fixtures.py "[[Test Article]] 6" --prefix test_article_6 --epub
python tests/regen_fixtures.py "[[Test Article]] 7" --prefix test_article_7
```
