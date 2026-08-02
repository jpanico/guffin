-- typst_todo.lua
-- Lua filter for the Typst/PDF output path.
-- A TODO item's block leads with its checkbox glyph (U+2610 BALLOT BOX / U+2612 BALLOT BOX
-- WITH X, stamped by pandoc_rendering.py from the vertex's TodoState).  The glyph cannot be
-- trusted to a font: the template's body font (Noto Sans) has no U+2610, so Typst renders
-- tofu — a boxed "?" in most PDF viewers.  This filter replaces the leading glyph with a
-- checkbox DRAWN from Typst primitives (a stroked box, crossed for a completed item), which
-- depends on no font and matches the body text's weight at any size.
-- The glyph is matched wherever a Plain or Para leads with it, so both list items and
-- document-layout paragraphs are covered; a literal leading ballot-box character in authored
-- text gains the same drawn box, which is strictly better than the tofu the font would show.

local OPEN_GLYPH = "\u{2610}"
local DONE_GLYPH = "\u{2612}"

local OPEN_BOX = "#box(baseline: 15%, width: 0.85em, height: 0.85em, stroke: 0.06em)"
local DONE_BOX = "#box(baseline: 15%, width: 0.85em, height: 0.85em, stroke: 0.06em, {"
  .. " place(line(start: (8%, 8%), end: (92%, 92%), stroke: 0.06em));"
  .. " place(line(start: (92%, 8%), end: (8%, 92%), stroke: 0.06em)) })"

-- Replace a leading checkbox glyph in *inlines* with its drawn-box raw Typst, in place.
-- Returns true when a replacement was made.
local function replace_leading_glyph(inlines)
  local first = inlines[1]
  if first == nil or first.t ~= "Str" then
    return false
  end
  if first.text == OPEN_GLYPH then
    inlines[1] = pandoc.RawInline("typst", OPEN_BOX)
    return true
  end
  if first.text == DONE_GLYPH then
    inlines[1] = pandoc.RawInline("typst", DONE_BOX)
    return true
  end
  return false
end

function Plain(el)
  if replace_leading_glyph(el.content) then
    return el
  end
  return nil
end

function Para(el)
  if replace_leading_glyph(el.content) then
    return el
  end
  return nil
end
