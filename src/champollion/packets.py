"""Deterministic, register-isolated per-unit task packets."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from .checks.numbering import extract_markers
from .findings import ChampollionError
from .sources import read_json, write_bytes_atomic, load_sources


def register_definition(profile: Any, register: Any, root: str) -> str:
    """Resolve shipped definitions or an explicit project register definition."""
    definitions = {
        "musean": "Fidelity joined to modern clarity, beauty, symbolism, and the source's structure.",
        "literal": "Source-near wording in intelligible target syntax, preserving technical distinctions and source form without distorting sense.",
        "plain": "Complete source content in ordinary contemporary target-language wording and direct syntax, without added explanation.",
        "literaria": "Complete direct-source Spanish preserving imagery, rhetorical structure, technical distinctions, and cadence in contemporary literary language.",
        "clara": "Complete independent direct-source Spanish using familiar contemporary words and direct syntax, without summaries or added explanations.",
    }
    if profile.name.casefold() == "mouseia":
        definitions["plain"] = "Everyday contemporary English, complete and direct, never a summary, shorter in content, or commentary."
    path = Path(root) / "registers.json"
    if path.exists():
        obj = read_json(path)
        if not isinstance(obj, dict) or not isinstance(obj.get("definitions"), dict):
            raise ChampollionError(f"{path}: expected definitions object", cause="schema")
        definitions.update(obj["definitions"])
    definition = definitions.get(register.id)
    if not isinstance(definition, str) or not definition.strip():
        raise ChampollionError(f"register {register.id}: missing definition in registers.json", cause="REG-4")
    return definition


def selected_register(profile: Any, id: str) -> Any:
    """Find a declared register or name the configuration failure."""
    register = next((r for r in profile.registers if r.id == id), None)
    if register is None:
        raise ChampollionError(f"undeclared register {id!r}", cause="configuration")
    return register


def numbering_policy(work: Any, root: str) -> tuple:
    """Read the same local source numbering contract used by the checker."""
    records = load_sources(root, [work])
    reference = work.front.get('source', '')
    record = records.get(reference) or records.get(work.slug) or records.get(work.front.get('source_id', '')) or {}
    policy = record.get('numbering', {})
    if not isinstance(policy, dict):
        raise ChampollionError('source numbering policy must be an object', cause='schema')
    notation = work.front.get('numbering_notation') or record.get('numbering_notation') or policy.get('notation')
    line_for_line = record.get('line_for_line', policy.get('line_for_line', False))
    if 'line_for_line' in work.front:
        value = work.front['line_for_line'].casefold()
        if value not in ('true', 'false'):
            raise ChampollionError('line_for_line must be true or false', cause='schema')
        line_for_line = value == 'true'
    if type(line_for_line) is not bool:
        raise ChampollionError('source line_for_line policy must be a boolean', cause='schema')
    return notation, line_for_line


def unit_filename(index: int, title: str) -> str:
    """Return a stable sortable filename independent of locale and timestamps."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-") or "unit"
    return f"{index:06d}-{slug}.md"


def packet_documents(work: Any, profile: Any, register_id: str, units: str, root: str) -> list:
    """Build packet contents with source numbering and no other register text."""
    register = selected_register(profile, register_id)
    definition = register_definition(profile, register, root)
    original = work.original()
    if not original.units or any(not unit.text.strip() for unit in original.units):
        raise ChampollionError("Original requires nonempty headed units", cause="WRK-1")
    match = re.fullmatch(r"([1-9][0-9]*)-([1-9][0-9]*)", units)
    if match is None:
        raise ChampollionError(f"units {units!r}: expected inclusive 1-based A-B range", cause="usage")
    first, last = map(int, match.groups())
    if first > last or last > len(original.units):
        raise ChampollionError(f"units {units!r}: range outside 1-{len(original.units)}", cause="usage")
    documents = []
    notation, line_for_line = numbering_policy(work, root)
    for index in range(first, last + 1):
        unit = original.units[index - 1]
        markers = extract_markers(unit.text, notation)
        line_contract = (f'Return exactly {sum(bool(line.strip()) for line in unit.text.splitlines())} nonempty target lines, one per source line.\n'
                         if line_for_line else '')
        text = (f"# Translation packet: {work.slug} / {unit.title}\n\n"
                f"Source language: {work.front.get('language', 'unspecified')}\n"
                f"Target language: {profile.target['tag'] if profile.target else 'unspecified; set profile.target before dispatch'}\n\n"
                f"Register: {register.label} (`{register.id}`)\n\nDefinition: {definition}\n\n"
                "## Constraints\n\n"
                "- WRK-1: Translate this complete source unit, preserving its source form and lacunae.\n"
                "- WRK-2: Work directly from Original, independently of every other register.\n"
                "- WRK-3: Preserve every source reference marker unchanged and in order.\n"
                "- WRK-4: Add no explanation and never fill a gap with a neighboring paraphrase.\n"
                "- Keep deliberate blanks as —— and genuine damage as [illegible in the source].\n"
                "- Retain contributor identity and direct-source/source-form attestation outside reader-facing text.\n\n"
                "## Source\n\n" + f"### {unit.title}\n\n{unit.text}\n\n"
                "## Exact response shape\n\n"
                f"Return only `### {unit.title}`, a blank line, and the complete translated unit text. "
                "No section heading, code fence, production note, or other unit is permitted.\n\n"
                "## Numbering contract\n\n"
                f"Ordered markers: {markers!r}\n" + line_contract +
                "Return this sequence exactly; assembly refuses missing, duplicate, extra, or out-of-order markers.\n")
        documents.append({"unit": unit.title, "index": index, "filename": unit_filename(index, unit.title), "text": text})
    return documents


def write_packets(work: Any, profile: Any, register_id: str, units: str, root: str,
                  out: Optional[str] = None) -> dict:
    """Write deterministic packet files to the explicit or conventional directory."""
    documents = packet_documents(work, profile, register_id, units, root)
    destination = (Path(out) if out else Path(root) / "packets" / work.slug / register_id).resolve()
    try:
        destination.mkdir(parents=True, exist_ok=True)
        for document in documents:
            path = destination / document["filename"]
            if path.resolve() == Path(work.path).resolve():
                raise ChampollionError(f"{path}: packets cannot replace a work", cause="WRK-1")
            if path.is_symlink():
                raise ChampollionError(f'{path}: refusing to replace a symlink', cause='WRK-1')
            payload = document['text'].encode('utf-8')
            if path.exists():
                if path.read_bytes() != payload:
                    raise ChampollionError(f'{path}: existing packet differs; choose a fresh output directory', cause='WRK-1')
            else:
                write_bytes_atomic(path, payload)
    except (OSError, UnicodeError) as exc:
        raise ChampollionError(f"{destination}: {exc}", cause="IO") from exc
    return {"work": work.slug, "register": register_id, "out": str(destination),
            "files": [{"unit": d["unit"], "path": str(destination / d["filename"])} for d in documents]}
