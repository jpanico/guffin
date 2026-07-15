-- epub_callout.lua
-- Lua filter for the EPUB output path.
-- Prepends the shared SVG callout icon to the title of each Div.callout produced
-- by pandoc_rendering.py, mirroring the gentle-clues header (icon + title) in the
-- PDF output. The SVG comes from pipeline/callout_icons/ (the same files the PDF
-- path uses), so both formats render an identical icon set. A callout without a
-- title gets an icon-only header.

-- Guffin CalloutType class -> shared icon SVG basename (matches callout_icons/<name>.svg).
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

  local icon_name
  for _, cls in ipairs(el.classes) do
    if ICON[cls] then
      icon_name = ICON[cls]
      break
    end
  end
  if not icon_name then return nil end

  local svg = read_svg(icon_name)
  if not svg then return nil end
  local icon = pandoc.RawInline("html", svg)

  -- Prepend the icon to the existing callout-title paragraph; if the callout has no
  -- title, add an icon-only callout-title header.
  for _, block in ipairs(el.content) do
    if block.t == "Div" and block.classes:includes("callout-title") then
      if #block.content > 0 and block.content[1].t == "Para" then
        local para = block.content[1]
        local content = pandoc.List({ icon, pandoc.Space() })
        content:extend(para.content)
        para.content = content
      end
      return el
    end
  end

  local title = pandoc.Div({ pandoc.Para({ icon }) }, pandoc.Attr("", { "callout-title" }))
  table.insert(el.content, 1, title)
  return el
end
