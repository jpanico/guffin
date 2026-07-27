-- gfm_bullet.lua
-- Lua filter for the GFM Markdown output path.
-- Maps the classification scaffold Div produced by pandoc_rendering.py (a classified list
-- item's body, stamped with data-guffin-marker-glyph) to Markdown's syntax ceiling: the glyph
-- riding the scaffold is prepended to the item's line, after the native dash marker, and the
-- Div wrapper is dissolved.  Markdown list syntax offers no marker control, so `- ⇒ result
-- text` is the whole treatment — which is why a lone source channel's badge, which the
-- paginated formats stand in the marker's place, still reads identically here.

local GLYPH_ATTRIBUTE = "data-guffin-marker-glyph"
local SEMANTIC_ATTRIBUTE = "data-guffin-semantic"

-- Prepend the glyph (and a space) to the first inline-bearing block among `blocks`,
-- descending one level into a leading Div (the whole-line bg-color wrapper).
-- Returns true when a target block was found.
local function lead_with_glyph(blocks, glyph)
  local first = blocks[1]
  if first == nil then
    return false
  end
  if first.t == "Plain" or first.t == "Para" then
    first.content:insert(1, pandoc.Space())
    first.content:insert(1, pandoc.Str(glyph))
    return true
  end
  if first.t == "Div" then
    return lead_with_glyph(first.content, glyph)
  end
  return false
end

function Div(el)
  local glyph = el.attributes[GLYPH_ATTRIBUTE]
  if glyph == nil then
    return nil
  end
  el.attributes[GLYPH_ATTRIBUTE] = nil
  el.attributes[SEMANTIC_ATTRIBUTE] = nil
  lead_with_glyph(el.content, glyph)
  return el.content
end
