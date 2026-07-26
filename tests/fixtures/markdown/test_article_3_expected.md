# Test Article 3

> [!NOTE]
> **THIS PAGE IS USED FOR TESTING [GUFFIN](https://github.com/jpanico/guffin) – DO NOT REMOVE**
>
> Features:
>
> - an exhaustive matrix of Roam `refs` and `embeds`: inline vs. standalone × internal (in-page) vs. external (out-of-page) × target kind
> - `Feature Content` section holds the reference targets:
>
> – styled text runs: plain, italics, bold, strikethrough, highlight, inline-code  
> – `color spans`: text color, highlight color, underline, box  
> – a fenced Python `code block`, a standalone `image`, a Roam `callout`, a native `{{table}}`  
> – `block quotes` (Markdown and Roam native, single- and multi-line) and Roam `pull quotes`
>
> - `Internal (in-page) links:` section: inline refs to the styled/colored targets, plus standalone refs to page / block / parent block / header and to every block-level target above, plus a block embed
> - `External (out-of-page) links:` section: the same matrix against Test Article 1 and Test Article 2, plus a Daily Notes Page ref, a page embed, a callout embed, and a standalone ref to a Test Article 1 PDF block tagged `guffin-meta:: pdf-render: "inline"` at the reference site (the site’s tag drives the PDF format’s inline placement)
> - this INFO `Callout box`, which contains Roam `page references`

## Feature Content

- This para features plain text
- This para features *italics*
- This para features **bold**
- This para features ~~strikethrough~~
- This para features <mark>highlight</mark>
- This para features `inline-code`

``` python
def fizz_buzz(limit: int = 100):
    for i in range(1, limit + 1):
        if i % 15 == 0:
            print("FizzBuzz")
        elif i % 3 == 0:
            print("Fizz")
        elif i % 5 == 0:
            print("Buzz")
        else:
            print(i)
```

- <span style="color: orange">**This span is BOLD orange text color**</span>. This span is not.
- <mark style="background-color: orange">This span is highlighted orange.</mark> This span is not.
- <span style="text-decoration: underline; color: orange">This span is underlined orange.</span>This span is not.
- <span style="border: 1px solid orange; padding: 2px 4px">This span has box color orange.</span> This span does not.
- the child block contains a standalone image
  [7rthRV4UHu.jpeg.enc](https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2F7rthRV4UHu.jpeg.enc?alt=media&token=0186f717-7b00-4ce8-af02-42bbf7e2cb89)
- the child block contains a Roam native callout
  > [!NOTE]
  > **This is the callout title**
  >
  > This is line 1 of the callout body  
  > This is line 2 of the callout body
- the child block contains a Roam native table
  | Header 1 | Header 2 | Header 3 |
  |----------|----------|----------|
  | r1.c1    | r1.c2    | r1.c3    |
  | r2.c1    | r2.c2    | r2.c3    |
- the child block contains a standard markdown single-line block quote
  > This is a *Markdown standard* single line **Block Quote**

  - this is a child block of Block Quote
- the child block contains a standard markdown multi-line block quote
  > This is a Markdown standard multi-line Block Quote  
  > this is the *2nd line*
  >
  > - this is the **3rd line**

  - this is a child block of Block Quote
- the child block contains a Roam native single-line block quote
  > This is a *Roam standard* single line **Block Quote**

  - this is a child block of Block Quote
- the child block contains a Roam native multi-line block quote
  > This is a Roam standard multi-line Block Quote  
  > this is the *2nd line*
  >
  > - this is the **3rd line**

  - this is a child block of Block Quote
- the child block contains a Roam native single line Pull Quote
  > **❝ This is a Roam single line Pull Quote**

  - this is a child block of Pull Quote
- the child block contains a Roam native multiline Pull Quote
  > **❝ This is a Roam multi-line Pull Quote**
  >
  > *this is the 2nd line*

  - this is a child block of Pull Quote

## Internal (in-page) links:

- <span style="color: fuchsia">**inline PAGE ref ⟶**</span> Test Article 3
- <span style="color: fuchsia">**inline PLAIN TEXT ref ⟶**</span> This para features plain text
- <span style="color: fuchsia">**inline ITALICS ref ⟶**</span> This para features *italics*
- <span style="color: fuchsia">**inline BOLD ref ⟶**</span> This para features **bold**
- <span style="color: fuchsia">**inline STRIKETHROUGH ref ⟶**</span> This para features ~~strikethrough~~
- <span style="color: fuchsia">**inline HIGHLIGHT ref ⟶**</span> This para features <mark>highlight</mark>
- <span style="color: fuchsia">**inline INLINE-CODE ref ⟶**</span> This para features `inline-code`
- <span style="color: fuchsia">**inline PARENT BLOCK ref ⟶**</span> Internal (in-page) links:
- <span style="color: fuchsia">**inline HEADER ref ⟶**</span> Feature Content
- <span style="color: fuchsia">**inline BOLD ORANGE ref ⟶**</span> <span style="color: orange">**This span is BOLD orange text color**</span>. This span is not.
- <span style="color: fuchsia">**inline HIGHLIGHTED ORANGE ref ⟶**</span> <mark style="background-color: orange">This span is highlighted orange.</mark> This span is not.
- <span style="color: fuchsia">**inline UNDERLINED ORANGE ref ⟶**</span> <span style="text-decoration: underline; color: orange">This span is underlined orange.</span>This span is not.
- <span style="color: fuchsia">**inline BOXED ORANGE ref ⟶**</span> <span style="border: 1px solid orange; padding: 2px 4px">This span has box color orange.</span> This span does not.
- <span style="color: fuchsia">**standalone PAGE ref ↓**</span>
  - Test Article 3
- <span style="color: fuchsia">**standalone BLOCK ref ↓**</span>
  - Section 3
- <span style="color: fuchsia">**standalone PARENT BLOCK ref ↓**</span>
  - Internal (in-page) links:
- <span style="color: fuchsia">**standalone IMAGE BLOCK ref ↓**</span>
  [7rthRV4UHu.jpeg.enc](https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2F7rthRV4UHu.jpeg.enc?alt=media&token=0186f717-7b00-4ce8-af02-42bbf7e2cb89)
- <span style="color: fuchsia">**standalone PDF BLOCK ref↓**</span>
  [u-F9pv-nvn.pdf](https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2Fu-F9pv-nvn.pdf.enc?alt=media&token=4e0e9645-a0e1-4da4-b699-a03638a1fc03 "u-F9pv-nvn.pdf")
- <span style="color: fuchsia">**standalone BLOCK EMBED ↓**</span>
  Section 3

  - section 3.1
    - section 3.1.1
  - section 3.2
  - section 3.3
- <span style="color: fuchsia">**standalone HEADER ref ↓**</span>
  - Feature Content
- <span style="color: fuchsia">**standalone FENCED-CODE ref ↓**</span>
  ``` python
  def fizz_buzz(limit: int = 100):
      for i in range(1, limit + 1):
          if i % 15 == 0:
              print("FizzBuzz")
          elif i % 3 == 0:
              print("Fizz")
          elif i % 5 == 0:
              print("Buzz")
          else:
              print(i)
  ```
- <span style="color: fuchsia">**standalone STANDARD MARKDOWN SINGLE-LINE BLOCK QUOTE ref ↓**</span>
  > This is a *Markdown standard* single line **Block Quote**
- <span style="color: fuchsia">**standalone STANDARD MARKDOWN MULTI-LINE BLOCK QUOTE ref ↓**</span>
  > This is a Markdown standard multi-line Block Quote  
  > this is the *2nd line*
  >
  > - this is the **3rd line**
- <span style="color: fuchsia">**standalone ROAM NATIVE SINGLE-LINE BLOCK QUOTE ref ↓**</span>
  > This is a *Roam standard* single line **Block Quote**
- <span style="color: fuchsia">**standalone ROAM NATIVE MULTI-LINE BLOCK QUOTE ref ↓**</span>
  > This is a Roam standard multi-line Block Quote  
  > this is the *2nd line*
  >
  > - this is the **3rd line**
- <span style="color: fuchsia">**standalone ROAM NATIVE SINGLE-LINE PULL QUOTE ref ↓**</span>
  > **❝ This is a Roam single line Pull Quote**
- <span style="color: fuchsia">**standalone ROAM NATIVE MULTI-LINE PULL QUOTE ref ↓**</span>
  > **❝ This is a Roam multi-line Pull Quote**
  >
  > *this is the 2nd line*
- <span style="color: fuchsia">**standalone CALLOUT ref ↓**</span>
  > [!NOTE]
  > **This is the callout title**
  >
  > This is line 1 of the callout body  
  > This is line 2 of the callout body
- <span style="color: fuchsia">**standalone ROAM NATIVE TABLE ref ↓**</span>
  | Header 1 | Header 2 | Header 3 |
  |----------|----------|----------|
  | r1.c1    | r1.c2    | r1.c3    |
  | r2.c1    | r2.c2    | r2.c3    |

## External (out-of-page) links:

- <span style="color: fuchsia">**inline PAGE ref ⟶**</span> Test Article 2
- <span style="color: fuchsia">**inline DAILY NOTES PAGE ref ⟶**</span> January 1st, 2026
- <span style="color: fuchsia">**inline BLOCK ref ⟶**</span> this image **has been resized** through the Roam UI (width:257, height:None)
- <span style="color: fuchsia">**inline ITALICS ref ⟶**</span> This &#91;para&#93; features &#91;*italics*&#93;
- <span style="color: fuchsia">**inline BOLD ref ⟶**</span> This para features **bold**
- <span style="color: fuchsia">**inline STRIKETHROUGH ref ⟶**</span> This para features ~~strikethrough~~
- <span style="color: fuchsia">**inline HIGHLIGHT ref ⟶**</span> This para features <mark>highlight</mark>
- <span style="color: fuchsia">**inline INLINE-CODE ref ⟶**</span> This para features `inline-code`
- <span style="color: fuchsia">**inline HEADER ref ⟶**</span> Section 1
- <span style="color: fuchsia">**inline BOLD ORANGE ref ⟶**</span> <span style="color: orange">**This span is BOLD orange text color**</span>. This span is not.
- <span style="color: fuchsia">**inline HIGHLIGHTED ORANGE ref ⟶**</span> <mark style="background-color: orange">This span is highlighted orange.</mark> This span is not.
- <span style="color: fuchsia">**inline UNDERLINED ORANGE ref ⟶**</span> <span style="text-decoration: underline; color: orange">This span is underlined orange.</span>This span is not.
- <span style="color: fuchsia">**inline BOXED ORANGE ref ⟶**</span> <span style="border: 1px solid orange; padding: 2px 4px">This span has box color orange.</span> This span does not.
- <span style="color: fuchsia">**standalone PAGE ref ↓**</span>
  - Test Article 2
- <span style="color: fuchsia">**standalone DAILY NOTES PAGE ref ↓**</span>
  - January 1st, 2026
- <span style="color: fuchsia">**standalone BLOCK ref ↓**</span>
  - this image **has been resized** through the Roam UI (width:257, height:None)
- <span style="color: fuchsia">**standalone IMAGE BLOCK ref ↓**</span>
  [A flower](https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2F_otAwc2B9g.jpeg.enc?alt=media&token=25c3ac2a-f62e-462e-99b4-99b337a476c0)
- <span style="color: fuchsia">**standalone PDF BLOCK ref, site-tagged pdf-render: “inline” (from Test Article 1) ↓**</span>
  [u-F9pv-nvn.pdf](https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2Fu-F9pv-nvn.pdf.enc?alt=media&token=4e0e9645-a0e1-4da4-b699-a03638a1fc03 "u-F9pv-nvn.pdf")
- <span style="color: fuchsia">**standalone BLOCK EMBED (from Test Article 1) ↓**</span>
  ### Section 2.1

  #### illustration 2.1

  - this image **has been resized** through the Roam UI (width:257, height:None)

  [aOC1FnrcwK.jpeg.enc](https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2FaOC1FnrcwK.jpeg.enc?alt=media&token=c6e7a3c2-c682-4ae9-a3ee-8e6c388cd05a)

  #### Section 2.1.1

  ##### Section 2.1.1.1
- <span style="color: fuchsia">**standalone PAGE EMBED ↓**</span>
  - When you leave the Bridge, and ride towards the west, finding all the way excellent hostelries for travellers, with fine vineyards, fields, and gardens, and springs of water, you come after 30 miles to a fine large city called Juju, where there are many abbeys of idolaters, and the people live by trade and manufactures. They weave cloths of silk and gold, and very fine taffetas.{1} Here too there are many hostelries for travellers.{2} After riding a mile beyond this city you find two roads, one of which goes west and the other south-east. The westerly road is that through Cathay, and the south-easterly one goes towards the province of Manzi.{3} Taking the westerly one through Cathay, and travelling by it for ten days, you find a constant succession of cities and boroughs, with numerous thriving villages, all abounding with trade and manufactures, besides the fine fields and vineyards and dwellings of civilized people; but nothing occurs worthy of special mention; and so I will only speak of a kingdom called Taianfu. Note 1.—The word is sendaus (Pauthier), pl. of sendal, and in G. T. sandal. It does not seem perfectly known what this silk texture was, but as banners were made of it, and linings for richer stuffs, it appears to have been a light material, and is generally rendered taffetas. In Richard Cœur de Lion we find “Many a pencel of sykelatoun And of sendel of grene and broun,”
  - and also pavilions of sendel; and in the Anglo-French ballad of the death of William Earl of Salisbury in St. Lewis’s battle on the Nile— “Le Meister du Temple brace les chivaux Et le Count Long-Espée depli les sandaux.”
  - The oriflamme of France was made of cendal. Chaucer couples taffetas and sendal. His “Doctor of Physic”
  - “In sanguin and in persë clad was allë, Linëd with taffata and with sendallë.”
  - &#91;La Curne, Dict., s.v. Sendaus has: Silk stuff: “Somme de la delivrance des sendaus.” (Nouv. Compt. de l’Arg. p. 19).—Godefroy, Dict., gives: “Sendain, adj., made with the stuff called cendal: Drap d’or sendains (1392, Test. de Blanche, duch d’Orl., Ste-Croix, Arch. Loiret).” He says s.v. Cendal, “cendau, cendral, cendel, … sendail, … étoffe légère de soie unie qui paraît avoir été analogue au taffetas.” “‘On faisait des cendaux forts ou faibles, et on leur donnait toute sorte de couleurs. On s’en servait surtout pour vêtements et corsets, pour doublures de draps, de fourrures et d’autres étoffes de soie plus précieuses, enfin pour tenture d’appartements.’ (Bourquelot, Foir. de Champ. I. 261).” “J’ay de toilles de mainte guise, De sidonnes et de cendaulx. Soyes, satins blancs et vermaulx.” —Greban, Mist. de la Pass., 26826, G. Paris.—H. C.&#93;
  - The origin of the word seems also somewhat doubtful. The word Σενδἑς occurs in Constant. Porphyrog. de Ceremoniis (Bonn, ed. I. 468), and this looks like a transfer of the Arabic Săndăs or Sundus, which is applied by Bakui to the silk fabrics of Yezd. (Not. et Ext. II. 469.) Reiske thinks this is the origin of the Frank word, and connects its etymology with Sind. Others think that sendal and the other forms are modifications of the ancient Sindon, and this is Mr. Marsh’s view. (See also Fr.-Michel, Recherches, etc. I. 212; Dict. des Tissus, II. 171 seqq.)
- <span style="color: fuchsia">**standalone HEADER ref ↓**</span>
  - Section 1
- <span style="color: fuchsia">**standalone FENCED-CODE ref ↓**</span>
  ``` python
  def fizz_buzz(limit: int = 100):
      for i in range(1, limit + 1):
          if i % 15 == 0:
              print("FizzBuzz")
          elif i % 3 == 0:
              print("Fizz")
          elif i % 5 == 0:
              print("Buzz")
          else:
              print(i)
  ```
- <span style="color: fuchsia">**standalone STANDARD MARKDOWN SINGLE-LINE BLOCK QUOTE ref ↓**</span>
  > This is a *Markdown standard* single line **Block Quote**
- <span style="color: fuchsia">**standalone STANDARD MARKDOWN MULTI-LINE BLOCK QUOTE ref ↓**</span>
  > This is a Markdown standard multi-line Block Quote  
  > this is the *2nd line*
  >
  > - this is the **3rd line**
- <span style="color: fuchsia">**standalone ROAM NATIVE SINGLE-LINE BLOCK QUOTE ref ↓**</span>
  > This is a *Roam standard* single line **Block Quote**
- <span style="color: fuchsia">**standalone ROAM NATIVE MULTI-LINE BLOCK QUOTE ref ↓**</span>
  > This is a Roam standard multi-line Block Quote  
  > this is the *2nd line*
  >
  > - this is the **3rd line**
- <span style="color: fuchsia">**standalone ROAM NATIVE SINGLE-LINE PULL QUOTE ref ↓**</span>
  > **❝ This is a Roam single line Pull Quote**
- <span style="color: fuchsia">**standalone ROAM NATIVE MULTI-LINE PULL QUOTE ref ↓**</span>
  > **❝ This is a Roam multi-line Pull Quote**
  >
  > *this is the 2nd line*
- <span style="color: fuchsia">**standalone CALLOUT ref ↓**</span>
  > [!NOTE]
  > **This is the callout title**
  >
  > This is line 1 of the callout body
  >
  > This is line 2 of the callout body
- <span style="color: fuchsia">**standalone ROAM NATIVE TABLE ref ↓**</span>
  | Header 1 | Header 2 | Header 3 |
  |----------|----------|----------|
  | r1.c1    | r1.c2    | r1.c3    |
  | r2.c1    | r2.c2    | r2.c3    |
- <span style="color: fuchsia">**standalone CALLOUT EMBED ↓**</span>
  > [!NOTE]
  > **This is the callout title**
  >
  > This is line 1 of the callout body
  >
  > This is line 2 of the callout body

- Section 3
  - section 3.1
    - section 3.1.1
  - section 3.2
  - section 3.3
