# Test Article 1

> [!NOTE]
> **THIS PAGE IS USED FOR TESTING [GUFFIN](https://github.com/jpanico/guffin) – DO NOT REMOVE**
>
> Features:
>
> - Page is completely self-contained – there are `no Roam embeds` of any kind
> - 3 top-level `headers`, all H1
> - nested `headers` down to H4, via *Augmented Headings* extension
> - a node, (Ma5KGUH9O) “AI assistant (Claude Opus 4.6):” that has property: BLOCK_HEADING = 0, which is not a valid Markdown level. It seems that this can happen when first a valid level value (1-6) is assigned, and then the heading level is removed altogether through the Roam UI.
> - a single JPEG `image` that **has not** been resized through the Roam UI (illustration 1.1)
> - a single JPEG `image` that **has** been resized through the Roam UI (illustration 2.1)
> - this INFO `Callout box`, which contains Roam `page references`

# Section 1

## Section 1.1

### illustration 1.1

- this image **has not been resized** through the Roam UI.
  <img src="flower.jpeg" style="margin: 0;">

<img src="flower-1.jpeg" alt="A flower" style="margin: 0;">

- AI assistant (Claude Opus 4.6):

# Section 2

## Section 2.1

### illustration 2.1

- this image **has been resized** through the Roam UI (width:257, height:None)

<img src="flower-2.jpeg" width="257" style="margin: 0;">

### Section 2.1.1

#### Section 2.1.1.1

## Section 2.2

# Section 3

## Section 3.1

- the following block contains the canonical w3.org “Dummy” PDF file: https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf

[dummy.pdf](dummy.pdf "dummy.pdf")
