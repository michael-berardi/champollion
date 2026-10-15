"""Read a work file into a printable book: metadata, then units of numbered text blocks."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from ..findings import ChampollionError
from ..format import parse_front_matter
from .refs import Block, parse_body

COMMENT = re.compile(r"<!--[\s\S]*?-->")
SECTION_HEAD = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.M)
UNIT_HEAD = re.compile(r"^###[ \t]+", re.M)
RTL = {"ar", "fa", "he", "ur", "ps", "syr", "arc", "yi"}

# Edition keys: the source text, then each register with the section labels (lowercase) that hold it.
DEFAULT_EDITIONS: Dict[str, Dict[str, object]] = {
    "original": {"label": "The Original", "sections": ["original"]},
    "musean": {"label": "Musean Translation", "sections": ["mouseia translation", "curated translation"],
               "translator": "musean_translator", "note": "musean_note", "legacy": ("curated_translator", "curated_note")},
    "plain": {"label": "Plain English Translation", "sections": ["plain english translation", "plain translation"],
              "translator": "plain_translator", "note": "plain_note"},
    "historical": {"label": "Historical Translation", "sections": ["historical translation", "reference translation"],
                   "translator": "historical_translator", "note": "historical_note"},
}


@dataclass
class Unit:
    label: str
    blocks: List[Block]


@dataclass
class Book:
    slug: str
    edition: str
    edition_label: str
    title: str
    author: str
    language: str            # language of this book's text
    source_language: str     # language of the original
    tradition: str
    genre: str
    period: str
    translator: str
    note: str
    source_url: str
    unknowns: str
    as_of: str
    units: List[Unit]
    front: Dict[str, str] = field(default_factory=dict)
    ref_mode: bool = False
    _prepared: bool = False

    @property
    def direction(self) -> str:
        return "rtl" if self.language.split("-")[0].lower() in RTL else "ltr"

    @property
    def divided(self) -> bool:
        return len(self.units) > 1 or any(u.label for u in self.units)


def _sections(text: str) -> Dict[str, str]:
    """Map lowercase section label -> raw body, in file order."""
    out: Dict[str, str] = {}
    matches = list(SECTION_HEAD.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        label = m.group(1).strip().lower()
        if label in out:
            raise ChampollionError(f"duplicate section {m.group(1)!r}", cause="SEG-PARITY")
        out[label] = text[m.end():end]
    return out


def _clean(body: str) -> str:
    body = COMMENT.sub("", body)
    body = re.sub(r"[ \t]+([,.;:!?])", r"\1", body)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def split_units(body: str) -> List[tuple]:
    parts = UNIT_HEAD.split(body)
    if len(parts) <= 1:
        return [("", body.strip())]
    out = []
    for part in parts[1:]:
        nl = part.find("\n")
        out.append((part[:nl].strip(), part[nl + 1:].strip()) if nl > 0 else (part.strip(), ""))
    if parts[0].strip():
        out.insert(0, ("", parts[0].strip()))
    return out


def load_book(path: str, edition: str, editions: Optional[Dict[str, Dict[str, object]]] = None) -> Book:
    """Load one edition of a work. Raises a named error when the edition is absent."""
    editions = editions or DEFAULT_EDITIONS
    if edition not in editions:
        raise ChampollionError(f"unknown edition {edition!r}; choose from {sorted(editions)}", cause="usage")
    spec = editions[edition]
    text = Path(path).read_bytes().decode("utf-8").replace("\r\n", "\n")
    front, start = parse_front_matter(text, str(path))
    sections = _sections("\n".join(text.split("\n")[start - 1:]))
    body = next((sections[s] for s in spec["sections"] if s in sections), None)  # type: ignore[index]
    if body is None:
        raise ChampollionError(f"{path}: no {edition} edition section ({', '.join(spec['sections'])})", cause="SEG-PARITY")  # type: ignore[arg-type]
    body = _clean(body)
    source_language = front.get("language", "")
    is_source = edition == "original"
    language = source_language if is_source else "en"
    units = [Unit(label, parse_body(chunk, original=is_source, language=source_language if is_source else ""))
             for label, chunk in split_units(body)]
    if not any(u.blocks for u in units):
        raise ChampollionError(f"{path}: the {edition} edition is empty", cause="SEG-COVERAGE")
    translator = note = ""
    if not is_source:
        for key in (spec.get("translator"), *(spec.get("legacy", ()) [:1])):
            if key and front.get(str(key)):
                translator = front[str(key)]
                break
        for key in (spec.get("note"), *(spec.get("legacy", ()) [1:])):
            if key and front.get(str(key)):
                note = front[str(key)]
                break
        translator = translator or front.get("translator", "")
    slug = front.get("slug", Path(path).stem)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", slug) or ".." in slug:
        raise ChampollionError(f"{path}: slug {slug!r} is not a safe file name", cause="SEG-FRONT-MATTER")
    return Book(
        slug=slug, edition=edition, edition_label=str(spec["label"]),
        title=front.get("title", Path(path).stem), author=front.get("author", ""), language=language,
        source_language=source_language, tradition=front.get("tradition", ""), genre=front.get("genre", ""),
        period=front.get("period", ""), translator=translator, note=note,
        source_url=front.get("source_url", ""), unknowns=front.get("unknowns", ""), as_of=front.get("as_of", ""),
        units=units, front=front,
    )


def available_editions(path: str, editions: Optional[Dict[str, Dict[str, object]]] = None) -> List[str]:
    editions = editions or DEFAULT_EDITIONS
    text = Path(path).read_bytes().decode("utf-8").replace("\r\n", "\n")
    _, start = parse_front_matter(text, str(path))
    sections = _sections("\n".join(text.split("\n")[start - 1:]))
    return [key for key, spec in editions.items() if any(s in sections and _clean(sections[s]) for s in spec["sections"])]  # type: ignore[union-attr]


def load_editions_file(path: str) -> Dict[str, Dict[str, object]]:
    data = json.loads(Path(path).read_text("utf-8"))
    for key, spec in data.items():
        if "label" not in spec or "sections" not in spec:
            raise ChampollionError(f"{path}: edition {key!r} needs label and sections", cause="usage")
    return data
