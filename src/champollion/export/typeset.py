"""Typesetting: one book model -> print HTML (for PDF) and XHTML chapters (for EPUB)."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from ..findings import ChampollionError
from .model import Book, Unit
from .refs import Block, Line, figure_of

_BAD_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")
KICKER = re.compile(
    r"^((?:Book|Chapter|Section|Part|Tablet|Column|Page|Hymn|Verse|Mandala|Clause|Declaration|Canto|Act|Scene|Letter|Spell|Sutra|Surah|Fascicle|Volume|Song|Ode|Satire|Epistle)\s+[0-9IVXLCDMivxlcdm]+[a-z]?)"
    r"(?:\s*[-–—:.·]\s*|\s+)(.+)$")
NUMERIC = re.compile(r"^[0-9IVXLCDM]+[a-z]?$")


def esc(value: object) -> str:
    return html.escape(_BAD_XML.sub("", str(value if value is not None else "")), quote=True)


def css_string(value: str) -> str:
    return '"' + _BAD_XML.sub("", value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


@dataclass
class Theme:
    deep: str = "#2b2118"
    accent: str = "#b8924a"
    motif: str = "§"
    ink: str = "#1c1812"


@dataclass
class Options:
    publisher: str = "Champollion"
    site_url: str = ""
    theme: Theme = field(default_factory=Theme)
    unit_noun: str = "Part"
    font_css: str = ""            # absolute path of an @font-face stylesheet for PDF rendering
    assets_dir: str = ""          # resolves /figures/... style image paths
    colophon: str = ""            # extra imprint line
    # PDF-only: {unit_index: page number} for the contents; None = placeholders.
    toc_pages: Optional[Dict[int, int]] = None
    markers: bool = False         # pass 1: invisible per-unit markers used to find page numbers


def split_label(label: str, index: int, noun: str) -> Tuple[str, str]:
    """(kicker, title) for a unit heading."""
    label = (label or "").strip()
    if not label:
        return f"{noun} {index + 1}", ""
    if NUMERIC.match(label):
        return f"{noun} {label}", ""
    match = KICKER.match(label)
    if match:
        return match.group(1), match.group(2).strip()
    return "", label


def unit_titles(book: Book, opts: Options) -> List[Tuple[str, str]]:
    return [split_label(u.label, i, opts.unit_noun) for i, u in enumerate(book.units)]


def display_title(kicker: str, title: str) -> str:
    return f"{kicker}. {title}" if kicker and title else (kicker or title)


def _sentence(text: str) -> str:
    text = text.strip()
    text = text[:1].upper() + text[1:]
    return text if text.endswith((".", "!", "?")) else text + "."


def source_host(url: str) -> str:
    if not url:
        return ""
    if re.search(r"github(usercontent)?\.com/PerseusDL/", url, re.I):
        return "the Perseus Digital Library"
    try:
        host = (urlparse(url).hostname or "").removeprefix("www.")
        return "a pinned GitHub edition" if host in ("github.com", "raw.githubusercontent.com") else host
    except ValueError:
        return ""


def lang_attr(code: str) -> str:
    code = (code or "").strip()
    if re.match(r"^[A-Za-z]{2,3}(-[A-Za-z]{4})?(-([A-Za-z]{2}|\d{3}))?$", code):
        return code
    return code.split("-")[0].lower() if code else ""


# ---------------------------------------------------------------- text blocks

_OPEN_BEFORE = "([{\u2014\u2013\u2018\u201c-/"


def smarten(text: str, prev: str = "") -> str:
    """Curly quotes, apostrophes and ellipses for English running text."""
    out = []
    last = prev[-1:] if prev else ""
    for i, ch in enumerate(text):
        before = out[-1] if out else last
        if ch == '"':
            ch = "\u201c" if (not before or before.isspace() or before in _OPEN_BEFORE) else "\u201d"
        elif ch == "'":
            nxt = text[i + 1:i + 2]
            ch = "\u2018" if ((not before or before.isspace() or before in _OPEN_BEFORE) and nxt.isalnum()) else "\u2019"
        out.append(ch)
    return "".join(out).replace("...", "\u2026")


def _segments(line: Line, smart: bool = False) -> str:
    out = []
    prev = ""
    for seg in line.segments:
        if seg.ref:
            out.append(f'<span class="mk">{esc(seg.ref)}</span>')
        elif seg.note:
            out.append(f'<sup class="fn">{esc(seg.note)}</sup>')
        else:
            text = smarten(seg.text, prev) if smart else seg.text
            prev = text
            out.append(esc(text))
    return "".join(out)


def _ref(lead: str) -> str:
    return f'<span class="ref">{esc(lead)}</span>' if lead else ""


def render_blocks(blocks: List[Block], lang: str, opts: Options, epub: bool = False) -> str:
    out: List[str] = []
    smart = lang_attr(lang).split("-")[0].lower() == "en"
    lang_part = f' lang="{esc(lang_attr(lang))}" xml:lang="{esc(lang_attr(lang))}"' if (lang and epub) else (f' lang="{esc(lang_attr(lang))}"' if lang else "")
    for index, block in enumerate(blocks):
        if block.kind == "chapter":
            out.append(f'<p class="subhead">Chapter {esc(block.ref.split(".")[-1])}</p>')
            continue
        fig = figure_of(block)
        if fig:
            alt, src = fig
            path = _asset(src, opts)
            if path:
                out.append(f'<figure class="fig"><img src="{esc(path)}" alt="{esc(alt)}"/><figcaption>{esc(alt)}</figcaption></figure>')
            continue
        if len(block.lines) > 1:
            lines = "".join(
                f'<span class="ln{" rubric" if ln.rubric else ""}">{_ref(ln.lead)}{_segments(ln, smart)}</span>' for ln in block.lines)
            keep = " keep" if len(block.lines) <= 10 else ""
            out.append(f'<p class="lines{" numbered" if any(l.lead for l in block.lines) else ""}{keep}">{lines}</p>')
        else:
            ln = block.lines[0]
            cls = ["prose"]
            if ln.lead:
                cls.append("numbered")
            if ln.rubric:
                cls.append("rubric")
            if index == 0 and dek_ok(ln, blocks):
                cls = ["dek"]
            out.append(f'<p class="{" ".join(cls)}">{_ref(ln.lead)}{_segments(ln, smart)}</p>')
    rtl = ' dir="rtl"' if lang_attr(lang).split("-")[0].lower() in {"ar", "fa", "he", "ur", "ps", "syr", "arc", "yi"} else ""
    return f'<div class="text"{lang_part}{rtl}>' + "\n".join(out) + "</div>"


def dek_ok(ln: Line, blocks: List[Block]) -> bool:
    """A short Title-Cased opening line before running text is the unit's subtitle (Candide: 'How Candide Was Raised…')."""
    text = ln.plain().strip()
    if not (len(blocks) > 2 and not ln.lead and 3 < len(text) < 100 and text[-1] not in ';:,"\u201d\u2019\u2014)'):
        return False
    if len(blocks[1].lines) != 1 or len(blocks[1].lines[0].plain()) < 120:
        return False
    words = [w for w in re.findall(r"[^\W\d_]+", text) if len(w) > 3]
    return len(words) >= 2 and sum(1 for w in words if w[0].isupper()) / len(words) >= 0.7


IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def _asset(src: str, opts: Options) -> str:
    """A figure's file: URI, only for images inside ``assets_dir``; anything else is refused by name."""
    if not src.startswith("/") or not opts.assets_dir:
        return ""
    root = Path(opts.assets_dir).resolve()
    path = (root / src.lstrip("/")).resolve()
    if root not in path.parents or path.suffix.lower() not in IMAGE_SUFFIXES:
        raise ChampollionError(f"figure {src!r} is outside the assets directory or not an image", cause="FIGURE-PATH")
    if not path.is_file():
        raise ChampollionError(f"figure {src!r} not found under {root}", cause="FIGURE-MISSING")
    return path.as_uri()


# ---------------------------------------------------------------- cover

def cover_markup(book: Book, opts: Options) -> str:
    t = opts.theme
    title = esc(book.title)
    long_cls = " long" if len(book.title) > 28 else (" mid" if len(book.title) > 16 else "")
    return f'''<div class="cv" style="--deep:{t.deep};--accent:{t.accent}">
<div class="cv-spine"></div>
<div class="cv-frame"></div>
<div class="cv-body">
<div class="cv-mark">{esc(t.motif)}</div>
<div class="cv-lower">
<h1 class="cv-title{long_cls}">{title}</h1>
<div class="cv-rule"></div>
<p class="cv-author">{esc(book.author)}</p>
<p class="cv-edition">{esc(book.edition_label)}</p>
</div>
<p class="cv-pub">{esc(opts.publisher)}</p>
</div>
</div>'''


