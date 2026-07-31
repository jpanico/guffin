# Plan: the Guffin Companion Roam extension

> **Status: phases 0–3 complete** (drafted 2026-07-30; phase-0 spike run 2026-07-30, findings
> recorded below — every unknown settled favorably; phase 1 implemented 2026-07-30 —
> `server/cors.py` wired to a repeatable `guffin-server --allow-origin`; phase 2 implemented
> and verified live 2026-07-30 — the extension MVP in its own repository,
> `~/Documents/github/guffin-companion`; phase 3 implemented and verified live 2026-07-30 —
> HTML dump inspector, block context menu, digest verification; phase 4, optional Depot
> distribution, is on **indefinite hold** — dev-mode loading serves the sole user, and
> publication would add a support surface with no present benefit). Two-sided: a small
> `guffin-server` change (opt-in CORS — phase 1)
> plus a new Roam extension living in its **own repository**; no other guffin code is
> touched. Companion to [server-mode.md](server-mode.md), the server this extension is a
> client of.

## Goal

Invoke `export-roam-tree` / `dump-roam-tree` from *inside* the Roam client: a command-palette
entry ("Guffin: export this page") that POSTs to the `guffin-server` running on the same
machine and hands back the rendered document — no terminal involved. The colocation that
server mode treats as a constraint (the Local API answers only on the machine running Roam
Desktop, see [roam-local-api.md](roam-local-api.md)) is here a guarantee: from the Roam
client's point of view, `guffin-server` is always reachable at loopback.

## Shape

A single hand-written `extension.js` — the Roam Depot extension contract: a default export
with `onload` / `onunload`, everything registered in `onload` torn down in `onunload`. No
`build.sh`, no bundler; nothing in this extension needs one, and their absence keeps Depot
review (if it ever comes to that — see phase 4) trivial.

All Roam-connection specifics — Local API port, graph name, bearer token — stay in the
**server's** environment, exactly as the derived-request design intends (an omitted request
field defers to the Typer default, including its `GUFFIN_*` env fallback resolved server-side).
The extension sends only `target` plus render overrides; it never touches, stores, or even
sees the Roam bearer token.

The Depot precedent for this architecture is mlava's *Capture for Roam Research companion*:
an extension fronting a service the user runs themselves.

## The constraint that shapes phase 1: CORS

A Roam extension runs in the Roam client's browser context — Roam Desktop is an Electron
shell loading `https://roamresearch.com`, so that is the extension's origin. A `fetch()` from
that origin to `http://127.0.0.1:8077` is a cross-origin request: the JSON POST triggers a
preflight, and the browser blocks the exchange unless the server answers with CORS headers.
`server/app.py` currently sets none — correct for the trusted-operator/curl model, fatal for
a browser client. Admitting the extension is therefore an explicit, opt-in server change, not
an extension-side workaround (there is none: the browser enforces CORS, not the page).

Two adjacent browser rules matter:

- **Private Network Access (PNA).** Chrome's PNA rules treat a request from a public `https`
  page to a loopback address specially: the preflight carries
  `Access-Control-Request-Private-Network: true` and must be answered with
  `Access-Control-Allow-Private-Network: true`. Starlette's `CORSMiddleware` does not emit
  that header; if Roam's Electron build enforces PNA (phase 0 verifies), a few-line custom
  middleware supplies it. Emitting it unconditionally is harmless when unenforced — build it
  in from the start and a future Roam Desktop Electron upgrade cannot break the extension.
- **Mixed content does not apply.** `http://127.0.0.1` is a *potentially trustworthy* origin
  per the Secure Contexts spec, so an `https` page may fetch it over plain HTTP.

## Phase 0 — de-risking spike (dev mode, throwaway)

Load a stub extension via Roam Depot's developer mode (load-from-directory) and settle
empirically the three unknowns that decide everything downstream:

1. **The real origin.** Log `location.origin` inside Roam Desktop. Almost certainly
   `https://roamresearch.com`, but the phase-1 allowlist value comes from observation, not
   assumption.
2. **Preflight behavior.** POST JSON to a local test server; observe whether the PNA
   preflight appears and what satisfies it in Roam's current Electron.
