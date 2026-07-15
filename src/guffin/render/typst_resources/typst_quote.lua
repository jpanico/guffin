-- typst_quote.lua
-- Lua filter for the Typst/PDF output path.
-- Transforms the Div.fancy-quote produced by pandoc_rendering.py (a pull quote, from a Roam
-- [[>]] [[!QUOTE]] block) into a call to the template's #fancy-quote helper (default_styles.typ),
-- which hangs the oversize opening mark in a left gutter and styles the quotation line (bold,
-- quote-font) and the attribution line(s) (italic, attribution-font).
--
-- Registered LAST among the Typst filters so that any inline transforms (e.g. color spans) have
-- already rewritten the quote/attribution content before it is serialized to Typst here.

-- Serialize a list of Pandoc blocks to a Typst content string.
local function to_typst(blocks)
  return pandoc.write(pandoc.Pandoc(blocks), "typst")
end

function Div(el)
  if not el.classes:includes("fancy-quote") then
    return nil
  end

  local quote_typ = nil
  local attribution_typ = nil
  local extra = pandoc.List()
  for _, block in ipairs(el.content) do
    if block.t == "Div" and block.classes:includes("fancy-quote-text") then
      quote_typ = to_typst(block.content)
    elseif block.t == "Div" and block.classes:includes("fancy-quote-attribution") then
      attribution_typ = to_typst(block.content)
    else
      -- Child vertices rendered inside the quote (rare); keep them after the helper call.
      extra:insert(block)
    end
  end

  local args = pandoc.List()
  if quote_typ then
    args:insert("quote: [" .. quote_typ .. "]")
  end
  if attribution_typ then
    args:insert("attribution: [" .. attribution_typ .. "]")
  end
  local raw = "#fancy-quote(" .. table.concat(args, ", ") .. ")"

  local result = pandoc.List({ pandoc.RawBlock("typst", raw) })
  for _, block in ipairs(extra) do
    result:insert(block)
  end
  return result
end
