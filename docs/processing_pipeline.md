# Guffin processing pipeline

A high-level overview of how Guffin turns a Roam page or node subtree into a self-contained
document. The pipeline is a **directional flow across sub-packages**: fetch the Roam graph,
transcribe it into a normalized content model, then render that model to output.


## The pipeline at a glance

```mermaid
flowchart LR
    ROAM["<b>roam/</b><br/><i>fetch source data</i>"]
    TRANSCRIBE["<b>transcribe/</b><br/><i>source → model</i>"]
    MODEL["<b>model/</b><br/><i>source-agnostic Guffin model</i>"]
    RENDER["<b>render/</b><br/><i>model → output</i>"]

    ROAM --> TRANSCRIBE --> MODEL --> RENDER
```

- **Fetch (`roam/`)** — a user qualifier (a page title or node UID) becomes a `NodeFetchAnchor` /
  `NodeFetchSpec`, which drives a Datalog pull-block query against the Roam Datomic DB through the
  Roam Local API. The raw results are parsed into validated `RoamNode` models and assembled into a
  `NodeTree` (a rooted DAG with referential-integrity validation).
- **Transcribe (`transcribe/`)** — `to_render_bundle()` converts the Roam-specific `NodeTree` into a
  Roam-agnostic `RenderBundle`: a `VertexTree` of normalized content paired with a `ViewMap`
  presentation overlay. Roam-flavored Markdown (Roamdown) is translated to Pandoc Markdown here.
- **Render (`render/`)** — the `RenderBundle`, together with a `ProjectProfile` (what *kind* of work)
  and `RenderOptions` (how / where to output), is rendered to Markdown, PDF, or EPUB. This stage is
  itself a two-stage Panflute → Pandoc pipeline; see [render-pipeline.md](render-pipeline.md).

The flow is one-directional and the layers don't reach back: each stage depends only on those to its
left, with `model/` as the shared content layer that `transcribe/` produces and `render/` consumes.
`transcribe/` and `render/` are siblings with **no code cross-dependency**. Orthogonal to all of
this, the `cli/` entry points orchestrate the flow and `common/` provides cross-cutting helpers.


## Detailed data flow

The artifacts that flow through the fetch and transcribe stages, ending at the `RenderBundle` that
the render layer consumes. (The render stage is expanded in [render-pipeline.md](render-pipeline.md).)

```mermaid
flowchart TD
    USER["<b>User input</b><br/>qualifier string<br/><i>page title or node UID</i>"]
    ANCHOR["<b>NodeFetchAnchor</b><br/>qualifier + kind<br/><i>PAGE_TITLE | NODE_UID</i>"]
    SPEC["<b>NodeFetchSpec</b><br/>anchor · include_refs"]
    QUERY["<b>Roam Datomic DB</b><br/>Datalog pull-block query<br/><i>via Roam Local API</i>"]
    RAW["<b>Raw result</b><br/>NodeFetchResult.raw_result<br/><i>list of pull-blocks</i>"]
    NETWORK["<b>NodeNetwork</b><br/>RoamNode records<br/><i>Pydantic validation per pull-block</i>"]
    TREE["<b>NodeTree</b><br/>rooted DAG<br/><i>referential integrity via _validate_is_tree</i>"]
    BUNDLE["<b>RenderBundle</b><br/>VertexTree + ViewMap<br/><i>Roamdown → Pandoc Markdown · roam_tree_to_guffin.py</i>"]
    RENDER["<b>render/</b><br/>Markdown · PDF · EPUB<br/><i>+ ProjectProfile + RenderOptions · see render-pipeline.md</i>"]
    OUT["<b>.md / .mdbundle · .pdf · .epub</b>"]

    USER    -->|"NodeFetchAnchor(qualifier)"| ANCHOR
    ANCHOR  -->|"NodeFetchSpec(...)"| SPEC
    SPEC    -->|"fetch_roam_nodes()"| QUERY
    QUERY   -->|"raw JSON response"| RAW
    RAW     -->|"RoamNode.model_validate() × N"| NETWORK
    NETWORK -->|"NodeTree.build(anchor)"| TREE
    TREE    -->|"to_render_bundle()"| BUNDLE
    BUNDLE  -->|"render(...)"| RENDER
    RENDER  --> OUT
```

The `cli/` layer wires these together end to end: `fetch_roam_trees()` (in `cli/common.py`) runs the
fetch and transcribe stages and returns a `RenderBundle`, which `export-roam-tree` then hands to the
format-specific renderer selected by `--format`.
