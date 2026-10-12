---
title: Alternatives — EPUB styling mockup
lang: en
---

# Alternatives — EPUB styling mockup

*Sample: one sentence with three wordings, the first selected — the same group as the PDF
mockup. The block quote below is guffin's EPUB block quote, shown for contrast.*

> A block quote, for comparison: 3px solid light-grey bar, italic text.

## C1 — Hanging into the margin (faithful to the PDF)

*Rail and markers sit outside the text column; the selected wording keeps the body's left
edge. Depends on the reading system not clipping content pulled into its page margin.*

The paragraph before the group sits in ordinary body flow, so the eye arrives at the group
from normal reading and can judge how much it interrupts the page.

```{=html}
<div class="alternatives hang-into-margin">
<p><svg class="alternative-marker" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" aria-label="selected wording"><circle cx="5" cy="5" r="4.4" fill="none" stroke="currentColor" stroke-width="1.1"/><circle cx="5" cy="5" r="2.1" fill="currentColor"/></svg>The committee met on Thursday and, after a long and occasionally heated discussion, agreed to postpone the vote until the full budget figures were available.</p>
<p><svg class="alternative-marker" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" aria-label="alternative wording"><circle cx="5" cy="5" r="4.4" fill="none" stroke="#737373" stroke-width="1.1"/></svg><span class="alternative-text">On Thursday the committee met and, after <em>much</em> debate, voted to defer the decision until it had seen the full budget figures.</span></p>
<p><svg class="alternative-marker" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" aria-label="alternative wording"><circle cx="5" cy="5" r="4.4" fill="none" stroke="#737373" stroke-width="1.1"/></svg><span class="alternative-text">The committee's Thursday meeting ended without a vote: members wanted the <strong>complete</strong> budget figures before committing either way.</span></p>
</div>
```

The paragraph after the group resumes ordinary flow. A good treatment lets a reader skim
straight past the alternatives while still seeing at a glance which wording is the one in
force.

## C2 — Inset (recommended for EPUB)

*Same look, but the whole group sits inside the text column: the rail at the body's left
edge, the wordings indented past the markers. Nothing depends on the page margin.*

The paragraph before the group sits in ordinary body flow, so the eye arrives at the group
from normal reading and can judge how much it interrupts the page.

```{=html}
<div class="alternatives">
<p><svg class="alternative-marker" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" aria-label="selected wording"><circle cx="5" cy="5" r="4.4" fill="none" stroke="currentColor" stroke-width="1.1"/><circle cx="5" cy="5" r="2.1" fill="currentColor"/></svg>The committee met on Thursday and, after a long and occasionally heated discussion, agreed to postpone the vote until the full budget figures were available.</p>
<p><svg class="alternative-marker" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" aria-label="alternative wording"><circle cx="5" cy="5" r="4.4" fill="none" stroke="#737373" stroke-width="1.1"/></svg><span class="alternative-text">On Thursday the committee met and, after <em>much</em> debate, voted to defer the decision until it had seen the full budget figures.</span></p>
<p><svg class="alternative-marker" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" aria-label="alternative wording"><circle cx="5" cy="5" r="4.4" fill="none" stroke="#737373" stroke-width="1.1"/></svg><span class="alternative-text">The committee's Thursday meeting ended without a vote: members wanted the <strong>complete</strong> budget figures before committing either way.</span></p>
</div>
```

The paragraph after the group resumes ordinary flow. A good treatment lets a reader skim
straight past the alternatives while still seeing at a glance which wording is the one in
force.
