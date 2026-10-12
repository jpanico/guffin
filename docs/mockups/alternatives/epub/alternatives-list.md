---
title: Alternatives in a list item — EPUB mockup
lang: en
---

# Alternatives in a list item — EPUB mockup

*PDF variant L1 carried into EPUB: the radio marker replaces the item's bullet, every wording
keeps the list's text edge, and the dashed rail runs in the list indent beside the markers.
First, an ordinary list, untouched, to compare the text edge against.*

- The chair opened the meeting and confirmed that a quorum was present.
- The committee met on Thursday and, after a long and occasionally heated discussion, agreed to postpone the vote until the full budget figures were available.
- The treasurer will circulate the revised figures to every member before the next meeting, with the variance against last year's budget highlighted.

## L1 — The radio marker replaces the bullet

*The list's native markers are suppressed; the siblings get a drawn dot, so every marker has
the same width and every text edge lines up.*

```{=html}
<div class="alternatives-list">
<ul>
<li><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" aria-hidden="true"><circle cx="5" cy="5" r="2.6" fill="currentColor"/></svg>The chair opened the meeting and confirmed that a quorum was present.</li>
<li><div class="alternatives in-list">
<p><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" aria-label="selected wording"><circle cx="5" cy="5" r="4.4" fill="none" stroke="currentColor" stroke-width="1.1"/><circle cx="5" cy="5" r="2.1" fill="currentColor"/></svg>The committee met on Thursday and, after a long and occasionally heated discussion, agreed to postpone the vote until the full budget figures were available.</p>
<p><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" aria-label="alternative wording"><circle cx="5" cy="5" r="4.4" fill="none" stroke="#737373" stroke-width="1.1"/></svg><span class="alternative-text">On Thursday the committee met and, after <em>much</em> debate, voted to defer the decision until it had seen the full budget figures.</span></p>
<p><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" aria-label="alternative wording"><circle cx="5" cy="5" r="4.4" fill="none" stroke="#737373" stroke-width="1.1"/></svg><span class="alternative-text">The committee's Thursday meeting ended without a vote: members wanted the <strong>complete</strong> budget figures before committing either way.</span></p>
</div></li>
<li><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" aria-hidden="true"><circle cx="5" cy="5" r="2.6" fill="currentColor"/></svg>The treasurer will circulate the revised figures to every member before the next meeting, with the variance against last year's budget highlighted.</li>
</ul>
</div>
```

## L1, one level down

*The rewritten list nested in an ordinary item. Its siblings keep the drawn dot at every
depth — as guffin's semantic bullets keep "•" — rather than the reading system's depth-2
marker, which is usually a hollow ◦ that would read as an alternative's ○.*

```{=html}
<ul>
<li>Items carried over from the previous meeting:
<div class="alternatives-list">
<ul>
<li><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" aria-hidden="true"><circle cx="5" cy="5" r="2.6" fill="currentColor"/></svg>The chair opened the meeting and confirmed that a quorum was present.</li>
<li><div class="alternatives in-list">
<p><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" aria-label="selected wording"><circle cx="5" cy="5" r="4.4" fill="none" stroke="currentColor" stroke-width="1.1"/><circle cx="5" cy="5" r="2.1" fill="currentColor"/></svg>The committee met on Thursday and, after a long and occasionally heated discussion, agreed to postpone the vote until the full budget figures were available.</p>
<p><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" aria-label="alternative wording"><circle cx="5" cy="5" r="4.4" fill="none" stroke="#737373" stroke-width="1.1"/></svg><span class="alternative-text">On Thursday the committee met and, after <em>much</em> debate, voted to defer the decision until it had seen the full budget figures.</span></p>
<p><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" aria-label="alternative wording"><circle cx="5" cy="5" r="4.4" fill="none" stroke="#737373" stroke-width="1.1"/></svg><span class="alternative-text">The committee's Thursday meeting ended without a vote: members wanted the <strong>complete</strong> budget figures before committing either way.</span></p>
</div></li>
<li><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" aria-hidden="true"><circle cx="5" cy="5" r="2.6" fill="currentColor"/></svg>The treasurer will circulate the revised figures to every member before the next meeting, with the variance against last year's budget highlighted.</li>
</ul>
</div>
</li>
</ul>
```
