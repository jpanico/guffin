# Test Article 3

> [!NOTE]
> **THIS PAGE IS USED FOR TESTING [GUFFIN](https://github.com/jpanico/guffin) – DO NOT REMOVE**
>
> Features:
>
> - This page is primarily a demonstration of different kinds of refs:
>
> – inline page ref
>
> – internal block ref (to block on this page)
>
> – external block ref (to block on a *different page*)
>
> – internal embed (of block from this page)
>
> – external embed (of block from *different page*)
>
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
  <img src="1f5047588dc26ea57a9d3e2364822fae77f3c2e82f9db652d5ddf7d0d8046c4c.jpg" style="margin: 0;">
- the child block contains a Roam native callout
  > [!NOTE]
  > **This is the callout title**
  >
  > This is line 1 of the callout body
  >
  > This is line 2 of the callout body
- the child block contains a Roam native table
  | Header 1 | Header 2 | Header 3 |
  |----------|----------|----------|
  | r1.c1    | r1.c2    | r1.c3    |
  | r2.c1    | r2.c2    | r2.c3    |

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
  <img src="1f5047588dc26ea57a9d3e2364822fae77f3c2e82f9db652d5ddf7d0d8046c4c.jpg" style="margin: 0;">
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

## External (out-of-page) links:

- <span style="color: fuchsia">**inline PAGE ref ⟶**</span> Test Article 2
- <span style="color: fuchsia">**inline BLOCK ref ⟶**</span> this image **has been resized** through the Roam UI (width:257, height:None)
- <span style="color: fuchsia">**inline ITALICS ref ⟶**</span> This para features *italics*
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
- <span style="color: fuchsia">**standalone BLOCK ref ↓**</span>
  - this image **has been resized** through the Roam UI (width:257, height:None)
- <span style="color: fuchsia">**standalone IMAGE BLOCK ref ↓**</span>
  <img src="4bb41fdc554dc75e557e9fcd463402db6d32abb30d93289a8ad644c6d89cf26f.jpg" alt="A flower" style="margin: 0;">
- <span style="color: fuchsia">**standalone BLOCK EMBED (from Test Article 1) ↓**</span>
  ## Section 2.1

  ### illustration 2.1

  - this image **has been resized** through the Roam UI (width:257, height:None)

  <img src="033a49ffff95aca42ad1b875cece7de2b757d71ee6ddd1152eaede4809727017.jpg" width="257" style="margin: 0;">

  ### Section 2.1.1

  #### Section 2.1.1.1
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

- Section 3
  - section 3.1
    - section 3.1.1
  - section 3.2
  - section 3.3
