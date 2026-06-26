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
- `image_node.json` — Raw Roam node payload for a Firestore image block; used in `TestTranscribeNode::test_transcribes_image_node_from_fixture`

### markdown/
- `descendant_rule.md` — CSS descendant-rule reference snippet used in `TestExportRoamPageNoBundle`
- `flower.jpeg` — Image asset bundled alongside `test_article_1_expected.md` in the no-bundle export test

### yaml/
- *(see **Test Articles**)*

## Test Articles

Six live Roam pages serve as the primary test sources: `[[Test Article]] 0`,
`[[Test Article]] 1`, `[[Test Article]] 2`, `[[Test Article]] 3`,
`[[Test Article]] 4`, and `[[Test Article]] 5`.

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
- Markdown single line block quote
- Markdown multi-line block quote
- Roam-native single line block quote
- Roam-native multi-line block quote
- Roam-native table (3x3)
- this INFO `Callout box`, which contains Roam `page references`

#### `[[Test Article]] 1`

- Page is completely self-contained – there are `no Roam embeds` of any kind
- 3 top-level `headers`, all H1
- nested `headers` down to H4, via __Augmented Headings__ extension
- a node, (Ma5KGUH9O) "AI assistant (Claude Opus 4.6):" that has property: BLOCK_HEADING = 0, which is not a valid Markdown level. It seems that this can happen when first a valid level value (1-6) is assigned, and then the heading level is removed altogether through the Roam UI.
- a single JPEG `image` that **has not** been resized through the Roam UI (illustration 1.1)
- a single JPEG `image` that **has** been resized through the Roam UI (illustration 2.1)
- this INFO `Callout box`, which contains Roam `page references`

#### `[[Test Article]] 2`

- **View as** block styling

#### `[[Test Article]] 3`

- This page is primarily a demonstration of different kinds of refs:
  - inline page ref
  - internal block ref (to block on this page)
  - external block ref (to block on a __different page__)
  - internal embed (of block from this page)
  - external embed (of block from __different page__)
- this INFO `Callout box`, which contains Roam `page references`

#### `[[Test Article]] 4`

- **Color Highlighter** Roam Extension: https://github.com/fbgallet/roam-extension-color-highlighter

#### `[[Test Article]] 5`

- **attributes**

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
```
