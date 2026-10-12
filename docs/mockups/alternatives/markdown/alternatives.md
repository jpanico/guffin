# Alternatives — Markdown styling mockup

*Sample: one sentence with three wordings, the first selected — the same group as the PDF and
EPUB mockups. GFM offers no styling of its own, so muting rides on the inline
`<span style="…">` guffin already emits for colour spans: Typora honours it, GitHub strips the
style and keeps the text. Each variant appears twice, because a guffin block renders either as
a paragraph (document layout) or as a list item (bullet layout, the default).*

> A block quote, for comparison.

## M1 — One block, hard line breaks (recommended)

*The group is a single paragraph (or list item): one line per wording, separated by hard
breaks, so it stays visually tight. ◉ leads the selected wording, ○ each alternative.*

### As paragraphs

The paragraph before the group sits in ordinary body flow, so the eye arrives at the group from normal reading and can judge how much it interrupts the page.

◉ The committee met on Thursday and, after a long and occasionally heated discussion, agreed to postpone the vote until the full budget figures were available.\
<span style="color: #737373; font-size: 0.93em">○ On Thursday the committee met and, after *much* debate, voted to defer the decision until it had seen the full budget figures.</span>\
<span style="color: #737373; font-size: 0.93em">○ The committee's Thursday meeting ended without a vote: members wanted the **complete** budget figures before committing either way.</span>

The paragraph after the group resumes ordinary flow. A good treatment lets a reader skim straight past the alternatives while still seeing at a glance which wording is the one in force.

### As list items

- The item before the group, in ordinary outline flow.
- ◉ The committee met on Thursday and, after a long and occasionally heated discussion, agreed to postpone the vote until the full budget figures were available.\
  <span style="color: #737373; font-size: 0.93em">○ On Thursday the committee met and, after *much* debate, voted to defer the decision until it had seen the full budget figures.</span>\
  <span style="color: #737373; font-size: 0.93em">○ The committee's Thursday meeting ended without a vote: members wanted the **complete** budget figures before committing either way.</span>
- The item after the group resumes ordinary outline flow.

## M2 — Alternatives as a sub-list

*The selected wording stays where it is; the alternatives hang beneath it as a nested list,
which gives each one a hanging indent, at the cost of a dash beside each ○.*

### As paragraphs

The paragraph before the group sits in ordinary body flow, so the eye arrives at the group from normal reading and can judge how much it interrupts the page.

◉ The committee met on Thursday and, after a long and occasionally heated discussion, agreed to postpone the vote until the full budget figures were available.

- <span style="color: #737373; font-size: 0.93em">○ On Thursday the committee met and, after *much* debate, voted to defer the decision until it had seen the full budget figures.</span>
- <span style="color: #737373; font-size: 0.93em">○ The committee's Thursday meeting ended without a vote: members wanted the **complete** budget figures before committing either way.</span>

The paragraph after the group resumes ordinary flow. A good treatment lets a reader skim straight past the alternatives while still seeing at a glance which wording is the one in force.

### As list items

- The item before the group, in ordinary outline flow.
- ◉ The committee met on Thursday and, after a long and occasionally heated discussion, agreed to postpone the vote until the full budget figures were available.
  - <span style="color: #737373; font-size: 0.93em">○ On Thursday the committee met and, after *much* debate, voted to defer the decision until it had seen the full budget figures.</span>
  - <span style="color: #737373; font-size: 0.93em">○ The committee's Thursday meeting ended without a vote: members wanted the **complete** budget figures before committing either way.</span>
- The item after the group resumes ordinary outline flow.

## M3 — HTML block with the dashed rail (paragraphs only)

*The closest to C2: a raw `<div>` draws the rail. Typora only — GitHub strips the style, and
Typora does not render block-level HTML inside list items, so there is no list form. The
whole group is one HTML block with no blank lines (a blank line would end the block and leave
the text outside the div), so its emphasis is written as `<em>`/`<strong>` rather than Markdown.*

The paragraph before the group sits in ordinary body flow, so the eye arrives at the group from normal reading and can judge how much it interrupts the page.

<div style="border-left: 1px dashed #b9b9b9; padding-left: 0.6em; margin-bottom: 16px">
◉ The committee met on Thursday and, after a long and occasionally heated discussion, agreed to postpone the vote until the full budget figures were available.<br>
<span style="color: #737373; font-size: 0.93em">○ On Thursday the committee met and, after <em>much</em> debate, voted to defer the decision until it had seen the full budget figures.</span><br>
<span style="color: #737373; font-size: 0.93em">○ The committee's Thursday meeting ended without a vote: members wanted the <strong>complete</strong> budget figures before committing either way.</span>
</div>

The paragraph after the group resumes ordinary flow. A good treatment lets a reader skim straight past the alternatives while still seeing at a glance which wording is the one in force.
