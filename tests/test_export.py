"""Book export: reference-number parsing, typesetting decisions, EPUB structure, optional PDF."""
import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.dom import minidom

sys.dont_write_bytecode = True

from champollion.cli import main
from champollion.export.build import export_book
from champollion.export.epub import build_epub
from champollion.export.model import available_editions, load_book
from champollion.export.pdf import find_chrome
from champollion.export.refs import parse_body
from champollion.export.typeset import Options, Theme, dek_ok, is_flow, prepare, print_html, smarten, split_label
from champollion.findings import ChampollionError

WORK = """---
slug: demo-work
title: "The Demo of Tests"
author: Anon Author
tradition: greek
language: grc
genre: dialogue
period: c. 400 BCE
source_url: "https://github.com/PerseusDL/canonical-greekLit/blob/master/demo.xml"
musean_translator: Mouseia
musean_note: "A complete test edition."
as_of: 2026-10-14
unknowns: none known
---

## Original

### Stephanus 17a

Ἀνδρες Ἀθηναῖοι, τὸ μὲν ἐγώ.

### Stephanus 17b

ἔτι τοῦτο λέγω καὶ τὰ ἄλλα.

## Mouseia translation

### Stephanus 17a

"Men of Athens," he said, "it's true -- isn't it?" Wait...

### Stephanus 17b

And so it goes on, 'tis said.
"""

CHAPTERS = """---
slug: chaptered
title: "A Chaptered Work"
author: Someone
tradition: european
language: fr
as_of: 2026-10-14
---

## Original

### Chapter I

Premier chapitre en français, assez long pour compter comme un paragraphe.

### Chapter II

Second chapitre.

## Mouseia translation

### Chapter I

How the First Chapter Was Written, and Why It Was Short

The first chapter in English, long enough to count as running prose for the layout rules in this test, so that it is clearly past the one hundred and twenty character mark.

### Chapter II

The second chapter.
"""


def write(directory, name, text):
    path = Path(directory) / name
    path.write_text(text, "utf-8")
    return str(path)


class RefsCase(unittest.TestCase):
    def test_numbers_become_margin_references(self):
        blocks = parse_body("1.1 First passage\n\n1.2 Second passage")
        self.assertEqual([b.lines[0].lead for b in blocks], ["1.1", "1.2"])
        self.assertEqual(blocks[0].lines[0].plain(), "First passage")

    def test_papyrus_lines_and_rubrics(self):
        blocks = parse_body("(7.7) * rubric line\n(7.8) plain line")
        self.assertEqual([(l.lead, l.rubric) for l in blocks[0].lines], [("7.7", True), ("7.8", False)])

    def test_gita_verse_numbers_close_the_verse(self):
        blocks = parse_body("धर्मक्षेत्रे ॥१२- ७॥", original=True)
        self.assertEqual(blocks[0].lines[0].lead, "12.7")
        self.assertTrue(blocks[0].lines[0].plain().endswith("॥"))

    def test_inline_notes_and_stephanus_marks(self):
        segments = parse_body("Word.[11] more [17b] text")[0].lines[0].segments
        self.assertEqual([(s.note, s.ref) for s in segments if s.note or s.ref], [("11", ""), ("", "17b")])

    def test_bekker_markers_flow_as_one_paragraph(self):
        block = parse_body("[Bekker 1447a line 8]\nLet us speak.\n[Bekker 1447a line 10]\nof the art.")[0]
        self.assertEqual(len(block.lines), 1)
        self.assertEqual([s.ref for s in block.lines[0].segments if s.ref], ["1447a8", "10"])

    def test_years_are_not_reference_numbers(self):
        self.assertEqual(parse_body("1492\nColumbus sailed")[0].lines[0].lead, "")


