-- epub_number_lines.lua
-- Lua filter for the EPUB output path.
-- Adds the `numberLines` class to every code block so Pandoc's skylighting HTML
-- writer emits per-line spans with line identities, matching the line numbering
-- the Typst template produces in the PDF output. Skylighting renders the numbers
-- via CSS counters; after packaging, epub_post_processing.bake_code_line_numbers
-- rewrites them into literal text for reading systems (notably the Kindle app)
-- that do not implement the counter/positioning CSS.

function CodeBlock(el)
  if not el.classes:includes("numberLines") then
    el.classes:insert("numberLines")
    return el
  end
end
