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
> - a native `{{table}}` (Section 2.2) whose four cells are each a standalone `block reference` to a JPEG `image` block, so each cell displays its referenced image
> - an embedded PDF document that has no special PublishingSemantics Attributes attached
> - an embedded PDF document that has `guffin-meta:: pdf-render: "inline"`
> - this INFO `Callout box`, which contains Roam `page references`

## Section 1

### Section 1.1

#### illustration 1.1

- this image **has not been resized** through the Roam UI.
  [mYFuvIq\_\_9.jpeg.enc](https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2FmYFuvIq__9.jpeg.enc?alt=media&token=b5fa90b8-ec37-49ea-b0e9-157570fb91c4)

[A flower](https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2F_otAwc2B9g.jpeg.enc?alt=media&token=25c3ac2a-f62e-462e-99b4-99b337a476c0)

- AI assistant (Claude Opus 4.6):

## Section 2

### Section 2.1

#### illustration 2.1

- this image **has been resized** through the Roam UI (width:257, height:None)

[aOC1FnrcwK.jpeg.enc](https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2FaOC1FnrcwK.jpeg.enc?alt=media&token=c6e7a3c2-c682-4ae9-a3ee-8e6c388cd05a)

#### asset 2.1

- an asset is a BLOB stored by Roam in Cloud Firestore; usually a file dragged into the Roam UI. The Roam Markdown representation of the asset is just the Cloud Firestore URL.
- https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2FfJoSdh65Ry.pkpass.enc?alt=media&token=b756b61a-8d04-4f30-a887-3feac7bb9d6a

#### Section 2.1.1

##### Section 2.1.1.1

### Section 2.2

| [j2QaOlGrbf.jpeg.enc](https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2Fj2QaOlGrbf.jpeg.enc?alt=media&token=0f8b5018-5acc-4fd1-8341-ad7611772ec1) | [IHkqRJ_Wmb.jpeg.enc](https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2FIHkqRJ_Wmb.jpeg.enc?alt=media&token=50b3450d-5b10-4a13-aa8d-25fa939994a7) |
|----|----|
| [u2aukLge2y.jpeg.enc](https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2Fu2aukLge2y.jpeg.enc?alt=media&token=0e8dded5-e39f-40a6-8eec-e4132da1e3e4) | [\_asI3qPwPQ.jpeg.enc](https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2F_asI3qPwPQ.jpeg.enc?alt=media&token=34e60f4b-62c9-43c1-b0f9-4ac542b70e7e) |

## Section 3

### Section 3.1

- the following block contains the canonical w3.org “Dummy” PDF file: https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf

- [u-F9pv-nvn.pdf](https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2Fu-F9pv-nvn.pdf.enc?alt=media&token=4e0e9645-a0e1-4da4-b699-a03638a1fc03 "u-F9pv-nvn.pdf")

### Section 3.2

- the following block embeds a PDF with guffin-meta:: pdf-render: “inline”

3IX5aCGhi\_.pdf
