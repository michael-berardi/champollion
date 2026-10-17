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

- **PDF**: 6 × 9 in, equal left and right margins, a cover, title page, an "About this edition" page (note, translator, source, gaps and uncertainties from the work's front matter), contents, then the text, whose page numbers start at 1 on its first page (the contents uses the same numbers). Verse keeps its lines with hanging indents; reference numbers (verse, section, Stephanus, papyrus line) sit in a left gutter; English gets curly quotes, true dashes for `--`, and a spaced dash never starts a line. The document information (title, author, subject with the translator, keywords) is filled in. Fonts come from `--font-css`, a stylesheet of `@font-face` rules with absolute `file:` URLs, or from the system.
- **EPUB 3**: reflowable, no forced fonts (the reader's font and size apply), a contents navigation file plus an NCX for older Kindle software, a cover, full metadata (title, author, translator as `trl`, language, publisher, date), and byte-identical output for the same input. Kindle accepts EPUB through *Send to Kindle* and the Kindle app.

## Layout decisions the exporter makes

- **Short divisions run on.** When the average division is under about a page, or at least three in ten divisions are short (a diary's years), divisions share pages under small headings instead of each starting a page.
- **Long lines are paragraphs.** A block whose lines average 140 characters or more is prose whose paragraphs the source separated with single line breaks; it is set as justified paragraphs, not as verse.
- **A reference division that starts mid-sentence runs on** from the one before, with its number in the margin beside the line where it begins, so a Stephanus page break does not break a sentence into two paragraphs.
- **Stray numbers stay text.** A handful of numbered lines in an otherwise unnumbered book (a table) keeps its numbers in the text instead of giving the whole book a reference gutter; a 1, 2, 3… sequence stays a set of references.
- **Headings.** In an English edition a division title written only in the source script (學而篇第一) gives way to the English kicker (Book 1) and is shown beneath it; naive title case ("Trade Of Latium") takes lower-case small words; a division whose text opens by repeating its own heading drops the repeat.
- **Anthology poem titles** ("Wang Wei — Clear Creek" as a poem's first line) are set as titles.
- **Hieroglyphs wrap.** Runs of signs get a break opportunity after every sign.
- **Manuel de Codage** (`--mdc`): an Egyptian original with no hieroglyphs written in MdC ASCII (`i.wsx nmt m iwnw`) is set in the standard letters (`j.wsḫ nmt m jwnw`), and its edition note says so.
- **Nothing is silently clipped or shrunk.** Before printing, every line that cannot wrap is laid out at the print column width; a line too wide for the page fails the export (`PAGE-OVERFLOW`) with its opening words, as does a book Chrome scaled down.
- **Divisions that are only reference numbers** (`Stephanus 17a`, `Verse 4`, `Clause 2`, `Declaration 9`, `Page 3`, `Column 1`) become margin numbers; they get no headings and no contents.
- **A title-cased opening line** before running prose is set as the division's subtitle.
- Reference-number syntax is the one the Mouseia reader uses (`src/champollion/export/refs.py`); the parser is a port, kept in step with it.

## Options

`--edition`, `--format`, `--out`, `--publisher`, `--site-url`, `--motif` (cover emblem), `--deep` and `--accent` (cover colours), `--unit-noun`, `--font-css`, `--epub-font FAMILY=FILE`, `--assets-dir` (resolves `/figures/...` image paths), `--colophon`, `--mdc`, `--translator-credit NAME=CREDIT` (print a credit where the front matter names a translator, e.g. a house name to the person who made the translation), `--chrome`, `--json`.

The library entry points are `champollion.export.build.export_book`, `load_book`, `print_html` and `build_epub`.