COVER_CSS = '''
.cv{position:relative;width:6in;height:9in;overflow:hidden;color:#f2e9d5;
 background:radial-gradient(circle at 70% 18%,color-mix(in srgb,var(--accent) 42%,transparent),transparent 52%),
 linear-gradient(155deg,color-mix(in srgb,var(--deep) 72%,#2c2519),var(--deep));
 font-family:"Cormorant Garamond","EB Garamond","Noto Sans Egyptian Hieroglyphs","Noto Sans Cuneiform",Georgia,serif}
.cv-spine{position:absolute;inset:0 auto 0 0;width:.52in;background:linear-gradient(90deg,rgba(0,0,0,.42),rgba(0,0,0,.18) 60%,transparent)}
.cv-spine::after{content:"";position:absolute;inset:0 auto 0 .5in;width:.025in;background:rgba(255,255,255,.14)}
.cv-frame{position:absolute;inset:.42in .42in .42in .78in;border:.01in solid rgba(233,208,146,.34)}
.cv-frame::after{content:"";position:absolute;inset:.07in;border:.006in solid rgba(233,208,146,.16)}
.cv-body{position:absolute;inset:.42in .42in .42in .78in;padding:.62in .45in .5in;display:flex;flex-direction:column;justify-content:space-between}
.cv-mark{color:var(--accent);font-size:1.05in;line-height:1;text-align:left;
 font-family:"Cormorant Garamond","Noto Sans Egyptian Hieroglyphs","Noto Sans Cuneiform","Noto Serif","Geeza Pro","Kohinoor Devanagari","Songti TC",serif}
.cv-title{font-weight:500;font-variant-numeric:lining-nums;font-size:.5in;line-height:1;margin:0;letter-spacing:.003em;text-wrap:balance;hyphens:manual;overflow-wrap:break-word}
.cv-title.mid{font-size:.42in}.cv-title.long{font-size:.34in;line-height:1.04}
.cv-rule{width:.9in;height:.014in;background:var(--accent);margin:.3in 0 .22in;opacity:.85}
.cv-author{font:600 .12in/1.35 "Helvetica Neue",Helvetica,Arial,sans-serif;letter-spacing:.2em;text-transform:uppercase;color:#d9cba9;margin:0}
.cv-edition{font:italic 400 .2in/1.3 "Cormorant Garamond","EB Garamond",Georgia,serif;color:var(--accent);margin:.14in 0 0;filter:brightness(1.25)}
.cv-pub{font:600 .09in/1 "Helvetica Neue",Helvetica,Arial,sans-serif;letter-spacing:.34em;text-transform:uppercase;color:rgba(242,233,213,.55);margin:0;text-align:left}
'''


# ---------------------------------------------------------------- print (PDF)