class TypesetCase(unittest.TestCase):
    def test_smart_quotes_apostrophes_and_ellipses(self):
        self.assertEqual(smarten('"It\'s," he said... \'tis'), "“It’s,” he said… ‘tis")

    def test_unit_labels_split_into_kicker_and_title(self):
        self.assertEqual(split_label("Chapter 1 — Initial Assessments", 0, "Chapter"), ("Chapter 1", "Initial Assessments"))
        self.assertEqual(split_label("Book 1 學而篇第一", 0, "Book"), ("Book 1", "學而篇第一"))
        self.assertEqual(split_label("12", 11, "Chapter"), ("Chapter 12", ""))
        self.assertEqual(split_label("The Flight", 0, "Part"), ("", "The Flight"))

    def test_reference_divided_works_carry_numbers_in_the_margin(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = prepare(load_book(write(tmp, "demo-work.md", WORK), "musean"))
            self.assertTrue(book.ref_mode and is_flow(book))
            self.assertEqual([u.blocks[0].lines[0].lead for u in book.units], ["17a", "17b"])
            html = print_html(book, Options())
            self.assertNotIn('class="opener', html)      # no heading per Stephanus page
            self.assertNotIn('class="front toc"', html)  # and no contents of 125 page numbers
            self.assertIn("“Men of Athens,”", html)
            # numbered text keeps the same visual centring as unnumbered text: the number gutter comes out of the page margins
            self.assertIn("@page body{margin:.95in .72in .98in .40in}", html)
            self.assertNotIn("half-title", html)

    def test_subtitle_lines_and_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = load_book(write(tmp, "chaptered.md", CHAPTERS), "musean")
            first = book.units[0].blocks
            self.assertTrue(dek_ok(first[0].lines[0], first + first))
            html = print_html(book, Options(unit_noun="Chapter"))
            self.assertIn('class="front toc"', html)
            self.assertIn("Contents", html)


class EpubCase(unittest.TestCase):
    def test_epub_package_is_well_formed(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = write(tmp, "chaptered.md", CHAPTERS)
            out = Path(tmp) / "book.epub"
            info = build_epub(load_book(work, "musean"), Options(publisher="Test Press", unit_noun="Chapter"), str(out))
            self.assertGreater(info["bytes"], 1000)
            with zipfile.ZipFile(out) as z:
                names = z.namelist()
                self.assertEqual(names[0], "mimetype")
                self.assertEqual(z.getinfo("mimetype").compress_type, zipfile.ZIP_STORED)
                self.assertEqual(z.read("mimetype"), b"application/epub+zip")
                for name in names:
                    if name.endswith((".xhtml", ".opf", ".ncx", ".xml")):
                        minidom.parseString(z.read(name))
                opf = z.read("OEBPS/content.opf").decode()
                self.assertIn("<dc:title>A Chaptered Work — Musean Translation</dc:title>", opf)
                self.assertIn("<dc:publisher>Test Press</dc:publisher>", opf)
                self.assertIn('properties="nav"', opf)
                nav = z.read("OEBPS/nav.xhtml").decode()
                self.assertIn("Chapter I", nav)

    def test_same_input_gives_identical_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = write(tmp, "chaptered.md", CHAPTERS)
            for name in ("a.epub", "b.epub"):
                build_epub(load_book(work, "original"), Options(), str(Path(tmp) / name))
            self.assertEqual((Path(tmp) / "a.epub").read_bytes(), (Path(tmp) / "b.epub").read_bytes())


class ModelCase(unittest.TestCase):
    def test_editions_present_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = write(tmp, "demo-work.md", WORK)
            self.assertEqual(available_editions(work), ["original", "musean"])
            with self.assertRaises(ChampollionError) as ctx:
                load_book(work, "plain")
            self.assertIn("plain", str(ctx.exception))

    def test_translator_and_note_come_from_front_matter(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = load_book(write(tmp, "demo-work.md", WORK), "musean")
            self.assertEqual((book.translator, book.note, book.language), ("Mouseia", "A complete test edition.", "en"))
            self.assertEqual(load_book(write(tmp, "demo-work.md", WORK), "original").language, "grc")


class SafetyCase(unittest.TestCase):
    def test_unsafe_slug_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = write(tmp, "x.md", CHAPTERS.replace("slug: chaptered", "slug: ../../etc/x"))
            with self.assertRaises(ChampollionError) as ctx:
                load_book(work, "musean")
            self.assertIn("safe file name", str(ctx.exception))

    def test_figures_must_stay_inside_the_assets_directory(self):
        from champollion.export.typeset import _asset
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp) / "assets"
            (assets / "figures").mkdir(parents=True)
            (assets / "figures" / "a.png").write_bytes(b"png")
            (Path(tmp) / "secret.txt").write_text("x")
            opts = Options(assets_dir=str(assets))
            self.assertTrue(_asset("/figures/a.png", opts).endswith("a.png"))
            for bad in ("/../secret.txt", "/figures/../../secret.txt", "/figures/missing.png"):
                with self.assertRaises(ChampollionError):
                    _asset(bad, opts)

    def test_markup_in_titles_is_escaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = write(tmp, "chaptered.md", CHAPTERS.replace('title: "A Chaptered Work"', 'title: "A <script>x</script> & Work"'))
            html = print_html(load_book(work, "musean"), Options())
            self.assertNotIn("<script>x", html)
            self.assertIn("&lt;script&gt;", html)

    def test_rtl_epub_declares_direction(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = write(tmp, "ar.md", CHAPTERS.replace("language: fr", "language: ar").replace("slug: chaptered", "slug: arabic"))
            out = Path(tmp) / "ar.epub"
            build_epub(load_book(work, "original"), Options(), str(out))
            with zipfile.ZipFile(out) as z:
                self.assertIn('page-progression-direction="rtl"', z.read("OEBPS/content.opf").decode())
                self.assertIn('dir="rtl"', z.read("OEBPS/c001.xhtml").decode())


def _chrome():
    try:
        return find_chrome()
    except ChampollionError:
        return None


@unittest.skipUnless(_chrome(), "Chrome/Chromium not installed")
class PdfCase(unittest.TestCase):
    def test_cli_exports_a_pdf_and_epub(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = write(tmp, "chaptered.md", CHAPTERS)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                status = main(["export", work, "--edition", "musean", "--out", str(Path(tmp) / "out"), "--json", "--unit-noun", "Chapter"])
            self.assertEqual(status, 0)
            files = json.loads(out.getvalue())["files"]
            self.assertEqual(sorted(f["format"] for f in files), ["epub", "pdf"])
            pdf = next(f for f in files if f["format"] == "pdf")
            self.assertTrue(Path(pdf["path"]).read_bytes().startswith(b"%PDF"))
            self.assertGreaterEqual(pdf["pages"], 4)  # cover, title, imprint, text


if __name__ == "__main__":
    unittest.main()
