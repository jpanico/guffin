-- Rewrite Image elements to raw HTML <img> tags for GFM output.
-- Width and height are read from the image's Pandoc attributes (set by the
-- Python rendering layer from ImageVertex.scaled_image_size).

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
  return pandoc.RawInline('html', tag .. '>')
end
