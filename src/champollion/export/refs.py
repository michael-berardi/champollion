"""Reference numbers in edition bodies, lifted out of the text for margin or inline typesetting.

A faithful Python port of the reader-side parser Mouseia uses (section, verse, line and page numbers
written many ways: ``CHAPTER 1.2``, ``SECTION 1.2.3``, ``1.1 ``, ``12. ``, ``[1.1]``, ``[17a]``,
``(7.7)`` papyrus columns, Gita ``॥१२- ७॥``, Bekker marker lines, inline footnote calls).
Change this and the site's ``refs.ts`` together.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

CHAPTER = re.compile(r"^CHAPTER\s+(\S+)$")
SECTION = re.compile(r"^SECTION\s+(\d[\dA-Za-z.]*)(?:\s+(.*))?$")
LEAD = re.compile(
    r"^(?:\[(\d{1,4}(?:\.\d{1,4})*[a-e]?)\]\s*|(\d{1,4}(?:\.\d{1,4})*)\.\s+"
    r"|(\d{1,4}(?:\.\d{1,4})+)(?:\s+|\.?(?=[　-鿿＀-￯]))|(\d{2,4})\s{2,})(?=\S)"
)
ALONE = re.compile(r"^\[?(\d{1,4}(?:\.\d{1,4})*[a-e]?)\]?\.?$")
PAPYRUS = re.compile(r"^\((\d{1,3}(?:\.\d{1,3})?)\)\s*(\*\s*)?")
GITA = re.compile(r"\s*॥\s*([०-९\d]+)\s*-\s*([०-९\d]+)\s*॥\s*$")
COLOPHON = re.compile(r"\s*॥\s*[०-९\d]+\s*॥\s*$")
BEKKER = re.compile(r"^\[Bekker (\d{3,4}[ab])(?: line (\d{1,2}[a-z]?))?\]$")
INLINE = re.compile(r"(\[\d{1,3}[a-e]\]|(?<=[^\s\[])\[\d{1,3}\])")
STEPHANUS = re.compile(r"^\[\d{1,3}[a-e]\]$")
NOTE = re.compile(r"^\[\d{1,3}\]$")
YEAR = re.compile(r"^\d{4}$")
FIGURE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)\)$")
HIEROGLYPH_CONTROLS = re.compile("[\U00013430-\U0001345F︀-️]")


@dataclass
class Segment:
    text: str = ""
    ref: str = ""     # Stephanus / Bekker marker typeset where it falls
    note: str = ""    # inline footnote call
    margin: str = ""  # reference number set in the margin beside the line where it falls (a division that runs on mid-sentence)


@dataclass
class Line:
    lead: str = ""
    rubric: bool = False
    segments: List[Segment] = field(default_factory=list)

    def plain(self) -> str:
        return "".join(s.text for s in self.segments)


@dataclass
class Block:
    kind: str                      # "chapter" | "text"
    ref: str = ""
    lines: List[Line] = field(default_factory=list)


def _trim_zeros(ref: str) -> str:
    return re.sub(r"(^|\.)0+(?=\d)", r"\1", ref)


def _last(ref: str) -> str:
    return ref.split(".")[-1] or ref


def _digits(value: str) -> str:
    return "".join(str(ord(c) - 0x0966) if "०" <= c <= "९" else c for c in value)


def _not_year(line: str) -> bool:
    return not YEAR.match(line)


def _inline(line: str) -> List[Segment]:
    out: List[Segment] = []
    for part in INLINE.split(line):
        if not part:
            continue
        if STEPHANUS.match(part):
            out.append(Segment(ref=part[1:-1]))
        elif NOTE.match(part):
            out.append(Segment(note=part[1:-1]))
        else:
            out.append(Segment(text=part))
    return out


def figure_of(block: Block) -> Optional[tuple]:
    if block.kind != "text" or len(block.lines) != 1:
        return None
    match = FIGURE.match(block.lines[0].plain())
    return (match.group(1), match.group(2)) if match else None


def parse_body(body: str, original: bool = False, language: str = "") -> List[Block]:
    """Parse an edition body into chapter markers and numbered text blocks."""
    if language == "egy":
        body = HIEROGLYPH_CONTROLS.sub("", body or "")
    blocks: List[Block] = []
    paragraphs: List[List[str]] = []
    for raw in re.split(r"\n{2,}", (body or "").replace("\r", "")):
        lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
        if len(lines) > 1 and all(LEAD.match(ln) for ln in lines):
            paragraphs.extend([ln] for ln in lines)
        elif lines:
            paragraphs.append(lines)
    pending = ""
    for lines in paragraphs:
        chapter = CHAPTER.match(lines[0]) if len(lines) == 1 else None
        if chapter:
            blocks.append(Block("chapter", chapter.group(1)))
            continue
        ref, pending = pending, ""
        section = SECTION.match(lines[0])
        if section and (len(lines) > 1 or section.group(2)):
            ref = section.group(1)
            lines = [" ".join(x for x in [section.group(2) or "", *lines[1:]] if x)]
        elif len(lines) > 1 and ALONE.match(lines[0]) and _not_year(lines[0]):
            section = None
            ref = ALONE.match(lines[0]).group(1)
            lines = lines[1:]
        elif len(lines) == 1 and ALONE.match(lines[0]) and _not_year(lines[0]):
            pending = ALONE.match(lines[0]).group(1)
            continue
        else:
            section = None
            match = LEAD.match(lines[0])
            if match:
                ref = match.group(1) or match.group(2) or match.group(3) or match.group(4)
                lines[0] = lines[0][match.end():]
        verse = GITA.search(lines[-1])
        if verse:
            ref = f"{_digits(verse.group(1))}.{_digits(verse.group(2))}"
            lines[-1] = GITA.sub(" ॥" if original else "", lines[-1])
        elif not original:
            lines[-1] = COLOPHON.sub("", lines[-1])
        shown = _trim_zeros(ref) if ref else ""
        lead = (("" if _last(shown) == "0" else _last(shown)) if section else shown)
        if any(BEKKER.match(ln) for ln in lines):
            segments: List[Segment] = []
            page = page_shown = ""
            for ln in lines:
                bek = BEKKER.match(ln)
                if bek:
                    page = bek.group(1)
                    if not bek.group(2):
                        continue
                    label = bek.group(2) if page_shown == page else f"{page}{bek.group(2)}"
                    page_shown = page
                    segments.append(Segment(ref=label))
                else:
                    if any(s.text for s in segments):
                        segments.append(Segment(text=" "))
                    segments.extend(_inline(ln))
            blocks.append(Block("text", shown, [Line(lead, False, segments)]))
            continue
        out: List[Line] = []
        for index, ln in enumerate(lines):
            own = lead if index == 0 else ""
            rubric = False
            pap = PAPYRUS.match(ln)
            if pap:
                own = pap.group(1)
                rubric = bool(pap.group(2))
                ln = ln[pap.end():]
            out.append(Line(own, rubric, _inline(ln)))
        if verse and len(out) > 1 and lines[0].endswith("उवाच"):
            out[1].lead, out[0].lead = out[0].lead, ""
        blocks.append(Block("text", shown or out[0].lead, out))
    return blocks
