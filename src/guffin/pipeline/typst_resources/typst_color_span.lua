-- Rewrite color Span and Div elements to raw Typst for PDF output.
-- Inner content is passed through so nested formatting (e.g. bold) is preserved.
--
-- Handled Span cases:
--   Span with "color" attribute            → #text(fill: COLOR)[...]
--   Span with class "mark" and
--     "highlight-color" attribute          → #highlight(fill: COLOR)[...]
--   Span with "underline-color" attribute  → #underline[#text(fill: COLOR)[...]]
--   Span with "box-color" attribute        → #box(stroke: COLOR)[...]
--   Span with class "pill"                  → #box(fill: rgb("#FF851C"), inset: (x: 0.5em), outset: (y: 0.35em), radius: 1em)[#text(fill: black, weight: "bold", size: 0.85em)[...]]
--                                              (a capsule-shaped badge; the large radius clamps to
--                                               half the box height, yielding fully rounded ends)
--
-- Handled Div cases:
--   Div with "bg-color" attribute          → #block(fill: COLOR, width: 100%)[...]

function Span(el)
  local color = el.attributes["color"]
  if color then
    local result = pandoc.List({pandoc.RawInline('typst', '#text(fill: ' .. color .. ')[')})
    result:extend(el.content)
    result:extend({pandoc.RawInline('typst', ']')})
    return result
  end

  local highlight_color = el.attributes["highlight-color"]
  if highlight_color and el.classes:includes("mark") then
    local result = pandoc.List({pandoc.RawInline('typst', '#highlight(fill: ' .. highlight_color .. ')[')})
    result:extend(el.content)
    result:extend({pandoc.RawInline('typst', ']')})
    return result
  end

  local underline_color = el.attributes["underline-color"]
  if underline_color then
    local result = pandoc.List({pandoc.RawInline('typst', '#underline[#text(fill: ' .. underline_color .. ')[')})
    result:extend(el.content)
    result:extend({pandoc.RawInline('typst', ']]')})
    return result
  end

  local box_color = el.attributes["box-color"]
  if box_color then
    local result = pandoc.List({pandoc.RawInline('typst', '#box(stroke: ' .. box_color .. ')[')})
    result:extend(el.content)
    result:extend({pandoc.RawInline('typst', ']')})
    return result
  end

  if el.classes:includes("pill") then
    local result = pandoc.List({pandoc.RawInline('typst', '#box(fill: rgb("#FF851C"), inset: (x: 0.5em), outset: (y: 0.35em), radius: 1em)[#text(fill: black, weight: "bold", size: 0.85em)[')})
    result:extend(el.content)
    result:extend({pandoc.RawInline('typst', ']]')})
    return result
  end
end

function Div(el)
  local bg_color = el.attributes["bg-color"]
  if bg_color then
    local result = pandoc.List({pandoc.RawBlock('typst', '#block(fill: ' .. bg_color .. ', width: 100%)[')})
    result:extend(el.content)
    result:extend({pandoc.RawBlock('typst', ']')})
    return result
  end
end
