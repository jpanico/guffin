// Mockup: visual styling of an epigraph's alternative wordings in PDF output.
// Standalone — mirrors the Bergfink defaults (A4, 2.5cm side margins, Noto Sans 11pt, justified,
// 0.65em leading) and guffin's #epigraph helper (flush left, italic, 1.1x, 0.9em leading, the
// source upright and flush right against the quotation's longest line, wrap width 75%), plus the
// shipped alternatives pieces (dashed luma(185) rail, drawn radio markers, luma(115) muting at
// 0.93em).  Not wired into guffin.

#set page(paper: "a4", margin: (x: 2.5cm, top: 2.2cm, bottom: 2.2cm))
#set text(font: "noto sans", size: 11pt, lang: "en")
#set par(justify: true, leading: 0.65em, spacing: 1.2em)
#show heading: set text(font: "noto sans")
#show heading.where(level: 1): set text(size: 1.6em)
#show heading.where(level: 2): set text(size: 1.1em)

// ---------------------------------------------------------------- shared pieces

#let muted = luma(115)
#let rail = (paint: luma(185), thickness: 0.8pt, dash: (2pt, 2pt))

#let marker(selected) = box(baseline: 0.12em, {
  let d = 0.62em
  if selected {
    circle(radius: d / 2, stroke: 0.7pt + black, inset: 0pt,
      align(center + horizon, circle(radius: d / 4.2, fill: black, stroke: none)))
  } else {
    circle(radius: d / 2, stroke: 0.7pt + muted)
  }
})

// guffin's epigraph, parameterized for muting: the quotation (italic unless `upright`) and its
// source, in a block as wide as the wider of the two, capped at 75% of the region.
#let epigraph-body(quote, source, fill: black, scale: 1.0, upright: false) = {
  set par(justify: false, leading: 0.9em)
  set text(size: 1.1em * scale, fill: fill)
  layout(region => {
    let limit = 75% * region.width
    let body = text(style: if upright { "normal" } else { "italic" }, quote)
    let source-line = [—#source]
    let width = calc.max(measure(body, width: limit).width, measure(source-line, width: limit).width)
    block(width: width, {
      body
      block(above: 0.8em, width: 100%, align(right, source-line))
    })
  })
}

// The sample: Test Article 3's version group (Dijkstra selected, the two Perlis lines alternatives).
#let wordings = (
  (quote: [The question of whether Machines Can Think … is about as relevant as the question of
    whether Submarines Can Swim.], source: [Edsger Dijkstra]),
  (quote: [Within a computer natural language is unnatural.], source: [Alan Perlis]),
  (quote: [Programming is an unnatural act.], source: [Alan Perlis]),
)
#let selected = wordings.at(0)
#let alternatives = wordings.slice(1)

#let chapter(title) = heading(level: 1, title)
#let body-text = [Chapter body text resumes here in ordinary flow. A good treatment lets a reader
  see at once which epigraph opens the chapter, while the candidates remain legible for the author
  weighing them, and the chapter's first paragraph is not crowded by the group above it.]

#let note(body) = block(above: 0.4em, below: 1.2em, text(size: 0.85em, fill: luma(90), style: "italic", body))

// The group frame shared by E1 and E2: the rail and markers hang into the left margin, so the
// selected epigraph keeps the text block's left edge, exactly where it sits without alternatives.
#let hung-group(rows) = block(above: 1.5em, below: 2em, pad(left: -1.6em, block(
  width: 100%,
  stroke: (left: rail),
  inset: (left: 0.35em, y: 0.2em),
  grid(
    columns: (1.25em, 1fr),
    row-gutter: 1.1em,
    // Lower each marker to the first line of an epigraph set at 1.1x.
    ..rows.map(((selected, body)) => (pad(top: 0.18em, marker(selected)), body)).flatten(),
  ),
)))

// ---------------------------------------------------------------- variants

// E1 — the shipped treatment applied whole: every wording keeps the full epigraph form (italic,
// own source line), the alternatives muted and a touch smaller.  Keeps italic in the alternatives,
// because italic is the epigraph's form rather than authored emphasis.
#let variant-e1 = hung-group((
  (true, epigraph-body(selected.quote, selected.source)),
  ..alternatives.map(w => (false, epigraph-body(w.quote, w.source, fill: muted, scale: 0.93))),
))

// E2 — as E1, but the alternatives set upright, honouring the alternatives rule that a muted
// wording is never italic: the selected epigraph alone has the epigraph's voice.
#let variant-e2 = hung-group((
  (true, epigraph-body(selected.quote, selected.source)),
  ..alternatives.map(w => (false, epigraph-body(w.quote, w.source, fill: muted, scale: 0.93, upright: true))),
))

// E3 — compact: the selected epigraph is set exactly as without alternatives; the alternatives
// follow as a short run of one-line candidates, each quotation with its source run in, in the
// muted body size, so the chapter opening keeps its proportions.  The rail spans the whole group.
#let variant-e3 = block(above: 1.5em, below: 2em, pad(left: -1.6em, block(
  width: 100%,
  stroke: (left: rail),
  inset: (left: 0.35em, y: 0.2em),
  grid(
    columns: (1.25em, 1fr),
    row-gutter: 0.6em,
    pad(top: 0.18em, marker(true)), epigraph-body(selected.quote, selected.source),
    grid.cell(colspan: 2, v(0.3em)),
    ..alternatives.map(w => (
      marker(false),
      text(size: 0.93em, fill: muted)[#emph(w.quote) #h(0.3em)—#w.source],
    )).flatten(),
  ),
)))

#let specimen(label, number, title, body, description) = {
  text(size: 0.8em, fill: luma(90), weight: "bold", tracking: 0.04em, upper(label))
  note(description)
  chapter[#number #title]
  body
  body-text
}

// ---------------------------------------------------------------- page

#specimen(
  [E1 — Full epigraphs, muted alternatives (chosen)],
  [3],
  [Thinking Machines],
  variant-e1,
  [Each wording keeps the whole epigraph form, its source flush right under its own longest line;
    alternatives muted at 0.93× and still italic. Rail and markers hang in the margin.],
)

#v(2.5em)

#specimen(
  [E2 — Full epigraphs, upright alternatives],
  [3],
  [Thinking Machines],
  variant-e2,
  [As E1, but the alternatives set upright (the alternatives rule: a muted wording is never
    italic), so only the selected epigraph speaks in the epigraph's voice.],
)

#pagebreak()

#specimen(
  [E3 — Compact candidates],
  [3],
  [Thinking Machines],
  variant-e3,
  [The selected epigraph is set exactly as it is without alternatives; the alternatives follow
    as one-line candidates, source run in, at the muted body size.],
)

#v(2.5em)

#text(size: 0.8em, fill: luma(90), weight: "bold", tracking: 0.04em, upper[Reference — no alternatives])
#note[The same chapter opening as it renders today, for comparison.]
#chapter[3 Thinking Machines]
#block(above: 1.5em, below: 2em, epigraph-body(selected.quote, selected.source))
#body-text
