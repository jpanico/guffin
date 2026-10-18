-- gfm_float.lua
-- Lua filter for the GFM Markdown output path.
-- Unwraps a float — a Figure (a figure or a listing) or a captioned Table produced by
-- pandoc_rendering.py, carrying a float-<uid> identifier — into plain Markdown: the GFM writer
-- would otherwise emit a Figure as a raw HTML <figure> (an HTML island whose listing is
-- highlighted <span> soup rather than a fenced code block) and a table's caption as a stray
-- paragraph after the table with the identifier in braces.
--
-- A Figure becomes an empty <a id="float-<uid>"></a> anchor (the device heading links use, so a
-- reference's link lands on it), its content blocks, and its caption as an emphasized paragraph
-- beneath them.  A captioned Table becomes the anchor, its caption as an emphasized paragraph
-- ABOVE the table (where Chicago sets a table's title), and the table without its caption.

local FLOAT_ID_PREFIX = "float-"

local function is_float(el)
  return el.identifier ~= nil and el.identifier:sub(1, #FLOAT_ID_PREFIX) == FLOAT_ID_PREFIX
end

local function anchor(el)
  return pandoc.RawBlock("html", '<a id="' .. el.identifier .. '"></a>')
end

-- The caption's blocks as one emphasized paragraph (its inlines, joined).
local function caption_para(caption)
  local inlines = pandoc.List()
  for _, block in ipairs(caption.long or caption.content or {}) do
    if block.content then
      if #inlines > 0 then inlines:insert(pandoc.Space()) end
      inlines:extend(block.content)
    end
  end
  if #inlines == 0 then return nil end
  return pandoc.Para({ pandoc.Emph(inlines) })
end

function Figure(el)
  if not is_float(el) then return nil end
  local result = pandoc.List({ anchor(el) })
  result:extend(el.content)
  local caption = caption_para(el.caption)
  if caption then result:insert(caption) end
  return result
end

function Table(el)
  if not is_float(el) then return nil end
  local result = pandoc.List({ anchor(el) })
  local caption = caption_para(el.caption)
  if caption then result:insert(caption) end
  el.caption = pandoc.Caption({})
  el.identifier = ""
  result:insert(el)
  return result
end
