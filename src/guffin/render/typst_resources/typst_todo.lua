-- typst_todo.lua
-- Lua filter for the Typst/PDF output path.
-- A TODO item's blocks — and the display inlines of a reference to one — carry the item's
-- checkbox glyph (U+2610 BALLOT BOX / U+2612 BALLOT BOX WITH X, stamped by
-- pandoc_rendering.py from the vertex's TodoState).  The glyph cannot be trusted to a font:
-- the template's body font (Noto Sans) has no U+2610, so Typst renders tofu — a boxed "?"
-- in most PDF viewers.  This filter replaces every Str that IS the glyph with a checkbox
-- DRAWN from Typst primitives (a stroked box, crossed for a completed item), which depends
-- on no font and matches the body text's weight at any size.  The glyph is always emitted
-- space-separated, so it arrives as its own Str token; a literal ballot-box character in
-- authored text gains the same drawn box, which is strictly better than the tofu the font
-- would show.

local OPEN_GLYPH = "\u{2610}"
local DONE_GLYPH = "\u{2612}"

local OPEN_BOX = "#box(baseline: 15%, width: 0.85em, height: 0.85em, stroke: 0.06em)"
local DONE_BOX = "#box(baseline: 15%, width: 0.85em, height: 0.85em, stroke: 0.06em, {"
  .. " place(line(start: (8%, 8%), end: (92%, 92%), stroke: 0.06em));"
  .. " place(line(start: (92%, 8%), end: (8%, 92%), stroke: 0.06em)) })"

function Str(el)
  if el.text == OPEN_GLYPH then
    return pandoc.RawInline("typst", OPEN_BOX)
  end
  if el.text == DONE_GLYPH then
    return pandoc.RawInline("typst", DONE_BOX)
  end
  return nil
end
