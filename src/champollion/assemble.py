"""Validate complete response sequences before writing a separate work copy."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, List, Tuple

from .checks.numbering import extract_markers
from .findings import ChampollionError
from .packets import selected_register, numbering_policy


def read_responses(directory: str) -> List[Tuple[str, str]]:
    """Read filename-ordered single-unit Markdown responses without reordering."""
    path = Path(directory)
    try:
        if not path.is_dir():
            raise ChampollionError(f"{path}: response directory missing", cause="IO")
        files = sorted(path.glob("*.md"), key=lambda p: p.name)
        responses = []
        for file in files:
            text = file.read_text(encoding="utf-8")
            match = re.fullmatch(r"\s*### ([^\n]+)\n([\s\S]*)", text)
            if not match:
                raise ChampollionError(f"{file}: expected one ### unit heading and response text", cause="WRK-5")
            title, body = match.group(1).strip(), match.group(2).strip()
            if not title or not body or not re.sub(r"<!--[\s\S]*?-->", "", body).strip():
                raise ChampollionError(f"{file}: empty response unit", cause="WRK-5")
            if re.search(r"(?m)^#{1,3}(?:\s|$)", body):
                raise ChampollionError(f"{file}: duplicate unit or unexpected heading", cause="WRK-5")
            responses.append((title, body))
        return responses
    except (OSError, UnicodeError) as exc:
        raise ChampollionError(f"{path}: {exc}", cause="IO") from exc


def validate_responses(work: Any, responses: List[Tuple[str, str]], root: str = None) -> None:
    """Refuse gaps, duplicates, unknown/order errors, and differing markers."""
    original = work.original()
    if not original.units or any(not unit.text.strip() for unit in original.units):
        raise ChampollionError("Original requires nonempty headed units", cause="WRK-5")
    expected = [unit.title for unit in original.units]
    actual = [title for title, _ in responses]
    if len(actual) != len(set(actual)):
        raise ChampollionError("duplicate response units", cause="WRK-5")
    unknown = [title for title in actual if title not in expected]
    if unknown:
        raise ChampollionError(f"unknown response unit {unknown[0]!r}", cause="WRK-5")
    missing = [title for title in expected if title not in actual]
    if missing:
        raise ChampollionError(f"missing response unit {missing[0]!r}", cause="WRK-5")
    if actual != expected:
        raise ChampollionError("response units out of Original order", cause="WRK-5")
    notation, line_for_line = numbering_policy(work, root or str(Path(work.path).resolve().parent.parent))
    for source, (title, body) in zip(original.units, responses):
        clean = re.sub(r"<!--[\s\S]*?-->", "", body).strip()
        if not clean:
            raise ChampollionError(f"unit {title!r}: empty response", cause="WRK-5")
        expected_markers, actual_markers = extract_markers(source.text, notation), extract_markers(clean, notation)
        if actual_markers != expected_markers:
            raise ChampollionError(f"unit {title!r}: marker sequence mismatch; expected {expected_markers!r}, got {actual_markers!r}", cause="SEG-NUMBERING")
        if line_for_line:
            if sum(bool(line.strip()) for line in clean.splitlines()) != sum(bool(line.strip()) for line in source.text.splitlines()):
                raise ChampollionError(f"unit {title!r}: line-for-line count differs", cause="SEG-NUMBERING")
        if clean.count("——") != source.text.count("——"):
            raise ChampollionError(f"unit {title!r}: deliberate blank count differs", cause="SEG-COVERAGE")


def assemble_work(work: Any, profile: Any, register_id: str, directory: str, root: str = None) -> dict:
    """Merge a validated register into a copy, never the source document."""
    register = selected_register(profile, register_id)
    responses = read_responses(directory)
    validate_responses(work, responses, root)
    section = work.register_section(profile, register_id)
    source_path = Path(work.path)
    # Preserve the filename/slug invariant so the copy can be checked directly.
    destination = source_path.parent / 'assembled' / source_path.name
    if destination.resolve() == source_path.resolve():
        raise ChampollionError("assembly output would edit the source", cause="WRK-5")
    merged = f"## {section.label if section else register.sections[0]}\n\n" + "\n\n".join(
        f"### {title}\n\n{body}" for title, body in responses) + "\n"
    try:
        source = source_path.read_text(encoding="utf-8")
        if section:
            lines = source.splitlines(keepends=True)
            start = section.line - 1
            end = next((i for i in range(start + 1, len(lines)) if re.match(r"^##\s+", lines[i])), len(lines))
            output = "".join(lines[:start]) + merged + "\n" + "".join(lines[end:])
        else:
            output = source.rstrip() + "\n\n" + merged
        if destination.parent.is_symlink():
            raise ChampollionError(f'{destination.parent}: assembly output directory is a symlink', cause='IO')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(output)
    except (OSError, UnicodeError) as exc:
        raise ChampollionError(f"{destination}: {exc}", cause="IO") from exc
    return {"work": work.slug, "register": register_id, "output": str(destination), "units": len(responses)}
