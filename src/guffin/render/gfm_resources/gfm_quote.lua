-- gfm_quote.lua
-- Lua filter for the GFM Markdown output path.
-- Transforms the Div.fancy-quote produced by pandoc_rendering.py (a pull quote, from a Roam
-- [[>]] [[!QUOTE]] block) into a best-effort GFM block quote: a bold quotation led by an opening
-- quotation-mark ornament.  A pull quote carries no attribution: its source is the work itself.
-- Plain Markdown cannot assign fonts or scale a glyph, so the lead uses U+275D (❝) — a Dingbats
-- ornament whose largeness is baked into the font's glyph — rather than the plain U+201C the
-- PDF/EPUB paths scale up themselves.
--
-- Also unwraps a block quotation's attribution — the Div.quote-attribution closing its BlockQuote,
-- the em-dash-led source line — to its bare paragraph, the quote's last line, left-aligned with the
-- quotation; a raw <div> wrapper would be noise.

-- Remove every wrapper of type `tag` (e.g. "Strong") from an inline list, promoting its children.
-- Wrapping the whole line in `tag` makes the entire line that style, so any inner same-type wrapper
-- is redundant; stripping it first avoids degenerate nested Markdown like `**a **b** c**`.
local function unwrap(inlines, tag)
  local filter = {}
  filter[tag] = function(el)
    return el.content
  end
  return pandoc.walk_inline(pandoc.Span(inlines), filter).content
end

function Div(el)
  if el.classes:includes("quote-attribution") then
    return el.content
  end
  if not el.classes:includes("fancy-quote") then
    return nil
  end

  local quote_blocks_src = nil
  local extra = pandoc.List()
  for _, block in ipairs(el.content) do
    if block.t == "Div" and block.classes:includes("fancy-quote-text") then
      quote_blocks_src = block.content
    else
      -- Child vertices rendered inside the quote (rare); keep them after the quotation.
      extra:insert(block)
    end
  end

  local out = pandoc.List()
  -- Quotation: bold each paragraph, dropping any inner Strong so wrapping the whole paragraph in
  -- bold cannot nest degenerately; the first is led by the oversize opening quote.  Any other block
  -- (e.g. a list) passes through unchanged so no content is lost.
  for i, block in ipairs(quote_blocks_src or {}) do
    if block.t == "Para" or block.t == "Plain" then
      local inlines = pandoc.List()
      if i == 1 then
        inlines:extend({ pandoc.Str("\u{275D}"), pandoc.Space() })
      end
      inlines:extend(unwrap(block.content, "Strong"))
      out:insert(pandoc.Para({ pandoc.Strong(inlines) }))
    else
      out:insert(block)
    end
  end
  out:extend(extra)

  return pandoc.BlockQuote(out)
end
