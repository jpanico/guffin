# Quarto borrowing analysis

An examination of the Quarto publishing system (quarto.org) for concepts, ideas, and abstractions
worth borrowing into guffin.  Researched 2026-08-03 against the live quarto.org documentation
(Quarto 1.7–1.9 era).  Guffin already borrowed Quarto's `project: type:` concept
(`render/project.py`); this analysis asks what else is worth mining.

This is a *design backlog*, not a commitment: items here are candidate threads to pick up later.
Companions: [render-pipeline.md](render-pipeline.md) (the render layer these ideas would land in),
[publishing-semantics.md](publishing-semantics.md) (the vocabulary several of them extend),
[server-mode.md](server-mode.md) and [server-packaging-plan.md](server-packaging-plan.md) (the
server-side items).

## What the comparison validates (no action)

Several guffin decisions turn out to be independently arrived-at Quarto doctrine, sometimes with
guffin the stricter of the two:

- **Type ≠ format.** Quarto's `project: type:` is exactly the orthogonality `render/project.py`
  borrowed, and Quarto confirms the whole shape: type is a structural-policy switch (numbering,
  division, chrome) applied per format by the renderer.
- **Graceful degradation with a documented floor.** Every Quarto feature page states its per-format
  fallback (callout → bold-titled blockquote; video → link in PDF/docx; margin-left content → body
  in LaTeX).  Guffin's `honoured_pdf_render` fallback-with-WARNING is the same doctrine — and
  stricter: Quarto *silently drops* book parts in EPUB/DOCX, where guffin's EPUB splits at level 2
  and `promote_non_body_sections()` keeps ToCs faithful.
- **Format-independent vocabulary, per-format explicit maps.** Quarto 1.3 moved from
  convention-laden Divs to typed custom AST nodes (Callout, Tabset, FloatRefTarget) with per-format
  registered renderers — structurally the same architecture as `PublishingSemantics` + scaffold
  attributes + per-format Lua filters.  The typed-node upgrade requires Quarto's own AST machinery,
  so the scaffold-Div approach remains the right call in Panflute-land.
- **Structure from content, not config (polarity check).** Quarto declares book structure in
  `_quarto.yml` (an ordered chapter manifest, parts, appendices), with content-side escape hatches
  (`.unnumbered` heading class).  Guffin runs the polarity the other way — structure derived from
  content tags (`element-type::`, `has_parts()`) — the right call for a Roam-resident source.
  Quarto's `index.qmd` is mandatory *because the HTML book is secretly a website*; guffin escapes
  that class of constraint entirely.

## Tier 1 — real gaps, strong fit

### 1. Typed cross-references (the biggest gap)

Quarto gives every referenceable element a *typed identity* through its ID prefix
(`#fig-elephant`, `#tbl-`, `#lst-`, `#sec-`, `#eq-`, the theorem family, the callout types); the
prefix drives a numbering counter, a prefix word, and the reference rendering (`@fig-elephant` →
"Figure 2.3", chapter-scoped in books).  Any content becomes a typed float by wrapping it in a div
whose ID carries the prefix, with "last paragraph = caption" as the uniform caption convention.
New float types are *declared*, not coded (`crossref: custom:` — kind/key/reference-prefix, plus a
per-format hook like `latex-env` only where a format needs it).

Guffin currently renders a Roam block ref to an image as a plain vertex link — there is no
"see Figure 3" anywhere in the pipeline, a conspicuous hole for the book use case.

