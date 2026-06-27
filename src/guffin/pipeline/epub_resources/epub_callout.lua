-- epub_callout.lua
-- Lua filter for the EPUB output path.
-- Prepends a type indicator (shared SVG icon + label word) to each
-- Div.callout produced by pandoc_rendering.py, as a `callout-label` sub-Div
-- styled by epub_resources/epub.css.
-- The SVG comes from pipeline/callout_icons/ (the same files the PDF path uses),
-- so both formats render an identical icon set.

-- Guffin CalloutType class -> shared icon SVG basename (matches callout_icons/<name>.svg).
local ICON = {
  ["callout-info"]      = "info",
  ["callout-note"]      = "memo",
  ["callout-quote"]     = "memo",
  ["callout-example"]   = "example",
  ["callout-summary"]   = "conclusion",
  ["callout-question"]  = "question",
  ["callout-tip"]       = "tip",
  ["callout-success"]   = "success",
  ["callout-warning"]   = "warning",
  ["callout-danger"]    = "danger",
  ["callout-failure"]   = "error",
  ["callout-bug"]       = "error",
}

-- Guffin CalloutType class -> human label word shown beside the icon.
local LABEL = {
  ["callout-info"]      = "Info",
  ["callout-note"]      = "Note",
  ["callout-quote"]     = "Quote",
  ["callout-example"]   = "Example",
  ["callout-summary"]   = "Summary",
  ["callout-question"]  = "Question",
  ["callout-tip"]       = "Tip",
  ["callout-success"]   = "Success",
  ["callout-warning"]   = "Warning",
  ["callout-danger"]    = "Danger",
  ["callout-failure"]   = "Failure",
  ["callout-bug"]       = "Bug",
}

-- Absolute path to the bundled callout_icons directory, supplied by epub_rendering.py
-- via the GUFFIN_CALLOUT_ICONS_DIR environment variable.
local function icons_dir()
  return os.getenv("GUFFIN_CALLOUT_ICONS_DIR")
end

-- Read the shared SVG for `icon_name` as inline XHTML, or nil if unavailable.
local function read_svg(icon_name)
  local dir = icons_dir()
  if not dir then return nil end
  local fh = io.open(dir .. "/" .. icon_name .. ".svg", "r")
  if not fh then return nil end
  local svg = fh:read("*a")
  fh:close()
  return (svg:gsub("[\r\n]", " "))
end

function Div(el)
  if not el.classes:includes("callout") then return nil end

  local icon_name, label
  for _, cls in ipairs(el.classes) do
    if ICON[cls] then
      icon_name = ICON[cls]
      label = LABEL[cls]
      break
    end
  end
  if not icon_name then return nil end

  local label_inlines = pandoc.List()
  local svg = read_svg(icon_name)
  if svg then
    label_inlines:insert(pandoc.RawInline("html", svg))
    label_inlines:insert(pandoc.Space())
  end
  label_inlines:insert(pandoc.Str(label))

  local label_div = pandoc.Div({ pandoc.Plain(label_inlines) }, pandoc.Attr("", { "callout-label" }))
  table.insert(el.content, 1, label_div)
  return el
end