PRINT_CSS = '''
:root{--ink:#1c1812;--soft:#6f6659;--accent:#8a6a2c;--rule:#cfc4ad;
 --serif:"EB Garamond","Noto Serif","Times New Roman",Georgia,serif;
 --display:"Cormorant Garamond","EB Garamond","Noto Sans Egyptian Hieroglyphs","Noto Sans Cuneiform",Georgia,serif}
@page{size:6in 9in;margin:0}
@page cover{margin:0}
@page front{margin:1in .8in 1in .8in}
@page body{margin:.95in .72in .98in .86in;
 @bottom-center{content:counter(page);font:400 9.6pt/1 var(--serif);color:var(--soft);font-variant-numeric:oldstyle-nums;vertical-align:top;padding-top:.22in}}
@page body:left{margin:.95in .86in .98in .72in}
*{box-sizing:border-box}
html{font-size:10.6pt}
body{margin:0;color:var(--ink);font-family:var(--serif);line-height:1.5;font-kerning:normal;font-feature-settings:"liga","kern","onum";
 -webkit-font-smoothing:antialiased;orphans:3;widows:3}
.cover-page{page:cover;break-after:page}
.front{page:front}
.half-title{height:6.9in;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;break-after:page}
.half-title .ht{font:500 18pt/1.15 var(--display);letter-spacing:.03em}
.title-page{height:6.9in;display:flex;flex-direction:column;align-items:center;text-align:center;break-after:page;padding-top:.7in}
.tp-mark{font:400 34pt/1 var(--display);color:var(--accent)}
.tp-title{font:500 30pt/1.04 var(--display);font-variant-numeric:lining-nums;margin:.55in 0 .2in;text-wrap:balance;max-width:4.2in;overflow-wrap:break-word}
.tp-title.long{font-size:22pt}.tp-title.mid{font-size:26pt}
.tp-rule,.ornament{display:flex;align-items:center;justify-content:center;gap:.14in;color:var(--accent);font-size:11pt;margin:.06in 0}
.tp-rule::before,.tp-rule::after{content:"";width:.5in;height:.6pt;background:var(--accent)}
.tp-author{font:600 8.6pt/1.4 "Helvetica Neue",Helvetica,Arial,sans-serif;letter-spacing:.24em;text-transform:uppercase;margin:.28in 0 0}
.tp-edition{font:italic 400 15pt/1.3 var(--display);margin:.3in 0 0;color:var(--accent)}
.tp-by{font:400 10pt/1.4 var(--serif);color:var(--soft);margin:.1in 0 0}
.tp-pub{margin-top:auto;font:600 7.2pt/1 "Helvetica Neue",Helvetica,Arial,sans-serif;letter-spacing:.36em;text-transform:uppercase;color:var(--soft)}
.imprint{break-after:page;font-size:9.2pt;line-height:1.55;color:#3c352b;padding-top:.1in}
.imprint h2{font:600 7.4pt/1 "Helvetica Neue",Helvetica,Arial,sans-serif;letter-spacing:.22em;text-transform:uppercase;color:var(--accent);margin:.26in 0 .09in}
.imprint h2:first-child{margin-top:0}
.imprint p{margin:0 0 .08in;text-align:left;hyphens:manual}
.imprint .fine{color:var(--soft);font-size:8.2pt;margin-top:.3in}
.toc{break-after:page}
.toc h2.toc-h{font:500 22pt/1 var(--display);font-variant-numeric:lining-nums;text-align:center;margin:.12in 0 .1in}
.toc .ornament{margin-bottom:.3in}
.toc-rows{list-style:none;margin:0;padding:0}
.toc-rows.two{columns:2;column-gap:.4in}
.toc-rows.dense li{font-size:8.8pt;gap:.05in;margin-bottom:.04in}
.toc-rows.dense .dots{min-width:.08in;flex-basis:.08in}
.toc-rows li{display:flex;align-items:baseline;gap:.08in;margin:0 0 .052in;font-size:9.8pt;line-height:1.3;break-inside:avoid}
.toc-rows .t{flex:0 1 auto}
.toc-rows .k{font:600 7.2pt/1 "Helvetica Neue",Helvetica,Arial,sans-serif;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);white-space:nowrap}
.toc-rows .dots{flex:1 1 .2in;border-bottom:.8pt dotted #b9ad94;transform:translateY(-.03in);min-width:.2in}
.toc-rows .n{font-variant-numeric:oldstyle-nums;color:var(--soft);min-width:.3in;text-align:right}
.toc-grid{display:grid;grid-template-columns:repeat(8,1fr);gap:.08in .06in;list-style:none;margin:0;padding:0}
.toc-grid li{display:block;text-align:center;border-top:.6pt solid var(--rule);padding-top:.06in;break-inside:avoid}
.toc-grid .g{display:block;font:500 12pt/1.1 var(--display);font-variant-numeric:lining-nums}
.toc-grid .n{display:block;font-size:8pt;color:var(--soft);font-variant-numeric:oldstyle-nums}
.toc-grid a,.toc-rows a{color:inherit;text-decoration:none}
.unit,.flow{page:body}
.unit{break-before:page}
.unit.first{break-before:auto}
.opener.compact{padding:.34in 0 .16in;break-after:avoid}
.opener.compact h2{font-size:15pt;margin:.06in auto 0}
.opener.compact .k{font-size:6.8pt}
.flow .unit{break-before:auto;margin-top:.06in}
.lines.keep{break-inside:avoid}
.opener{position:relative;text-align:center;padding:.9in 0 .4in;break-after:avoid;break-inside:avoid}
.opener h2{break-inside:avoid}
.opener .k{font:600 7.6pt/1 "Helvetica Neue",Helvetica,Arial,sans-serif;letter-spacing:.3em;text-transform:uppercase;color:var(--accent)}
.opener h2{font:500 24pt/1.12 var(--display);font-variant-numeric:lining-nums;margin:.22in auto .1in;max-width:4in;text-wrap:balance;letter-spacing:.005em}
.opener .ornament{margin-top:.2in}
.opener.untitled{padding-top:.4in}
.opener.untitled h2{font-size:21pt}
.marker{font-size:1px;line-height:0;color:#fff;letter-spacing:0;white-space:nowrap}
.text{position:relative}
.text p{margin:0;position:relative}
.prose{text-align:justify;hyphens:auto;hyphenate-limit-chars:6 3 3;overflow-wrap:break-word}
.text:not(.has-refs) .prose{text-indent:1.35em}
.text:not(.has-refs) .prose:first-child,.subhead+.prose,.dek+.prose{text-indent:0}
.prose.numbered{text-indent:0;margin-top:.1in}
.opener+.text .prose:first-child:not(.numbered):first-letter,
.opener+.text .lines:first-child:first-letter{}
.lines{margin:.14in 0;break-inside:auto}
.ln{display:block;padding-inline-start:1.7em;text-indent:-1.7em;position:relative;hyphens:manual}
.lines.numbered .ln{padding-inline-start:1.7em}
.text.has-refs{padding-inline-start:.46in}
.ref{position:absolute;inset-inline-start:-.46in;width:.36in;text-align:end;font:500 7.6pt/1 var(--serif);color:var(--accent);
 font-variant-numeric:oldstyle-nums;letter-spacing:.03em;text-indent:0;padding-top:.26em;white-space:nowrap}
.ln .ref{padding-top:.26em}
.rubric{color:#8c3b2c}
.mk{font:600 6.6pt/1 var(--serif);color:var(--accent);vertical-align:super;margin:0 .15em;font-variant-numeric:oldstyle-nums}
.fn{font-size:.66em;vertical-align:super;line-height:0;color:var(--accent)}
.dek{font:italic 400 1.02em/1.4 var(--display);font-variant-numeric:lining-nums;color:var(--soft);text-align:center;margin:-.12in 0 .26in!important;text-indent:0!important}
.subhead{font:600 7.6pt/1 "Helvetica Neue",Helvetica,Arial,sans-serif;letter-spacing:.24em;text-transform:uppercase;color:var(--accent);margin:.34in 0 .14in !important;text-align:center;break-after:avoid}
.fig{margin:.2in 0;text-align:center;break-inside:avoid}.fig img{max-width:100%;max-height:4in}
.fig figcaption{font:italic 8.6pt/1.35 var(--serif);color:var(--soft);margin-top:.06in}
.end-mark{text-align:center;color:var(--accent);margin:.35in 0 0;font-size:12pt}
[lang^=lzh] .text,[lang^=zh] .text{font-family:"Songti TC","Songti SC","Noto Serif CJK TC","Noto Serif TC",serif;line-height:1.75;font-size:1.02em}
[lang^=lzh] .prose,[lang^=zh] .prose{hyphens:none;text-align:justify}
[lang^=ar] .text{font-family:"Geeza Pro","Noto Naskh Arabic","Noto Sans Arabic","Al Nile",serif;font-size:1.12em;line-height:1.95}
[lang^=sa] .text,[lang^=hi] .text{font-family:"Kohinoor Devanagari","Noto Serif Devanagari","Devanagari Sangam MN",serif;font-size:1em;line-height:1.7}
[lang^=egy] .text{font-family:"Noto Sans Egyptian Hieroglyphs","Noto Serif","EB Garamond",serif;line-height:1.9;font-size:1.32em}
[lang^=egy] .ref{font-size:.58em;padding-top:.95em}
[lang^=egy] .ln{hyphens:none}
[lang^=grc] .text{font-family:"EB Garamond","Gentium Plus","GFS Didot","Times New Roman",serif}

.running-source{display:none}
'''