The guffin-shaped version needs **no new author syntax**: Roam block references *are* the
references, and guffin already has the precedent of type-aware reference rendering —
`make_resolver` reformats a reference by target type when the target is a daily-note page.  The
same move generalizes: a standalone block ref whose target is an `ImageVertex` / `TableVertex` /
`CodeBlockVertex` renders as "Figure N" / "Table N" / "Listing N" (linked, numbered in document
order, chapter-scoped like Quarto's `crossref: chapters: true`).  A caption wants a small
vocabulary addition (a `caption::` guffin-meta tag, anchored like `pdf-render`), and
captioned-asset-becomes-numbered-float mirrors Quarto's "a captioned image alone in a paragraph is
a figure" rule.  Landing zone: `make_resolver` / `pandoc_rendering` plus one new
`PublishingSemantics` member.

### 2. Render profiles (named option overlays)

Quarto profiles (`_quarto-<name>.yml`, activated by `--profile` / `QUARTO_PROFILE`, with a
declarable default and mutually-exclusive profile groups) bundle coordinated settings under one
name; the canonical use cases are draft-vs-final and multiple editions from one source.

Guffin has accumulated exactly the toggles a profile wants to bundle: `--element-numbers`,
`--code-sources`, `--colophon`, `--verify-code-sources`, `--numbering`, `--preamble`.  A "review
draft" export is currently a long incantation (and some of it rides shell env).  A
`--profile draft` / `--profile final` resolving to a bundle of `RenderOptions` defaults — explicit
flags still winning, matching the existing tag-beats-default precedence — is a small, clean
feature.  It composes with server mode: a Request names a profile instead of re-listing ten
booleans.

Quarto wart to avoid: mistyped profile names are silently ignored.  Guffin's validation posture
(reject non-members) should apply.

### 3. Conditional content beyond boolean `publish::`

Quarto gates content per output with `.content-visible` / `.content-hidden` divs and spans, with
condition attributes `when-format` / `unless-format`, `when-profile` / `unless-profile`,
`when-meta` — and the format conditions target *format families*, capability classes rather than
writer names (`html` matches epub and revealjs; `html:js` — JavaScript-capable — excludes epub).
Multiple conditions on one element AND together.

Guffin's `publish::` is the boolean corner of this space.  Extending it (or a sibling tag, e.g.
`publish-when::`) with values like `pdf`, `epub`, `paginated`, or a profile name would let one Roam
source serve multiple editions — the natural companion to render profiles.  Content-declared,
anchored at `BLOCK`, pruned in Phase 0 alongside `drop_unpublished()` — it slots into existing
machinery with almost no new architecture.

### 4. A format-independent theme declaration (brand.yml's move)

Quarto's `_brand.yml` declares visual identity once — a named color palette plus semantic slots
(`primary`, `warning`, …), typography (per-element family/size/weight, Google-font auto-download
for Typst), logos — and compiles it per format: SCSS variables for HTML, dictionaries + generated
`set` rules for Typst, Lua getters, shortcodes.  Light/dark variants; document-over-project
cascade; explicit position in the theme stack.

Guffin already does this move *internally*: `callout_theme.py` is one accent-per-type compiled to
both `GUFFIN_CALLOUT_COLORS` (Typst) and a generated `callout_colors.css` (EPUB);
`semantic_theme.py` likewise for classification glyphs.  The borrow is generalizing that precedent
into an **author-facing** theme surface: body/heading/mono font families and a small semantic color
set, declared once, compiled to Bergfink variables and a generated CSS layer.  It would also fix a
current asymmetry: `--template-dir` customizes PDF only, while EPUB's `epub.css` (the documented
font-family customization point) has no per-export override.  Given the digital-first strategy,
one theme feeding both screen formats is the right grain.

### 5. Toolchain pinning and Typst-package vendoring

Quarto bundles its entire toolchain (Pandoc, Typst, Deno) so one version number pins everything;
extensions gate compatibility with `quarto-required: ">=1.2"`; and `quarto call typst-gather`
scans `.typ` files for `@preview` imports and vendors the packages locally for offline builds.
Reproducibility via vendoring, not lockfile resolution — committed `_extensions/`, committed
`_freeze/`, bundled binaries.

Two concrete takeaways:

- A cheap runtime gate: guffin requires typst ≥ 0.14 and a Pandoc floor, but nothing checks; a
  version probe with a clear error beats a mid-render Typst failure.
- `typst-gather` is precisely the mechanism the
  [server-packaging plan](server-packaging-plan.md) needs for its "bundle @preview packages" step —
  worth imitating rather than inventing.

## Tier 2 — worth having on the roadmap

- **Structured author model.** Quarto's author schema: structured names, ORCID, email,
  `corresponding`, degrees, CRediT `roles`, affiliations by reference into a top-level
  `affiliations` list carrying institutional identifiers (ISNI/Ringgold/ROR).  Guffin's `authors::`
  is a flat list; the shape to borrow — parsed at the vocabulary layer, parse-don't-validate — if
  the manuscript type gets real use.
- **Metadata-generated back matter.** Quarto mechanically generates "Reuse" and "Citation (how to
  cite this)" appendix sections from `license:` / `citation:` metadata.  Guffin's colophon is the
  same species; natural extensions: `rights::` → a generated copyright page for books, and a
  how-to-cite block from `identifier::` + `authors::` + `title::`.
- **A freeze analog for server mode.** Quarto's freeze (`execute: freeze: auto`, per-document
  snapshots in a committed `_freeze/`, honored only on *full* project renders so the editor of a
  file is always the one refreshing its entry) exists so renders skip work when sources haven't
  changed.  Guffin already computes the perfect cache key: `Revision.snapshot` (canonical content
  hash).  An export cache keyed on snapshot × options could make repeated server-mode exports
  near-instant — relevant to server-mode phases 2–3.
