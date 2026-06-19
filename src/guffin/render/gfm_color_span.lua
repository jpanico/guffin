-- Rewrite color Span elements to raw HTML for GFM output.
-- Inner inlines are passed through so nested formatting (e.g. bold) is preserved.
--
-- Handled cases:
--   Span with "color" attribute       → <span style="color: COLOR">...</span>
--   Span with class "mark" and
--     "highlight-color" attribute     → <mark style="background-color: COLOR">...</mark>

function Span(el)
  local color = el.attributes["color"]
  if color then
    local result = pandoc.List({pandoc.RawInline('html', '<span style="color: ' .. color .. '">')})
    result:extend(el.content)
    result:extend({pandoc.RawInline('html', '</span>')})
    return result
  end

  local highlight_color = el.attributes["highlight-color"]
  if highlight_color and el.classes:includes("mark") then
    local result = pandoc.List({pandoc.RawInline('html', '<mark style="background-color: ' .. highlight_color .. '">')})
    result:extend(el.content)
    result:extend({pandoc.RawInline('html', '</mark>')})
    return result
  end
end