def _toc_markup(book: Book, opts: Options, titles) -> str:
    numbered = opts.toc_pages
    n = len(titles)
    grid = n > 40 and sum(1 for _, t in titles if not t) / n > 0.8
    items: List[str] = []
    for i, (kicker, title) in enumerate(titles):
        num = (str(numbered.get(i, "")) if numbered is not None else "000")
        if grid:
            label = re.sub(r"^\D+\s*", "", kicker) or kicker
            items.append(f'<li><a href="#u{i}"><span class="g">{esc(label)}</span><span class="n">{esc(num)}</span></a></li>')
        else:
            k = f'<span class="k">{esc(kicker)}</span>' if kicker and title else ""
            t = esc(re.sub(r"\s(?=\S$)", "\u00a0", title or kicker))
            items.append(f'<li><a class="t" href="#u{i}">{t}</a>{k}<span class="dots"></span><a class="n" href="#u{i}">{esc(num)}</a></li>')
    cls = "toc-grid" if grid else ("toc-rows two dense" if n > 50 else ("toc-rows two" if n > 21 else "toc-rows"))
    return f'<section class="front toc"><h2 class="toc-h">Contents</h2><div class="ornament">❦</div><ol class="{cls}">{"".join(items)}</ol></section>'


def _imprint_markup(book: Book, opts: Options) -> str:
    parts = ['<section class="front imprint">']
    if book.edition != "original":
        parts.append(f'<h2>This edition</h2><p>{esc(book.note) if book.note else esc(book.edition_label)}</p>')
        if book.translator:
            parts.append(f'<h2>Translator</h2><p>{esc(book.translator)}</p>')
    else:
        parts.append(f'<h2>This edition</h2><p>The complete source text in the original language, without translation.</p>')
    facts = []
    if book.period:
        facts.append(f"Written {esc(book.period)}")
    if book.genre:
        facts.append(esc(book.genre[:1].upper() + book.genre[1:]))
    if facts:
        parts.append(f'<h2>The work</h2><p>{" · ".join(facts)}</p>')
    host = source_host(book.source_url)
    if book.source_url:
        parts.append(f'<h2>Source</h2><p>Original text from {esc(host or book.source_url)}.</p>')
    if book.unknowns and not book.unknowns.lower().startswith("none"):
        parts.append(f'<h2>Gaps and uncertainties</h2><p>{esc(_sentence(book.unknowns))}</p>')
    tail = " · ".join(x for x in [opts.publisher, opts.site_url] if x)
    fine = f'{esc(tail)}' if tail else ""
    if opts.colophon:
        fine += f'<br/>{esc(opts.colophon)}'
    if book.as_of:
        fine += f'<br/>Edition dated {esc(book.as_of)}'
    parts.append(f'<p class="fine">{fine}</p></section>')
    return "".join(parts)


