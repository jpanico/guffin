// Report, for every list item and group wording, the x of its marker and of its first text.
const rows = [];
for (const el of document.querySelectorAll("li, div.alternatives.in-list > p")) {
  const svg = el.querySelector(":scope > svg");
  const range = document.createRange();
  const textNode = [...el.childNodes].find(n => n.nodeType === 3 && n.textContent.trim()) ||
    el.querySelector(":scope > span.alternative-text")?.firstChild;
  let textX = null;
  if (textNode) { range.setStart(textNode, 0); range.setEnd(textNode, 1); textX = range.getBoundingClientRect().x; }
  rows.push({
    tag: el.tagName.toLowerCase() + (el.closest("ul ul") ? " (nested)" : ""),
    text: el.textContent.trim().slice(0, 28),
    markerX: svg ? Math.round(svg.getBoundingClientRect().x * 10) / 10 : null,
    textX: textX === null ? null : Math.round(textX * 10) / 10,
    boxX: Math.round(el.getBoundingClientRect().x * 10) / 10,
    textIndent: getComputedStyle(el).textIndent,
  });
}
const out = document.createElementNS("http://www.w3.org/1999/xhtml", "pre");
out.id = "measure";
out.textContent = JSON.stringify(rows, null, 1);
document.body.appendChild(out);
