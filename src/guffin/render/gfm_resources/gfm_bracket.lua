-- Rewrite literal square brackets in Str elements to raw HTML character entities
-- (&#91; / &#93;) for GFM output. Pandoc's GFM writer would otherwise backslash-escape
-- them (\[ ... \]), which some MathJax-backed previewers (Typora) misread as LaTeX
-- display-math delimiters; the entities render as plain brackets everywhere and can
-- never be sniffed as math. Structural brackets (links, spans, code) are untouched:
-- they are not Str text.

local BRACKET_ENTITY = { ["["] = "&#91;", ["]"] = "&#93;" }

function Str(el)
  local text = el.text
  if not text:find("[%[%]]") then
    return nil
  end
  -- Brackets are single ASCII bytes, so byte-indexed splitting is UTF-8 safe.
  local result = pandoc.List({})
  local start = 1
  while true do
    local pos = text:find("[%[%]]", start)
    if pos == nil then
      if start <= #text then
        result:insert(pandoc.Str(text:sub(start)))
      end
      break
    end
    if pos > start then
      result:insert(pandoc.Str(text:sub(start, pos - 1)))
    end
    result:insert(pandoc.RawInline('html', BRACKET_ENTITY[text:sub(pos, pos)]))
    start = pos + 1
  end
  return result
end
