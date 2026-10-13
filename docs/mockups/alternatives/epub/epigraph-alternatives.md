---
title: Epigraph alternatives — EPUB styling mockup
lang: en
---

# Epigraph alternatives — EPUB styling mockup

*Sample: Test Article 3's version group, the same as the PDF mockup: the Dijkstra epigraph
selected, the two Perlis lines its alternatives. First the chapter opening as it renders today,
then variant E1.*

## Reference — no alternatives

```{=html}
<div class="epigraph" epub:type="epigraph">
<div class="epigraph-text"><p>The question of whether Machines Can Think … is about as relevant as the question of whether Submarines Can Swim.</p></div>
<div class="epigraph-attribution"><p>—Edsger Dijkstra</p></div>
</div>
```

Chapter body text resumes here in ordinary flow. A good treatment lets a reader see at once
which epigraph opens the chapter, while the candidates remain legible for the author weighing
them.

## E1 — Full epigraphs, muted alternatives (inset; chosen)

```{=html}
<div class="alternatives epigraph-alternatives">
<div class="wording">
<div class="epigraph" epub:type="epigraph">
<div class="epigraph-text"><p><svg class="alternative-marker" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" aria-label="selected wording"><circle cx="5" cy="5" r="4.4" fill="none" stroke="currentColor" stroke-width="1.1"/><circle cx="5" cy="5" r="2.1" fill="currentColor"/></svg>The question of whether Machines Can Think … is about as relevant as the question of whether Submarines Can Swim.</p></div>
<div class="epigraph-attribution"><p>—Edsger Dijkstra</p></div>
</div>
</div>
<div class="wording">
<div class="epigraph">
<div class="epigraph-text"><p><svg class="alternative-marker" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" aria-label="alternative wording"><circle cx="5" cy="5" r="4.4" fill="none" stroke="#737373" stroke-width="1.1"/></svg><span class="alternative-text">Within a computer natural language is unnatural.</span></p></div>
<div class="epigraph-attribution"><p><span class="alternative-text">—Alan Perlis</span></p></div>
</div>
</div>
<div class="wording">
<div class="epigraph">
<div class="epigraph-text"><p><svg class="alternative-marker" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" aria-label="alternative wording"><circle cx="5" cy="5" r="4.4" fill="none" stroke="#737373" stroke-width="1.1"/></svg><span class="alternative-text">Programming is an unnatural act.</span></p></div>
<div class="epigraph-attribution"><p><span class="alternative-text">—Alan Perlis</span></p></div>
</div>
</div>
</div>
```

Chapter body text resumes here in ordinary flow. A good treatment lets a reader see at once
which epigraph opens the chapter, while the candidates remain legible for the author weighing
them.
