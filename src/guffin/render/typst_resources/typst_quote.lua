-- typst_quote.lua
-- Lua filter for the Typst/PDF output path.
-- Transforms the Div.fancy-quote produced by pandoc_rendering.py (a pull quote, from a Roam
-- [[>]] [[!QUOTE]] block) into a call to the template's #fancy-quote helper (default_styles.typ),
-- which hangs the oversize opening mark in a left gutter and styles the quotation (bold,
-- quote-font).  A pull quote carries no attribution: its source is the work itself.
--
-- Also unwraps a block quotation's attribution — the Div.quote-attribution closing its BlockQuote,
-- the em-dash-led source line — to its bare paragraph, so it sits on a line of its own beneath the
-- quotation, left-aligned with it, and renders like any other text in the quote.
--
-- Registered LAST among the Typst filters so that any inline transforms (e.g. color spans) have
-- already rewritten the quote content before it is serialized to Typst here.

-- Serialize a list of Pandoc blocks to a Typst content string.
local function to_typst(blocks)
  return pandoc.write(pandoc.Pandoc(blocks), "typst")
end

function Div(el)
  if el.classes:includes("quote-attribution") then
    return el.content
  end
  if not el.classes:includes("fancy-quote") then
    return nil
  end

  local quote_typ = nil
  local extra = pandoc.List()
  for _, block in ipairs(el.content) do
    if block.t == "Div" and block.classes:includes("fancy-quote-text") then
      quote_typ = to_typst(block.content)
    else
      -- Child vertices rendered inside the quote (rare); keep them after the helper call.
      extra:insert(block)
    end
  end

  local raw = "#fancy-quote(" .. (quote_typ and ("quote: [" .. quote_typ .. "]") or "") .. ")"

  local result = pandoc.List({ pandoc.RawBlock("typst", raw) })
  for _, block in ipairs(extra) do
    result:insert(block)
  end
  return result
end
