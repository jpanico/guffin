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
> - a pair of JPEG `image`s that **have not** been resized through the Roam UI (illustration 1.1)
> - a single JPEG `image` that **has** been resized through the Roam UI (illustration 2.1)
> - an embedded PDF document that has no special PublishingSemantics Attributes attached
> - an embedded PDF document that has `guffin-meta:: pdf-render: "inline"`
> - this INFO `Callout box`, which contains Roam `page references`

## Section 1

### Section 1.1

#### illustration 1.1

- this image **has not been resized** through the Roam UI.
  <img src="flower.jpeg" style="margin: 0;">

<img src="flower-1.jpeg" alt="A flower" style="margin: 0;">

- AI assistant (Claude Opus 4.6):

## Section 2

### Section 2.1

#### illustration 2.1

- this image **has been resized** through the Roam UI (width:257, height:None)

<img src="flower-2.jpeg" width="257" style="margin: 0;">

#### Section 2.1.1

##### Section 2.1.1.1

### Section 2.2

| [<img src="https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2Fj2QaOlGrbf.jpeg.enc?alt=media&token=0f8b5018-5acc-4fd1-8341-ad7611772ec1" style="margin: 0;">](https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2Fj2QaOlGrbf.jpeg.enc?alt=media&token=0f8b5018-5acc-4fd1-8341-ad7611772ec1) | [<img src="https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2FIHkqRJ_Wmb.jpeg.enc?alt=media&token=50b3450d-5b10-4a13-aa8d-25fa939994a7" style="margin: 0;">](https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2FIHkqRJ_Wmb.jpeg.enc?alt=media&token=50b3450d-5b10-4a13-aa8d-25fa939994a7) |
|----|----|
| [<img src="https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2Fu2aukLge2y.jpeg.enc?alt=media&token=0e8dded5-e39f-40a6-8eec-e4132da1e3e4" style="margin: 0;">](https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2Fu2aukLge2y.jpeg.enc?alt=media&token=0e8dded5-e39f-40a6-8eec-e4132da1e3e4) | [<img src="https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2F_asI3qPwPQ.jpeg.enc?alt=media&token=34e60f4b-62c9-43c1-b0f9-4ac542b70e7e" style="margin: 0;">](https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2F_asI3qPwPQ.jpeg.enc?alt=media&token=34e60f4b-62c9-43c1-b0f9-4ac542b70e7e) |

## Section 3

### Section 3.1

- the following block contains the canonical w3.org “Dummy” PDF file: https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf

- [dummy.pdf](dummy.pdf "dummy.pdf")

### Section 3.2

- the following block embeds a PDF with guffin-meta:: pdf-render: “inline”

[dummy.pdf](dummy-1.pdf "dummy.pdf")
