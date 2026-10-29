"""Orchestrate one export: load the edition, typeset, write EPUB and/or PDF."""
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .. import __version__
from ..findings import ChampollionError
from .epub import build_epub
from .model import Book, DEFAULT_EDITIONS, available_editions, load_book
from .pdf import check_overflow, check_scale, find_chrome, html_to_pdf, html_to_png, check_folio, locate_body, locate_markers, page_texts, pdf_pages, require_poppler, set_info
import re
from .typeset import convert_mdc, prepare, unit_titles, COVER_CSS, Options, cover_markup, esc, print_html


def convert_font(path: str) -> Tuple[str, bytes]:
    """Return (ttf filename, bytes) for a font file, converting woff2/woff with fontTools when needed."""
    source = Path(path)
    if source.suffix.lower() in (".ttf", ".otf"):
        return source.name, source.read_bytes()
    try:
        from fontTools.ttLib import TTFont  # type: ignore
    except ImportError as exc:
        raise ChampollionError(f"cannot embed {source.name}: install fonttools (and brotli for woff2)", cause="ENGINE-MISSING") from exc
    # recalcTimestamp=False keeps the source head.modified; by default fontTools stamps the current
    # time on save, so the same font converted twice gives different bytes and the EPUB size check flaps.
    font = TTFont(str(source), recalcTimestamp=False)
    font.flavor = None
    buf = io.BytesIO()
    font.save(buf)
    return source.stem + (".otf" if "CFF " in font else ".ttf"), buf.getvalue()


def cover_image(book: Book, opts: Options, chrome: str):
    font_link = f'<link rel="stylesheet" href="{Path(opts.font_css).as_uri()}"/>' if opts.font_css else ""
    page = (f'<!doctype html><html><head><meta charset="utf-8"/>{font_link}<style>html,body{{margin:0;background:#000}}{COVER_CSS}</style></head>'
            f'<body>{cover_markup(book, opts)}</body></html>')
    data = html_to_png(page, chrome, 576, 864, 2.5)
    try:  # JPEG is a third of the size and what readers expect; Pillow is optional
        from PIL import Image  # type: ignore
        img = Image.open(io.BytesIO(data)).convert("RGB")
        out = io.BytesIO()
        img.save(out, "JPEG", quality=90, optimize=True, progressive=True)
        return out.getvalue(), "jpg"
    except ImportError:
        return data, "png"


def _timeout(html: str) -> int:
    """Chrome prints a book in seconds; a stall is cut off and retried, sooner for small books."""
    return int(min(1500, max(240, 240 + len(html) / 12000)))


def _verify_contents(book: Book, opts: Options, pdf: str, pages_map: Dict[int, int]) -> None:
    """Every contents entry must name the page where that division's heading really is."""
    texts = page_texts(pdf)
    norm = lambda s: re.sub(r"\s+", "", s).casefold()
    wrong = []
    for i, (kicker, title) in enumerate(unit_titles(book, opts)):
        heading = norm(title or kicker)[:24]
        page = pages_map[i]
        if not heading or page > len(texts) or heading not in norm(texts[page - 1]):
            wrong.append(f"{i + 1}:{title or kicker!r}->p{page}")
    if wrong:
        raise ChampollionError(f"{book.slug}: contents numbers do not match headings: {', '.join(wrong[:6])}", cause="ENGINE-FAILED")


def _finish_pdf(book: Book, opts: Options, out_path: str) -> Dict[str, object]:
    """Refuse a shrunken book, record the document information, and report it."""
    check_overflow(out_path)
    check_scale(out_path)
    check_folio(out_path, opts.folio_offset)
    by = f", translated by {book.translator}" if book.edition != "original" and book.translator else ""
    set_info(out_path, {
        "Title": f"{book.title} \u2014 {book.edition_label}",
        "Author": book.author,
        "Subject": f"{book.edition_label}{by}",
        "Keywords": ", ".join(x for x in [book.genre, book.period, book.tradition] if x),
        "Creator": opts.publisher,
        "Producer": f"Champollion {__version__}",
    })
    return {"path": out_path, "bytes": Path(out_path).stat().st_size, "pages": pdf_pages(out_path)}


