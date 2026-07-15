-- gfm_quote.lua
-- Lua filter for the GFM Markdown output path.
-- Transforms the Div.fancy-quote produced by pandoc_rendering.py (a decorated Roam-native
-- block quote) into a best-effort GFM block quote: a bold quotation line led by an opening
-- quotation-mark ornament, followed by an italic attribution line.  Plain Markdown cannot assign
-- fonts or scale a glyph, so the lead uses U+275D (❝) — a Dingbats ornament whose largeness is
-- baked into the font's glyph — rather than the plain U+201C the PDF/EPUB paths scale up themselves.

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
  if not el.classes:includes("fancy-quote") then
    return nil
  end

  local quote_blocks_src = nil
  local attribution_blocks = nil
  local extra = pandoc.List()
  for _, block in ipairs(el.content) do
    if block.t == "Div" and block.classes:includes("fancy-quote-text") then
      quote_blocks_src = block.content
    elseif block.t == "Div" and block.classes:includes("fancy-quote-attribution") then
      attribution_blocks = block.content
    else
      -- Child vertices rendered inside the quote (rare); keep them after the quote/attribution.
      extra:insert(block)
    end
  end

  local out = pandoc.List()
  -- Quotation: the first line is a single paragraph. Prepend an oversize opening quote and bold it,
  -- dropping any inner Strong so wrapping the whole line in bold cannot nest degenerately.
  if quote_blocks_src and quote_blocks_src[1] then
    local lead = pandoc.List({ pandoc.Str("\u{275D}"), pandoc.Space() })
    lead:extend(unwrap(quote_blocks_src[1].content, "Strong"))
    out:insert(pandoc.Para({ pandoc.Strong(lead) }))
  end
  -- Attribution: italicize the first paragraph (dropping inner Emph), and pass any further
  -- attribution blocks (e.g. a list) through unchanged so no content is lost.
  if attribution_blocks then
    for i, block in ipairs(attribution_blocks) do
      if i == 1 and (block.t == "Para" or block.t == "Plain") then
        out:insert(pandoc.Para({ pandoc.Emph(unwrap(block.content, "Emph")) }))
      else
        out:insert(block)
      end
    end
  end
  out:extend(extra)

  return pandoc.BlockQuote(out)
end
