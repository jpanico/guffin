-- Rewrite Span elements with a "color" attribute to Typst #text(fill: COLOR)[...] for PDF output.
-- Inner inlines are passed through so nested formatting (e.g. bold) is preserved.

function Span(el)
  local color = el.attributes["color"]
  if color then
    local result = pandoc.List({pandoc.RawInline('typst', '#text(fill: ' .. color .. ')[')})
    result:extend(el.content)
    result:extend({pandoc.RawInline('typst', ']')})
    return result
  end
end
