# Test Article 0

> [!NOTE]
> **THIS PAGE IS USED FOR TESTING [GUFFIN](https://github.com/jpanico/guffin) – DO NOT REMOVE**
>
> Features:
>
> - 3 top-level blocks
> - nested blocks
> - *italics* text
> - **bold** text
> - ~~strikethrough~~
> - <mark>highlight</mark>
> - `inline-code`
> - fenced code mixed with text, block
> - isolated fenced code block
> - isolated fenced code block whose `plain text` fence language is overridden by a `code-language:: FORTRAN` tag
> - Markdown single line block quote
> - Markdown multi-line block quote
> - Roam-native single line block quote
> - Roam-native multi-line block quote
> - Roam-native single line pull quote
> - Roam-native multi-line pull quote
> - Roam-native table (3x3)
> - this INFO `Callout box`, which contains Roam `page references`

- block 1
  - This &#91;para&#93; features &#91;*italics*&#93;

  - This para features **bold**

  - This para features ~~strikethrough~~

  - This para features <mark>highlight</mark>

  - This para features `inline-code`

  - This para features includes a fenced code block:

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

  - The child of this block is an isolated fenced code block
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

  - The child of this block is an isolated fenced code block whose fence language (`plain text`) is overridden by a `code-language:: FORTRAN` tag
    ``` fortran
    C     FIZZBUZZ FOR IBM 704 FORTRAN
          DO 100 I = 1, 100
    C     CHECK FOR 15 (3 * 5)
          M15 = I - (I/15)*15
          IF (M15) 10, 5, 10
        5 PRINT 501
          GO TO 100
    C     CHECK FOR 3
       10 M3 = I - (I/3)*3
          IF (M3) 20, 15, 20
       15 PRINT 502
          GO TO 100
    C     CHECK FOR 5
       20 M5 = I - (I/5)*5
          IF (M5) 30, 25, 30
       25 PRINT 503
          GO TO 100
    C     PRINT THE NUMBER
       30 PRINT 504, I
      100 CONTINUE
    C     FORMAT STATEMENTS FOR THE TELETYPE
      501 FORMAT (8HFIZZBUZZ)
      502 FORMAT (4HFIZZ)
      503 FORMAT (4HBUZZ)
      504 FORMAT (I3)
          STOP
    ```

  > This is a *Markdown standard* single line **Block Quote**

  > This is a Markdown standard multi-line Block Quote  
  > this is the *2nd line*
  >
  > - this is the **3rd line**

  > This is a *Roam standard* single line **Block Quote**

  > This is a Roam standard multi-line Block Quote  
  > this is the *2nd line*
  >
  > - this is the **3rd line**

  > **❝ This is a Roam single line Pull Quote**

  > **❝ This is a Roam multi-line Pull Quote**
  >
  > *this is the 2nd line*

  - block 1.1
    - block 1.1.1
  - block 1.2
- block 2
  - the next block is a basic Roam-native table: 3x3. No column/row/col resizing of any kind

  | Header 1 | Header 2 | Header 3 |
  |----------|----------|----------|
  | r1.c1    | r1.c2    | r1.c3    |
  | r2.c1    | r2.c2    | r2.c3    |

  - the next block is a basic Roam-native table: 3x3, but has no values in some cells

  | Header 1 | Header 2 | Header 3 |
  |----------|----------|----------|
  | r1.c1    |          | r1.c3    |
  | r2.c1    | r2.c2    |          |
- block 3
  - block 3.1
    - block 3.1.1
  - block 3.2
    > [!NOTE]
    > **This is the callout title**
    >
    > This is line 1 of the callout body
    >
    > This is line 2 of the callout body
