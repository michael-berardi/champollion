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
from champollion.export.typeset import (Options, Theme, dek_ok, human_date, is_flow, is_poem_title, is_prose, prepare, print_html,
                                        convert_mdc, render_blocks, smarten, split_label, tidy_title, unit_titles)
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


RUN_ON = """---
slug: run-on
title: "Run On"
author: Plato
tradition: greek
language: grc
musean_translator: Mouseia
as_of: 2026-10-14
---

## Original

### Stephanus 17a

ἀρχή.

### Stephanus 17b

τέλος.

### Stephanus 17c

ἔτι.

## Mouseia translation

### Stephanus 17a

I shall defend myself against the earlier

### Stephanus 17b

accusers first. That is fair.

### Stephanus 17c

Next the later ones.
"""


class LayoutCase(unittest.TestCase):
    def test_dashes(self):
        self.assertEqual(smarten("true -- isn't it"), "true\u00a0\u2014 isn\u2019t it")
        self.assertEqual(smarten("so--then"), "so\u2014then")
        self.assertEqual(smarten("a --- b"), "a --- b")

    def test_a_division_that_starts_mid_sentence_runs_on_with_its_number_in_the_margin(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = prepare(load_book(write(tmp, "run-on.md", RUN_ON), "musean"))
            first = book.units[0].blocks[0].lines[0]
            self.assertEqual([s.margin for s in first.segments if s.margin], ["17b"])
            self.assertEqual(book.units[1].blocks, [])
            self.assertEqual(book.units[2].blocks[0].lines[0].lead, "17c")   # a new sentence keeps its own paragraph
            html = print_html(book, Options())
            self.assertIn('earlier <span class="ref run">17b</span>accusers first.', html)

    def test_long_lines_are_paragraphs_and_short_lines_are_verse(self):
        long = "A sentence long enough to be prose rather than verse, running on well past any line of poetry. " * 2
        prose = parse_body(f"{long}\n{long}")[0]
        verse = parse_body("Sing, goddess, the wrath\nof Peleus' son Achilles\nthat brought ten thousand sorrows")[0]
        self.assertTrue(is_prose(prose))
        self.assertFalse(is_prose(verse))
        html = render_blocks([prose], "en", Options())
        self.assertEqual(html.count('<p class="prose para'), 2)
        self.assertIn('prose para cont', html)

    def test_anthology_poem_titles(self):
        block = parse_body("Wang Wei \u2014 Clear Creek\nWhenever I enter Yellow Flower River,\nI follow the Clear Creek's waters.")[0]
        self.assertTrue(is_poem_title(block))
        self.assertIn('<span class="ln poem-title">Wang Wei', render_blocks([block], "en", Options()))
        self.assertFalse(is_poem_title(parse_body("Smintheus \u2014 if ever I roofed a temple,\nor burned the thighs\nof bulls")[0]))

    def test_hieroglyph_runs_can_break(self):
        html = render_blocks(parse_body("(1.1) \U00013337\U000130ED\U00013324 [\u2bd1]", original=True, language="egy"), "egy", Options())
        self.assertIn("\U00013337<wbr/>\U000130ED<wbr/>\U00013324", html)

    def test_english_headings_for_titles_in_the_source_script(self):
        work = CHAPTERS.replace("### Chapter I\n\nHow", "### Chapter 1 學而篇第一\n\nHow").replace("language: fr", "language: lzh")
        with tempfile.TemporaryDirectory() as tmp:
            book = load_book(write(tmp, "chaptered.md", work), "musean")
            self.assertEqual(unit_titles(book, Options(unit_noun="Chapter"))[0], ("", "Chapter 1"))
            html = print_html(book, Options(unit_noun="Chapter"))
            self.assertIn('<p class="src-title" lang="lzh">學而篇第一</p>', html)
            original = load_book(write(tmp, "chaptered.md", work), "original")
            self.assertNotIn('class="src-title"', print_html(original, Options(unit_noun="Chapter")))

    def test_stray_numbers_stay_in_the_text(self):
        body = "\n\n".join(["Plain paragraph of running prose."] * 30 + ["90  = 29,886", "80  = 23,638"])
        work = CHAPTERS.replace("Premier chapitre en français, assez long pour compter comme un paragraphe.", body)
        with tempfile.TemporaryDirectory() as tmp:
            book = prepare(load_book(write(tmp, "chaptered.md", work), "original"))
            lines = [l for u in book.units for b in u.blocks for l in b.lines]
            self.assertFalse(any(l.lead for l in lines))
            self.assertIn("90 = 29,886", [l.plain() for l in lines])

    def test_mostly_short_divisions_run_on(self):
        units = "".join(f"### Year {1550 + i}\n\n{'Short entry. ' * 5}\n\n" for i in range(8)) + "### Year 1600\n\n" + "Long entry. " * 1200
        work = CHAPTERS.split("## Original")[0] + "## Original\n\n" + units
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(is_flow(load_book(write(tmp, "chaptered.md", work), "original")))

    def test_title_case_small_words_and_repeated_headings(self):
        work = CHAPTERS.replace("### Chapter I\n\nHow the First", "### Chapter 1 — The Early Trade Of Latium And Etruria\n\nCHAPTER I\n\nTHE EARLY TRADE OF LATIUM AND ETRURIA\n\nHow the First")
        with tempfile.TemporaryDirectory() as tmp:
            book = prepare(load_book(write(tmp, "chaptered.md", work), "musean"))
            self.assertEqual(unit_titles(book, Options(unit_noun="Chapter"))[0], ("Chapter 1", "The Early Trade of Latium and Etruria"))
            self.assertTrue(book.units[0].blocks[0].lines[0].plain().startswith("How the First"))
        self.assertEqual(tidy_title(book, "Book One \u00b7 On Absorption"), "Book One \u00b7 On Absorption")

    def test_manuel_de_codage_becomes_standard_transliteration(self):
        work = CHAPTERS.replace("language: fr", "language: egy").replace(
            "Premier chapitre en français, assez long pour compter comme un paragraphe.", "i.wsx nmt m iwnw\nn ir.i isft Dd-mdw in N")
        with tempfile.TemporaryDirectory() as tmp:
            book = load_book(write(tmp, "chaptered.md", work), "original")
            self.assertTrue(convert_mdc(book))
            self.assertEqual([l.plain() for l in book.units[0].blocks[0].lines], ["j.ws\u1e2b nmt m jwnw", "n jr.j jsft \u1e0fd-mdw jn N"])
            self.assertFalse(convert_mdc(book))  # already standard letters: left alone

    def test_parenthetical_titles_become_subtitles(self):
        work = CHAPTERS.replace("### Chapter I\n\nHow", "### Chapter 1 (Mahabharata 3.293)\n\nHow")
        with tempfile.TemporaryDirectory() as tmp:
            book = load_book(write(tmp, "chaptered.md", work), "musean")
            self.assertEqual(unit_titles(book, Options(unit_noun="Chapter"))[0], ("", "Chapter 1"))
            self.assertIn('<p class="src-title">Mahabharata 3.293</p>', print_html(book, Options(unit_noun="Chapter")))

    def test_human_dates(self):
        self.assertEqual(human_date("2026-09-17"), "17 September 2026")
        self.assertEqual(human_date("c. 1600"), "c. 1600")


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
            info = __import__("subprocess").run(["pdfinfo", pdf["path"]], capture_output=True, text=True).stdout
            self.assertRegex(info, r"Author:\s+Someone")
            self.assertRegex(info, r"Producer:\s+Champollion")

    def test_translator_credit_and_scale_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = write(tmp, "chaptered.md", CHAPTERS.replace("as_of:", "musean_translator: House\nas_of:"))
            files = export_book(work, "musean", ["pdf"], str(Path(tmp) / "out"),
                                Options(unit_noun="Chapter", translator_names={"House": "Jane Doe"}))
            info = __import__("subprocess").run(["pdfinfo", files[0]["path"]], capture_output=True, text=True).stdout
            self.assertIn("translated by Jane Doe", info)
            # an unbreakable line wider than the page makes Chrome shrink every page: refused by name
            wide = CHAPTERS.replace("Second chapitre.", "\n".join(["a short line"] * 5 + ["W" * 300]))
            with self.assertRaises(ChampollionError) as ctx:
                export_book(write(tmp, "wide.md", wide), "original", ["pdf"], str(Path(tmp) / "wide"), Options(unit_noun="Chapter"))
            self.assertEqual(ctx.exception.cause, "PAGE-OVERFLOW")


if __name__ == "__main__":
    unittest.main()
