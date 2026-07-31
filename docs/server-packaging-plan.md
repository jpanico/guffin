# Plan: guffin-server consumer packaging & distribution

> **Status: unimplemented plan** (drafted 2026-07-30). Produced by a multi-agent research pass
> (codebase recon + current-2026 platform research) followed by adversarial verification of
> every load-bearing claim; code facts below were verified to the file:line, platform facts
> against primary sources. Companion to [server-mode.md](server-mode.md) (what is being
> shipped) and [companion-extension-plan.md](companion-extension-plan.md) (the in-Roam client
> that consumes it).

## Requirements

- Target audience is **non-technical end-users** — not developers.
- Single-artifact distribution per target OS, installing with a single button push; ideally
  no installer.
- **All** dependencies/runtimes bundled — zero install-time or first-run downloads.
- Fully isolated from host/OS/application dependencies (no Python that anything else can
  see or break).
- Once installed: opaquely maintenance-free — a black box.
- Target OSs: macOS, Windows, Linux.

## The shape

Freeze the Python app with **PyInstaller 6.x in onedir mode** and wrap it per-OS in a native
single-artifact delivery: a signed + notarized **DMG** (macOS), a signed **MSIX** with an
Inno Setup fallback (Windows), a **type2-runtime AppImage** (Linux). The bundle carries
everything: CPython 3.14, all wheels, guffin's resource dirs, the official **pandoc** and
**typst** binaries, the **vendored Typst `@preview` packages** and **Noto fonts** (two
zero-download violations surfaced only by adversarial verification), and a small new
**tray/menu-bar launcher** that injects config, sets tool paths, runs uvicorn in a thread,
and gives users status/settings/quit. "Single binary" is satisfied at the *delivery* layer —
one double-clickable artifact per OS — not as one literal executable, which pandoc's
~190 MB on-disk size forecloses anyway.

## 1. Core technology

**Primary: PyInstaller ≥ 6.15, onedir.**

- PyInstaller added Python 3.14 support in 6.15.0 (2025-08) — the binding constraint, since
  guffin pins `requires-python >= 3.14`. Hooks exist for the whole compiled-dep set
  (pydantic-core, pypdfium2's ctypes-loaded PDFium, Pillow, uvicorn's dynamic imports).
- guffin is unusually freeze-friendly (verified): no dynamic imports, no multiprocessing,
  uvicorn receives the app *object* (`cli/serve.py`), resources load via
  `importlib.resources`.
- **onedir, never onefile**: onefile's extract-per-launch is slow and a leading antivirus
  false-positive trigger.

**Runner-up: Briefcase** (0.3.25+ has 3.14 support; produces DMG/MSI/AppImage with signing
and notarization driving built in). Worth a **timeboxed ≤3-day spike** before committing
bespoke CI: if a tray server fits its template, it deletes most signing plumbing. Frictions:
macOS console apps must ship as .pkg; a localhost tray server is off its GUI happy path.

**Rejected**: Nuitka (3.14 support still experimental in 4.1; adds a C toolchain per
platform), PyOxidizer (unmaintained since Jan 2023; Anki migrated off), PyApp (first-run
interpreter download violates zero-download), hand-rolled python-build-standalone (viable
base, but re-owns launcher/layout/signing per OS).

