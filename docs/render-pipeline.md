# Render pipeline & project types

How the **render** layer turns the normalized model into output, and where **project types**
(`book` vs. `article` vs. `manuscript`) fit into that.

This is the downstream companion to [processing_pipeline.md](processing_pipeline.md): that doc
covers *fetch → model* (Roam → `VertexTree`); this one covers *model → output* and the
project-type model layered on top of it.

> Status note: the project-type model (`render/project.py`) is defined and **plumbed** — a
> `ProjectProfile` is threaded from the CLI `--type` flag through each render entry point — but its
> structural and metadata effects are **not yet applied** to the output. This doc describes both the
> current shape and the intended design so the remaining wiring has a spec to follow. Sections that
> describe planned behavior are marked _(planned)_.


## Where the render layer sits

The package layering is a directional pipeline:

```
roam/        →   transcribe/   →   model/      →   render/
(source)         (source→model)    (the content)   (model→output)
```

- `transcribe/` produces a `RenderBundle` (a `VertexTree` of content + a `ViewMap` presentation
  overlay). It is **project-type-agnostic**: the same transcribed tree becomes a book or an article
  purely by how it is *rendered*.
- `render/` consumes that `RenderBundle` and emits Markdown, PDF, EPUB (export) or a Rich terminal
  tree (dump).

`transcribe/` and `render/` are sibling layers with **no code cross-dependency**.


## The render layer is a two-stage pipeline

Every export format goes through the same two stages:

```mermaid
flowchart LR
    VB["RenderBundle<br/><i>VertexTree + ViewMap</i>"]
    PP["ProjectProfile<br/><i>project_type + metadata</i>"]
    RO["RenderOptions<br/><i>output_format + knobs</i>"]

    subgraph render["render/"]
      S1["<b>Stage 1</b><br/>vertex_tree_to_pandoc()<br/><i>VertexTree → Panflute Doc</i>"]
      S2["<b>Stage 2</b><br/>md / pdf / epub _rendering<br/><i>Doc → format output</i>"]
    end

    VB --> S1
    PP -. "metadata" .-> S1
    PP -. "StructuralPolicy" .-> S2
    RO --> S2
    S1 --> S2
    S2 --> OUT["Markdown · PDF · EPUB"]
```

- **Stage 1 — `render/pandoc_rendering.py::vertex_tree_to_pandoc()`**: walks the `VertexTree`,
  batch-parses inline Pandoc Markdown, and builds a **format-neutral** Panflute `Doc` (the in-memory
  Pandoc AST). Shared by all formats.
- **Stage 2 — `render/{md,pdf,epub}_rendering.py`**: serializes the `Doc` to Pandoc JSON and invokes
  Pandoc (plus Typst for PDF), applying the **format-specific** writer, Lua filters, templates, and
  bundled resources.


## Three orthogonal inputs

A render call combines three independent things. They are kept as separate objects on purpose —
each is a different axis:

| Object | Question it answers | Module | Discriminator |
|---|---|---|---|
| `RenderBundle` | *what is the content?* | `model/render_bundle.py` | — |
| `ProjectProfile` | *what kind of work is it?* | `render/project.py` | `project_type` |
| `RenderOptions` | *how / where to output?* | `render/render_options.py` | `output_format` |

`RenderOptions` and `ProjectProfile` are **both** format-independent in their base, but that does not
make them the same kind of thing:

- `RenderOptions` base fields (`output_dir`, `cache_dir`, `dump_pandoc_ast`, `suppress_attributes`)
  are render-**operation** knobs — they only exist *because* you are rendering.
- `ProjectProfile` describes the **work itself** (its kind plus bibliographic identity), which is
  invariant across formats and across render operations. A book is a book whether you render it to
  PDF, to EPUB, or not at all.

### Why they are not merged

`output_format` (md/pdf/epub) and `project_type` (default/book/manuscript) cross-product
independently — a 3×3 space. Folding the profile into `RenderOptions` would either:

- **flatten the two discriminators** → one subclass per *combination* (`PdfBookOptions`,
  `EpubArticleOptions`, …): combinatorial explosion; or
- **nest `profile` as a field** of `RenderOptions` → a *format-specific* object would carry a
  *format-independent* thing, and rendering one work to two formats would mean specifying the
  profile twice and keeping the copies in sync.

Keeping them separate gives the correct cardinality: **one** `ProjectProfile`, **N** format options.


