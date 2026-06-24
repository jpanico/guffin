-- Rewrite Image elements to raw HTML <img> tags for GFM output.
-- Width and height are read from the image's Pandoc attributes (set by the
-- Python rendering layer from ImageVertex.scaled_image_size).
--
-- An inline `style="margin: 0"` is always emitted to keep images left-justified.  Typora
-- (and renderers sharing its convention) center an image that is the only child of its
-- paragraph via `p > img:only-child { display: block; margin: auto }`.  Even a bare <img>
-- hits this rule because the renderer wraps a loose image in a paragraph.  The inline margin
-- overrides that auto-centering — inline styles beat the (non-!important) stylesheet rule —
-- so a standalone image renders left, matching an image that sits inline within a block.
-- The style is harmless for inline images, whose margins are already zero.

function Image(el)
  local tag = string.format('<img src="%s"', el.src)
  local alt = pandoc.utils.stringify(el.caption)
  if alt ~= "" then
    tag = tag .. string.format(' alt="%s"', alt)
  end
  if el.attributes.width then
    tag = tag .. string.format(' width="%s"', el.attributes.width)
  end
  if el.attributes.height then
    tag = tag .. string.format(' height="%s"', el.attributes.height)
  end
  tag = tag .. ' style="margin: 0;"'
  return pandoc.RawInline('html', tag .. '>')
end
