-- typst_caption.lua
-- Lua filter for the Typst/PDF output path.
-- Transforms a Div.caption produced by pandoc_rendering.py — the caption below an image or code
-- listing (the block's own nested content), or the code-source attribution below a sourced
-- listing — into a raw Typst block styled as a caption: reduced size, muted grey, and pulled up
-- toward the block it annotates.  The content is serialized to Typst as-is.

function Div(el)
  if not el.classes:includes("caption") then
    return nil
  end
  local content = pandoc.write(pandoc.Pandoc(el.content), "typst")
  local raw = "#block(above: 0.5em)[#text(size: 0.8em, fill: luma(35%))[" .. content .. "]]"
  return pandoc.RawBlock("typst", raw)
end
