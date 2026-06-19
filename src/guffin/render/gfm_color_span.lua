-- Rewrite Span elements with a "color" attribute to raw HTML <span style="color: ..."> tags for GFM output.
-- Inner inlines are passed through so nested formatting (e.g. bold) is preserved.

function Span(el)
  local color = el.attributes["color"]
  if color then
    local result = pandoc.List({pandoc.RawInline('html', '<span style="color: ' .. color .. '">')})
    result:extend(el.content)
    result:extend({pandoc.RawInline('html', '</span>')})
    return result
  end
end
