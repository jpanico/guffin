// Mockup: visual styling of a text block's alternative wordings in PDF output.
// Standalone — mirrors the Bergfink defaults (A4, 2.5cm side margins, Noto Sans 11pt,
// justified, 0.65em leading, 1.2em paragraph spacing) so the variants read as they would
// in a real export.  Not wired into guffin.

#set page(paper: "a4", margin: (x: 2.5cm, top: 2.2cm, bottom: 2.2cm))
#set text(font: "noto sans", size: 11pt, lang: "en")
#set par(justify: true, leading: 0.65em, spacing: 1.2em)
#show heading: set text(font: "noto sans")
#show heading.where(level: 1): set text(size: 1.3em)
#show heading.where(level: 2): set text(size: 1.1em)

// Bergfink's block quote, reproduced so each variant can be judged against it.
#show quote.where(block: true): it => block(
  stroke: (left: 3pt + luma(170)),
  inset: (left: 1em, right: 0em, top: 0.4em, bottom: 0.4em),
  width: 100%,
)[#it.body]

// ---------------------------------------------------------------- shared pieces

#let muted = luma(115)      // alternatives' text colour (~#737373; body text is black)
#let rule-colour = luma(185)

// Radio-button markers drawn from primitives (no font dependency): filled for the
// selected wording, hollow for the alternatives — the dump-roam-tree ◉/○ convention.
#let marker(selected) = box(baseline: 0.12em, {
  let d = 0.62em
  if selected {
    circle(radius: d / 2, stroke: 0.7pt + black, inset: 0pt,
      align(center + horizon, circle(radius: d / 4.2, fill: black, stroke: none)))
  } else {
    circle(radius: d / 2, stroke: 0.7pt + muted)
  }
})

#let alt(body) = text(fill: muted, body)

// The sample group: three wordings of one sentence, long enough to wrap, with inline
// emphasis in the alternatives so the muted treatment can be judged against it.
#let selected = [The committee met on Thursday and, after a long and occasionally heated
  discussion, agreed to postpone the vote until the full budget figures were available.]
#let alternatives = (
  [On Thursday the committee met and, after _much_ debate, voted to defer the decision
    until it had seen the full budget figures.],
  [The committee's Thursday meeting ended without a vote: members wanted the *complete*
    budget figures before committing either way.],
)

#let before = [The paragraph before the group sits in ordinary body flow, so the eye
  arrives at the group from normal reading and can judge how much it interrupts the page.]
#let after = [The paragraph after the group resumes ordinary flow. A good treatment lets
  a reader skim straight past the alternatives while still seeing at a glance which
  wording is the one in force.]

#let note(body) = block(above: 0.4em, below: 1em, text(size: 0.85em, fill: luma(90), style: "italic", body))

// ---------------------------------------------------------------- variants

// A — the brief as given: a framed box around the whole group, members stacked as
// paragraphs, the selected wording in body colour, alternatives a lighter grey.
#let variant-a = block(
  width: 100%,
  stroke: 0.6pt + rule-colour,
  radius: 3pt,
  inset: (x: 0.8em, y: 0.7em),
  {
    set par(spacing: 0.7em)
    selected
    for a in alternatives { parbreak(); alt(a) }
  },
)

// B — A plus hanging radio markers, so "which one is in force" survives greyscale
// printing, colour-blindness, and a low-contrast screen.
#let variant-b = block(
  width: 100%,
  stroke: 0.6pt + rule-colour,
  radius: 3pt,
  inset: (x: 0.8em, y: 0.7em),
  grid(
    columns: (1.3em, 1fr),
    row-gutter: 0.7em,
    marker(true), selected,
    ..alternatives.map(a => (marker(false), alt(a))).flatten(),
  ),
)

// C — recommended: no box.  A thin dashed rail on the left (deliberately unlike the
// block quote's solid 3pt bar) binds the group; the markers hang in the gutter so the
// selected wording keeps the body's left edge and reads as ordinary text; alternatives
// are muted and set a touch smaller, with tighter spacing so the group reads as one unit.
#let variant-c = {
  let rail = (paint: rule-colour, thickness: 0.8pt, dash: (2pt, 2pt))
  pad(left: -1.6em, block(
    width: 100%,
    stroke: (left: rail),
    inset: (left: 0.35em, y: 0.15em),
    grid(
      columns: (1.25em, 1fr),
      row-gutter: 0.55em,
      marker(true), selected,
      ..alternatives
        .map(a => (marker(false), text(size: 0.93em, alt(a))))
        .flatten(),
    ),
  ))
}

// D — the selected wording stays a plain paragraph; the alternatives follow on a faint
// tinted band with a small-caps label, as an aside to the text rather than part of it.
#let variant-d = {
  parbreak()
  selected
  block(
    width: 100%,
    above: 0.5em,
    fill: luma(246),
    radius: 2pt,
    inset: (x: 0.8em, y: 0.6em),
    {
      set par(spacing: 0.5em)
      text(size: 0.75em, fill: muted, tracking: 0.06em, smallcaps[Alternatives])
      for a in alternatives { parbreak(); text(size: 0.93em, alt(a)) }
    },
  )
}

#let specimen(title, body, description) = {
  heading(level: 2, title)
  note(description)
  before
  body
  after
}

// ---------------------------------------------------------------- page

= Alternatives — PDF styling mockup

#note[Sample: one sentence with three wordings, the first selected. Each variant sits between two ordinary paragraphs. The block quote below is Bergfink's,
  shown for contrast — a treatment must not be mistaken for it.]

#quote(block: true)[A block quote, for comparison: solid 3pt grey bar, body-colour text.]

#specimen(
  [A — Framed (as briefed)],
  variant-a,
  [Box around the group; selected in body colour; alternatives in lighter grey.],
)

#specimen(
  [B — Framed, with markers],
  variant-b,
  [As A, plus filled/hollow radio markers, so the selected wording doesn't depend on colour alone.],
)

#pagebreak()

#specimen(
  [C — Dashed rail, hanging markers (recommended)],
  variant-c,
  [No box: a thin dashed rail binds the group, markers hang in the margin, the selected text
    keeps the body's left edge; alternatives muted and slightly smaller.],
)

#specimen(
  [D — Aside band],
  variant-d,
  [Selected wording stays a normal paragraph; alternatives follow on a faint tinted band under a
    small-caps label.],
)
