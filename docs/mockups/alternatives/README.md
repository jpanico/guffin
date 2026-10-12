# Alternatives styling mockups

Standalone mockups, made outside the guffin code, of how `export-roam-tree --render-alternatives`
should render a text block's alternative wordings (Roam's block versions) in each output format.
The option is plumbed onto `RenderOptions.render_alternatives`, and every renderer implements the
chosen treatment: PDF (variant C in flow, L1 in bullet lists), EPUB (C2 in flow, L1 in bullet
lists), and Markdown (M1 everywhere). These files are the visual reference for the
implementations. Each mockup shows every
variant considered, including the rejected ones, between ordinary paragraphs or list items. The
chosen variant is recorded below.

The sample group is one sentence written three ways, the first selected. It's long enough to
wrap, and the alternatives carry inline emphasis so the muted treatment can be judged against it.

## Decisions (2026-10-12)

| Format | Paragraph (document layout) | List item (bullet layout, guffin's default) |
|---|---|---|
| PDF | **C** — dashed rail and radio markers in the left margin; the selected wording keeps the body edge | **L1** — the radio marker replaces the item's bullet, and the list is redrawn as a grid (as `typst_bullet.lua` does) |
| EPUB | **C2** — C's look, set just inside the text column (C1, hanging into the page margin, gets clipped) | **L1** — `list-style: none`, drawn markers in the list indent via a negative `text-indent` |
| Markdown | **M1** — one block, hard line breaks, ◉/○-led lines, alternatives in grey `<span style>`s, no rail | **M1** |

Shared across formats:

- **Markers.** A filled radio marker (◉) leads the selected wording and a hollow one (○) leads
  each alternative, so which wording is selected never depends on colour alone. In PDF and EPUB
  they're drawn (Typst `circle`, inline SVG), never font glyphs.
- **Styling.** The selected wording is ordinary body text. Alternatives are muted (`luma(115)` /
  `#737373`) at 0.93em and **never italic**, so authored emphasis inside them survives. The rail
  is a thin dashed `luma(185)` / `#b9b9b9` line, deliberately unlike the block quote's solid bar.
- **No label.** The group carries no "Alternatives" heading.
- **Semantic glyphs.** On a versioned list item that also has a semantic classification, the
  radio marker takes the bullet slot and the semantic glyph leads the selected wording's text
  (`◉ ⇒ The committee met…`). The ○ rows carry no semantic glyph.

Still open: whether alternatives always follow the selected wording or keep their source order.
The mockups put the selected wording first.

## Files

| File | What it shows |
|---|---|
| `pdf/alternatives.typ` | PDF paragraph variants A–D (C chosen) |
| `pdf/alternatives-list.typ` | PDF list-item variants L1–L3 (L1 chosen), L1 at two depths |
| `epub/alternatives.md` + `alternatives.css` | EPUB paragraph variants C1, C2 (C2 chosen) |
| `epub/alternatives-list.md` + `alternatives-list.css` | EPUB L1 at two depths, beside an ordinary list |
| `epub/measure.js` | Chrome alignment check: the x of every marker and text edge |
| `markdown/alternatives.md` | Markdown variants M1–M3 (M1 chosen), each as paragraph and list item |
| `markdown/preview.css` | GitHub-like stylesheet for previewing the Markdown in a browser |

## Building

Run these from this directory. Build products go to `out/`, which is git-ignored.

```bash
mkdir -p out
```

PDF (Typst ≥ 0.14, with the Noto Sans font installed, as for guffin's PDF output):

```bash
typst compile pdf/alternatives.typ out/alternatives.pdf
```

```bash
typst compile pdf/alternatives-list.typ out/alternatives-list.pdf
```

EPUB, built against guffin's own `epub.css` the way the renderer builds it:

```bash
pandoc epub/alternatives.md -t epub3 --css ../../../src/guffin/render/epub_resources/epub.css --css epub/alternatives.css --split-level=1 -o out/alternatives.epub
```

```bash
pandoc epub/alternatives-list.md -t epub3 --css ../../../src/guffin/render/epub_resources/epub.css --css epub/alternatives.css --css epub/alternatives-list.css --split-level=1 -o out/alternatives-list.epub
```

Markdown: open `markdown/alternatives.md` in Typora, which applies the inline styles. To preview
how GitHub shows it, render it with `pandoc -f gfm -t html5 -s --css markdown/preview.css` and
strip the `style` attributes from the result.

## Verifying EPUB layout

Check alignment in Chrome (WebKit-like, close to Apple Books), not calibre. calibre rewrites CSS
on conversion: it clipped C1, as expected, but it also shifted L1's nested case by a few pixels
that the CSS itself doesn't produce. To measure, unzip the EPUB, add
`<script src="measure.js"></script>` before `</body>` in the chapter XHTML (with `measure.js`
copied next to it), and dump the DOM with headless Chrome; the script appends a
`<pre id="measure">` table of marker and text positions:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --window-size=400,1900 --allow-file-access-from-files --dump-dom "file://$PWD/out/unpacked/EPUB/text/measure.xhtml"
```

Not yet checked on a device: Apple Books, the Kindle app, or any reader's dark mode.