REF_UNIT = re.compile(r"^(Stephanus|Verse|Clause|Declaration|Page|Column)\s+(\S+)$")


def prepare(book: Book) -> Book:
    """Works divided only by reference numbers (Stephanus pages, verses, clauses) carry those numbers in the margin
    instead of a heading per division. Idempotent."""
    if getattr(book, "_prepared", False):
        return book
    labels = [u.label for u in book.units]
    if len(labels) >= 2 and all(REF_UNIT.match(l) for l in labels):
        for unit in book.units:
            ref = REF_UNIT.match(unit.label).group(2)
            first = next((b for b in unit.blocks if b.kind == "text"), None)
            if first and first.lines and not first.lines[0].lead:
                first.lines[0].lead = ref
        book.ref_mode = True
    book._prepared = True
    return book


def is_flow(book: Book) -> bool:
    """Short units run on within the page rather than each opening a new one."""
    if len(book.units) < 2:
        return False
    if getattr(book, "ref_mode", False):
        return True
    chars = sum(len(l.plain()) for u in book.units for b in u.blocks for l in b.lines)
    return chars / len(book.units) < 2600


def print_html(book: Book, opts: Options, base_css: str = "") -> str:
    book = prepare(book)
    ref_mode = getattr(book, "ref_mode", False)
    titles = unit_titles(book, opts)
    has_refs = any(l.lead for u in book.units for b in u.blocks if b.kind == "text" for l in b.lines)
    lang = lang_attr(book.language)
    dir_attr = ""
    cover = f'<section class="cover-page">{cover_markup(book, opts)}</section>'
    tp_cls = " long" if len(book.title) > 34 else (" mid" if len(book.title) > 20 else "")
    by = f"Translated by {esc(book.translator)}" if (book.edition != "original" and book.translator) else ""
    title_page = (
        f'<section class="front half-title"><div class="ht">{esc(book.title)}</div></section>'
        f'<section class="front title-page"><div class="tp-mark">{esc(opts.theme.motif)}</div>'
        f'<h1 class="tp-title{tp_cls}">{esc(book.title)}</h1><div class="tp-rule">❦</div>'
        f'<p class="tp-author">{esc(book.author)}</p><p class="tp-edition">{esc(book.edition_label)}</p>'
        f'{f"<p class=tp-by>{by}</p>" if by else ""}<p class="tp-pub">{esc(opts.publisher)}</p></section>'
    )
    body: List[str] = []
    flow = is_flow(book)
    for i, unit in enumerate(book.units):
        kicker, title = titles[i]
        marker = f'<span class="marker">§§U{i}§§</span>' if opts.markers else ""
        opener = ""
        if book.divided and not ref_mode:
            h = esc(title) if title else esc(kicker)
            k = f'<div class="k">{esc(kicker)}</div>' if (kicker and title) else ""
            ornament = "" if flow else '<div class="ornament">❦</div>'
            cls = "opener compact" if flow else "opener"
            opener = f'<header class="{cls}">{k}<h2>{h}{marker}</h2>{ornament}</header>'
        text = render_blocks(unit.blocks, book.language, opts)
        if has_refs:
            text = text.replace('<div class="text"', '<div class="text has-refs"', 1)
        body.append(f'<section class="unit{" first" if i == 0 else ""}" id="u{i}">{opener}{text}</section>')
    if flow:
        body = [f'<div class="flow">{"".join(body)}</div>']
    toc = _toc_markup(book, opts, titles) if book.divided and len(book.units) > 1 and not ref_mode else ""
    head = (f'<meta charset="utf-8"/><title>{esc(book.title)} — {esc(book.edition_label)}</title>'
            f'<meta name="author" content="{esc(book.author)}"/>'
            + (f'<link rel="stylesheet" href="{esc(Path(opts.font_css).as_uri())}"/>' if opts.font_css else "")
            + f'<style>{COVER_CSS}{PRINT_CSS}{base_css}</style>')
    return (f'<!doctype html><html lang="{esc(book.language and lang or "en")}"{dir_attr}><head>{head}</head><body>'
            f'{cover}{title_page}<section class="front">{_imprint_markup(book, opts)}</section>{toc}{"".join(body)}</body></html>')
