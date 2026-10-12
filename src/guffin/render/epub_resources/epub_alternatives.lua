-- epub_alternatives.lua
-- Lua filter for the EPUB (XHTML) output path.
-- Renders each alternatives group (the scaffold Div produced by pandoc_rendering.py: an
-- "alternatives" Div holding a "selected-wording" Div, then one "alternative-wording" Div per
-- alternative) as the treatment epub.css styles: a thin dashed rail binding the wordings, each
-- led by a drawn radio marker — filled for the selected wording, hollow for each alternative —
-- with each alternative's text muted and a touch smaller.  The markers are inline SVG, never a
-- font glyph, so no reading system's font can render them as tofu.
--
-- Where a group sits decides its form:
--   * as the leading block of a bullet-list item, the radio marker replaces that item's bullet:
--     the list is wrapped in Div.alternatives-list (epub.css suppresses its native markers), every
--     ordinary item leads with a drawn dot (or its classification glyph), and the group's wordings
--     hang their markers into the list's own indent, beside the rail — so every text edge in the
--     list lines up;
--   * anywhere else, the group sits inside the text column, the rail at the column's edge.  It
--     never hangs into the page margin: reading systems own that margin and may clip into it.
--
-- The wordings stay native Pandoc blocks (only the markers are raw), so every later filter still
-- reaches their content.  Registered FIRST among the EPUB filters: a bullet list holding a group
-- is laid out here whole — classified siblings included — before epub_bullet.lua sees it.

local GROUP_CLASS = "alternatives"
local SELECTED_CLASS = "selected-wording"
local ALTERNATIVE_CLASS = "alternative-wording"
local GLYPH_ATTRIBUTE = "data-guffin-marker-glyph"

local SVG_OPEN = '<svg class="alternative-marker" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"'
local SELECTED_MARKER = SVG_OPEN .. ' role="img" aria-label="selected wording">'
    .. '<circle cx="5" cy="5" r="4.4" fill="none" stroke="currentColor" stroke-width="1.1"/>'
    .. '<circle cx="5" cy="5" r="2.1" fill="currentColor"/></svg>'
local ALTERNATIVE_MARKER = SVG_OPEN .. ' role="img" aria-label="alternative wording">'
    .. '<circle cx="5" cy="5" r="4.4" fill="none" stroke="#737373" stroke-width="1.1"/></svg>'
-- An ordinary item's bullet, drawn at the radio markers' width so every text edge lines up.
local DOT_MARKER = SVG_OPEN .. ' aria-hidden="true"><circle cx="5" cy="5" r="2.6" fill="currentColor"/></svg>'

local function is_group(block)
  return block ~= nil and block.t == "Div" and block.classes:includes(GROUP_CLASS)
end

-- The blocks of *blocks* with *leading* inlines put at the head of the first inline block — that
-- block becoming a Para when *as_para* (each wording its own paragraph), else keeping its type (a
-- tight list item's Plain stays Plain) — or, when none opens the blocks, in a new block ahead of
-- them.  Built on a clone, so the document is never mutated in place.
local function led_by(blocks, leading, as_para)
  local out = pandoc.List(blocks):clone()
  local first = out[1]
  if first ~= nil and (first.t == "Plain" or first.t == "Para") then
    local inlines = pandoc.List(leading)
    inlines:extend(first.content)
    out[1] = (as_para or first.t == "Para") and pandoc.Para(inlines) or pandoc.Plain(inlines)
  elseif first ~= nil and first.t == "Div" and first.attributes["bg-color"] ~= nil then
    -- A whole-line background colour wraps the wording's text: the marker leads inside it.
    out[1] = pandoc.Div(led_by(first.content, leading, as_para), first.attr)
  else
    out:insert(1, as_para and pandoc.Para(leading) or pandoc.Plain(leading))
  end
  return out
end

-- An alternative wording's blocks, the first one's text muted (span.alternative-text, styled by
-- epub.css).  Built on a clone.
local function muted(blocks)
  local out = pandoc.List(blocks):clone()
  local first = out[1]
  if first ~= nil and (first.t == "Plain" or first.t == "Para") then
    out[1] = pandoc.Para({ pandoc.Span(first.content, pandoc.Attr("", { "alternative-text" })) })
  end
  return out
end

-- The group's wordings as marker-led paragraphs, selected first, in a Div with *classes*.
local function group_div(group, classes)
  local blocks = pandoc.List()
  for _, wording in ipairs(group.content) do
    if wording.t == "Div" and wording.classes:includes(SELECTED_CLASS) then
      blocks:extend(led_by(wording.content, { pandoc.RawInline("html", SELECTED_MARKER) }, true))
    elseif wording.t == "Div" and wording.classes:includes(ALTERNATIVE_CLASS) then
      blocks:extend(led_by(muted(wording.content), { pandoc.RawInline("html", ALTERNATIVE_MARKER) }, true))
    end
  end
  return pandoc.Div(blocks, pandoc.Attr("", classes))
end

-- An ordinary item's blocks led by its marker: its classification glyph (the semantic-bullet
-- scaffold dissolved, as epub_bullet.lua does) or the drawn dot.
local function ordinary_item(item)
  local first = item[1]
  if first ~= nil and first.t == "Div" and first.attributes[GLYPH_ATTRIBUTE] ~= nil then
    local body = first.content:clone()
    for index = 2, #item do
      body:insert(item[index])
    end
    local glyph = pandoc.Span({ pandoc.Str(first.attributes[GLYPH_ATTRIBUTE]) },
      pandoc.Attr("", { "bullet-glyph", "classified" }))
    return led_by(body, { glyph, pandoc.Space() }, false)
  end
  return led_by(item, { pandoc.RawInline("html", DOT_MARKER) }, false)
end

local process_blocks

local function process_item(item)
  return process_blocks(pandoc.List(item))
end

-- A bullet list holding a group, laid out whole: every item's marker in the list's indent.
local function alternatives_list(list)
  local items = pandoc.List()
  for _, item in ipairs(list.content) do
    if is_group(item[1]) then
      -- The group itself is rendered here; only the blocks following it are processed further
      -- (the rendered group still carries the group class, so it must not be processed again).
      local rest = pandoc.List()
      for index = 2, #item do
        rest:insert(item[index])
      end
      local blocks = pandoc.List({ group_div(item[1], { GROUP_CLASS, "in-list" }) })
      blocks:extend(process_blocks(rest))
      items:insert(blocks)
    else
      items:insert(ordinary_item(process_item(item)))
    end
  end
  return pandoc.Div({ pandoc.BulletList(items) }, pandoc.Attr("", { "alternatives-list" }))
end

-- Rewrite every group among *blocks* and their descendants.
process_blocks = function(blocks)
  local out = pandoc.List()
  for _, block in ipairs(blocks) do
    if is_group(block) then
      out:insert(group_div(block, { GROUP_CLASS }))
    elseif block.t == "BulletList" then
      local holds_group = false
      for _, item in ipairs(block.content) do
        if is_group(item[1]) then
          holds_group = true
        end
      end
      if holds_group then
        out:insert(alternatives_list(block))
      else
        block.content = block.content:map(process_item)
        out:insert(block)
      end
    else
      if block.t == "OrderedList" then
        block.content = block.content:map(process_item)
      elseif block.t == "Div" or block.t == "BlockQuote" then
        block.content = process_blocks(block.content)
      end
      out:insert(block)
    end
  end
  return out
end

function Pandoc(doc)
  doc.blocks = process_blocks(doc.blocks)
  return doc
end
