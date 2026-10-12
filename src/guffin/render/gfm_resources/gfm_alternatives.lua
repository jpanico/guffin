-- gfm_alternatives.lua
-- Lua filter for the Markdown (GFM) output path.
-- Renders each alternatives group (the scaffold Div produced by pandoc_rendering.py: an
-- "alternatives" Div holding a "selected-wording" Div, then one "alternative-wording" Div per
-- alternative) as ONE block — a paragraph, or the list item's text — with one line per wording,
-- the lines joined by hard breaks so the group reads as a tight unit.  A radio glyph leads each
-- line: ◉ the selected wording, ○ each alternative, whose line is wrapped in an inline-styled
-- <span> muting it (grey, a touch smaller).  Markdown can draw no rail, and GitHub strips the
-- span's style, so the glyphs alone carry the selection there; Typora honours the style.
--
-- A wording that is not a single inline block (one holding a fenced code block, say) cannot join
-- a line-per-wording block, so such a group falls back to its wordings' blocks in sequence, each
-- led by its glyph the same way.
--
-- Registered after gfm_color_span.lua, which has by then turned a whole-line background colour
-- into an inline span within a paragraph, so a coloured wording is still one inline block here.

local GROUP_CLASS = "alternatives"
local SELECTED_CLASS = "selected-wording"
local ALTERNATIVE_CLASS = "alternative-wording"

local SELECTED_GLYPH = "◉"
local ALTERNATIVE_GLYPH = "○"
local MUTED_OPEN = '<span style="color: #737373; font-size: 0.93em">'
local MUTED_CLOSE = "</span>"

-- One wording's line: its glyph, then its inlines; an alternative's line wrapped in the muting span.
local function line(glyph, inlines, alternative)
  local out = pandoc.List()
  if alternative then
    out:insert(pandoc.RawInline("html", MUTED_OPEN))
  end
  out:extend({ pandoc.Str(glyph), pandoc.Space() })
  out:extend(inlines)
  if alternative then
    out:insert(pandoc.RawInline("html", MUTED_CLOSE))
  end
  return out
end

local function is_inline_block(block)
  return block.t == "Plain" or block.t == "Para"
end

function Div(el)
  if not el.classes:includes(GROUP_CLASS) then
    return nil
  end
  local wordings = pandoc.List()
  for _, wording in ipairs(el.content) do
    if wording.t == "Div" and wording.classes:includes(SELECTED_CLASS) then
      wordings:insert({ glyph = SELECTED_GLYPH, blocks = wording.content, alternative = false })
    elseif wording.t == "Div" and wording.classes:includes(ALTERNATIVE_CLASS) then
      wordings:insert({ glyph = ALTERNATIVE_GLYPH, blocks = wording.content, alternative = true })
    end
  end
  if #wordings == 0 then
    return nil
  end

  local mergeable = true
  for _, wording in ipairs(wordings) do
    if #wording.blocks ~= 1 or not is_inline_block(wording.blocks[1]) then
      mergeable = false
    end
  end

  if mergeable then
    -- One block, the selected wording's type (Plain in a list item, Para in flow).
    local inlines = pandoc.List()
    for index, wording in ipairs(wordings) do
      if index > 1 then
        inlines:insert(pandoc.LineBreak())
      end
      inlines:extend(line(wording.glyph, wording.blocks[1].content, wording.alternative))
    end
    return wordings[1].blocks[1].t == "Plain" and pandoc.Plain(inlines) or pandoc.Para(inlines)
  end

  -- Fallback: each wording's blocks in sequence, its first inline block led by its glyph.
  local out = pandoc.List()
  for _, wording in ipairs(wordings) do
    local first = wording.blocks[1]
    if first ~= nil and is_inline_block(first) then
      out:insert(pandoc.Para(line(wording.glyph, first.content, wording.alternative)))
      for index = 2, #wording.blocks do
        out:insert(wording.blocks[index])
      end
    else
      out:insert(pandoc.Para(line(wording.glyph, {}, wording.alternative)))
      out:extend(wording.blocks)
    end
  end
  return out
end
