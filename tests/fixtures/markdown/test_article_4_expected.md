# Test Article 4

> [!NOTE]
> **THIS PAGE IS USED FOR TESTING [GUFFIN](https://github.com/jpanico/guffin) – DO NOT REMOVE**
>
> Features:
>
> - **Color Highlighter** Roam Extension: [fbgallet/roam-extension-color-highlighter: Highlight with different color and color bold text](https://github.com/fbgallet/roam-extension-color-highlighter)  
> - **Better Bullets** Roam Extension: [mlava/better-bullets](https://github.com/mlava/better-bullets)

- Children blocks exercise *Color Highlighter* (Roam Extension)
  - **BOLD** text color
    - **This span is BOLD uncolored**.
    - <span style="color: orange">**This span is BOLD orange text color**</span>. This span is not.
    - <span style="color: fuchsia">**This span is BOLD fuchsia text color**</span>. This span is not.
    - <span style="color: fuchsia"> **This span is BOLD fuchsia text color**</span>. extra space
    - [ ] <span style="color: fuchsia">**This is a BOLD fuchsia block turned into a TODO**</span>
    - [x] <span style="color: fuchsia">**This is a BOLD fuchsia block turned into a DONE**</span>
    - [ ] <span style="color: fuchsia">**This block is a TODO turned into BOLD fuschia**</span>
    - [x] <span style="color: fuchsia">**This block is a DONE turned into BOLD fuschia**</span>
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
- Children blocks exercise *Better Bullets* (Roam Extension)
  - = Equal / definition -\> `=`
  - → Leads to -\> `→`
  - ⇒ Result -\> `⇒`
  - ? Question -\> `?`
  - ! Important / warning -\> `!`
  - \+ Idea / addition -\> `+`
  - ⤷ Right-angle arrow -\> `⤷`
  - ≠ Contrast / however -\> `≠`
  - ▸ Evidence / support -\> `▸`
  - ∴ Conclusion / synthesis -\> `∴`
  - ◊ Hypothesis / tentative -\> `◊`
  - ↤ Depends on / prerequisite -\> `↤`
  - ⎇ Decision / choice -\> `⎇`
  - ↗ Reference / related -\> `↗`
  - ↻ Process / ongoing -\> `↻`
  - Provenance
    - 📅 Calendar event -\> 📅
    - 📨 Email -\> 📨
    - 📞 Phone call -\> 📞
    - 💬 Chat message -\> 💬
    - 📪 Postal mail -\> 📪
    - ＃ Slack -\> ＃
  - Mixed
    - = 📅 Equal / definition, Calendar event -\> `=`📅
    - ? 💬 Chat Message, Question -\> ?💬
