# Epigraph alternatives — Markdown styling mockup

*Sample: Test Article 3's version group, as in the PDF and EPUB mockups: the Dijkstra epigraph
selected, the two Perlis lines its alternatives. GFM cannot draw the dashed rail, narrow the
column, or set a source flush right; a guffin epigraph is a block quote with an italic
quotation and an upright, em-dash-led last line. The variants follow M1 (◉/○-led lines, the
alternatives muted by an inline `<span style>` that Typora honours and GitHub strips). Each
appears twice, because a guffin block renders either as a paragraph (document layout) or as a
list item (bullet layout, the default).*

## Reference — no alternatives

> *The question of whether Machines Can Think … is about as relevant as the question of whether Submarines Can Swim.*
>
> —Edsger Dijkstra

Chapter body text resumes here in ordinary flow.

## ME1 — One block quote, a paragraph per wording

*The whole group is one block quote, so its bar binds the candidates as the rail does in PDF
and EPUB — the bar already says "epigraph" in Markdown, and here it says "one epigraph slot".
Each wording is one paragraph: the quotation, a hard break, its source. The selected wording
keeps the epigraph's styling; each alternative is muted, italic kept (E1).*

### As paragraphs

The paragraph before the group sits in ordinary body flow.

> ◉ *The question of whether Machines Can Think … is about as relevant as the question of whether Submarines Can Swim.*\
> —Edsger Dijkstra
>
> <span style="color: #737373; font-size: 0.93em">○ *Within a computer natural language is unnatural.*</span>\
> <span style="color: #737373; font-size: 0.93em">—Alan Perlis</span>
>
> <span style="color: #737373; font-size: 0.93em">○ *Programming is an unnatural act.*</span>\
> <span style="color: #737373; font-size: 0.93em">—Alan Perlis</span>

Chapter body text resumes here in ordinary flow.

### As list items

- The item before the group, in ordinary outline flow.
- VERSION GROUP of standalone BLOCK ref (epigraph)↓
  > ◉ *The question of whether Machines Can Think … is about as relevant as the question of whether Submarines Can Swim.*\
  > —Edsger Dijkstra
  >
  > <span style="color: #737373; font-size: 0.93em">○ *Within a computer natural language is unnatural.*</span>\
  > <span style="color: #737373; font-size: 0.93em">—Alan Perlis</span>
  >
  > <span style="color: #737373; font-size: 0.93em">○ *Programming is an unnatural act.*</span>\
  > <span style="color: #737373; font-size: 0.93em">—Alan Perlis</span>
- The item after the group resumes ordinary outline flow.

## ME1b — As ME1, muted a step lighter (chosen)

*GitHub and Typora's default theme already set block-quote text grey (GitHub `#59636e`), so
inside a block quote ME1's `#737373` barely separates the alternatives from the selected
wording. Here they are muted to `#a0a0a0` instead, a step lighter than the quote's own grey.*

> ◉ *The question of whether Machines Can Think … is about as relevant as the question of whether Submarines Can Swim.*\
> —Edsger Dijkstra
>
> <span style="color: #a0a0a0; font-size: 0.93em">○ *Within a computer natural language is unnatural.*</span>\
> <span style="color: #a0a0a0; font-size: 0.93em">—Alan Perlis</span>
>
> <span style="color: #a0a0a0; font-size: 0.93em">○ *Programming is an unnatural act.*</span>\
> <span style="color: #a0a0a0; font-size: 0.93em">—Alan Perlis</span>

Chapter body text resumes here in ordinary flow.

## ME2 — A block quote per wording

*Each wording is exactly today's epigraph block quote — quotation paragraph, then source
paragraph — led by its marker, the alternatives muted. Nothing binds the group but adjacency,
and the quotation-to-source gap equals the gap between wordings' bars.*

### As paragraphs

The paragraph before the group sits in ordinary body flow.

> ◉ *The question of whether Machines Can Think … is about as relevant as the question of whether Submarines Can Swim.*
>
> —Edsger Dijkstra

> <span style="color: #737373; font-size: 0.93em">○ *Within a computer natural language is unnatural.*</span>
>
> <span style="color: #737373; font-size: 0.93em">—Alan Perlis</span>

> <span style="color: #737373; font-size: 0.93em">○ *Programming is an unnatural act.*</span>
>
> <span style="color: #737373; font-size: 0.93em">—Alan Perlis</span>

Chapter body text resumes here in ordinary flow.

### As list items

- The item before the group, in ordinary outline flow.
- VERSION GROUP of standalone BLOCK ref (epigraph)↓
  > ◉ *The question of whether Machines Can Think … is about as relevant as the question of whether Submarines Can Swim.*
  >
  > —Edsger Dijkstra

  > <span style="color: #737373; font-size: 0.93em">○ *Within a computer natural language is unnatural.*</span>
  >
  > <span style="color: #737373; font-size: 0.93em">—Alan Perlis</span>

  > <span style="color: #737373; font-size: 0.93em">○ *Programming is an unnatural act.*</span>
  >
  > <span style="color: #737373; font-size: 0.93em">—Alan Perlis</span>
- The item after the group resumes ordinary outline flow.
