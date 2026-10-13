"""Explicit, read-only translation of Mouseia's legacy vocabulary."""
from __future__ import annotations

from dataclasses import replace
from typing import Any, List, Optional, Tuple

from ..findings import ChampollionError


def speech_work_scope() -> frozenset:
    """Return the legacy straight-quotation gate's documented work scope."""
    return frozenset(("iliad", "odyssey"))


def adapt_work(work: Any, profile: Optional[Any] = None) -> Tuple[Any, List[dict]]:
    """Copy legacy fields/labels into declared vocabulary, refusing conflicts."""
    front = dict(work.front)
    mappings: List[dict] = []
    for old, new in (("curated_translator", "musean_translator"), ("curated_note", "musean_note")):
        if old not in front:
            continue
        if new in front and front[new] != front[old]:
            raise ChampollionError(f"{work.path}: conflicting {old} and {new}", cause="SEG-FRONT-MATTER")
        front[new] = front[old]
        mappings.append({"kind": "front-matter", "from": old, "to": new})
    for key in ("plain_translator", "plain_note"):
        if key in front:
            mappings.append({"kind": "front-matter", "from": key, "to": key})
    sections = []
    found_musean = None
    register = next((r for r in profile.registers if r.id == "musean"), None) if profile else None
    target = register.sections[0] if register else "mouseia translation"
    for section in work.sections:
        label = section.label.strip().casefold()
        is_musean = label in ("mouseia translation", "curated translation")
        if register:
            is_musean = is_musean or label in {s.strip().casefold() for s in register.sections}
        if is_musean:
            if found_musean is not None:
                raise ChampollionError(f"{work.path}: conflicting Musean sections {found_musean!r} and {section.label!r}",
                                       cause="SEG-PARITY")
            found_musean = section.label
            sections.append(replace(section, label=target))
            mappings.append({"kind": "section", "from": section.label, "to": target, "register": "musean"})
        else:
            sections.append(replace(section, units=list(section.units)))
    mappings.append({"kind": "gate-scope", "check": "speech", "works": sorted(speech_work_scope())})
    return replace(work, front=front, sections=sections), mappings