- **Multi-format in one invocation.** `quarto render` produces every declared format from one
  parse; guffin re-fetches and re-transcribes per `--format` run.  `--format pdf,epub` sharing one
  fetch/transcribe is straightforward since the split happens late (one `VertexTree`, per-format
  render entry points).  Quarto's per-format `output-file` collision story is already solved by
  guffin's `<target>.<type>.<ext>` stem.
- **Template partials.** Quarto decomposes each format's template into named partials, any subset
  replaceable (`template-partials:`); the Typst set is `definitions.typ` / `typst-template.typ` /
  `page.typ` / `typst-show.typ` / `notes.typ` / `biblio.typ`, with the two-file idiom —
  `typst-template.typ` (pure template function) + `typst-show.typ` (metadata→arguments show rule) —
  as the intended customization grain.  Bergfink's `user_cfg.typ` is a one-partial version; if PDF
  customization requests grow, Quarto's cut lines are the proven decomposition.
- **Code annotations.** Annotated code lines end with a comment marker (`# <1>`), an ordered list
  after the block supplies the text; renders as numbered callouts, degrading to line-number labels
  in constrained formats.  Genuinely useful for a technical book with sourced listings, though the
  Roam-side authoring story needs thought.
- **Small ones:** generalize `page-break::` beyond headings (Quarto's `pagebreak` shortcode works
  anywhere; the `PAGE_BREAK` anchor could widen to `BLOCK`); a `landscape`-style block treatment
  for wide tables (docx/pdf/typst in Quarto); `pdf-standard: ua-1`-style accessibility flags now
  that Typst supports PDF/UA — cheap and aligned with digital-first.

## Deliberately not borrowed

- **Config-declared structure** (the chapter manifest).  Opposite polarity to guffin's
  content-derived structure, deliberately — see the validation section above.
- **Execution engines, `params`, freeze-as-computation, Jupyter embedding.**  Guffin has no
  computation layer; the closest analog (code-source verification/snapshotting) already exists and
  is a better fit for prose-with-code.
- **The `include` shortcode.**  Deliberately dumb textual paste with main-document-relative path
  resolution and shared-execution-context caveats; Roam block/page embeds are a strictly better
  transclusion model and guffin already renders them.  (Quarto's `embed` shortcode — label-addressed,
  output-scoped, with automatic provenance backlinks — is the closer cousin to Roam embeds +
  guffin's code-source attribution.)
- **Extension marketplace machinery** (`quarto add`, `_extension.yml`, the `contributes:`
  taxonomy).  A single-author toolchain doesn't need distribution; the useful residue is the
  vendoring discipline (Tier 1, item 5).
- **Website/publishing verbs** — with one asterisk: the digital-first strategy names HTML as a
  primary screen format, and guffin has no HTML output yet.  If that changes, Quarto's "HTML book =
  website + sequence policy" is the reference design, and several HTML-only niceties (lightbox,
  format links, hover citations, the appendix styling) come along with it.

## Appendix: Quarto mechanisms referenced above, in brief

For future readers without the quarto.org context:

- **Metadata cascade**: project `_quarto.yml` → directory `_metadata.yml` → document front matter →
  CLI, deep-merging objects and *concatenating* arrays (both bibliographies kept); one hard-override
  exception (a document's `format:` list replaces, never merges).  `metadata-files:` splits config;
  `_quarto.yml.local` holds uncommitted machine-local overrides.
- **Profiles**: `_quarto-<name>.yml` overlays merged over the base config; activation via
  `--profile` / `QUARTO_PROFILE`; `profile: default:` and mutually exclusive `profile: group:`;
  profiles also gate content (`when-profile`) and export an env var to executing code.
- **Cross-references**: `#<type>-<name>` IDs / `@<type>-<name>` references; div syntax makes any
  content a typed float ("last paragraph is the caption"); subreferences (`Figure 1(b)`);
  `crossref:` YAML controls titles/prefixes/numbering schemes; `crossref: custom:` declares new
  float types.
- **Conditional content**: `.content-visible` / `.content-hidden` with `when-format` /
  `when-profile` / `when-meta` (and `unless-` duals); format conditions match capability families.
- **brand.yml**: color palette + semantic slots, typography, logos, light/dark — compiled per
  format (SCSS vars, Typst dictionaries and generated set rules, Lua getters, shortcodes).
- **Freeze**: `execute: freeze: true|auto`; per-document result snapshots in committed `_freeze/`;
  honored only on full project renders — incremental renders always execute, so the file's editor
  refreshes its own freeze entry.
- **Template partials**: each built-in format template decomposed into named, individually
  replaceable partials; policy-heavy pieces (title, toc, biblio) replaceable, plumbing inherited.
- **typst-gather**: `quarto call typst-gather` vendors `@preview` Typst packages into the
  extension/project for offline compilation.
