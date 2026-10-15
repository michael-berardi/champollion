# Exporting books

`champollion export` typesets a work as a printed-quality **PDF** and a **Kindle-ready EPUB**, one book per edition: the original, and each register (Musean, Plain English, Historical in the `mouseia` profile). It reads the same work file the checks read and uses only the standard library, plus one external engine for PDF.

```sh
champollion export works/analects.md --out books/ \
  --publisher "My Press" --site-url example.org \
  --motif 道 --deep "#4a1815" --accent "#d16c5d" --unit-noun Book
```

Without `--edition` every edition present in the file is exported; without `--format` both formats are written (`<slug>-<edition>.pdf`, `<slug>-<edition>.epub`).

## Requirements

| Output | Needs |
| --- | --- |
| EPUB | nothing beyond Python 3.9+ (the cover is rendered by Chrome; `Pillow` makes it a JPEG when installed) |
| PDF | Chrome or Chromium (`--chrome`, `$CHAMPOLLION_CHROME`, or a standard install path) and `pdftotext`/`pdfinfo` from poppler, which place the page numbers in the contents |
| Egyptian fonts in EPUB | `fonttools` and `brotli`, to convert a `woff2` to a font EPUB readers accept |

A missing engine fails with a named error (`ENGINE-MISSING`); nothing is downloaded.

## What it makes

- **PDF**: 6 × 9 in, mirrored margins, a cover, half title, title page, an "About this edition" page (note, translator, source, gaps and uncertainties from the work's front matter), contents with page numbers, then the text. Verse keeps its lines with hanging indents; reference numbers (verse, section, Stephanus, papyrus line) sit in a left gutter; English gets curly quotes. Fonts come from `--font-css`, a stylesheet of `@font-face` rules with absolute `file:` URLs, or from the system.
- **EPUB 3**: reflowable, no forced fonts (the reader's font and size apply), a contents navigation file plus an NCX for older Kindle software, a cover, full metadata (title, author, translator as `trl`, language, publisher, date), and byte-identical output for the same input. Kindle accepts EPUB through *Send to Kindle* and the Kindle app.

## Layout decisions the exporter makes

- **Short divisions run on.** When the average division is under about a page, divisions share pages under small headings instead of each starting a page.
- **Divisions that are only reference numbers** (`Stephanus 17a`, `Verse 4`, `Clause 2`, `Declaration 9`, `Page 3`, `Column 1`) become margin numbers; they get no headings and no contents.
- **A title-cased opening line** before running prose is set as the division's subtitle.
- Reference-number syntax is the one the Mouseia reader uses (`src/champollion/export/refs.py`); the parser is a port, kept in step with it.

## Options

`--edition`, `--format`, `--out`, `--publisher`, `--site-url`, `--motif` (cover emblem), `--deep` and `--accent` (cover colours), `--unit-noun`, `--font-css`, `--epub-font FAMILY=FILE`, `--assets-dir` (resolves `/figures/...` image paths), `--colophon`, `--chrome`, `--json`.

The library entry points are `champollion.export.build.export_book`, `load_book`, `print_html` and `build_epub`.
