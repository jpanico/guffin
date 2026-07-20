# Plan: `code-source::` decomposed display in Roam

> **Status: unimplemented plan** (drafted 2026-07-20). A Roam-side (`roam/js`) display
> extension — no guffin code changes. Implementation target: the **GitHub Code** branch on
> the SCFH graph's `[[roam/js]]` page, documented on `[[GitHub Code]]`.

## Problem

A `code-source::` tag stores exactly three values — GitHub blob URL, full commit SHA, fetch
date — and in Roam the block renders as that raw line. The reader who wants the discrete
facts (owner, repo, ref, file path, line range) has to visually parse them out of the URL,
and the 40-hex SHA dominates the line while its useful content (which commit, abbreviated)
is buried. Switching the stored URL to the blob form (2026-07-20) fixed the *click target*
and made the URL scannable; this extension fixes the *presentation*.

## Design principle: derive at render time, store nothing new

Storing discrete fields (`repo::`, `branch::`, …) alongside the URL was considered and
rejected: the fields would duplicate facts the URL already declares and inevitably drift
from it. The extension therefore renders a decomposed view **computed from the stored
triple at display time**, in the DOM only. Graph content is never touched — the
`code-source::` block string stays the single source of truth, and guffin's transcription,
validation, and export pipelines are entirely unaffected.

## Rendered display (sketch)

Replace the value portion of a rendered `code-source::` attribute block with:

```
code-source  jpanico/guffin @ main · src/guffin/common/validation.py · L14–L60 · 3b081e9 · 2026-07-19  [view] [pinned]
```

- **owner/repo** — links the repository page (`https://github.com/<owner>/<repo>`).
- **@ ref** — the human ref (`ref_name`: `refs/heads/main` displays as `main`); a SHA ref
  displays abbreviated. Distinguish track-vs-pin visually (e.g. italic branch, monospace SHA).
- **path** — links the stored blob URL (the *ref view*: current content of the tracked ref).
- **line range** — from the URL's `#L…` fragment; omitted for whole-file references.
- **abbreviated SHA (7)** — links the blob URL **re-pinned at the recorded SHA** (the
  *pinned view*: exactly what was snapshotted, even after the branch moves). Full SHA in the
  `title` tooltip.
- **fetch date** — verbatim third value.
- `[view]`/`[pinned]` affordances are optional if path and SHA already carry those links —
  prefer fewer, well-labeled links.

Malformed lines (URL that doesn't parse, wrong value count) are left **completely
undecorated** — the raw text is the honest display, and guffin's validators are the proper
reporting channel.

## Mechanism

Extend the existing GitHub Code `roam/js` script (same IIFE), reusing its `splitBlobPath`
— the decomposition logic must not be duplicated in a second script block.

1. **Finding rendered tags.** A `MutationObserver` on the Roam app root watches for
   rendered attribute blocks. In Roam's DOM an attribute renders as
   `span.rm-attr-ref` (the `code-source` pill) inside `div.rm-block__input`/`.roam-block`;
   the remainder of the block's rendered children is the value text (the URL auto-links as
   an `a`). Verify the exact selectors against the current Roam DOM at implementation time —
   they are Roam-internal and the plan's main fragility point.
2. **Decorating.** For each matching block not already decorated (mark with a
   `data-…-decorated` attribute for idempotence): read the block uid from the enclosing
   `[id^="block-input"]` container (the `uidFromDom` helper already exists), pull the block
   string via `roamAlphaAPI`, parse the three values (same trim/split as the exporter),
   `splitBlobPath` the URL, and build the widget. Hide the original value nodes
   (`display: none`) rather than removing them, and insert the widget after the pill.
3. **Edit round-trip.** Roam swaps a block to a plain textarea on focus and re-renders on
   blur; the re-render discards the decoration and the observer re-applies it. No special
   handling should be needed beyond idempotence — but verify typing inside the block never
   fights the observer (decorate only blocks that are *not* in edit mode:
   no `textarea` present in the container).
4. **Styling.** Class-based (`guffin-code-source-display`, element classes per field), with
   the rules in a `roam/css` block rather than inline styles — follow the existing
   `roam/css` conventions (see the mlava/toc precedent: theme-injected styles may need
   `!important` to override).
5. **Scope guard.** Only decorate attribute blocks whose attribute name is exactly
   `code-source` — cheap check on the pill text before any API pull.

## Non-goals

- No graph mutation of any kind (display only).
- No fetching: the widget is built from the stored triple alone — zero network, zero API
  quota. (Freshness checking stays in the palette **Refresh** command and guffin's
  `--verify-code-sources`.)
- No change to `dump-roam-tree`/export rendering — guffin's own surfaces already decompose
  via `CodeSource.file_ref()` where needed.

## Implementation steps

1. Verify Roam's current attribute-block DOM shape (selectors, edit-mode markers) in the
   SCFH graph with dev tools; note findings on `[[GitHub Code]]`.
2. Add the observer + widget builder to the GitHub Code script on `[[roam/js]]`
   (SCFH edits require explicit approval, per standing rule).
3. Add the stylesheet block to `[[roam/css]]`.
4. Reload the graph; sanity-check: TA0's tag and the 2026-07-17 daily-note tag decorate
   correctly; a deliberately malformed line stays raw; editing the block round-trips; both
   links land (ref view + pinned view).
5. Document the behavior on `[[GitHub Code]]` (new **Display** section).
6. If TA0's *rendered appearance* matters to any fixture, confirm fixtures are unaffected
   (they capture block strings, not DOM — expected: no regen needed).

## Open questions (decide at implementation)

- Hover vs always-visible for the fetch date and full SHA (the line is long; the date is
  the least-consulted fact).
- Whether the decoration should also apply inside block *references* and query results,
  where Roam renders the same attribute DOM in other contexts.
- Dark/light theme handling in the `roam/css` rules.
