-- gfm_todo.lua
-- Lua filter for the Markdown/GFM output path.
-- A reference to a TODO item carries the item's checkbox glyph (U+2610 BALLOT BOX / U+2612
-- BALLOT BOX WITH X, stamped by pandoc_rendering.py from the vertex's TodoState) in its
-- display inlines.  Rendered bare, the glyph sits small against the surrounding text, so a
-- glyph that does NOT open its block is wrapped in an inline-styled HTML span boosting it 20%
-- (line-height pinned so the taller glyph cannot inflate the line box).  The wrapped DONE
-- glyph is displayed as U+2611 BALLOT BOX WITH CHECK, matching the checkmark GFM's native
-- task-list checkboxes render with; U+2612 stays confined to the AST, where it is the
-- task-list convention the GFM writer recognizes.
-- A glyph that IS the block's first inline is deliberately left bare: on a list item that
-- leading Str is what the GFM writer's task_lists extension converts to native checkbox
-- syntax (`- [ ]` / `- [x]`), which an HTML wrapper would defeat.

local OPEN_GLYPH = "\u{2610}"
local DONE_GLYPH = "\u{2612}"
local DONE_DISPLAY_GLYPH = "\u{2611}"

local SPAN_OPEN = '<span style="font-size: 1.2em; line-height: 1">'
local SPAN_CLOSE = '</span>'

-- Wrap every checkbox-glyph Str past the first inline of *inlines*, in place.
-- Returns true when at least one glyph was wrapped.
local function wrap_trailing_glyphs(inlines)
  local wrapped = false
  for index = 2, #inlines do
    local inline = inlines[index]
    if inline.t == "Str" and (inline.text == OPEN_GLYPH or inline.text == DONE_GLYPH) then
      local display = inline.text == DONE_GLYPH and DONE_DISPLAY_GLYPH or inline.text
      inlines[index] = pandoc.RawInline("html", SPAN_OPEN .. display .. SPAN_CLOSE)
      wrapped = true
    end
  end
  return wrapped
end

function Plain(el)
  if wrap_trailing_glyphs(el.content) then
    return el
  end
  return nil
end

function Para(el)
  if wrap_trailing_glyphs(el.content) then
    return el
  end
  return nil
end