3. **File saving.** Verify that the anchor-click-on-object-URL download pattern triggers
   Electron's save flow in Roam Desktop; if not, test `window.showSaveFilePicker`. One of
   the two will work; which one shapes the export UX.

### Findings (2026-07-30 — Roam Desktop 0.0.38, Electron 38.2.0, Chrome 140)

The spike ran an instrumented dev-mode extension against a loopback logging server answering
exactly the phase-1 CORS response shape. Every unknown settled favorably:

1. **Origin: `https://roamresearch.com`** — confirmed twice over: `location.origin` as seen
   by the extension, and the browser-stamped `Origin` header on every request the server
   logged.
2. **The CORS dialog works end to end.** A simple GET is sent with no preflight and its
   response is readable under the allow-origin echo; the JSON POST's preflight
   (`OPTIONS` + `Access-Control-Request-Method`/`-Headers`) is satisfied by the phase-1
   response shape and the POST follows.
3. **PNA is not enforced** in this Electron: the real preflight carries no
   `Access-Control-Request-Private-Network`. The conditional response header stays in
   phase 1 regardless — harmless today, immunizes against a future Electron upgrade.
4. **No CSP interference**: zero `securitypolicyviolation` events — Roam's page policy does
   not restrict `connect-src` against loopback HTTP.
5. **Anchor download works**: the anchor-click-on-object-URL pattern raises Electron's
   native save dialog; the saved file's bytes verified intact against the generated content.
6. **`showSaveFilePicker` works too**: present, shows a native dialog, write + close
   succeed — a viable direct-write alternative.

Consequence: the architecture is viable exactly as planned — phase 1's CORS middleware is
sufficient and necessary, no extension-side workaround is needed, and phase 2's save UX may
use either mechanism (the anchor flow is the baseline).

## Phase 1 — `guffin-server`: opt-in CORS

> Implemented 2026-07-30: `server/cors.py` (`cors_wrapped_app` — a non-mutating wrap in
> Starlette's `CORSMiddleware`, whose native `allow_private_network` answers the PNA
> preflight) wired to a repeatable `--allow-origin` in `cli/serve.py`; offline tests in
> `tests/server/test_cors.py` and `tests/cli/test_serve.py`.

- New `guffin-server` option `--allow-origin <origin>` (env `GUFFIN_SERVER_ALLOW_ORIGIN`),
  **default unset = no CORS**, preserving the current posture; the operator explicitly names
  the Roam origin to admit browser clients.
- When set: allow methods `GET`/`POST`/`OPTIONS`; allow the `Content-Type` request header;
  answer the PNA preflight header; and — easy to forget —
  `Access-Control-Expose-Headers: Content-Disposition, Content-Digest`, without which a
  browser client can read the body but not the filename it should save under nor the digest
  it could verify.
- Security posture, recorded in [server-mode.md](server-mode.md)'s terms: allowing the Roam
  origin means *any* extension or `roam/js` script in any graph on that machine can invoke
  the server. Within the trusted-operator model that is acceptable — same user, loopback
  bind, token held server-side — and server mode's planned phase-2 API key is the eventual
  tightening. The extension's settings anticipate an optional API-key field so it slots in
  without redesign.
- Tests in the offline tier: preflight answered, expose headers present, and — the posture
  guard — flag unset means **no** CORS headers at all.

## Phase 2 — extension MVP

> Implemented and verified live 2026-07-30, in the extension's own repository
> (`~/Documents/github/guffin-companion`: `extension.js`, README, CHANGELOG, MIT license —
> dev-mode loaded, not yet in Depot). Everything below is as specified; health, dump, and
> export (multiple targets and formats) confirmed end to end against `guffin-server
> --allow-origin https://roamresearch.com`, preflights and all.

**Targeting.** `roamAlphaAPI.ui.mainWindow.getOpenPageOrBlockUid()` → pass the **UID** as
`target`. The server accepts title-or-UID; the UID sidesteps every title-quoting question,
and a zoomed-in block naturally exports that subtree — exactly the CLI's own contract. The
null case (e.g. the scrolling daily-notes view) gets a clear message, not a guess.

