# Changelog

Changes are recorded in [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. Versions follow [Semantic Versioning](https://semver.org/).

Champollion enforces mechanical requirements and records judgement (VER-1). It does not translate or certify sense. The dated 1.0.0 entry records release contents, not approval to publish; SPEC.md remains a working specification until publication is approved.

## [Unreleased]

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
