-- gfm_callout.lua
-- Lua filter for the GFM Markdown output path.
-- Transforms Div.callout-{type} produced by pandoc_rendering.py into a
-- GFM alert BlockQuote: > [!TYPE] / > **title** / > body...

-- Mapping from Guffin CalloutType (lowercased) to GFM alert types.
local GFM_TYPES = {
  ["callout-info"]      = "NOTE",
  ["callout-note"]      = "NOTE",
  ["callout-quote"]     = "NOTE",
  ["callout-example"]   = "NOTE",
  ["callout-summary"]   = "NOTE",
  ["callout-question"]  = "NOTE",
  ["callout-tip"]       = "TIP",
  ["callout-success"]   = "TIP",
  ["callout-warning"]   = "WARNING",
  ["callout-danger"]    = "CAUTION",
  ["callout-failure"]   = "CAUTION",
  ["callout-bug"]       = "CAUTION",
}

function Div(el)
  local gfm_type = nil
  for _, cls in ipairs(el.classes) do
    gfm_type = GFM_TYPES[cls]
    if gfm_type then break end
  end
  if not gfm_type then return nil end

  -- Separate the callout-title sub-Div from body blocks.
  local title_inlines = nil
  local body_blocks = pandoc.List()
  for _, block in ipairs(el.content) do
    if block.t == "Div" and block.classes:includes("callout-title") and title_inlines == nil then
      if #block.content > 0 and block.content[1].t == "Para" then
        title_inlines = block.content[1].content
      end
    else
      body_blocks:insert(block)
    end
  end

  -- Build the BlockQuote: marker Para + body blocks.
  local quote_blocks = pandoc.List()
  local marker = pandoc.RawInline("markdown", "[!" .. gfm_type .. "]")
  if title_inlines and #title_inlines > 0 then
    local nl = pandoc.RawInline("markdown", "\n")
    quote_blocks:insert(pandoc.Para({ marker, nl, pandoc.Strong(title_inlines) }))
  else
    quote_blocks:insert(pandoc.Para({ marker }))
  end
  for _, b in ipairs(body_blocks) do
    quote_blocks:insert(b)
  end

  return pandoc.BlockQuote(quote_blocks)
end
