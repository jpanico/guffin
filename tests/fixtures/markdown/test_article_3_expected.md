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

Section 1

- <span style="color: fuchsia">**inline page ref**</span>: Test Article 2
- <span style="color: fuchsia">**internal block ref**</span>: Section 3
- <span style="color: fuchsia">**internal block embed (from *this Page*):**</span>
  - {{embed: section 3.1.1}}

Section 2

- <span style="color: fuchsia">**external block ref:**</span> this image **has been resized** through the Roam UI (width:257, height:None)
- <span style="color: fuchsia">**external block embed (from Test Article 1)**</span>:
  - {{embed: Section 2.1}}

Section 3

- <span style="color: fuchsia">**child block is a standalone page ref:**</span>
  - Test Article 1
- section 3.1
  - <span style="color: fuchsia">**the child block is a standalone block ref:**</span>
    - `python def fizz_buzz(limit: int = 100):     for i in range(1, limit + 1):         if i % 15 == 0:             print("FizzBuzz")         elif i % 3 == 0:             print("Fizz")         elif i % 5 == 0:             print("Buzz")         else:             print(i)`
  - section 3.1.1
