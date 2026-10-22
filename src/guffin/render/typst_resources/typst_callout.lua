-- typst_callout.lua
-- Lua filter for the Typst/PDF output path.
-- Transforms Div.callout-{type} produced by pandoc_rendering.py into a call of the
-- template's `callout` helper (default_styles.typ), which draws the box as a card of
-- the visual design language in the colours cfg.callout-colors holds for the kind.
-- The icon is the shared SVG from render/callout_icons/ (so PDF and EPUB render an
-- identical icon set), passed as its source text for the helper to colour.  A label the
-- shared build leads the title with (a Span.callout-label, e.g. "Definition") is passed to
-- the helper separately, which sets it on its own line above the title.

-- Mapping from Guffin CalloutType class to the icon SVG basename (e.g. "info" -> info.svg).
local ICON = {
  ["callout-info"]      = "info",
  ["callout-note"]      = "memo",
  ["callout-example"]   = "example",
  ["callout-summary"]   = "conclusion",
  ["callout-question"]  = "question",
  ["callout-tip"]       = "tip",
  ["callout-success"]   = "success",
  ["callout-warning"]   = "warning",
  ["callout-danger"]    = "danger",
  ["callout-failure"]   = "error",
  ["callout-bug"]       = "error",
  ["callout-definition"] = "book",
}

-- Absolute path to the bundled callout_icons directory, supplied by pdf_rendering.py
-- via the GUFFIN_CALLOUT_ICONS_DIR environment variable.
local function icons_dir()
  return os.getenv("GUFFIN_CALLOUT_ICONS_DIR")
end

-- Escape `text` for a Typst double-quoted string literal.
local function typst_string(text)
  return '"' .. text:gsub("\\", "\\\\"):gsub('"', '\\"') .. '"'
end

-- Read the shared SVG for `icon_name` as a Typst string literal, or nil if the icon dir /
-- file is unavailable (the helper then draws the band without an icon).
local function icon_literal(icon_name)
  local dir = icons_dir()
  if not dir then return nil end
  local fh = io.open(dir .. "/" .. icon_name .. ".svg", "r")
  if not fh then return nil end
  local svg = fh:read("*a")
  fh:close()
  -- Collapse newlines: Typst string literals are single-line.
  return typst_string((svg:gsub("[\r\n]", " ")))
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
  local icon_name = nil
  local kind = nil
  for _, cls in ipairs(el.classes) do
    if ICON[cls] then
      icon_name = ICON[cls]
      kind = cls:gsub("^callout%-", "")  -- e.g. "callout-note" -> "note"
      break
    end
  end
  if not kind then return nil end

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

  local args = { "kind: " .. typst_string(kind) }
  local label = nil
  if title_inlines then
    label, title_inlines = split_label(title_inlines)
  end
  if label then
    args[#args + 1] = "label: " .. typst_string(label)
  end
  if title_inlines and #title_inlines > 0 then
    args[#args + 1] = "title: " .. typst_string(pandoc.utils.stringify(title_inlines))
  end
  local icon = icon_literal(icon_name)
  if icon then
    args[#args + 1] = "icon: " .. icon
  end
  -- A callout with no body content (marked callout-no-body by pandoc_rendering) is its title
  -- band alone.
  if el.classes:includes("callout-no-body") then
    args[#args + 1] = "with-body: false"
  end

  -- Return: open raw block, rendered body blocks, close raw block ("]" closes the body).
  local result = pandoc.List({ pandoc.RawBlock("typst", "#callout(" .. table.concat(args, ", ") .. ")[\n") })
  for _, b in ipairs(body_blocks) do
    result:insert(b)
  end
  result:insert(pandoc.RawBlock("typst", "]\n"))
  return result
end
