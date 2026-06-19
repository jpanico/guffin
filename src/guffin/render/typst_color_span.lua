-- Rewrite color Span elements to raw Typst for PDF output.
-- Inner inlines are passed through so nested formatting (e.g. bold) is preserved.
--
-- Handled cases:
--   Span with "color" attribute            → #text(fill: COLOR)[...]
--   Span with class "mark" and
--     "highlight-color" attribute          → #highlight(fill: COLOR)[...]
--   Span with "underline-color" attribute  → #underline[#text(fill: COLOR)[...]]

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
end
