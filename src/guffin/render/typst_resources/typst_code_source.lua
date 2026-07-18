-- typst_code_source.lua
-- Lua filter for the Typst/PDF output path.
-- Transforms the Div.code-source produced by pandoc_rendering.py (the source attribution below a
-- sourced code listing) into a raw Typst block styled as a caption: reduced size, muted grey, and
-- pulled up toward the listing it annotates.  The content (an emphasized line with the GitHub
-- link) is serialized to Typst as-is.

function Div(el)
  if not el.classes:includes("code-source") then
    return nil
  end
  local content = pandoc.write(pandoc.Pandoc(el.content), "typst")
  local raw = "#block(above: 0.5em)[#text(size: 0.8em, fill: luma(35%))[" .. content .. "]]"
  return pandoc.RawBlock("typst", raw)
end
