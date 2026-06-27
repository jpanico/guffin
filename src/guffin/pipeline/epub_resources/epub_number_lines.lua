-- epub_number_lines.lua
-- Lua filter for the EPUB output path.
-- Adds the `numberLines` class to every code block so Pandoc's skylighting HTML
-- writer emits line numbers (rendered via CSS counters), matching the line
-- numbering the Typst template produces in the PDF output.

function CodeBlock(el)
  if not el.classes:includes("numberLines") then
    el.classes:insert("numberLines")
    return el
  end
end
