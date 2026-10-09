-- typst_keep_with_next.lua
-- Lua filter for the Typst/PDF output path.
-- A text paragraph that introduces a figure-like block — an image paragraph, a table, or a
-- figure — is kept on the same page as that block.  Typst breaks pages between flow blocks,
-- and an image or table it cannot split moves whole to the next page, orphaning the lead-in
-- above it ("See the concentrating face:" at the foot of one page, the faces on the next).
-- Wrapping the lead-in in a sticky block (#block(sticky: true)) forbids a break between it
-- and the block that follows; the following block itself still breaks as its own rules allow
-- (the template makes tables breakable, images are not).  Headings need no such treatment:
-- Typst's heading block is sticky by default.
--
-- Two shapes of lead-in are recognized, in every block list the document holds (the body,
-- each list item, each cell) through the Blocks handler:
--
-- - a text Para / Plain directly followed by the figure-like block — the figure is the
--   lead-in's own child in Roam, so both sit in one list item;
-- - a bullet or ordered list whose LAST item is nothing but a text Para / Plain, directly
--   followed by the figure-like block — the figure is the lead-in's next sibling in Roam, and
--   pandoc_rendering.py closes the list around an image, leaving the text as the list's last
--   item and the image as the block after the list.  That item is split off into a list of
--   its own inside the sticky block, so the rest of the list stays free to break; an ordered
--   list's split-off item keeps its number.  A last item that holds more than its text (a
--   nested list, say) is left alone: the figure does not follow the text there.
--
-- A paragraph that is itself an image is never a lead-in, so a run of images is left to
-- break between its members.

local function is_image_paragraph(block)
  if block.t ~= "Para" and block.t ~= "Plain" then
    return false
  end
  local seen_image = false
  for _, inline in ipairs(block.content) do
    if inline.t == "Image" then
      seen_image = true
    elseif inline.t ~= "Space" and inline.t ~= "SoftBreak" and inline.t ~= "LineBreak" then
      return false
    end
  end
  return seen_image
end

local function is_figure_like(block)
  return block.t == "Figure" or block.t == "Table" or is_image_paragraph(block)
end

local function is_lead_in(block)
  return (block.t == "Para" or block.t == "Plain") and not is_image_paragraph(block)
end

local function is_list(block)
  return block.t == "BulletList" or block.t == "OrderedList"
end

-- Does the list end in an item that is nothing but a lead-in paragraph?
local function ends_in_lead_in(list)
  local last = list.content[#list.content]
  return last ~= nil and #last == 1 and is_lead_in(last[1])
end

-- The same kind of list as `list`, holding `items`; an ordered list restarts its numbering at
-- `start`.
local function list_like(list, items, start)
  if list.t == "OrderedList" then
    local attrs = list.listAttributes
    return pandoc.OrderedList(items, pandoc.ListAttributes(start, attrs.style, attrs.delimiter))
  end
  return pandoc.BulletList(items)
end

local function sticky(block)
  return {
    pandoc.RawBlock("typst", "#block(sticky: true)["),
    block,
    pandoc.RawBlock("typst", "]"),
  }
end

function Blocks(blocks)
  local out = pandoc.Blocks({})
  local changed = false
  for i, block in ipairs(blocks) do
    local following = blocks[i + 1]
    if following ~= nil and is_figure_like(following) and is_lead_in(block) then
      out:extend(sticky(block))
      changed = true
    elseif following ~= nil and is_figure_like(following) and is_list(block) and ends_in_lead_in(block) then
      local items = block.content
      local count = #items
      local start = block.t == "OrderedList" and block.listAttributes.start or 1
      if count > 1 then
        local leading = pandoc.List()
        for index = 1, count - 1 do
          leading:insert(items[index])
        end
        out:insert(list_like(block, leading, start))
      end
      out:extend(sticky(list_like(block, { items[count] }, start + count - 1)))
      changed = true
    else
      out:insert(block)
    end
  end
  if changed then
    return out
  end
  return nil
end
