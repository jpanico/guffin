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

# This is a HEADER

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

Internal (in-page) links:

- <span style="color: fuchsia">**inline PAGE ref ➔**</span> Test Article 3
- <span style="color: fuchsia">**inline PLAIN TEXT ref ➔**</span> This para features plain text
- <span style="color: fuchsia">**inline ITALICS ref ➔**</span> This para features *italics*
- <span style="color: fuchsia">**inline BOLD ref ➔**</span> This para features **bold**
- <span style="color: fuchsia">**inline STRIKETHROUGH ref ➔**</span> This para features ~~strikethrough~~
- <span style="color: fuchsia">**inline HIGHLIGHT ref ➔**</span> This para features <mark>highlight</mark>
- <span style="color: fuchsia">**inline INLINE-CODE ref ➔**</span> This para features `inline-code`
- <span style="color: fuchsia">**inline PARENT BLOCK ref ➔**</span> Internal (in-page) links:
- <span style="color: fuchsia">**inline HEADER ref ➔**</span> This is a HEADER
- <span style="color: fuchsia">**standalone page ref ⬇**</span>
  - Test Article 3
- <span style="color: fuchsia">**standalone block ref ⬇**</span>
  - Section 3
- <span style="color: fuchsia">**standalone parent block ref ⬇**</span>
  - Internal (in-page) links:
- <span style="color: fuchsia">**standalone block embed ⬇**</span>
  - {{embed: section 3.1.1}}
- <span style="color: fuchsia">**standalone HEADER ref ⬇**</span>
  - This is a HEADER
- <span style="color: fuchsia">**standalone FENCED-CODE ref ⬇**</span>
  - ``` python
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

external (out-of-page) links:

- <span style="color: fuchsia">**inline page ref ➔**</span> Test Article 2
- <span style="color: fuchsia">**inline block ref ➔**</span> this image **has been resized** through the Roam UI (width:257, height:None)
- <span style="color: fuchsia">**standalone page ref ⬇**</span>
  - Test Article 2
- <span style="color: fuchsia">**standalone block ref ⬇**</span>
  - this image **has been resized** through the Roam UI (width:257, height:None)
- <span style="color: fuchsia">**external block embed (from Test Article 1)**</span>:
  - {{embed: Section 2.1}}

Section 3

- section 3.1
  - section 3.1.1
