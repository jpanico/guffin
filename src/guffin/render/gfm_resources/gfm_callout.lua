-- gfm_callout.lua
-- Lua filter for the GFM Markdown output path.
-- Transforms Div.callout-{type} produced by pandoc_rendering.py into a
-- GFM alert BlockQuote: > [!TYPE] / > **title** / > body...
--
-- A GFM alert's label is fixed by its type (GitHub and Typora title a [!NOTE] box
-- "Note" and accept nothing after the marker on its line), so the callout's title
-- can only travel as a bold first body line.  That line is written only when the
-- title says something the alert's own label does not: a title that is merely the
-- callout's type keyword ("INFO", "Note") or the alert's label ("Note") is dropped,
-- since the box would otherwise carry its label twice.

-- Mapping from Guffin CalloutType (lowercased) to GFM alert types.
local GFM_TYPES = {
  ["callout-info"]      = "NOTE",
  ["callout-note"]      = "NOTE",
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

-- The title text, lowercased and trimmed, for comparison against the labels it may duplicate.
local function normalized_title(inlines)
  local text = pandoc.utils.stringify(pandoc.Para(inlines))
  return text:lower():match("^%s*(.-)%s*$")
end

-- Whether a title adds nothing beyond the alert's own label: it is the callout's type
-- keyword (the "callout-" class suffix, e.g. "info") or the GFM alert type (e.g. "note").
local function title_is_redundant(inlines, callout_class, gfm_type)
  local title = normalized_title(inlines)
  local type_keyword = callout_class:sub(#"callout-" + 1)
  return title == type_keyword or title == gfm_type:lower()
end

function Div(el)
  local gfm_type = nil
  local callout_class = nil
  for _, cls in ipairs(el.classes) do
    gfm_type = GFM_TYPES[cls]
    if gfm_type then
      callout_class = cls
      break
    end
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
  if title_inlines and #title_inlines > 0 and not title_is_redundant(title_inlines, callout_class, gfm_type) then
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
