"""Word-bounded packets of a long text: split, verify drafts mechanically, rejoin.

`champollion packets split|verify|join` (docs/ai-workers.md). Packets break only at
paragraph or heading boundaries; a heading or a bare marker line such as a page
milestone stays with the block that follows it, and
an author-note line stays with the paragraph before it. Verification compares each
draft packet with its source packet for identical paragraph anchors, page markers,
heading count and note lines. It is a mechanical contract (WRK-3, WRK-5), not a
judgement of sense.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, List, Optional

from .findings import ChampollionError
from .notes import NOTE_LINE, anchors as note_anchors, note_labels
from .sources import write_bytes_atomic

# Line-initial paragraph IDs such as "[DTA 0001]" (a letter first, so page markers are excluded).
DEFAULT_ANCHOR = r"^\[(?!Note )[A-Za-z][^\]\n]*\]"
# Edition-year page milestones such as "[1845 35]" or "[1845 xii]".
DEFAULT_PAGE = r"\[[0-9]{4} [^\]\s]+\]"
HEADING = re.compile(r"^#{1,6} ", re.M)
# A block that is only a bracketed marker, such as a page milestone on its own line.
MARKER_ONLY = re.compile(r"^\[[^\[\]\n]+\]$")
MANIFEST = "packets.json"


def blocks(text: str) -> List[str]:
    """Return nonempty blank-line-separated blocks, stripped of surrounding space."""
    return [b.strip() for b in re.split(r"\n[ \t]*\n", text.replace("\r\n", "\n")) if b.strip()]


def normalized(text: str) -> str:
    """The canonical form split and join preserve: blocks separated by one blank line."""
    return "\n\n".join(blocks(text)) + "\n"


def _words(parts: List[str]) -> int:
    return sum(len(part.split()) for part in parts)


def split_text(text: str, max_words: int) -> List[str]:
    """Pack whole blocks greedily into packets of at most max_words words.

    A block longer than the limit becomes a packet of its own; callers see it as
    oversize rather than having a paragraph cut.
    """
    if type(max_words) is not int or max_words < 1:
        raise ChampollionError("max words must be a positive integer", cause="usage")
    atoms: List[List[str]] = []
    headings: List[str] = []
    for block in blocks(text):
        if HEADING.match(block) or MARKER_ONLY.match(block):
            headings.append(block)
        elif NOTE_LINE.match(block) and atoms and not headings:
            atoms[-1].append(block)
        else:
            atoms.append(headings + [block])
            headings = []
    if headings:
        atoms.append(headings)
    packets: List[List[str]] = []
    for atom in atoms:
        if packets and _words(packets[-1]) + _words(atom) <= max_words:
            packets[-1].extend(atom)
        else:
            packets.append(list(atom))
    return ["\n\n".join(packet) + "\n" for packet in packets]


def _name(index: int, count: int) -> str:
    return f"{index:0{max(3, len(str(count)))}d}.md"


def _write_new(path: Path, payload: bytes) -> None:
    if path.is_symlink():
        raise ChampollionError(f"{path}: refusing to replace a symlink", cause="WRK-1")
    if path.exists():
        if path.read_bytes() != payload:
            raise ChampollionError(f"{path}: existing file differs; choose a fresh output", cause="WRK-1")
        return
    write_bytes_atomic(path, payload)


def write_split(source: str, out: str, max_words: int) -> dict:
    """Write NNN.md packets and a packets.json manifest; never overwrite different bytes."""
    path = Path(source)
    try:
        data = path.read_bytes()
        text = data.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise ChampollionError(f"{path}: {exc}", cause="IO") from exc
    packets = split_text(text, max_words)
    if not packets:
        raise ChampollionError(f"{path}: no text to split", cause="usage")
    destination = Path(out).resolve()
    if destination == path.resolve().parent:
        raise ChampollionError(f"{destination}: write packets outside the source file's directory", cause="usage")
    entries = []
    try:
        destination.mkdir(parents=True, exist_ok=True)
        for index, packet in enumerate(packets, 1):
            name = _name(index, len(packets))
            _write_new(destination / name, packet.encode("utf-8"))
            words = len(packet.split())
            entries.append({"file": name, "words": words, "oversize": words > max_words})
        manifest = {"source": path.name, "source_sha256": hashlib.sha256(data).hexdigest(),
                    "max_words": max_words, "packets": entries}
        _write_new(destination / MANIFEST,
                   (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    except OSError as exc:
        raise ChampollionError(f"{destination}: {exc}", cause="IO") from exc
    return {"out": str(destination), **manifest}


def _compare(kind: str, source: List[str], draft: List[str]) -> List[str]:
    """Name missing, extra, duplicate and out-of-order items of one marker kind."""
    problems = []
    have, want = Counter(draft), Counter(source)
    for item in dict.fromkeys(source):
        if have[item] < want[item]:
            count = "" if want[item] == 1 else f" ({have[item]} of {want[item]})"
            problems.append(f"{kind}: missing {item}{count}")
        elif have[item] > want[item]:
            problems.append(f"{kind}: duplicate {item} ({have[item]} for {want[item]})")
    for item in dict.fromkeys(draft):
        if not want[item]:
            problems.append(f"{kind}: extra {item}")
    expected = [x for x in dict.fromkeys(source) if have[x]]
    found = [x for x in dict.fromkeys(draft) if want[x]]
    if expected != found:
        position = next(i for i, (a, b) in enumerate(zip(expected, found)) if a != b)
        problems.append(f"{kind}: out of order at {position + 1}: expected {expected[position]}, found {found[position]}")
    return problems


def packet_keys(text: str, anchor: str = DEFAULT_ANCHOR, page: str = DEFAULT_PAGE) -> dict:
    """Extract the mechanical contract of one packet."""
    lines = text.splitlines()
    labels = note_labels(lines)
    return {"anchors": re.findall(anchor, text, re.M), "page markers": re.findall(page, text),
            "headings": len(HEADING.findall(text)), "notes": labels,
            "note anchors": sorted(set(note_anchors(lines, labels)))}


def compare_packet(source: str, draft: str, anchor: str = DEFAULT_ANCHOR, page: str = DEFAULT_PAGE) -> List[str]:
    """Return every contract difference between a source packet and its draft."""
    want, have = packet_keys(source, anchor, page), packet_keys(draft, anchor, page)
    problems = []
    for kind in ("anchors", "page markers", "notes"):
        problems += _compare(kind, want[kind], have[kind])
    if want["headings"] != have["headings"]:
        problems.append(f"headings: {have['headings']} in draft, {want['headings']} in source")
    for label in want["note anchors"]:
        if label in have["notes"] and label not in have["note anchors"]:
            problems.append(f"notes: inline anchor {label} missing from draft text")
    return problems


def _packet_files(directory: Path) -> dict:
    if not directory.is_dir():
        raise ChampollionError(f"{directory}: packet directory missing", cause="IO")
    return {p.name: p for p in sorted(directory.glob("*.md")) if p.is_file()}


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ChampollionError(f"{path}: {exc}", cause="IO") from exc


def verify_packets(source_dir: str, draft_dir: str, anchor: str = DEFAULT_ANCHOR,
                   page: str = DEFAULT_PAGE) -> dict:
    """Compare every draft packet with the same-named source packet; read-only."""
    for pattern in (anchor, page):
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ChampollionError(f"invalid pattern {pattern!r}: {exc}", cause="usage") from exc
    sources, drafts = _packet_files(Path(source_dir)), _packet_files(Path(draft_dir))
    if not sources:
        raise ChampollionError(f"{source_dir}: no source packets", cause="usage")
    packets = []
    for name, path in sources.items():
        if name not in drafts:
            packets.append({"file": name, "problems": ["draft missing"]})
            continue
        packets.append({"file": name, "problems": compare_packet(_read(path), _read(drafts[name]), anchor, page)})
    for name in drafts:
        if name not in sources:
            packets.append({"file": name, "problems": ["draft has no source packet"]})
    failed = [p for p in packets if p["problems"]]
    return {"valid": not failed, "source": str(Path(source_dir).resolve()), "drafts": str(Path(draft_dir).resolve()),
            "anchor": anchor, "page": page, "packets": len(sources), "failed": failed,
            "problems": sum(len(p["problems"]) for p in failed)}


def join_packets(directory: str, out: str, source_dir: Optional[str] = None,
                 anchor: str = DEFAULT_ANCHOR, page: str = DEFAULT_PAGE) -> dict:
    """Concatenate packets in file order; with source_dir, refuse unless every packet verifies."""
    if source_dir is not None:
        result = verify_packets(source_dir, directory, anchor, page)
        if not result["valid"]:
            first = result["failed"][0]
            raise ChampollionError(f"{len(result['failed'])} packet(s) fail verification, first {first['file']}: "
                                   f"{first['problems'][0]}", cause="WRK-5")
    files = _packet_files(Path(directory))
    if not files:
        raise ChampollionError(f"{directory}: no packets", cause="usage")
    text = "\n\n".join(_read(path).strip() for path in files.values()) + "\n"
    target = Path(out).resolve()
    if target.parent == Path(directory).resolve():
        raise ChampollionError(f"{target}: write the joined text outside the packet directory", cause="usage")
    payload = text.encode("utf-8")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        _write_new(target, payload)
    except OSError as exc:
        raise ChampollionError(f"{target}: {exc}", cause="IO") from exc
    return {"out": str(target), "packets": len(files), "sha256": hashlib.sha256(payload).hexdigest(),
            "verified": source_dir is not None}


def render_verify(result: Any) -> str:
    """Human-readable verification lines, one per problem."""
    lines = [f"{p['file']}: {problem}" for p in result["failed"] for problem in p["problems"]]
    lines.append(f"{result['packets']} packets, {len(result['failed'])} failed, {result['problems']} problems")
    return "\n".join(lines)