## Project types

`render/project.py` models the *kind of work*, adopting the **concept** from Quarto's
`project: type:` — but **no Quarto artifact**: no `_quarto.yml`, no `quarto` CLI, no extensions.
Just a native vocabulary and the structural semantics it implies, expressed as Guffin's own Pydantic
models (mirroring the `RenderOptions` discriminated-hierarchy pattern).

- `ProjectType` — `default` | `book` | `manuscript` (the discriminator).
- `ProjectProfile` — the format-independent base, carrying bibliographic metadata
  (`title`, `authors`, `date`, `identifier`) shared by every kind of work.
- Per-type subclasses — `DefaultProfile`, `BookProfile` (`with_parts`),
  `ManuscriptProfile` (`abstract`, `keywords`).
- `StructuralPolicy` — the format-independent structural directives a profile **resolves to** (via
  `profile.structural_policy`). Renderers consume this rather than branching on `ProjectType`, so the
  type→structure semantics live in one place.

| `ProjectType` | top-level division | title page | numbered | abstract |
|---|---|---|---|---|
| `default` (article) | section | no | no | no |
| `book` | chapter (or part) | yes | yes | no |
| `manuscript` | section | yes | no | yes |


## Where the profile is consumed

In the **render layer only** — never in `transcribe/`. Two reasons:

1. **Conceptual.** Transcription is project-type-agnostic. It produces the same `VertexTree`
   regardless of how the work will later be packaged; the book-vs-article distinction is realized at
   render time (heading→division mapping, title page, numbering).
2. **Structural.** `ProjectProfile` lives in `render/`, and `transcribe/` may not depend on
   `render/` (sibling layers). So `transcribe/` *cannot* import it — it would invert the layering.

Within `render/`, the profile's effects split across the two stages.

### Stage 1 — metadata _(planned)_

The **bibliographic** fields (`title`, `authors`, `date`, `identifier`, `abstract`) become
`doc.metadata` on the Panflute `Doc` in `vertex_tree_to_pandoc()`. Every Pandoc writer then maps the
metadata to its format natively (LaTeX/Typst title block, EPUB `dc:*`, the `abstract` template
variable). **The format renderers do not change for this half.**

### Stage 2 — structure _(planned)_

The `StructuralPolicy` directives (`top_level_division`, `number_sections`, title page) are **not
representable in the Pandoc AST** — the AST has only `Header` elements with a level 1–6, no
"chapter," "numbered," or "title page" node. They are produced by the **writer + template at
invocation time**, and the mechanism differs per format:

| Policy directive | PDF (Typst / Bergfink) | EPUB (Pandoc) |
|---|---|---|
| chapters vs. sections | Bergfink template variable (Typst ignores `--top-level-division`) | `--split-level` |
| numbering | template / `--number-sections` | `--number-sections` |
| title page | Bergfink `titlepage.typ` partial | auto-generated from metadata |

So the structural half **cannot** be absorbed entirely into stage 1: at minimum the EPUB renderer
(`--split-level`) and the PDF path (a Bergfink template variable) must consult the policy. The
heaviest single piece is teaching the Bergfink Typst template a "book mode," which is template work,
separate from the Python wiring.

### Summary

| Profile data | Stage | Consumed in | Format renderers change? |
|---|---|---|---|
| `title`, `authors`, `date`, `identifier`, `abstract` | 1 (metadata) | `pandoc_rendering` | no |
| `top_level_division`, `number_sections`, title page | 2 (structure) | `pdf` / `epub` renderers + Bergfink template | yes (minimal) |


## Status & next steps

1. **Plumbing — done.** `render/project.py` defines the model and `profile_for()` maps a
   `ProjectType` to its default-valued profile. The CLI exposes `--type default|book|manuscript`
   (parallel to `--format`, default `default`), and each render entry point
   (`render/{md,pdf,epub}_rendering.py::render`) now takes a `profile: ProjectProfile` argument,
   threaded through `cli/export_roam_tree.py::_render`. Nothing reads `StructuralPolicy` to shape
   output yet — the renderers currently only log it.
2. **First behavior** _(next)_ — wire `top_level_division` only. Start with EPUB (`--split-level`
   derived from the policy) as a quick, verifiable slice, then the PDF Bergfink "book mode" as the
   visually-compelling second increment.
3. Title page / numbering / abstract follow as later increments.
