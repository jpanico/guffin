// Mockup: an alternatives group whose host block renders as a LIST ITEM (guffin's default
// bullet layout) in PDF output.  Companion to alternatives.typ (the paragraph case, variant C).
// Standalone — mirrors the Bergfink defaults, including its list styling (indent 6pt, Typst's
// default depth markers, tight-list spacing).  Not wired into guffin.
//
// Typst's list() cannot give one item its own marker (list.marker varies by depth, not item),
// so — exactly like guffin's typst_bullet.lua for semantic bullets — a list holding a versioned
// item is drawn as a grid of (marker, body) rows.

#set page(paper: "a4", margin: (x: 2.5cm, top: 2.2cm, bottom: 2.2cm))
#set text(font: "noto sans", size: 11pt, lang: "en")
#set par(justify: true, leading: 0.65em, spacing: 1.2em)
#show heading: set text(font: "noto sans")
#show heading.where(level: 1): set text(size: 1.3em)
#show heading.where(level: 2): set text(size: 1.1em)
#show list: set list(indent: 6pt)

// ---------------------------------------------------------------- shared pieces (as variant C)

#let muted = luma(115)
#let rule-colour = luma(185)
#let rail = (paint: rule-colour, thickness: 0.8pt, dash: (2pt, 2pt))
#let list-gap = 0.65em     // Typst's tight-list item spacing (= par leading)
#let group-gap = 0.4em     // tighter inside a group, so it reads as one unit

#let marker(selected) = box(baseline: 0.12em, {
  let d = 0.62em
  if selected {
    circle(radius: d / 2, stroke: 0.7pt + black, inset: 0pt,
      align(center + horizon, circle(radius: d / 4.2, fill: black, stroke: none)))
  } else {
    circle(radius: d / 2, stroke: 0.7pt + muted)
  }
})
#let alt(body) = text(size: 0.93em, fill: muted, body)

#let group = (
  selected: [The committee met on Thursday and, after a long and occasionally heated
    discussion, agreed to postpone the vote until the full budget figures were available.],
  alternatives: (
    [On Thursday the committee met and, after _much_ debate, voted to defer the decision
      until it had seen the full budget figures.],
    [The committee's Thursday meeting ended without a vote: members wanted the *complete*
      budget figures before committing either way.],
  ),
)
#let first-item = [The chair opened the meeting and confirmed that a quorum was present.]
#let last-item = [The treasurer will circulate the revised figures to every member before the
  next meeting, with the variance against last year's budget highlighted.]

#let note(body) = block(above: 0.4em, below: 1em, text(size: 0.85em, fill: luma(90), style: "italic", body))

// ---------------------------------------------------------------- L1: radio replaces the bullet

// A list as a grid.  Columns: 3pt of indent, 3pt more (the rail runs on the boundary between
// them, so it sits 3pt left of the markers — together the native list's 6pt indent), the
// marker column, and the body.  A versioned item expands into one row per wording: ◉ stands
// where its bullet was, each ○ in the same column beneath, and the rail spans the group.
#let l1-list(items, bullet: [•]) = {
  let cells = ()
  let lines = ()
  let gutters = ()
  let row = 0
  for item in items {
    if row > 0 { gutters.push(list-gap) }
    if type(item) == dictionary {
      let start = row
      cells += (none, none, marker(true), item.selected)
      row += 1
      for a in item.alternatives {
        gutters.push(group-gap)
        cells += (none, none, marker(false), alt(a))
        row += 1
      }
      lines.push(grid.vline(x: 1, start: start, end: row, stroke: rail))
    } else {
      cells += (none, none, bullet, item)
      row += 1
    }
  }
  grid(
    columns: (3pt, 3pt, auto, 1fr),
    column-gutter: (0pt, 0pt, 0.5em),
    row-gutter: gutters,
    ..lines,
    ..cells,
  )
}

// ---------------------------------------------------------------- L2: bullet kept, group inside

#let l2-group(item) = block(
  stroke: (left: rail),
  inset: (left: 0.35em, y: 0.1em),
  grid(
    columns: (auto, 1fr),
    column-gutter: 0.5em,
    row-gutter: group-gap,
    marker(true), item.selected,
    ..item.alternatives.map(a => (marker(false), alt(a))).flatten(),
  ),
)

// ---------------------------------------------------------------- L3: alternatives as sub-items

#let l3-item(item) = {
  item.selected
  block(
    above: group-gap,
    pad(left: 6pt, block(
      stroke: (left: rail),
      inset: (left: 3pt),
      grid(
        columns: (auto, 1fr),
        column-gutter: 0.5em,
        row-gutter: group-gap,
        ..item.alternatives.map(a => (marker(false), alt(a))).flatten(),
      ),
    )),
  )
}

// ---------------------------------------------------------------- page

= Alternatives in a list item — PDF mockup

#note[The paragraph treatment (variant C) puts its markers in the page margin. In a list the
  natural place is the bullet column, which already holds a marker — so each variant below
  answers what becomes of the item's bullet. The middle item has three wordings; its
  siblings are ordinary.]

== L1 — The radio marker replaces the bullet (recommended)
#note[#marker(true) stands where the item's bullet was and each #marker(false) sits in the same column beneath it, so
  every wording keeps the list's text edge. The rail runs in the list indent, just left of the
  markers. The same move guffin already makes for semantic bullets.]

#l1-list((first-item, group, last-item))

#v(0.8em)
#note[The same, one level down: the sibling bullets are Typst's depth-2 ‣, the group's
  markers take the same column.]

#list(
  [Items carried over from the previous meeting:
    #block(above: list-gap, l1-list((first-item, group, last-item), bullet: [‣]))],
)

#pagebreak()

== L2 — Bullet kept, the group nested in the item
#note[The item keeps its bullet; its body is the variant-C group with the rail and markers
  inside it. Two markers lead the item (• then #marker(true)), and the wordings sit one step in from
  their siblings' text.]

#list(first-item, l2-group(group), last-item)

== L3 — Bullet kept, alternatives as sub-items
#note[The selected wording is the item's ordinary text; the alternatives hang beneath it like
  child items, #marker(false)-marked and railed. Compact, but alternatives read as the item's children —
  which, in a document with real child items, they are not.]

#list(first-item, l3-item(group), last-item)
