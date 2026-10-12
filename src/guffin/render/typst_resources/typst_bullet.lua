-- typst_bullet.lua
-- Lua filter for the Typst/PDF output path.
-- Transforms a BulletList containing classified items (the scaffold Div produced by
-- pandoc_rendering.py, stamped with data-guffin-marker-glyph) into a raw Typst two-column
-- grid: each item's glyph in the first column — the semantic bullet, or a lone source
-- channel's badge, standing where the list marker was — and the item's body in the second.
-- Unclassified items in the same list get the plain default bullet, keeping the run visually
-- one uniform list.  A list holding an item with alternatives is likewise rebuilt as a grid, with
-- that item's wordings each given a radio marker in the marker column (see alternatives_grid).
-- A grid is required because neither Pandoc's list model nor Typst's list() supports per-item
-- markers (Typst's list.marker varies by nesting depth, not item index).
--
-- Registered LAST among the Typst filters so that the inline transforms (e.g. color spans) and
-- the block transforms (fancy-quote, code-source) have already rewritten any item content
-- before it is serialized to Typst here.

local GLYPH_ATTRIBUTE = "data-guffin-marker-glyph"
-- The plain bullet for unclassified items listed among classified ones; mirrors
-- DEFAULT_BULLET_GLYPH in render/semantic_theme.py.
local DEFAULT_GLYPH = "•"
-- Classification glyphs render 20% larger than the item text, so the marker reads at a glance;
-- the default bullet stays at text size, mimicking the native marker it stands in for.  Mirrors
-- the span.bullet-glyph.classified font-size in epub_resources/epub.css.
local CLASSIFIED_GLYPH_SIZE = "1.2em"

-- Serialize a list of Pandoc blocks to a Typst content string.
local function to_typst(blocks)
  return pandoc.write(pandoc.Pandoc(blocks), "typst")
end

-- Return the item's glyph (or nil when unclassified) and its body blocks, the scaffold Div
-- dissolved.  Side-effect-free: the body is built on a clone — pandoc.List(existing) would
-- alias the Div's own content (it returns the same table), so inserting the item's trailing
-- blocks into it would mutate the document, duplicating them on a repeated call.
local function glyph_and_body(item)
  local first = item[1]
  if first == nil or first.t ~= "Div" or first.attributes[GLYPH_ATTRIBUTE] == nil then
    return nil, item
  end
  local body = first.content:clone()
  for index = 2, #item do
    body:insert(item[index])
  end
  return first.attributes[GLYPH_ATTRIBUTE], body
end

-- Alternatives (the scaffold Div produced by pandoc_rendering.py when a versioned block renders as
-- a list item: an "alternatives" Div holding a "selected-wording" Div, then one
-- "alternative-wording" Div per alternative) take the item's marker slot themselves: a filled radio
-- marker stands where the item's bullet was, with a hollow one beneath it for each alternative, all
-- in the one marker column, so every wording keeps the list's text edge.  A dashed rail runs in the
-- list's indent beside the group's markers.  The markers, rail, and muted alternative styling are
-- the template's (default_styles.typ), shared with typst_alternatives.lua's in-flow groups.
local GROUP_CLASS = "alternatives"
local SELECTED_CLASS = "selected-wording"
local ALTERNATIVE_CLASS = "alternative-wording"
-- Typst's tight-list item spacing, and the tighter spacing within a group so it reads as one unit.
local LIST_GAP = "0.65em"
local GROUP_GAP = "0.4em"

local function is_group(block)
  return block ~= nil and block.t == "Div" and block.classes:includes(GROUP_CLASS)
end

-- One grid row's four cells: two 3pt indent columns (the native list's 6pt indent, split so the
-- rail can run between them), the marker, and the body.
local function row_cells(marker, body)
  return string.format("none, none, %s, %s,", marker, body)
end

-- A list holding at least one alternatives group, as a grid.  An ordinary item keeps its glyph —
-- its classification glyph, or the default bullet — in the marker column; a versioned item
-- expands into one row per wording under a rail, and any blocks following its group (attribute
-- pills, say) take a further row, outside the rail.
local function alternatives_grid(el)
  local cells = pandoc.List()
  local lines = pandoc.List()
  local gutters = pandoc.List()
  local row = 0
  for _, item in ipairs(el.content) do
    if row > 0 then
      gutters:insert(LIST_GAP)
    end
    if is_group(item[1]) then
      local start = row
      for _, wording in ipairs(item[1].content) do
        if wording.t == "Div" and wording.classes:includes(SELECTED_CLASS) then
          if row > start then
            gutters:insert(GROUP_GAP)
          end
          cells:insert(row_cells("alternative-marker(true)", "[" .. to_typst(wording.content) .. "]"))
          row = row + 1
        elseif wording.t == "Div" and wording.classes:includes(ALTERNATIVE_CLASS) then
          if row > start then
            gutters:insert(GROUP_GAP)
          end
          cells:insert(row_cells("alternative-marker(false)", "alternative-wording[" .. to_typst(wording.content) .. "]"))
          row = row + 1
        end
      end
      lines:insert(string.format("grid.vline(x: 1, start: %d, end: %d, stroke: alternative-rail),", start, row))
      if #item > 1 then
        local rest = pandoc.List()
        for index = 2, #item do
          rest:insert(item[index])
        end
        gutters:insert(LIST_GAP)
        cells:insert(row_cells("none", "[" .. to_typst(rest) .. "]"))
        row = row + 1
      end
    else
      local glyph, body = glyph_and_body(item)
      local glyph_cell = glyph ~= nil and string.format('text(size: %s, "%s")', CLASSIFIED_GLYPH_SIZE, glyph)
        or string.format('"%s"', DEFAULT_GLYPH)
      cells:insert(row_cells(glyph_cell, "[" .. to_typst(body) .. "]"))
      row = row + 1
    end
  end
  if #gutters == 0 then
    gutters:insert(LIST_GAP)
  end
  return pandoc.RawBlock("typst", "#grid(\n"
      .. "  columns: (3pt, 3pt, auto, 1fr),\n"
      .. "  column-gutter: (0pt, 0pt, 0.5em),\n"
      .. "  row-gutter: (" .. table.concat(gutters, ", ") .. ",),\n  "
      .. table.concat(lines, "\n  ") .. (#lines > 0 and "\n  " or "")
      .. table.concat(cells, "\n  ")
      .. "\n)")
end

function BulletList(el)
  local classified = false
  for _, item in ipairs(el.content) do
    if is_group(item[1]) then
      return alternatives_grid(el)
    end
    if glyph_and_body(item) ~= nil then
      classified = true
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
    local glyph_cell
    if glyph ~= nil then
      glyph_cell = string.format('text(size: %s, "%s")', CLASSIFIED_GLYPH_SIZE, glyph)
    else
      glyph_cell = string.format('"%s"', DEFAULT_GLYPH)
    end
    cells:insert(string.format("%s, [%s],", glyph_cell, to_typst(body)))
  end
  local grid = "#grid(\n"
      .. "  columns: (auto, 1fr),\n"
      .. "  column-gutter: 0.5em,\n"
      .. "  row-gutter: 0.65em,\n  "
      .. table.concat(cells, "\n  ")
      .. "\n)"
  return pandoc.RawBlock("typst", grid)
end