**Rejected: OCI containers (Docker/Podman) as the end-user distribution.** They fail nearly
every requirement at once: (1) the prerequisite runtime — Docker/Podman Desktop — is itself
a large developer-tool install needing admin rights, its own updater, and (Docker) its own
licensing, breaking "single button, bundle everything" before guffin enters the picture;
(2) on macOS/Windows a container runs inside a hidden Linux VM, with VM overhead and
lifecycle a black box shouldn't have; (3) the loopback inversion is functional, not
cosmetic — inside a container `127.0.0.1` is the container, so reaching Roam's Local API on
the *host* loopback needs `host.docker.internal`/host-networking special cases, and the
companion extension's requests to `127.0.0.1:8077` need port mapping back the other way —
two config-bearing crossings where the requirement is zero; (4) images, restart policies,
and volume mounts are Docker-literate maintenance by nature. The container *ideas* survive
elsewhere: Flatpak/Snap (desktop-containerized app formats) are evaluated and rejected in
§3, AppImage wins the Linux slot precisely by delivering a container image's bundling
benefit with no runtime/daemon prerequisite, and plain build containers appear on the CI
side (§7's old-glibc AppImage leg).

No freezer cross-compiles: each OS/arch needs a native CI runner.

## 2. Bundle architecture

```
GuffinServer/                     (macOS: "Guffin Server.app")
├── guffin-launcher               config→env injection, tool paths, tray UI, uvicorn thread
├── _internal/                    CPython 3.14 + all wheels + guffin package + dist-info
│   └── guffin/render/…           the 4 resource dirs as real on-disk files (never zip-frozen;
│                                 the .sublime-syntax grammars live inside typst_resources/)
├── tools/<os>-<arch>/
│   ├── pandoc, typst             official release binaries, pinned + checksummed
│   ├── typst-packages/           vendored @preview deps: glossarium, gentle-clues, linguify…
│   └── fonts/                    Noto Sans + Noto Sans Mono (SIL OFL)
└── licenses/                     see §6
```

Tool wiring (all verified to the line):

- **pandoc**: launcher sets `PYPANDOC_PANDOC=<bundle>/tools/…/pandoc`; pypandoc honors it as
  the *sole* candidate (replaces the whole search list), which also stops a user's newer
  Homebrew pandoc from shadowing ours (pypandoc otherwise picks the highest version found).
- **typst**: guffin never spawns typst — pandoc does, via `--pdf-engine` resolved on the
  PATH pandoc inherits. Launcher prepends the tools dir to `PATH` (Finder-launched apps get
  a bare `/usr/bin:/bin:…`), plus new `GUFFIN_TYPST_PATH` support making guffin emit an
  absolute `--pdf-engine` path (pandoc accepts one — live-tested).
- **Typst packages**: the Bergfink template imports `@preview/glossarium` and
  `@preview/gentle-clues` (plus transitives, e.g. `linguify`); typst downloads `@preview`
  packages from the network on first use. Unmitigated, the **first PDF export on a fresh
  machine performs network fetches and fails offline**. Vendor the packages in Typst's
  package layout and point `TYPST_PACKAGE_PATH` at them (Quarto documents this exact
  gathering workflow). The CI smoke test must run network-isolated to keep this honest.
- **Fonts**: `base_cfg.typ` requests Noto Sans / Noto Sans Mono, which neither typst nor
  stock macOS/Windows ship — typst silently substitutes, so end-user PDFs would not match
  the developer's. Bundle the fonts; set `TYPST_FONT_PATHS` for the pandoc→typst child.
- **pandoc-server acceleration**: leave disabled in bundles (opt-in via
  `GUFFIN_PANDOC_SERVER`, graceful fallback). Enabling later requires a code change:
  `render/pandoc_server.py` only knows `shutil.which("pandoc-server")`, and no separate
  binary ships — the `pandoc server` argv form is the packaging-safe spawn.
- Renderers pass resource paths to pandoc as absolute filesystem paths and via
  `GUFFIN_CALLOUT_ICONS_DIR`/`GUFFIN_CALLOUT_COLORS` env vars — so resources must be real
  files on disk; any zip-frozen layout is forbidden.

**Tray layer** (new `guffin/tray`, imported only by the launcher): rumps on macOS
(`LSUIElement=True` for a Dock-less agent; PyInstaller respects it), pystray on Windows
(windowed build — see §5.4's stdio caveat), best-effort on Linux (stock GNOME shows no tray
without a third-party extension, and freezing PyGObject/AppIndicator is fragile — the
loopback status page is the primary Linux surface). Menu: status, open settings, start at
login, copy server URL, quit.

**Size** (measured from release assets): pandoc 26–42 MB + typst 14–22 MB compressed per
platform, pandoc ~190 MB on disk; total artifact estimated 100–200 MB compressed — CI
records actuals per release. Never UPX-compress pandoc (breaks notarization; AV heuristics).

## 3. Per-OS delivery matrix

| OS | Artifact | Install UX | Signing | Arch |
|---|---|---|---|---|
| macOS | Signed, notarized, stapled **DMG** (drag-to-Applications) | Drag, launch; one one-time Gatekeeper "downloaded from the Internet" dialog — unavoidable even notarized | **Mandatory**: Sequoia removed the right-click bypass. Apple Developer $99/yr. Inside-out signing of *every* nested Mach-O (pandoc, typst, libpdfium, every .so) with hardened runtime + `allow-unsigned-executable-memory`; `--deep` is deprecated — never use it; `codesign --timestamp`; `notarytool` + staple app and DMG | **arm64-only**: Tahoe 26 is the last Intel macOS; universal2 blocked by thin pydantic-core/pypdfium2 wheels |
| Windows | Signed **MSIX** (primary) + signed **Inno Setup .exe** (Win10 fallback) | Double-click → App Installer's one Install button; clean uninstall | **Mandatory in practice** (Defender/SmartScreen on unsigned PyInstaller output). **Azure Trusted/Artifact Signing** $9.99/mo (individuals: US/Canada/EU/UK). Certs are ~72-hour-lived — **RFC 3161 timestamping is existential**, or signatures die days after release. No instant SmartScreen reputation exists any more (even EV lost it, 2024-08); submit each release to the FP portal. Trust floor: patched, online Win10 1809+ / Win11 | x86_64 (no official pandoc windows-arm64 exists; typst has one — pandoc is the sole blocker for native WoA) |
| Linux | **AppImage** on the statically linked **type2 runtime** (no libfuse2 dependency; kernel FUSE still needed — detect and fall back to `--appimage-extract-and-run`) | Download → mark executable (an honest extra step; guidance on the download page) → run; first run offers menu-entry/autostart install | None | x86_64 first; arm64 later (both tools publish linux-arm64) |

Flatpak rejected as primary: its shared runtime is a separate install-time download —
violates zero-download. Snap rejected (strict = friction, classic = no isolation). AppImage
provides dependency *isolation* without *sandboxing* — an acceptable reading of the
isolation requirement (nothing touches the host); accepted-or-not is open decision §10.7.
Build on **one** declared glibc baseline (Ubuntu 22.04 *or* manylinux_2_28 — they differ:
2.35 vs 2.28) and publish the resulting minimum-distro statement; the bundled tools don't
move the floor (typst Linux builds are musl-static, pandoc's Linux tarball is static — note
the macOS/Windows pandoc binaries are *not* static, merely OS-libs-only, and must be found
and signed like any other Mach-O/PE).

## 4. Config & first-run (the non-technical story)

Configuration today is env-var-only, which a GUI-launched app never inherits — a hard
blocker for the audience.

1. **Config file as the user surface**: TOML at the platform config dir (platformdirs) —
   `~/Library/Application Support/Guffin/`, `%APPDATA%\Guffin\`, `~/.config/guffin/`. Keys
   mirror the env vars.
2. **Zero-code-change injection**: the launcher `os.environ.setdefault()`s each key into the
   corresponding `GUFFIN_*` var before anything initializes; every option the config file
   needs already has `envvar=` plumbing (verified — note `--format`/`--type`/`--bundle`/
   `--suppress-attributes` do *not*, but those are per-request fields the extension sends).
   Real env vars still win (power-user escape hatch).
3. **First-run setup page** at `http://127.0.0.1:8077/setup`: graph name + token + "test
   connection", saved via a localhost endpoint that writes the config file. **The write
   endpoint must carry CSRF protection** (Origin/Host validation or a token): a loopback
   write is reachable by any website's simple form POST or DNS-rebinding page — CORS grants
   only govern *reads* (`server/cors.py` says so itself). The **launcher itself** opens the
   setup page on first run — the tray cannot be relied on (stock GNOME shows none; Windows
   11 hides new tray icons in the overflow — add a first-run window/toast).
4. **The honest limit**: the user must still obtain a Roam Local API token inside Roam
   Desktop's settings — the most technical step in the journey. Minimize (illustrated
   in-form walkthrough, paste validation, "Roam isn't running" diagnosis on test failure)
   but it cannot be eliminated; the plan says so rather than promising otherwise.