def export_pdf(book: Book, opts: Options, out_path: str, chrome: str) -> Dict[str, object]:
    """Typeset to PDF. A probe pass prints the PDF page number as the folio, so the first page ending on its own number
    is where the text begins; the clean pass then prints folios from 1 there. For divided books the probe's invisible
    per-division markers also give each division's page for the contents; the clean result is checked to have the
    probe's page count, and re-measured if not."""
    require_poppler()
    book = prepare(book)
    numbered = book.divided and len(book.units) > 1 and not book.ref_mode
    pages_map: Optional[Dict[int, int]] = None
    probe = out_path + ".probe.pdf"
    try:
        for attempt in range(3):
            probe_pages = 0
            opts.markers, opts.toc_pages, opts.folio_offset = True, pages_map, 0
            html = print_html(book, opts)
            html_to_pdf(html, probe, chrome, _timeout(html))
            opts.folio_offset, probe_pages = locate_body(probe) - 1, pdf_pages(probe)
            opts.folio_pages = probe_pages + 20
            if numbered:
                found = locate_markers(probe, len(book.units))
                if len(found) != len(book.units):
                    raise ChampollionError(f"{book.slug}: found {len(found)} of {len(book.units)} division markers in the probe", cause="ENGINE-FAILED")
                pages_map = found
            opts.markers, opts.toc_pages = False, pages_map
            html = print_html(book, opts)
            html_to_pdf(html, out_path, chrome, _timeout(html))
            pages = pdf_pages(out_path)
            if not numbered or pages == probe_pages:
                if numbered:
                    _verify_contents(book, opts, out_path, pages_map or {})
                return _finish_pdf(book, opts, out_path)
        if numbered and pages_map:
            # The probe's markers shifted a break by a page, so probe and clean page counts never agree. Read each
            # heading's page from the clean PDF itself (within a page of the probe's guess), then confirm it still holds.
            norm = lambda t: re.sub(r"\s+", "", t).casefold()
            texts = page_texts(out_path)
            fixed: Dict[int, int] = {}
            for i, (kicker, title) in enumerate(unit_titles(book, opts)):
                heading = norm(title or kicker)[:24]
                guess = pages_map[i]
                hits = [q for q in (guess, guess - 1, guess + 1) if 0 < q <= len(texts) and heading and heading in norm(texts[q - 1])]
                if not hits:
                    break
                fixed[i] = hits[0]
            if len(fixed) == len(book.units):
                opts.markers, opts.toc_pages = False, fixed
                html_to_pdf(print_html(book, opts), out_path, chrome, _timeout(html))
                _verify_contents(book, opts, out_path, fixed)
                return _finish_pdf(book, opts, out_path)
        raise ChampollionError(f"{book.slug}: contents page numbers did not settle after 3 passes", cause="ENGINE-FAILED")
    finally:
        Path(probe).unlink(missing_ok=True)


def export_book(work: str, edition: str, formats: Sequence[str], out_dir: str, opts: Options,
                chrome: Optional[str] = None, epub_fonts: Sequence[str] = (),
                editions: Optional[Dict[str, Dict[str, object]]] = None) -> List[Dict[str, object]]:
    book = load_book(work, edition, editions)
    book.translator = opts.translator_names.get(book.translator, book.translator)
    if opts.mdc_transliteration and convert_mdc(book):
        book.note = ("Its transliteration is set in standard Egyptological letters (\ua723 j \ua725 \u1e25 \u1e2b \u1e96 \u0161 \u1e6f \u1e0f), "
                     "converted from the source\u2019s Manuel de Codage.")
    results: List[Dict[str, object]] = []
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    chrome_bin = find_chrome(chrome)
    stem = f"{book.slug}-{edition}"
    if "epub" in formats:
        fonts = []
        if book.source_language == "egy" and book.edition == "original":
            for spec in epub_fonts:
                family, _, path = spec.partition("=")
                name, data = convert_font(path)
                fonts.append((family, name, data))
        cover = cover_image(book, opts, chrome_bin)
        info = build_epub(book, opts, str(out / f"{stem}.epub"), cover, fonts)
        results.append({"format": "epub", "edition": edition, **info})
    if "pdf" in formats:
        info = export_pdf(book, opts, str(out / f"{stem}.pdf"), chrome_bin)
        results.append({"format": "pdf", "edition": edition, **info})
    return results
