-- Separate a list item's leading text from a following non-list block for Typst output.
--
-- Pandoc emits a list item's leading text as a Plain block; the Typst writer then places only
-- a single newline before the next block.  In Typst a single newline is a space, so the text
-- and a following block (e.g. an image) collapse into one paragraph — and a wide following
-- block forces the justified text line to stretch to the block's full width.  Promoting the
-- leading Plain to a Para emits a blank line, keeping the two as separate paragraphs.
--
-- Only applied when the following block is not itself a list: a nested list already begins a
-- new block and never merges, so sibling list spacing is left untouched.

local function separate_leading_text(items)
  for _, item in ipairs(items) do
    if #item >= 2 and item[1].t == "Plain" then
      local next_type = item[2].t
      if next_type ~= "BulletList" and next_type ~= "OrderedList" then
        item[1] = pandoc.Para(item[1].content)
      end
    end
  end
end

function BulletList(el)
  separate_leading_text(el.content)
  return el
end

function OrderedList(el)
  separate_leading_text(el.content)
  return el
end
