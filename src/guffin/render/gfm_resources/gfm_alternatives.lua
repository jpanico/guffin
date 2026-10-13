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
-- A group whose every wording is a quotation — as when a versioned block's wordings are references
-- to epigraphs, each rendered as the epigraph it references, which gfm_quote.lua has by now made a
-- block quote — becomes ONE block quote instead, whose bar binds the candidates: a paragraph per
-- wording, the quotation then a hard break then its source, led by the glyph, each alternative's
-- lines muted a step lighter than the quote's own grey.
--
-- Any other wording that is not a single inline block (one holding a fenced code block, say)
-- cannot join a line-per-wording block, so such a group falls back to its wordings' blocks in
-- sequence, each led by its glyph the same way.
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
local QUOTE_MUTED_OPEN = '<span style="color: #a0a0a0; font-size: 0.93em">'

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

-- Whether *blocks* is one block quote of inline blocks only — the form gfm_quote.lua (registered
-- earlier) gives an epigraph or any other quotation, as when a versioned block's wordings are
-- references to epigraphs.
local function is_quotation(blocks)
  if #blocks ~= 1 or blocks[1].t ~= "BlockQuote" then
    return false
  end
  for _, block in ipairs(blocks[1].content) do
    if not is_inline_block(block) then
      return false
    end
  end
  return true
end

-- An alternative's lines inside a block quote, each muted on its own: the quote's own text is
-- already grey in GitHub and Typora's default theme, so QUOTE_MUTED_OPEN is a step lighter.
-- Each line between hard breaks gets its own span, as an inline span cannot open across one.
local function muted_lines(inlines)
  local out = pandoc.List({ pandoc.RawInline("html", QUOTE_MUTED_OPEN) })
  for _, inline in ipairs(inlines) do
    if inline.t == "LineBreak" then
      out:extend({ pandoc.RawInline("html", MUTED_CLOSE), inline, pandoc.RawInline("html", QUOTE_MUTED_OPEN) })
    else
      out:insert(inline)
    end
  end
  out:insert(pandoc.RawInline("html", MUTED_CLOSE))
  return out
end

-- A group of quotations as ONE block quote, its bar binding the candidates as the rail does in the
-- paginated formats: one paragraph per wording, the quotation's paragraphs (the epigraph's
-- quotation, then its source line) joined by hard breaks and led by the wording's glyph, each
-- alternative's lines muted.
local function quotation_group(wordings)
  local paragraphs = pandoc.List()
  for _, wording in ipairs(wordings) do
    local inlines = pandoc.List({ pandoc.Str(wording.glyph), pandoc.Space() })
    for index, block in ipairs(wording.blocks[1].content) do
      if index > 1 then
        inlines:insert(pandoc.LineBreak())
      end
      inlines:extend(block.content)
    end
    paragraphs:insert(pandoc.Para(wording.alternative and muted_lines(inlines) or inlines))
  end
  return pandoc.BlockQuote(paragraphs)
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
  local quotations = true
  for _, wording in ipairs(wordings) do
    if #wording.blocks ~= 1 or not is_inline_block(wording.blocks[1]) then
      mergeable = false
    end
    if not is_quotation(wording.blocks) then
      quotations = false
    end
  end

  if quotations then
    return quotation_group(wordings)
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
