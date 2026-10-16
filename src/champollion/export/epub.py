"""EPUB 3 writer (stdlib only). Kindle accepts EPUB through Send to Kindle; every major reader opens it."""
from __future__ import annotations

import datetime
import re
import uuid
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .model import Book
from .typeset import _sentence, prepare, COVER_CSS, Options, display_title, esc, human_date, is_flow, lang_attr, render_blocks, source_host, source_titles, unit_titles

EPUB_CSS = '''
html{-epub-hyphens:auto;hyphens:auto}
body{margin:0 4%;padding:0;line-height:1.5;font-family:serif}
h1,h2,h3{font-weight:normal;margin:0;page-break-after:avoid;break-after:avoid;hyphens:manual;-epub-hyphens:manual}
.opener{text-align:center;margin:3.2em 0 1.6em;page-break-before:always;break-before:page}
.opener.compact{margin:2.2em 0 1em;page-break-before:auto;break-before:auto}
.opener.first{page-break-before:auto;break-before:auto}
.opener .k{font-size:.72em;letter-spacing:.24em;text-transform:uppercase;color:#8a6a2c;margin-bottom:.9em}
.opener h2{font-size:1.55em;line-height:1.2}
.orn{text-align:center;color:#8a6a2c;margin:.8em 0 0}
.text p{margin:0}
.prose{text-align:justify;text-indent:1.3em}
.text .prose:first-child,.subhead+.prose,.dek+.prose{text-indent:0}
.prose.numbered{text-indent:0;margin-top:.7em}
.lines{margin:.9em 0}
.ln{display:block;margin:0;margin-inline-start:1.7em;text-indent:-1.7em}
.ref{font-size:.74em;color:#8a6a2c;margin-inline-end:.55em;letter-spacing:.03em;font-variant-numeric:oldstyle-nums}
.rubric{color:#8c3b2c}
.mk{font-size:.7em;color:#8a6a2c;vertical-align:super;margin:0 .15em}
.fn{font-size:.7em;vertical-align:super;line-height:0;color:#8a6a2c}
.dek{text-align:center;font-style:italic;color:#6f6659;margin:-.4em 0 1.4em;text-indent:0}
.subhead{font-size:.74em;letter-spacing:.2em;text-transform:uppercase;color:#8a6a2c;text-align:center;margin:2em 0 .8em !important;text-indent:0}
.fig{margin:1.2em 0;text-align:center;page-break-inside:avoid}.fig img{max-width:100%}
.fig figcaption{font-size:.85em;font-style:italic}
.cover-img{display:block;margin:0 auto;max-width:100%;max-height:100%}
.tp{text-align:center;margin-top:4em}.tp .mark{font-size:2.6em;color:#8a6a2c;line-height:1}
.tp h1{font-size:2em;line-height:1.1;margin:1em 0 .3em}.tp .by{letter-spacing:.2em;text-transform:uppercase;font-size:.78em;margin-top:1.4em}
.tp .ed{font-style:italic;color:#8a6a2c;font-size:1.2em;margin-top:1em}.tp .pub{margin-top:3em;font-size:.7em;letter-spacing:.3em;text-transform:uppercase;color:#777}
.about h2{font-size:.72em;letter-spacing:.2em;text-transform:uppercase;color:#8a6a2c;margin:1.6em 0 .4em}
.about h2:first-child{margin-top:0}.about p{margin:0 0 .5em;font-size:.95em}.about .fine{color:#777;font-size:.8em;margin-top:2em}
.text[lang^="lzh"],.text[lang^="zh"]{line-height:1.8}
.text[lang^="ar"]{line-height:1.95}
.text[lang^="egy"]{line-height:1.7}
.prose.para{text-indent:0}.prose.para.cont{text-indent:1.3em}
.ref.run{margin-inline-start:.25em}
.ln.poem-title{font-style:italic;color:#8a6a2c;margin:1.6em 0 .3em;text-indent:0;margin-inline-start:0}
.src-title{margin:.3em 0 0;color:#6f6659;letter-spacing:.06em}
.tp .pub-by{margin-top:.6em;color:#555}
.text[lang^="egy"] .ln{overflow-wrap:anywhere}
nav ol{list-style:none;padding:0;margin:0}nav li{margin:.35em 0}nav a{color:inherit;text-decoration:none}
'''


