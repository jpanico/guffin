-- typst_bullet.lua
-- Lua filter for the Typst/PDF output path.
-- Transforms a BulletList containing semantic-classified items (the scaffold Div produced by
-- pandoc_rendering.py, stamped with data-guffin-semantic / data-guffin-semantic-glyph) into a
-- raw Typst two-column grid: each item's glyph in the first column — the semantic glyph
-- standing where the list marker was — and the item's body in the second.  Unclassified items
-- in the same list get the plain default bullet, keeping the run visually one uniform list.
-- A grid is required because neither Pandoc's list model nor Typst's list() supports per-item
-- markers (Typst's list.marker varies by nesting depth, not item index).
--
-- Registered LAST among the Typst filters so that the inline transforms (e.g. color spans) and
-- the block transforms (fancy-quote, code-source) have already rewritten any item content
-- before it is serialized to Typst here.

local GLYPH_ATTRIBUTE = "data-guffin-semantic-glyph"
local SEMANTIC_ATTRIBUTE = "data-guffin-semantic"
-- The plain bullet for unclassified items listed among classified ones; mirrors
-- DEFAULT_BULLET_GLYPH in render/semantic_theme.py.
local DEFAULT_GLYPH = "•"

-- Serialize a list of Pandoc blocks to a Typst content string.
local function to_typst(blocks)
  return pandoc.write(pandoc.Pandoc(blocks), "typst")
end

-- Return the item's glyph (or nil when unclassified) and its body blocks, the scaffold Div
-- dissolved.
local function glyph_and_body(item)
  local first = item[1]
  if first == nil or first.t ~= "Div" or first.attributes[GLYPH_ATTRIBUTE] == nil then
    return nil, item
  end
  local body = pandoc.List(first.content)
  for index = 2, #item do
    body:insert(item[index])
  end
  return first.attributes[GLYPH_ATTRIBUTE], body
end

function BulletList(el)
  local classified = false
  for _, item in ipairs(el.content) do
    if glyph_and_body(item) ~= nil then
      classified = true
      break
    end
  end
  if not classified then
    return nil
  end
  local cells = pandoc.List()
  for _, item in ipairs(el.content) do
    local glyph, body = glyph_and_body(item)
    -- The glyph rides as a quoted Typst string, immune to markup parsing (a bare `=` or `+`
    -- would otherwise read as heading or list syntax at content start).  Quoted by hand: the
    -- glyphs carry no quotes or backslashes, and Lua's %q would byte-escape their UTF-8.
    cells:insert(string.format('"%s", [%s],', glyph or DEFAULT_GLYPH, to_typst(body)))
  end
  local grid = "#grid(\n"
      .. "  columns: (auto, 1fr),\n"
      .. "  column-gutter: 0.5em,\n"
      .. "  row-gutter: 0.65em,\n  "
      .. table.concat(cells, "\n  ")
      .. "\n)"
  return pandoc.RawBlock("typst", grid)
end
