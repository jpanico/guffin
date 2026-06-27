-- typst_callout.lua
-- Lua filter for the Typst/PDF output path.
-- Transforms Div.callout-{type} produced by pandoc_rendering.py into a
-- gentle-clues callout block (bergfink.typst imports gentle-clues:1.3.1).
-- Each gentle-clues default icon is overridden with the shared SVG from
-- pipeline/callout_icons/ (so PDF and EPUB render an identical icon set).


-- Mapping from Guffin CalloutType (lowercased) to gentle-clues function names.
-- The function name is also the basename of the shared icon SVG (e.g. "info" -> info.svg).
local TYPST_FNS = {
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

-- Absolute path to the bundled callout_icons directory, supplied by pdf_rendering.py
-- via the GUFFIN_CALLOUT_ICONS_DIR environment variable.
local function icons_dir()
  return os.getenv("GUFFIN_CALLOUT_ICONS_DIR")
end

-- Read the shared SVG for `fn_name` and return a Typst `image(bytes(...), format: "svg")`
-- expression, or nil if the icon dir / file is unavailable (gentle-clues then keeps its default).
local function icon_typst(fn_name)
  local dir = icons_dir()
  if not dir then return nil end
  local fh = io.open(dir .. "/" .. fn_name .. ".svg", "r")
  if not fh then return nil end
  local svg = fh:read("*a")
  fh:close()
  -- Collapse newlines (Typst string literals are single-line) then escape for the literal.
  svg = svg:gsub("[\r\n]", " "):gsub("\\", "\\\\"):gsub('"', '\\"')
  return 'image(bytes("' .. svg .. '"), format: "svg")'
end

function Div(el)
  local fn_name = nil
  for _, cls in ipairs(el.classes) do
    fn_name = TYPST_FNS[cls]
    if fn_name then break end
  end
  if not fn_name then return nil end

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

  -- Wrap the call in a Typst code block #{...} so that #set par rules are
  -- scoped locally and do not leak in from the bergfink template's global
  -- #set par(justify: true, first-line-indent: ...).  Inside code mode,
  -- function names and set rules have no # prefix.
  -- gentle-clues expects title as a string literal, not a content block.
  local args = {}
  if title_inlines and #title_inlines > 0 then
    local title_text = pandoc.utils.stringify(title_inlines)
    -- Escape backslash then double-quote for a Typst string literal.
    title_text = title_text:gsub("\\", "\\\\"):gsub('"', '\\"')
    args[#args + 1] = 'title: "' .. title_text .. '"'
  end
  local icon = icon_typst(fn_name)
  if icon then
    args[#args + 1] = "icon: " .. icon
  end
  local open_str = "#{\nset par(first-line-indent: 0pt, justify: false)\n"
    .. fn_name .. "(" .. table.concat(args, ", ") .. ")[\n"

  -- Return: open raw block, rendered body blocks, close raw block.
  -- The "]" closes the gentle-clues content block; "}" closes the #{...} scope.
  local result = pandoc.List({ pandoc.RawBlock("typst", open_str) })
  for _, b in ipairs(body_blocks) do
    result:insert(b)
  end
  result:insert(pandoc.RawBlock("typst", "]\n}\n"))
  return result
end