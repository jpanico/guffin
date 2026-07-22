-- typst_page_break.lua
-- Lua filter for the Typst/PDF output path.
-- A Header carrying the page-break-before class (stamped by pandoc_rendering.py from an authored
-- page-break:: before tag) opens on a new page: a raw Typst pagebreak is prepended ahead of the
-- heading.  The break is weak, so a heading already at the top of a page gains no blank page.
-- The class is consumed here (removed from the Header); Typst has no use for it downstream.

function Header(el)
  if not el.classes:includes("page-break-before") then
    return nil
  end
  el.classes = el.classes:filter(function(cls) return cls ~= "page-break-before" end)
  return { pandoc.RawBlock("typst", "#pagebreak(weak: true)"), el }
end