**Commands** (via `extensionAPI.ui.commandPalette.addCommand`):

- *Guffin: Export current page/block* — the settings' default format and type
- *Guffin: Export current page/block as…* — one command per format, sharing the other
  defaults
- *Guffin: Dump current page/block*
- *Guffin: Server health* — `GET /v1/health`, toast the version + provenance

**Settings panel** (via `extensionAPI.settings.panel.create`): server URL (default
`http://127.0.0.1:8077`), default `output_format`, default `project_type`, request timeout,
and one free-form *extra request fields (JSON)* escape hatch. The escape hatch is the
panel's answer to a derived vocabulary: the request fields are read off the CLI signature
and will keep growing (`daily_note_format`, `default_pdf_render`, …), so every current and
future field stays reachable without the panel chasing the CLI — the server's
`GET /openapi.json` is the always-current field reference.

**Request flow.** POST `{target, output_format, project_type, …}` with an `AbortController`
on a generous, configurable timeout — renders can take minutes, and the server executes
invocations serially behind its process-wide lock, so requests also queue. Client-side
single-flight with a progress toast, so one impatient user does not stack five exports.

**Response flow.** `200` → blob; filename from `Content-Disposition` (a `.mdbundle` arrives
as a zip and saves as one — correct and expected); saved via the phase-0-verified mechanism.
Error → parse the RFC 9457 problem body and show `detail` — the complete captured
log/traceback text — in a scrollable overlay, never a truncated toast: that text is the
entire debugging story for a failed export (semantics-gate violations, code-source findings)
and is exactly what a terminal would have shown.

**Hygiene.** `onunload` unregisters every command, aborts in-flight fetches, and removes any
overlay DOM — the Depot contract.

## Phase 3 — rounding out

> Implemented and verified live 2026-07-30 (companion 0.3.0): all three items below, with the
> dump inspector rendering in a fully sandboxed iframe and a *Dump width* setting; the block
> context-menu commands (export / export-with-options / dump of the clicked subtree) register
> on `roamAlphaAPI` directly and follow the fixed-command-list unload discipline; a digest
> mismatch refuses to save and shows both hashes.

- **Dump rendering in-app**: request `console_format: "html"` and show the rendering in a
  sandboxed iframe overlay (or `svg` inline); `console_width` from settings. The dump
  becomes a visual inspector inside Roam.
- **Block context menu** (`roamAlphaAPI.ui.blockContextMenu.addCommand`): right-click any
  block → export/dump that subtree, no zooming required.
- **Integrity check**: hash the received blob with `crypto.subtle.digest` and compare
  against `Content-Digest` before saving — cheap, and the client-side half of the server's
  render-then-send reliability story.

## Phase 4 — optional: Depot distribution

> On **indefinite hold** (2026-07-30): dev-mode loading covers the sole user completely, and
> publication would add a maintenance/support surface with no present benefit. Everything
> below stays accurate whenever the hold lifts.

Repo with a `README` prominently documenting the prerequisite (a locally running
`guffin-server` with `GUFFIN_*` env and `--allow-origin`), metadata JSON PR to
`Roam-Research/roam-depot`, updates via `source_commit` bumps. Review posture is clean: no
remote code, no bundler, all traffic to a user-configured loopback service. Until then,
developer mode covers personal use indefinitely — this phase is genuinely severable.

## Risks

- **PNA enforcement drift**: Roam's current Electron does not enforce Private Network
  Access (phase 0 confirmed), but a Roam Desktop upgrade could start. Mitigated by emitting
  the PNA response header from day one (phase 1).
- **Origin changes**: an offline build or `file://` shell would present a different (or
  null) origin. Mitigated by `--allow-origin` being operator-set, never hardcoded.
- **Long renders vs. fetch timeouts**: the strictly-synchronous v1 means the extension
  simply waits. If that UX grates, the pressure points at server mode's phase 3
  (submit → poll → fetch), not at a client-side workaround.

## Open decisions

- **Multiple origins** — *resolved with phase 1*: `--allow-origin` is repeatable (the env
  var takes space-separated origins), per the leaning that it costs nothing now and avoids
  a v2 of the flag.
