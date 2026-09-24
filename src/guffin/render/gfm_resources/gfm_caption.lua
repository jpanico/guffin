-- gfm_caption.lua
-- Lua filter for the GFM Markdown output path.
-- Unwraps a Div.caption produced by pandoc_rendering.py — the caption below an image or code
-- listing (the block's own nested content), or the code-source attribution below a sourced
-- listing — to its bare content, so the Markdown carries the caption's paragraphs rather than a
-- raw <div> wrapper.  Plain Markdown cannot shrink or grey the text; whatever emphasis the
-- content already carries is the whole treatment.

function Div(el)
  if not el.classes:includes("caption") then
    return nil
  end
  return el.content
end
