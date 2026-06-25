-- Rewrite Span elements with class "mark" to raw HTML <mark> tags for GFM output.
-- Inner inlines are passed through so nested formatting is preserved.

function Span(el)
  if el.classes:includes("mark") then
    local result = pandoc.List({pandoc.RawInline('html', '<mark>')})
    result:extend(el.content)
    result:extend({pandoc.RawInline('html', '</mark>')})
    return result
  end
end
