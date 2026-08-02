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
> - Roam-native TODO item (open and done)
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

    - The child of this block is an isolated fenced code block whose `code-source` is https://github.com/jpanico/guffin/blob/main/src/guffin/common/validation.py
      ``` python
      """Generic accumulator-pipeline validation framework.
      
      Provides a small, side-effect-free validation pipeline:
      
      - :class:`ValidationError` — immutable record of a single validation failure.
      - :class:`ValidationResult` — immutable collection of all failures from a
        validation run; empty means valid.
      - :data:`Validator` — type alias for a pure validator function.
      - :func:`validate_all` — runs every validator in sequence and accumulates
        results into a :class:`ValidationResult`.
      
      All validators always run regardless of prior failures (no short-circuit),
      so the caller receives the complete set of errors in one pass.
      """
      
      from collections.abc import Callable
      from dataclasses import dataclass
      from typing import Final
      
      
      @dataclass(frozen=True)
      class ValidationError:
          """Immutable record of a single validation failure.
      
          Attributes:
              validator: The validator function that produced this error.
              message: Human-readable description of the validation failure.
          """
      
          validator: Callable[..., ValidationError | None]
          message: str
      
          def __str__(self) -> str:
              """Return a human-readable string combining the validator name and message."""
              return f"{self.validator.__name__}: {self.message}"
      
      
      @dataclass(frozen=True)
      class ValidationResult:
          """Immutable collection of all validation failures from a single run.
      
          An empty :attr:`errors` tuple means the input was valid.
      
          Attributes:
              errors: All failures produced by the validator pipeline. Empty when valid.
          """
      
          errors: tuple[ValidationError, ...]
      
          @property
          def is_valid(self) -> bool:
              """Return True when no validation errors were recorded."""
              return len(self.errors) == 0
      
      
      type Validator[T] = Callable[[T], ValidationError | None]
      """A pure validator function over an input of type ``T``.
      
      Returns a :class:`ValidationError` if the input violates the rule,
      or ``None`` if the input passes.
      
      Each validator is responsible only for detecting a single violation; it has
      no knowledge of the :class:`ValidationResult` accumulator or other validators
      in the pipeline.
      """
      
      
      def validate_all[T](input: T, validators: list[Validator[T]]) -> ValidationResult:
          """Run every validator over ``input`` and return the accumulated result.
      
          All validators always run regardless of prior failures — no short-circuit.
      
          Args:
              input: The value to validate.
              validators: Ordered list of validators to apply.
      
          Returns:
              A :class:`ValidationResult` containing all failures, or an empty
              result if every validator passed.
          """
          errors: Final[tuple[ValidationError, ...]] = tuple(error for v in validators if (error := v(input)) is not None)
          return ValidationResult(errors=errors)
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
      - {{TODO}} a short <span style="text-decoration: underline; color: orange">open todo</span>
      - {{DONE}} a short <span style="text-decoration: underline; color: orange">closed todo</span>
  - block 3.2
    > [!NOTE]
    > **This is the callout title**
    >
    > This is line 1 of the callout body
    >
    > This is line 2 of the callout body
  - block 3.3
    > [!NOTE]
    > **This is a callout with only a title– no body.**
