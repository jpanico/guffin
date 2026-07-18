-- gfm_code_source.lua
-- Lua filter for the GFM Markdown output path.
-- Unwraps the Div.code-source produced by pandoc_rendering.py (the source attribution below a
-- sourced code listing) to its bare content, so the Markdown carries the already-emphasized
-- attribution line rather than a raw <div> wrapper.  Plain Markdown cannot shrink or grey the
-- line; the italic emphasis the line already carries is the whole treatment.

function Div(el)
  if not el.classes:includes("code-source") then
    return nil
  end
  return el.content
end
