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
--
-- A callout whose type names its box in words leads its title with that label (the
-- Span.callout-label the shared build writes, e.g. "Definition").  The alert cannot carry
-- it, so it opens the bold first line instead: "**Definition: <title>**", or the label
-- alone when the callout has no title.

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
  ["callout-definition"] = "NOTE",
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

-- Split a title's inlines into its label (the text of a leading Span.callout-label, or nil)
-- and the title proper (the inlines after it, less the space that parts them).
local function split_label(inlines)
  if #inlines == 0 or inlines[1].t ~= "Span" or not inlines[1].classes:includes("callout-label") then
    return nil, inlines
  end
  local rest = pandoc.Inlines({})
  for i = 2, #inlines do
    if not (#rest == 0 and inlines[i].t == "Space") then
      rest:insert(inlines[i])
    end
  end
  return pandoc.utils.stringify(inlines[1]), rest
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

  local label = nil
  if title_inlines then
    label, title_inlines = split_label(title_inlines)
  end
  local shows_title = title_inlines and #title_inlines > 0
    and not title_is_redundant(title_inlines, callout_class, gfm_type)

  -- The bold first line: the label, then the title after a colon, either one alone, or none.
  local heading = pandoc.Inlines({})
  if label then
    heading:insert(pandoc.Str(shows_title and (label .. ":") or label))
    if shows_title then
      heading:insert(pandoc.Space())
    end
  end
  if shows_title then
    heading:extend(title_inlines)
  end

  -- Build the BlockQuote: marker Para + body blocks.
  local quote_blocks = pandoc.List()
  local marker = pandoc.RawInline("markdown", "[!" .. gfm_type .. "]")
  if #heading > 0 then
    local nl = pandoc.RawInline("markdown", "\n")
    quote_blocks:insert(pandoc.Para({ marker, nl, pandoc.Strong(heading) }))
  else
    quote_blocks:insert(pandoc.Para({ marker }))
  end
  for _, b in ipairs(body_blocks) do
    quote_blocks:insert(b)
  end

  return pandoc.BlockQuote(quote_blocks)
end
