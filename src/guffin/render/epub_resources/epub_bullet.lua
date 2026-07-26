-- epub_bullet.lua
-- Lua filter for the EPUB output path.
-- Transforms a BulletList containing semantic-classified items (the scaffold Div produced by
-- pandoc_rendering.py, stamped with data-guffin-semantic / data-guffin-semantic-glyph) so each
-- item's glyph stands where the list marker was: the list is wrapped in a Div.semantic-bullets
-- (epub.css suppresses its native markers via list-style: none — no ::marker and no :has(),
-- which the Kindle app's renderer does not support) and every item's content is led by a
-- bullet-glyph Span carrying the item's glyph.  Unclassified items in the same list get the
-- plain default bullet, keeping the run visually one uniform list.

local GLYPH_ATTRIBUTE = "data-guffin-semantic-glyph"
local SEMANTIC_ATTRIBUTE = "data-guffin-semantic"
-- The plain bullet for unclassified items listed among classified ones; mirrors
-- DEFAULT_BULLET_GLYPH in render/semantic_theme.py.
local DEFAULT_GLYPH = "•"

-- Return the item's glyph (or nil when unclassified) and its body blocks, the scaffold Div
-- dissolved.
local function glyph_and_body(item)
  local first = item[1]
  if first == nil or first.t ~= "Div" or first.attributes[GLYPH_ATTRIBUTE] == nil then
    return nil, item
  end
  local body = pandoc.List(first.content)
  for index = 2, #item do
    body:insert(item[index])
  end
  return first.attributes[GLYPH_ATTRIBUTE], body
end

-- Lead the first inline-bearing block of `body` with a bullet-glyph Span; prepend a new Plain
-- when the body opens with a non-inline block.
local function lead_with_glyph(body, glyph)
  local span = pandoc.Span({ pandoc.Str(glyph) }, pandoc.Attr("", { "bullet-glyph" }))
  local first = body[1]
  if first ~= nil and (first.t == "Plain" or first.t == "Para") then
    first.content:insert(1, pandoc.Space())
    first.content:insert(1, span)
  else
    body:insert(1, pandoc.Plain({ span }))
  end
end

function BulletList(el)
  local classified = false
  for _, item in ipairs(el.content) do
    if glyph_and_body(item) ~= nil then
      classified = true
      break
    end
  end
  if not classified then
    return nil
  end
  local items = pandoc.List()
  for _, item in ipairs(el.content) do
    local glyph, body = glyph_and_body(item)
    lead_with_glyph(body, glyph or DEFAULT_GLYPH)
    items:insert(body)
  end
  return pandoc.Div({ pandoc.BulletList(items) }, pandoc.Attr("", { "semantic-bullets" }))
end
