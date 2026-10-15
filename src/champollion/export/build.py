"""Orchestrate one export: load the edition, typeset, write EPUB and/or PDF."""
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from ..findings import ChampollionError
from .epub import build_epub
from .model import Book, DEFAULT_EDITIONS, available_editions, load_book
from .pdf import find_chrome, html_to_pdf, html_to_png, locate_markers, pdf_pages
from .typeset import prepare, COVER_CSS, Options, cover_markup, esc, print_html


def convert_font(path: str) -> Tuple[str, bytes]:
    """Return (ttf filename, bytes) for a font file, converting woff2/woff with fontTools when needed."""
    source = Path(path)
    if source.suffix.lower() in (".ttf", ".otf"):
        return source.name, source.read_bytes()
    try:
        from fontTools.ttLib import TTFont  # type: ignore
    except ImportError as exc:
        raise ChampollionError(f"cannot embed {source.name}: install fonttools (and brotli for woff2)", cause="ENGINE-MISSING") from exc
    font = TTFont(str(source))
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


def export_pdf(book: Book, opts: Options, out_path: str, chrome: str) -> Dict[str, object]:
    pages_map: Optional[Dict[int, int]] = None
    book = prepare(book)
    if book.divided and len(book.units) > 1 and not book.ref_mode:
        opts.markers, opts.toc_pages = True, None
        probe = out_path + ".probe.pdf"
        try:
            html_to_pdf(print_html(book, opts), probe, chrome)
            found = locate_markers(probe, len(book.units))
        finally:
            Path(probe).unlink(missing_ok=True)
        if len(found) == len(book.units):
            pages_map = found
        else:
            raise ChampollionError(
                f"{book.slug}: contents page numbers need pdftotext (poppler); found {len(found)} of {len(book.units)} markers",
                cause="ENGINE-MISSING")
    opts.markers, opts.toc_pages = False, pages_map
    html_to_pdf(print_html(book, opts), out_path, chrome)
    return {"path": out_path, "bytes": Path(out_path).stat().st_size, "pages": pdf_pages(out_path)}


def export_book(work: str, edition: str, formats: Sequence[str], out_dir: str, opts: Options,
                chrome: Optional[str] = None, epub_fonts: Sequence[str] = (),
                editions: Optional[Dict[str, Dict[str, object]]] = None) -> List[Dict[str, object]]:
    book = load_book(work, edition, editions)
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