5. **Defaults baked into bundles**: `allow_origin = https://roamresearch.com`, host/port
   127.0.0.1:8077. Users never see CORS terminology.
6. **Autostart**: SMAppService (macOS 13+, signed apps self-register, visible in System
   Settings); per-user Startup-folder shortcut / MSIX `StartupTask` (Windows); systemd user
   unit with XDG autostart fallback (Linux).
7. **Robustness UX**: single-instance detection + a bind-failure dialog (a dead tray icon
   with no diagnosis is the anti-black-box); MSIX must declare filesystem virtualization
   disabled or the config file silently lives inside the package sandbox and dies on
   uninstall; an uninstall affordance on macOS/Linux (login item + config + cache cleanup —
   MSIX is the only leg with clean uninstall for free).
8. **Cache/logs** default to platform cache/log dirs in bundled mode (today
   `GUFFIN_CACHE_DIR` unset means no caching at all — a black box shouldn't re-download
   every Firestore asset per export). Never write beside the executable.

## 5. Prerequisite work in guffin (ordered)

0. **Stage 0 — OS-portability gate.** guffin has never run on Windows or Linux; the whole
   suite runs on one Mac. Stand up windows-latest/ubuntu-latest CI running the offline
   tiers plus a real PDF/EPUB export **before any packaging work**. First known bug: the
   hardcoded `--pdf-engine-opt=--root=/` (POSIX-ism; on Windows, files on another drive
   fall outside Typst's root and the compile fails).
1. Guard `importlib.metadata.version("guffin")` in `cli/params.py` (today `--version`
   *crashes* in a frozen bundle missing dist-info; `provenance.py` has the fallback pattern
   to copy) + `copy_metadata("guffin")` in the spec so /v1/health reports a real version.
2. Fix the five `as_file()` resource helpers (pdf_rendering ×2, md_rendering ×1,
   epub_rendering ×2) that return a Path *after* its context exits — dangling if resources
   were ever zip-imported; hold a lazily entered module-level ExitStack. Latent-correctness;
   onedir masks it.
3. Add `GUFFIN_TYPST_PATH` → absolute `--pdf-engine` value.
4. New `guffin/launcher` + `guffin/tray`: config injection (§4), tool paths (§2), Windows
   windowed-mode stdio redirection **before anything logs** (frozen `--windowed` builds have
   `sys.stdout/stderr = None`; uvicorn/rich would crash), `uvicorn.Server(Config(...))` in a
   worker thread with `should_exit` wiring for Quit (NOT `serve.main`'s blocking,
   signal-installing `uvicorn.run`), dispatch to the three Typer apps by subcommand (the
   `[project.scripts]` shims don't exist frozen).
5. `/setup` endpoint + config write, with the §4.3 CSRF protection.
6. platformdirs cache/log defaults in bundled mode.
7. PyInstaller spec: `collect_data_files("guffin")` (four resource dirs), certifi collected
   (TLS to Roam/Firestore/GitHub fails otherwise), hooks-contrib set.
8. *(Optional)* bake build provenance at freeze time — frozen bundles aren't git worktrees,
   so provenance degrades to `UNKNOWN_COMMIT` (gracefully — cosmetic only).
9. *(Deferred)* the `pandoc server` argv spawn form, only if the acceleration is ever
   enabled in bundles.

## 6. Licensing compliance

- **guffin stays MIT**: pandoc/typst are invoked strictly as subprocesses — FSF "mere
  aggregation"; no copyleft infection.
- **Redistributing the pandoc binary triggers GPLv2 §3**, and the naive fix was *refuted in
  verification*: pandoc binaries are statically linked Haskell containing dozens of Hackage
  libraries, and §3's "complete corresponding source" covers that dependency closure plus
  build scripts — the jgm/pandoc release tarball alone is a partial measure. Plan: archive
  per release (automated in CI) the pandoc source tarball **plus** the build's dependency
  pin (cabal freeze/plan.json) and fetched dependency sources; do **not** issue a 3-year
  written offer unless prepared to honor it in full — an unhonorable offer is worse than
  §3(a) source-accompanies-binary alone.
- `licenses/` dir + tray About→Licenses: GPL text + pandoc's COPYRIGHT *taken from the exact
  shipped artifact* (not repo HEAD); Apache-2.0 + typst's NOTICE at the pinned tag;
  pypdfium2's Apache/BSD texts **plus** `LicenseRef-PdfiumThirdParty.txt`; the Noto fonts'
  SIL OFL.
- Precedent: Quarto (MIT since 1.4) bundles GPL pandoc + Apache typst under `bin/tools/`
  with a public license inventory.
- Pin at authoring time: pandoc 3.10.1 (2026-07-22), typst 0.15.1 (2026-07-17; ≥ 0.14
  required for inline-native PDF placement).

## 7. CI / release pipeline

Tag-triggered GitHub Actions; three native legs (no cross-compilation):

| Runner | Output |
|---|---|
| macos-15 (arm64) | .app → inside-out sign (timestamped, hardened runtime) → notarytool → staple → DMG |
| windows-latest (x64) | onedir → Trusted Signing (timestamped) → MSIX + Inno .exe |
| old-glibc container (declared baseline) | AppDir → type2-runtime AppImage |

Stages per leg: fetch pinned pandoc/typst by checksum → vendor typst packages + fonts →
`pyinstaller guffin.spec` → sign → package → **network-isolated smoke test of the shipped
artifact** (launch, `/v1/health`, one offline PDF export from a recorded fixture — the only
stage that catches missing hooks, uncollected data, *and* the Typst-package download trap) →
upload with the GPL source archive + licenses. Secrets: Apple cert + notary API key; Azure
signing credentials. Naming: `GuffinServer-<semver>-<os>-<arch>.<ext>`. The guffin package
version is the product version; bundled tool versions in release notes + `/v1/health`
provenance.

## 8. Update story

- **MSIX**: versioned in-place updates via App Installer — essentially free.
- **macOS**: verification argued **Sparkle belongs in phase 1**, not phase 2 — the
  alternative (notification → re-download → quit → re-drag → relaunch) is the least
  black-box flow in the whole plan for this audience. Decision §10.5.
- **Linux**: notification-only (AppImageUpdate/zsync can't be assumed installed).
- Config/cache live outside the app dir, so updates never touch user state. Bundled
  pandoc/typst update *with* the app, never independently — preserving the
  tested-combination guarantee.
- The update check is a phone-home (an HTTP GET of a static release JSON) — default-on vs
  opt-in is decision §10.9.

## 9. Risk register

| # | Risk | Mitigation |
|---|---|---|
| 1 | Notarization rejects the bundle over any single unsigned nested Mach-O | Exhaustive find-and-sign in CI; smoke-notarize in week one, not at the end |
| 2 | SmartScreen/Defender friction even when signed (no instant reputation path exists) | Trusted Signing + RFC 3161 timestamping from day one; onedir; MSIX primary; FP-portal submission per release |
| 3 | Silent tool-resolution breakage (bare Finder PATH; Homebrew pandoc shadowing) | `PYPANDOC_PANDOC` absolute pin + `GUFFIN_TYPST_PATH`; startup self-check execs bundled pandoc/typst `--version` and surfaces failure in the tray |
| 4 | Tray + uvicorn + PyInstaller conflicts that only appear frozen | The tray spike is milestone 1 on all three OSs |
| 5 | MSIX containment breaks subprocess spawn / StartupTask / config-file visibility | Early MSIX prototype; virtualization declaration; Inno leg as tested fallback |
| 6 | Windows/Linux app-layer bugs discovered late | Stage-0 portability gate before any packaging (§5.0) |
| 7 | First PDF export downloads Typst packages / wrong fonts | Vendored packages + fonts (§2); network-isolated CI smoke test |
| 8 | GPL §3 compliance drift | Source + dependency-closure archive automated per release |
| 9 | Signing-account lead times gate everything | Enroll Apple + Azure immediately; decide individual-vs-org first (risk: an individual cert shows the owner's **legal name** in install/UAC dialogs, not "Guffin") |

## 10. Open decisions

1. Approve the ≤3-day **Briefcase spike** before bespoke CI work?
2. macOS **arm64-only** (recommended) or also x86_64?
3. Windows: keep the **Win10/Inno leg** or MSIX-only?
4. **Linux tier**: full parity or explicitly best-effort? Note the dependency: the "companion
   extension as the Linux control surface" assumes an installable extension, but its Depot
   submission is on indefinite hold ([companion-extension-plan.md](companion-extension-plan.md)) —
   either the status page carries the whole Linux UX, or the Depot hold is a dependency of
   this plan.
5. **Sparkle on macOS at launch**, or accept manual updates initially?
6. **Signing identity**: individual (owner's legal name visible in dialogs) or organization?
   Open Apple Developer ($99/yr) + Azure Trusted Signing ($9.99/mo) accounts regardless.
7. Is AppImage's **isolation-without-sandbox** an acceptable reading of the requirement?
8. **Autostart** default: on after first-run consent, or opt-in toggle only?
9. **Update check** (phone-home GET): default-on or opt-in?
10. **pandoc-server acceleration** in bundles: leave disabled (recommended; zero risk) or
    enable via the `pandoc server` argv form (§5.9)?
