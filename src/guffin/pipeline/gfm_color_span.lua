-- Rewrite color Span and Div elements to raw HTML for GFM output.
-- Inner content is passed through so nested formatting (e.g. bold) is preserved.
--
-- Handled Span cases:
--   Span with "color" attribute            → <span style="color: COLOR">...</span>
--   Span with class "mark" and
--     "highlight-color" attribute          → <mark style="background-color: COLOR">...</mark>
--   Span with "underline-color" attribute  → <span style="text-decoration: underline; color: COLOR">...</span>
--   Span with "box-color" attribute        → <span style="border: 1px solid COLOR; padding: 2px 4px">...</span>
--
-- Handled Div cases:
--   Div with "bg-color" attribute          → <span style="background-color: COLOR">...</span>
--     (uses span rather than div: Typora does not render block-level HTML in list items)

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

  local underline_color = el.attributes["underline-color"]
  if underline_color then
    local result = pandoc.List({pandoc.RawInline('html', '<span style="text-decoration: underline; color: ' .. underline_color .. '">')})
    result:extend(el.content)
    result:extend({pandoc.RawInline('html', '</span>')})
    return result
  end

  local box_color = el.attributes["box-color"]
  if box_color then
    local result = pandoc.List({pandoc.RawInline('html', '<span style="border: 1px solid ' .. box_color .. '; padding: 2px 4px">')})
    result:extend(el.content)
    result:extend({pandoc.RawInline('html', '</span>')})
    return result
  end
end

function Div(el)
  local bg_color = el.attributes["bg-color"]
  if bg_color then
    local inner_inlines = pandoc.List()
    for _, block in ipairs(el.content) do
      if block.t == "Para" or block.t == "Plain" then
        inner_inlines:extend(block.content)
      end
    end
    local result = pandoc.List({pandoc.RawInline('html', '<span style="background-color: ' .. bg_color .. '">')})
    result:extend(inner_inlines)
    result:extend({pandoc.RawInline('html', '</span>')})
    return pandoc.Para(result)
  end
end