def _xhtml(title: str, body: str, lang: str, css: str = "style.css", dir_attr: str = "") -> str:
    lang = lang_attr(lang) or "en"
    return ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{esc(lang)}" xml:lang="{esc(lang)}"{dir_attr}>'
            f'<head><meta charset="utf-8"/><title>{esc(title)}</title><link rel="stylesheet" type="text/css" href="{css}"/></head>'
            f'<body>{body}</body></html>')


def _group(book: Book, flow: bool) -> List[List[int]]:
    """Unit indexes per XHTML file: each unit alone unless units are short, then grouped by size."""
    if not flow:
        return [[i] for i in range(len(book.units))]
    groups: List[List[int]] = []
    size = 0
    for i, unit in enumerate(book.units):
        n = sum(len(l.plain()) for b in unit.blocks for l in b.lines)
        if groups and size + n <= 36000 and len(groups[-1]) < 40:
            groups[-1].append(i)
            size += n
        else:
            groups.append([i])
            size = n
    return groups


def build_epub(book: Book, opts: Options, out_path: str, cover: Optional[Tuple[bytes, str]] = None,
               fonts: Sequence[Tuple[str, str, bytes]] = ()) -> Dict[str, object]:
    """Write the EPUB. ``fonts`` is (family, filename, ttf bytes) to embed."""
    book = prepare(book)
    ref_mode = book.ref_mode
    titles = unit_titles(book, opts)
    sources = source_titles(book, opts)
    flow = is_flow(book)
    ident = uuid.uuid5(uuid.NAMESPACE_URL, f"{opts.site_url or 'urn:champollion'}/{book.slug}/{book.edition}")
    date = book.as_of if re.match(r"^\d{4}-\d{2}-\d{2}$", book.as_of or "") else "2026-01-01"
    modified = f"{date}T00:00:00Z"
    lang = lang_attr(book.language) or "en"
    files: List[Tuple[str, str, bytes, str]] = []   # (path, id, data, media-type)
    spine: List[Tuple[str, str]] = []                # (id, properties)

    css = EPUB_CSS
    for family, filename, _ in fonts:
        css = f'@font-face{{font-family:"{family}";src:url("fonts/{filename}")}}\n' + css
    if fonts:
        fams = ",".join(f'"{f}"' for f, _, _ in fonts)
        css += f'.text[lang^="egy"]{{font-family:{fams},serif}}\n'

    def add(path: str, ident_: str, text: str, media: str = "application/xhtml+xml", props: str = "", in_spine: bool = True):
        files.append((path, ident_, text.encode("utf-8"), media + (("|" + props) if props else "")))
        if in_spine:
            spine.append((ident_, props))

    cover_png = cover is not None
    if cover:
        ext = cover[1]
        files.append((f"images/cover.{ext}", "cover-img", cover[0], ("image/png" if ext == "png" else "image/jpeg") + "|cover-image"))
        add("cover.xhtml", "cover", _xhtml(book.title, '<div style="text-align:center"><img class="cover-img" src="images/cover.' + cover[1] + '" alt="Cover: ' + esc(book.title) + '"/></div>', lang), props="")
    tp_by = f'<p class="by">{esc(book.author)}</p>'
    tp = (f'<div class="tp"><div class="mark">{esc(opts.theme.motif)}</div><h1>{esc(book.title)}</h1>{tp_by}'
          f'<p class="ed">{esc(book.edition_label)}</p>'
          + (f'<p class="pub-by">Translated by {esc(book.translator)}</p>' if book.edition != "original" and book.translator else "")
          + f'<p class="pub">{esc(opts.publisher)}</p></div>')
    add("title.xhtml", "title", _xhtml(book.title, tp, "en"))
    about = ['<div class="about">']
    about.append("<h2>This edition</h2><p>" + (esc(book.note) if (book.edition != "original" and book.note) else (esc(book.edition_label) if book.edition != "original" else "The complete source text in the original language, without translation." + (f" {esc(book.note)}" if book.note else ""))) + "</p>")
    if book.edition != "original" and book.translator:
        about.append(f"<h2>Translator</h2><p>{esc(book.translator)}</p>")
    if book.period or book.genre:
        about.append("<h2>The work</h2><p>" + " · ".join(x for x in [f"Written {esc(book.period)}" if book.period else "", esc(book.genre[:1].upper() + book.genre[1:]) if book.genre else ""] if x) + "</p>")
    if book.source_url:
        about.append(f"<h2>Source</h2><p>Original text from {esc(source_host(book.source_url) or book.source_url)}.</p>")
    if book.unknowns and not book.unknowns.lower().startswith("none"):
        about.append(f"<h2>Gaps and uncertainties</h2><p>{esc(_sentence(book.unknowns))}</p>")
    tail = " · ".join(x for x in [opts.publisher, opts.site_url] if x)
    about.append(f'<p class="fine">{esc(tail)}' + (f'<br/>Edition dated {esc(human_date(book.as_of))}' if book.as_of else "") + "</p></div>")
    add("about.xhtml", "about", _xhtml("About this edition", "".join(about), "en"))

    toc: List[Tuple[str, str]] = []
    for gi, group in enumerate(_group(book, flow)):
        parts: List[str] = []
        for i in group:
            kicker, title = titles[i]
            if book.divided and not ref_mode:
                head = esc(title or kicker)
                k = f'<div class="k">{esc(kicker)}</div>' if kicker and title else ""
                cls = "opener" + (" compact" if flow else "") + (" first" if i == 0 else "")
                sl = esc(lang_attr(book.source_language))
                src_lang = "" if re.search(r"[A-Za-z]", sources[i]) else f' lang="{sl}" xml:lang="{sl}"'
                src = f'<p class="src-title"{src_lang}>{esc(sources[i])}</p>' if sources[i] else ""
                parts.append(f'<section id="u{i}"><header class="{cls}">{k}<h2>{head}</h2>{src}' + ('' if flow else '<p class="orn">❦</p>') + '</header>')
            else:
                parts.append(f'<section id="u{i}">')
            body = render_blocks(book.units[i].blocks, book.language, opts, epub=True)
            parts.append(body + "</section>")
            if not ref_mode:
                toc.append((f"c{gi + 1:03d}.xhtml#u{i}", display_title(kicker, title) or book.title))
        if ref_mode:
            # One entry per file, named by the reference range it holds (Stephanus 17a–25a).
            first, last = display_title(*titles[group[0]]), display_title(*titles[group[-1]])
            span = first if first == last else f"{first}\u2013{last.split()[-1]}"
            toc.append((f"c{gi + 1:03d}.xhtml#u{group[0]}", span or book.title))
        add(f"c{gi + 1:03d}.xhtml", f"c{gi + 1:03d}", _xhtml(book.title, "".join(parts), lang, dir_attr=' dir="rtl"' if book.direction == "rtl" else ""))
    # figures
    for xhtml in [f for f in files if f[0].startswith("c")]:
        pass
    # nav
    nav_items = "".join(f'<li><a href="{href}">{esc(label)}</a></li>' for href, label in toc) if len(toc) > 1 else ""
    first_href = toc[0][0] if toc else "c001.xhtml"
    nav = ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">'
           '<head><meta charset="utf-8"/><title>Contents</title><link rel="stylesheet" type="text/css" href="style.css"/></head><body>'
           '<nav epub:type="toc" id="toc"><h1 style="text-align:center">Contents</h1><ol>'
           + (nav_items or f'<li><a href="{first_href}">{esc(book.title)}</a></li>') + '</ol></nav>'
           '<nav epub:type="landmarks" hidden="hidden"><ol>'
           + ('<li><a epub:type="cover" href="cover.xhtml">Cover</a></li>' if cover_png else "")
           + f'<li><a epub:type="bodymatter" href="{first_href}">Start of text</a></li></ol></nav></body></html>')
    files.append(("nav.xhtml", "nav", nav.encode("utf-8"), "application/xhtml+xml|nav"))
    # spine order: cover, title, about, nav, text
    order = [s for s in spine]
    head = [x for x in order if x[0] in ("cover", "title", "about")]
    rest = [x for x in order if x[0] not in ("cover", "title", "about")]
    spine_final = head + [("nav", "")] + rest
    # NCX (Kindle / EPUB 2 readers)
    ncx_points = "".join(
        f'<navPoint id="n{i}" playOrder="{i + 1}"><navLabel><text>{esc(label)}</text></navLabel><content src="{href}"/></navPoint>'
        for i, (href, label) in enumerate(toc))
    ncx = ('<?xml version="1.0" encoding="utf-8"?>\n<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><head>'
           f'<meta name="dtb:uid" content="urn:uuid:{ident}"/><meta name="dtb:depth" content="1"/><meta name="dtb:totalPageCount" content="0"/><meta name="dtb:maxPageNumber" content="0"/></head>'
           f'<docTitle><text>{esc(book.title)}</text></docTitle><navMap>{ncx_points}</navMap></ncx>')
    files.append(("toc.ncx", "ncx", ncx.encode("utf-8"), "application/x-dtbncx+xml"))
    files.append(("style.css", "css", css.encode("utf-8"), "text/css"))
    for family, filename, data in fonts:
        files.append((f"fonts/{filename}", "font-" + re.sub(r"\W", "", filename), data, "font/ttf" if filename.endswith(".ttf") else "font/otf"))
    # embedded figures
    figure_files = _collect_figures(files)
    files.extend(figure_files)

    manifest = []
    for path, fid, data, media in files:
        mt, _, props = media.partition("|")
        manifest.append(f'<item id="{esc(fid)}" href="{esc(path)}" media-type="{mt}"' + (f' properties="{props}"' if props else "") + "/>")
    spine_xml = "".join(f'<itemref idref="{esc(i)}"' + (' linear="yes"' if True else "") + "/>" for i, _ in spine_final)
    creator = book.author or "Anonymous"
    description = (book.note if book.edition != "original" and book.note else f"{book.title}, {book.edition_label}.")
    meta = [
        f'<dc:identifier id="uid">urn:uuid:{ident}</dc:identifier>',
        f'<dc:title>{esc(book.title)} — {esc(book.edition_label)}</dc:title>',
        f'<dc:creator id="creator">{esc(creator)}</dc:creator>',
        f'<dc:language>{esc(lang)}</dc:language>',
        f'<dc:publisher>{esc(opts.publisher)}</dc:publisher>',
        f'<dc:description>{esc(description[:600])}</dc:description>',
    ]
    if book.edition != "original" and book.translator:
        meta.append(f'<dc:contributor id="trl">{esc(book.translator)}</dc:contributor><meta refines="#trl" property="role" scheme="marc:relators">trl</meta>')
    if book.genre:
        meta.append(f'<dc:subject>{esc(book.genre)}</dc:subject>')
    if opts.site_url:
        meta.append(f'<dc:source>https://{esc(re.sub(r"^https?://", "", opts.site_url).strip("/"))}/texts/{esc(book.slug)}</dc:source>')
    if cover_png:
        meta.append('<meta name="cover" content="cover-img"/>')
    if book.as_of:
        meta.append(f'<dc:date>{date}</dc:date>')
    meta.append(f'<meta property="dcterms:modified">{modified}</meta>')
    opf = ('<?xml version="1.0" encoding="utf-8"?>\n<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid" xml:lang="' + esc(lang) + '">'
           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">' + "".join(meta) + "</metadata>"
           f'<manifest>{"".join(manifest)}</manifest><spine toc="ncx"{' page-progression-direction="rtl"' if book.direction == "rtl" else ""}>{spine_xml}</spine>'
           '<guide>' + ('<reference type="cover" title="Cover" href="cover.xhtml"/>' if cover_png else "") + f'<reference type="text" title="Start" href="{first_href.split("#")[0]}"/></guide></package>')
    container = ('<?xml version="1.0" encoding="utf-8"?>\n<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    stamp = (2026, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(out_path, "w") as z:
        def put(name: str, data: bytes, stored: bool = False):
            info = zipfile.ZipInfo(name, stamp)
            info.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)
        put("mimetype", b"application/epub+zip", stored=True)
        put("META-INF/container.xml", container.encode("utf-8"))
        put("OEBPS/content.opf", opf.encode("utf-8"))
        for path, _, data, _ in files:
            put(f"OEBPS/{path}", data)
    return {"path": out_path, "bytes": Path(out_path).stat().st_size, "files": len(files) + 3}


def _collect_figures(files) -> List[Tuple[str, str, bytes, str]]:
    """Inline ``file://`` figure references into the package as images/<name>; rewrite their markup in place."""
    found: List[Tuple[str, str, bytes, str]] = []
    seen: Dict[str, str] = {}
    for idx, (path, fid, data, media) in enumerate(files):
        if not path.startswith("c") or not path.endswith(".xhtml"):
            continue
        text = data.decode("utf-8")
        if "file://" not in text:
            continue
        def swap(m):
            uri = m.group(1)
            local = Path(__import__("urllib.parse").parse.unquote(uri[len("file://"):]))
            if not local.is_file():
                return m.group(0)
            if uri not in seen:
                name = f"images/fig-{len(seen) + 1}{local.suffix.lower()}"
                seen[uri] = name
                found.append((name, f"fig{len(seen)}", local.read_bytes(), {".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}.get(local.suffix.lower(), "image/jpeg")))
            return f'src="{seen[uri]}"'
        text = re.sub(r'src="(file://[^"]+)"', swap, text)
        files[idx] = (path, fid, text.encode("utf-8"), media)
    return found
