# Changelog

Changes are recorded in [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. Versions follow [Semantic Versioning](https://semver.org/).

Champollion enforces mechanical requirements and records judgement (VER-1). It does not translate or certify sense. The dated 1.0.0 entry records release contents, not approval to publish; SPEC.md remains a working specification until publication is approved.

## [1.10.0] - 2026-11-26

### Added

- Update notice (update contract v1): at most once a day, in interactive terminals only, one anonymous GET of the repository's public GitHub latest-release record; a two-line notice on stderr after the command. Off without a TTY, in CI, under agent hosts, for `--json`, from source checkouts and vendored snapshots, and with `CHAMPOLLION_NO_UPDATE_CHECK=1`. See `docs/updates.md`.
- `champollion update` with `--check` (exit 0 current, 10 available, 1 failed), `--skip`, `--auto on|off|status` and `--rollback`. Installer copies verify the wheel against the release's `SHA256SUMS` before a staged swap and keep one rollback copy; pip, uv and pipx copies run their package manager pinned to the release tag.
- Automatic installs, off by default: one detached, low-priority install per new version, a log under 256 KB, and the notice again if it fails.
- `PRIVACY.md` and a short README Privacy section.
- `tests/test_privacy.py`: fails if telemetry packages or tracking endpoints return, if a default command opens a socket or starts a subprocess, if the renderer loses its offline flags, or if toolkit-written text is not owner-only.

### Changed

- Files and folders created for project text, packets, review records, vendored snapshots and exported books are owner-only (0700/0600). Existing directories keep their mode; files the toolkit rewrites become 0600. On Windows the folder's permissions apply.
- The Chrome/Chromium renderer used by `export` runs with background networking, component updates, metrics, extensions and DNS disabled and `DO_NOT_TRACK=1`. Installers set `DO_NOT_TRACK=1` and run pip offline with no cache or version check.

### Migration

- Re-vendor v1.10.0 to adopt the owner-only permissions and offline renderer flags. No checker, profile, rule ID, report field or protocol version change. State lives in one owner-only `update.json` in the platform cache folder.
- Rollback: re-vendor v1.9.0.

## [1.9.0] - 2026-11-25

### Added

- Export typesetting for printed Markdown pipe tables and named source notes (`[^key]`):
  - Consecutive pipe-delimited rows (`| ... |`, with a second `|---|` divider row when a header is present) render as HTML tables (`<table class="tbl">`) in PDF and EPUB with one header row, all structural divider rows stripped (promoting row 0 to a header only when the divider is at index 1), escaped pipes (`\|`) preserved inside cells, padded ragged rows, per-cell escaping, inline note/reference markers, and `--inline-emphasis` support.
  - Inline `[^key]` calls render as superscript labels (`<sup class="fn">key</sup>`) and `[^key]: body` paragraphs render as note paragraphs (`<p class="note">`) carrying the same label; consecutive `[^key]:` definitions inside a single paragraph split into separate note blocks while preserving multi-line continuations, and malformed markers remain literal text.
  - Synthetic fixtures in `tests/test_export_tables_notes.py` cover headers, divider stripping, escaped pipes, ragged rows, escaping, table-cell note calls and author star marks, the emphasis option, consecutive and continued definitions, repeated and unreferenced notes, malformed keys, and EPUB CSS.

### Migration

- Feature release: no checker, profile, protocol, or vendored-gate change. Edition bodies containing pipe tables or `[^key]` source notes now typeset cleanly in PDF and EPUB; bodies without them are byte-identical.
- Rollback: re-vendor v1.8.0 (restore the previous vendored snapshot).

## [1.8.0] - 2026-11-20

### Added

- Author notes (SPEC §2.4): an author's footnotes are kept as `[Note L]` lines after their paragraph, with the printed mark `L` (`*)`, `**)`, `(a)`, `†`, …) written inline and unescaped. Motivated by Stirner's 1845 *Der Einzige und sein Eigenthum* in Mouseia, whose `*)`/`**)` marks had to be rewritten as (a)/(b) because the debris gate flagged `**`. Fixtures `author-notes` and `author-notes-unpaired`.
- `champollion packets split|verify|join` for long texts: split an Original into packets of at most N words at paragraph/heading boundaries; verify each draft packet against its source packet for identical paragraph anchors, page markers, heading count and note lines, naming missing, extra, duplicate and out-of-order items per packet (exit 1 on failure); rejoin in order, refusing (`WRK-5`) with `--source` when any packet fails. Haiku drafts of the Stirner edition dropped 19 page markers across 128 packets. Fixture `packets`. The existing `packets --register --units [--root] [--out] [--json]` form is unchanged; `packets` with neither a subcommand nor both `--register` and `--units` is now a named usage error (`champollion: usage: ...`, still exit 2) rather than an argparse error.
- `champollion.dta`: `join_hyphen_signs` joins DTA `¬` hyphenation across emphasis spans, page markers and note anchors and returns unresolved residuals; `page_label` reads `<pb n="35 [354]">`. docs/sourcing.md documents DTA TEI extraction traps, including footnotes inside `<p>` and footnotes split across page breaks.

### Fixed

- VER-6 (clarified under the same ID): a star note mark paired within its unit, an inline `**)` with a `[Note **)]` line, is no longer `VER-DEBRIS`. Unpaired marks, escaped marks and other markup on the line are still reported.
- `verify-vendor` no longer fails a vendored snapshot because interpreter caches (`__pycache__/*.pyc`, `*.pyo`) exist; it lists them under a new `bytecode` result key. `vendor` already excluded them from the manifest. Other files in `__pycache__` and loose `.pyc` files remain `extra`.
- `export --inline-emphasis` no longer pairs two `*)` note marks on one line as italics: an emphasis marker cannot open before `)`.

### Migration

- Feature release: no profile field, rule ID or protocol version change, and no new gate. VER-6 can only report fewer findings, for paired note marks. `verify-vendor` JSON gains the `bytecode` key, and a snapshot whose only extras were bytecode caches now verifies. The new `packets split|verify|join` subcommands are opt-in; existing `packets`, `review` and `assemble` invocations behave as before.
- Mouseia: the vendored compatibility gate does not follow this release automatically. Sync it deliberately: `champollion vendor --into vendor --tag v1.8.0`, then `champollion verify-vendor vendor/champollion`, rerun the frozen-oracle comparisons and focused fixtures, and commit the snapshot, integrity evidence and migration record together after the host's release review. Author notes rewritten as (a)/(b) to dodge the old debris gate may be restored to their printed `*)`/`**)` marks only after that sync.
- Rollback: re-vendor v1.7.1 (restore the previous vendored snapshot).

## [1.7.1] - 2026-11-20

### Fixed

- PDF export: Chinese and Literary Chinese text (`lang` `zh*`, `lzh*`) is set with `text-spacing-trim:space-all`, so full-width punctuation keeps its full advance at line ends. Under the default `normal`, Chrome 157 fits a line by trimming its closing `。”` and then paints them untrimmed, up to half an em past the column; the overflow probe then refused the book with `PAGE-OVERFLOW` (hall-secret-teachings-plain-zh, 2026-11-19: `…都等于701。”` 6.1px past a 424px column). Chrome 153 trimmed consistently and never overflowed. EPUB output is unchanged.
- PDF export: the overflow probe measures again once the web fonts have loaded (`document.fonts.ready`), not only as the page is parsed. A line measured in a fallback face before a font-css slice arrived could fit and then print wider than the column: the same hall-secret-teachings-plain-zh page passed one print and failed the next.

### Migration

- Re-vendor and rebuild Chinese PDFs. Line breaks in Chinese and Literary Chinese books can move where a line ended on trimmed punctuation, so page counts and folios can change; PDFs cached before this release keep the old line breaks. A book that passed before can now be refused with `PAGE-OVERFLOW` if a line overflows only in its printing face: fix the line rather than pinning 1.7.0. No protocol, profile, CLI flag, or report-field changes. Rollback: re-vendor v1.7.0.

## [1.7.0] - 2026-11-16

### Added

- Summary sidecars: optional `basis.unit_sha256` (one hash per unit). When a unit's text changes, `summary check` names the changed units (`SUM-STALE ... units 3, 7 changed`), so only those need re-review. `summary units` prints each unit's `sha256`.
- Summary sidecars: optional `summary.blurb`, one or two complete sentences for search results and link previews (at most 160 characters, 80 when mostly CJK). It is part of the `summary schema` output, not required.
- Summary sidecars: optional operator-stamped `lang`, `model` and `edition_source_sha256`. `summary check --lang LANG` requires a matching `lang`; a stamped source hash is compared with the edition's `source_sha256`.
- `SUM-TRUNCATED`: a reader-facing field that ends with an ellipsis, comma, semicolon, colon or dash, or a gist, overview, context, blurb, idea explanation or unit summary that does not end a sentence. A quotation ending in an ellipsis inside closing quotes is accepted.
- `champollion.summary` exports the rules a generator needs to satisfy the gate: `word_count`, `ending_problem`, `blurb_limit`, `passage_in`, `passage_key`, `clean_quote`, `quote_markup`.

### Changed

- Word limits are CJK-aware: ideographs count as 10/17 of a word each (rounded up) plus the remaining letter or digit tokens. Chinese summaries were previously counted as one word per run of text.
- Verbatim passages are compared with numbering, reference markers and emphasis marks set aside, so a verse edition with numbered lines can be quoted. A stored passage that itself contains such markup is refused (`SUM-PASSAGE ... contains markup`). A Latin-script passage must start and end on word boundaries.
- A key idea with no units is reported as a `SUM-XREF` warning.

### Migration

- All new fields are optional; existing `champollion-summary/1` sidecars keep their meaning. Re-vendor to adopt. The stricter checks can fail existing sidecars that end mid-sentence or quote text with emphasis marks: repair those fields before enabling the new snapshot in a build gate.

## [1.6.3] - 2026-11-15

### Fixed

- Vendor verification reports symlinked files without hashing their targets. An unreadable target no longer aborts the integrity report; symlinks still make the snapshot invalid.
- Installation documentation starts with working release installers; installer defaults, package metadata, and documentation use the repository URL instead of an owner placeholder. Export requirements correctly include Chrome for EPUB covers and POSIX process handling for both formats.
- Corrected the contributing guide's changelog path and refreshed package citation metadata.
- Migration: re-vendor and verify the new snapshot before adoption. No protocol, profile, CLI flag, or report-field changes.

## [1.6.2] - 2026-11-11

### Fixed

- Both installers: an upgrade over a `champollion` command written by 1.6.0 (which had no marker line) told the user the command was not ours and left it in place, so a broken Windows command was never repaired. The exact 1.6.0 command is now recognised as the installer's own and replaced; any other file is still left alone. On Windows the final health check runs through the command the installer wrote.

## [1.6.1] - 2026-11-11

### Fixed

- Windows installer: the `champollion.cmd` command was written as ASCII with an absolute path, so a Windows profile name with accents (for example `C:\Users\José`) produced a command pointing at nothing. The default command now uses a path relative to its own folder; a `CHAMPOLLION_BIN_DIR` override writes the absolute path in the console's OEM code page.
- Windows installer: if moving the new install into place failed, the previous install stayed moved aside; it is now put back.
- Windows installer: the user Path is read without expanding `%VAR%` entries, so existing entries are no longer rewritten as hard-coded paths; a relative or `/`-style `CHAMPOLLION_HOME` or `CHAMPOLLION_BIN_DIR` is normalised first; stderr lines from `python`, `pip` and the health check no longer abort the install on Windows PowerShell 5.1; the installer no longer leaves its preferences or function in the user's session after `irm | iex`.
- Both installers never overwrite a `champollion` command they did not write (their own command carries a marker line) and say so in one line, and both print the health check's result instead of discarding it.

## [1.6.0] - 2026-11-11

### Added

- One-step installers: `scripts/install.sh` (macOS and Linux) and `scripts/install.ps1` (Windows PowerShell 5.1 and 7, also runs under PowerShell 7 on Linux for testing). They download the release wheel named in `SHA256SUMS`, verify its SHA-256 before installing anything, install it into a private venv under `~/.champollion` (`%LOCALAPPDATA%\Champollion` on Windows) using the Python 3.9+ already on the machine, and put the `champollion` command in `~/.local/bin` (on Windows in the install's `bin` folder, added to the user PATH). Re-running upgrades in place; no sudo, no shell-profile edits, no new runtime dependencies.
- `scripts/build-release.sh` assembles the release assets into `dist/release/` (reproducible wheel and source archive from `scripts/build-release.py`, both installers with the release repository taken from the git remote, `SHA256SUMS` covering every asset except itself).
- `scripts/test-install.sh` tests the installers against a short-lived local release server: on the host, in an `ubuntu:24.04` container, and under PowerShell 7 in the `mcr.microsoft.com/powershell` container (install, upgrade, version check, corrupted wheel refused, missing Python named).
- README Install section leads with the two one-liners and notes that PDF export runs on macOS and Linux only (it controls headless Chrome through POSIX process groups); the checks, review, summary and EPUB export run on macOS, Linux and Windows.

## [1.5.0] - 2026-11-11

### Added

- Source-language review: an opt-in `champollion review` command group (`packets`, `verify-packets`, `apply`, `record`) that cuts every unit of the Original and every aligned register into parallel passages, writes deterministic reviewer packets bound to passage hashes, validates reviewer replies and writes independent second-reader packets, applies only confirmed or amended findings by exact single-match replacement under named refusal rules (stale passage, non-unique quotation, changed markers/line breaks/headings, disproportionate fixes, overlapping edits), never edits the Original, and writes a VER-11-shaped review record that `report` accepts. Offline and provider-neutral: packets and reply files only, no model calls. See [docs/review.md](docs/review.md).
- Migration: opt-in. No existing check, profile or vendored gate changes. A model-run review is machine review and must be recorded as such, never as human editorial approval.

## [1.4.3] - 2026-11-10

### Fixed

- PDF export: when the probe's invisible division markers disagree with the clean PDF's pagination even though the page counts agree (a heading drifted a page under the probe, seen with Chrome CJK pagination in the 2026-11-08 huangting export), the clean PDF is re-measured from its own text within a page of the probe's guess and re-settled, instead of failing with "contents numbers do not match headings".
- Tag `v1.4.2` was pushed with this fix but never released: its tree still declared version 1.4.1, so it was not published as 1.4.2. Version 1.4.2 is not a released version; 1.4.3 is the first release of this fix.
- Migration: re-vendor the new release and verify the snapshot and focused fixtures before adopting it. No checker, profile or protocol change.

## [1.4.1] - 2026-11-09

### Fixed

- The export credits PerseusDL-hosted original texts to `the Perseus Project, Trustees of Tufts University`, the rights holder named in the TEI headers, instead of `the Perseus Digital Library`, which hosts the files but is not the rights holder.
- Migration: re-vendor the new release and verify the snapshot and focused fixtures before adopting it. No checker, profile or protocol change.

## [1.4.0] - 2026-11-07

### Added

- Summaries: an optional study-guide sidecar for each complete work (`summaries/<work-id>.json`, format `champollion-summary/1`). It holds a one-line gist, an overview, authorial context, key facts, key ideas tracked to the units where they are developed, a summary of every unit, figures, terms, explained verbatim passages, and a machine index (genres, forms, themes, concepts, people, places, period, keywords, typed links to other works in the corpus). See [docs/summaries.md](docs/summaries.md).
- `champollion summary units` prints a register's units and basis hash; `champollion summary schema` prints the structured-output schema for the drafted fields; `champollion summary check` validates sidecars offline with named codes (`SUM-SCHEMA`, `SUM-WORK`, `SUM-STALE`, `SUM-UNITS`, `SUM-LENGTH`, `SUM-XREF`, `SUM-PASSAGE`, `SUM-RELATED`, `SUM-SLUG`, `SUM-REVIEW` warning, `SUM-MISSING` with `--require`). A summary that no longer matches its edition fails as stale.
- The summary check reads only front matter and section boundaries, so works accepted by a project's legacy gate can be summarised; `--works-glob` skips files without front matter, and related links resolve against the whole corpus even when only some works are checked.

### Migration

- Opt-in. No existing check, profile or vendored gate changes. Champollion ships no drafting model: the `aid` field records whatever tool or person drafted the summary.

## [1.3.0] - 2026-11-01

### Changed

- Neutralized shipped metadata and documentation: install commands, repository URLs, issue-tracker links, citation metadata and maintainer text no longer name a personal GitHub account. Neutral placeholders (`your-github-username`) and neutral maintainer text replace the previous handle. Legal attribution remains in `LICENSE`, `LICENSE-docs` and the package-metadata `authors` field.
- Added `tests/test_neutrality.py`, which scans shipped files for concrete model ids, ordered fallback chains and personal names. It excludes legal attribution and synthetic test fixtures, and it fails on the pre-change tree. Mouseia remains named as an external legacy-corpus and format identity.
- Migration: no checker, profile or protocol change. Projects that copied the previous install command should use the neutral placeholder or their own fork URL.

## [1.2.6] - 2026-10-30

### Fixed

- The Mouseia legacy compatibility lint matches the existing frozen Mouseia gate for paired `**strong**`, footnote tokens and pipe-prefixed lines. This legacy rule does not detect debris inside strong spans or validate table syntax; other lint checks still inspect the text.
- Migration: re-vendor the new release and verify the snapshot and focused fixtures before adopting it. Existing debris baselines for supported markup can be reviewed and removed when no longer needed; other checks, profiles and the protocol are unchanged. The strict checker is separate from the legacy compatibility lane.

## [1.2.4] - 2026-10-30

### Fixed

- WOFF2 conversion accepts whichever Brotli backend the installed fontTools supports, and the fonts extra requires fontTools 4.0.1 or newer to avoid an obsolete Python array API. Invalid fonts report an engine failure; CFF2 fonts use the correct OTF extension.
- Migration: no checker, profile or protocol change. Builds using the supported fontTools Brotli backend can embed WOFF2 fonts; malformed font errors are now reported as `ENGINE-FAILED`.

## [1.2.3] - 2026-10-30

### Fixed

- PDF creation and modification metadata dates are normalized to the Unix epoch, and contents leaders are solid rather than dotted, removing sources of build-to-build byte variation. Byte identity is not guaranteed across Chrome versions, platforms, fonts, or other build environments. Unsupported or malformed Chrome PDF metadata fails with `ENGINE-PDF-METADATA` rather than being rewritten by guesswork.
- Migration: no checker, profile, protocol or vendored-gate change. PDF bytes and the appearance of contents leaders change; existing EPUB output is unaffected.

## [1.2.2] - 2026-10-29

### Added

- Optional extras declare the engines that embedded fonts and cover images need: `pip install "champollion-protocol[fonts]"` adds `fonttools` and `brotli` (woff2 fonts), and `pip install "champollion-protocol[images]"` adds `Pillow` (JPEG cover). Missing engines still fail with a named `ENGINE-MISSING` error, and the default install stays dependency-free.
- Migration: no checker, profile, protocol or vendored-gate change. Output is unchanged for a build that already has its engines; a woff2 font without `brotli` now names the `fonts` extra in its error.

### Tests

- Hermetic tests for the woff2 font path and the JPEG cover path skip when their engine is not installed; a test confirms the cover stays PNG without Pillow. The SOURCE_DATE_EPOCH guard test on `main` ships in this release line.

## [1.2.1] - 2026-10-29

### Fixed

- An embedded WOFF or WOFF2 font is converted without changing its `head` timestamp, so the same font gives the same EPUB bytes on every build. Before, fontTools stamped the current time on each save and the size check could flap between rebuilds.
- Migration: no checker, profile, protocol or vendored-gate change. EPUBs with embedded WOFF/WOFF2 fonts will differ in bytes from 1.2.0 builds, but are otherwise unchanged; Mouseia's pinned manifest is not changed by this release.

## [1.2.0] - 2026-10-26

### Added

- Opt-in `champollion export --inline-emphasis` and Python `Options(inline_emphasis=True)` preserve source emphasis written as `*italics*` and `**bold**` in PDF and EPUB books. Text remains escaped; malformed, nested and cross-line markers stay literal. Synthetic fixtures cover source references, verse, Unicode, safe escaping, and unchanged default output.
- Migration: no checker, profile, protocol or vendored-gate change. The option is off by default; existing exports retain their literal asterisks. Enable it only for editions that deliberately encode emphasis this way.

## [1.1.5] - 2026-10-17

### Fixed

- A PDF is refused by name unless its first page of text prints the folio 1, including when the contents numbers had to be re-measured after three passes.

## [1.1.4] - 2026-10-17

### Fixed

- Right-to-left books with hanging reference numbers mirror the page margins and opener padding, so the text column stays centred with the number gutter on the right.

## [1.1.3] - 2026-10-17

### Fixed

- PDF page numbers restart at 1 on the first page of text instead of counting the cover, title page, imprint and contents; the contents page numbers follow the same numbering.
- PDF text pages have the same margin on both sides instead of a wider inner margin that alternated by page, and chapter openers in books with hanging reference numbers are centred over the text column.

## [1.1.2] - 2026-10-16

### Fixed

- A Chrome exit code during teardown (macOS CVDisplayLink, exit 2 under heavy load) no longer fails an export when Chrome has written its complete output and reported it; any other abnormal exit is still a named failure.

## [1.1.1] - 2026-10-16

### Fixed

- Export retries once when Chrome exits abnormally (macOS CVDisplayLink exit 2 under load), not only on a timeout, before raising the named engine error.

## [1.1.0] - 2026-10-16

### Added

- `champollion export`: typeset each edition of a work as a PDF (headless Chrome, 6 × 9 in, contents with page numbers) and as an EPUB 3 for Kindle and other readers. Standard library only apart from the PDF engine. See docs/export.md.
- `champollion export --translator-credit NAME=CREDIT`; PDF document information (author, subject, keywords).
- `champollion export --mdc`: Egyptian originals in Manuel de Codage are set in standard transliteration.
- Export refuses a book with a line wider than the page (`PAGE-OVERFLOW`) instead of letting Chrome clip it or shrink every page.

### Fixed

- Egyptian originals: hieroglyph runs wrap inside the page (they had made Chrome print the whole book at about two-thirds size, with lines clipped).
- Prose paragraphs separated by single line breaks were set as verse; reference divisions that start mid-sentence broke the sentence into two paragraphs; a few numbered table lines put a whole book into the numbered layout.
- English editions show English division headings with the source-script title beneath, in a serif CJK face; naive title case and headings repeated in the text are tidied; anthology poem titles are set as titles.
- Diaries and other works of mostly short divisions run on instead of giving each a page; readable edition dates; `--` becomes a dash.
- EPUB contents of reference-divided works name each file's range (Stephanus 17a–25a); hieroglyph lines wrap on narrow screens.

## [1.0.1] - 2026-10-13

### Fixed

- The first-work guide now edits the project-local profile without replacing project configuration.
- Installation instructions create an isolated environment; release checksum paths are explicit.
- Checker and vendored-package versions are independent of the unchanged 1.0.0 protocol version.
- Added an executable first-work walkthrough regression.

## [1.0.0] - 2026-10-13

### Added

- Protocol version 1.0.0 with work format `champollion/1`, scalar front matter, and profile schema `champollion-profile/1`.
- Stable rule families SRC (sourcing and rights), SEG (segmentation and alignment), REG (registers), VER (verification), PRV (provenance), and WRK (collaboration), with mechanical checks distinguished from recorded judgement.
- Python 3.9+ standard-library reference implementation, distributed as `champollion-protocol` with import package and console command `champollion`; checks use local evidence without network calls.
- CLI contract: `init`, `source add`, `check`, `lint` (alias of `check`), `packets`, `assemble`, `report`, `rules`, `profile validate`, `vendor`, and `verify-vendor`.
- Three shipped profiles: `generic`, `mouseia`, and `latin-to-spanish`. Language-specific policies belong in profiles.
- A complete Latin-to-Spanish example with independent `literaria` and `clara` registers, and a read-only Mouseia adoption example.
- Specification, method, adoption, authoring, verification, provenance, collaborator, acceptance-matrix, and migration documentation.
- Standard-library `unittest` fixture discipline: a failing fixture, rule ID, profile setting, finding code, migration note, and changelog entry for each new gate or changed rule; an independently frozen oracle when asserting compatibility with Mouseia's legacy linter (SPEC.md §11). Recorded judgement remains required under VER-10 and VER-11.
- Separate MIT code and CC BY 4.0 specification/documentation licenses, offline Make targets, and tracked-file SHA-256 release manifest generation.
