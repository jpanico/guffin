-- typst_heading_number.lua — set a heading's number from the one Guffin stamped on it.
--
-- In a parts book Guffin numbers the headings itself, by the Chicago convention (chapters counted
-- consecutively through the parts, parts in roman numerals), and stamps each numbered Header with
-- its number in the data-guffin-heading-number attribute (heading_numbering.py).  Typst's own
-- heading counter cannot count that way — stepping a part resets its chapters — so each stamped
-- Header is written as a Typst heading whose numbering is a constant function returning that
-- number.  The heading stays a real heading: it is outlined, linked by its label, and the outline
-- shows the number, since an outline entry displays its heading's numbering.
--
-- A Header without the attribute is left to the writer.

local NUMBER_ATTRIBUTE = "data-guffin-heading-number"

function Header(el)
  local number = el.attributes[NUMBER_ATTRIBUTE]
  if number == nil then
    return nil
  end
  local body = pandoc.write(pandoc.Pandoc({ pandoc.Plain(el.content) }), "typst"):gsub("%s+$", "")
  local label = ""
  if el.identifier ~= "" then
    label = "\n<" .. el.identifier .. ">"
  end
  return pandoc.RawBlock(
    "typst",
    string.format('#heading(level: %d, numbering: (..nums) => "%s")[%s]%s', el.level, number, body, label)
  )
end
