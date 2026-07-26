# Test Article 4

> [!NOTE]
> **THIS PAGE IS USED FOR TESTING [GUFFIN](https://github.com/jpanico/guffin) – DO NOT REMOVE**
>
> Features:
>
> - **Color Highlighter** Roam Extension: https://github.com/fbgallet/roam-extension-color-highlighter

- **BOLD** text color
  - **This span is BOLD uncolored**.
  - <span style="color: orange">**This span is BOLD orange text color**</span>. This span is not.
  - <span style="color: fuchsia">**This span is BOLD fuchsia text color**</span>. This span is not.
  - <span style="color: fuchsia"> **This span is BOLD fuchsia text color**</span>. It extra space between the color markup and the bold Markdown
- <mark>highlight</mark> color
  - <mark style="background-color: orange">This span is highlighted orange.</mark> This span is not.
  - <mark style="background-color: fuchsia">This span is highlighted fuchsia.</mark> This span is not.
- underline color (Markdown does not have a standard underline markup, because of the conflict with hyperlink rendering)
  - <span style="text-decoration: underline; color: orange">This span is underlined orange.</span>This span is not.
  - <span style="text-decoration: underline; color: fuchsia">This span is underlined fuchsia.</span>This span is not.
- box color
  - <span style="border: 1px solid orange; padding: 2px 4px">This span has box color orange.</span> This span does not.
  - <span style="border: 1px solid fuchsia; padding: 2px 4px">This span has box color fuchsia.</span> This span does not.
- box background color
  - <span style="background-color: orange">This entire line is an orange background box</span>

  - <span style="background-color: fuchsia">This entire line is an orange background box</span>
