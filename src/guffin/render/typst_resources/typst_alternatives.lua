-- typst_alternatives.lua
-- Lua filter for the Typst/PDF output path.
-- Renders each alternatives group (the scaffold Div produced by pandoc_rendering.py: an
-- "alternatives" Div holding a "selected-wording" Div, then one "alternative-wording" Div per
-- alternative) as a call to the template's alternatives-group helper (default_styles.typ).
--
-- Where a group sits decides its layout:
--   * in the body's own flow (a top-level block of the document), the rail and markers hang into
--     the left margin, so the selected wording keeps the body's left edge;
--   * nested anywhere else — inside a list item, a block quote, or another Div — the margin
--     belongs to the container, so the group sits inside the text column instead;
--   * as the leading block of a bullet-list item it is left untouched: the radio marker replaces
--     that item's bullet, which takes laying out the whole list as a grid — typst_bullet.lua's job.
--
-- A wording may be a display block rather than running text: a versioned reference to an epigraph
-- renders each wording as the epigraph it references, which typst_quote.lua later turns into an
-- #epigraph call.  The alternative-wording muting then greys and shrinks the epigraph's own italic
-- display type, and the group spaces its wordings with the wider display gutter.
--
-- The group's wordings stay native Pandoc blocks between raw Typst fragments, rather than being
-- serialized here, so every later filter still reaches their content (colour spans, TODO boxes,
-- marks).  Registered FIRST among the Typst filters for the same reason: the filters that
-- serialize a container's content (callouts, captions, quotes, bullet grids) must find each
-- nested group already rewritten.

local GROUP_CLASS = "alternatives"
local SELECTED_CLASS = "selected-wording"
local ALTERNATIVE_CLASS = "alternative-wording"
local EPIGRAPH_CLASS = "epigraph"

local function is_group(block)
  return block ~= nil and block.t == "Div" and block.classes:includes(GROUP_CLASS)
end

local function is_wording(block)
  return block.t == "Div" and (block.classes:includes(SELECTED_CLASS) or block.classes:includes(ALTERNATIVE_CLASS))
end

-- Whether a wording is a display block that sets its own space around itself in the flow — an
-- epigraph, as when a versioned block's wordings are references to epigraphs.
local function is_display_wording(wording)
  local first = wording.content[1]
  return first ~= nil and first.t == "Div" and first.classes:includes(EPIGRAPH_CLASS)
end

-- The space between the group's wordings: the display gutter when any wording is a display block,
-- since inside the group's grid nothing else would separate it from its neighbours.
local function gutter(group)
  for _, wording in ipairs(group.content) do
    if is_wording(wording) and is_display_wording(wording) then
      return "alternative-display-gutter"
    end
  end
  return "alternative-gutter"
end

-- The group's raw-fragment rendering: the helper call opens, each wording's native blocks become
-- one content argument (selected first, as the scaffold orders them), and the call closes.
local function group_blocks(group, hang)
  local out = pandoc.List()
  out:insert(
    pandoc.RawBlock("typst", string.format("#alternatives-group(hang: %s, gutter: %s, [", tostring(hang), gutter(group)))
  )
  local first = true
  for _, wording in ipairs(group.content) do
    if is_wording(wording) then
      if not first then
        out:insert(pandoc.RawBlock("typst", "], ["))
      end
      out:extend(wording.content)
      first = false
    end
  end
  out:insert(pandoc.RawBlock("typst", "])"))
  return out
end

local process_blocks

-- A list's items, each processed as nested content.  In a bullet list an item's leading group is
-- kept as is, for typst_bullet.lua to lay out with the list.
local function process_items(items, bullet)
  local out = pandoc.List()
  for _, item in ipairs(items) do
    if bullet and is_group(item[1]) then
      local rest = pandoc.List()
      for index = 2, #item do
        rest:insert(item[index])
      end
      local kept = pandoc.List({ item[1] })
      kept:extend(process_blocks(rest, true))
      out:insert(kept)
    else
      out:insert(process_blocks(item, true))
    end
  end
  return out
end

-- Rewrite every group among *blocks* and their descendants; *nested* is false only for the
-- document's top-level run.
process_blocks = function(blocks, nested)
  local out = pandoc.List()
  for _, block in ipairs(blocks) do
    if is_group(block) then
      out:extend(group_blocks(block, not nested))
    else
      if block.t == "BulletList" then
        block.content = process_items(block.content, true)
      elseif block.t == "OrderedList" then
        block.content = process_items(block.content, false)
      elseif block.t == "Div" or block.t == "BlockQuote" then
        block.content = process_blocks(block.content, true)
      end
      out:insert(block)
    end
  end
  return out
end

function Pandoc(doc)
  doc.blocks = process_blocks(doc.blocks, false)
  return doc
end
