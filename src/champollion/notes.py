"""Author footnotes: `[Note L]` lines and their inline `L` anchors (SPEC §2.4).

An author note is a line ``[Note L] text`` placed after the paragraph that carries
its anchor ``L``. A label is the printed mark: ``*)``, ``**)``, ``***)``, ``(a)``,
``1)``, ``†`` and similar, at most eight characters without spaces or brackets.
Star labels are matched as whole tokens, so ``*)`` never matches inside ``**)``.
"""
from __future__ import annotations

import re
from typing import Iterable, List, Set

NOTE_LINE = re.compile(r"^\[Note ([^\[\]\s]{1,8})\](?=\s|$)")
STAR_MARK = re.compile(r"(?<!\*)\*{1,4}\)")


def note_labels(lines: Iterable[str]) -> List[str]:
    """Return the labels of note lines in order."""
    return [m.group(1) for m in (NOTE_LINE.match(line) for line in lines) if m]


def _occurrences(line: str, label: str) -> int:
    if STAR_MARK.fullmatch(label):
        return sum(m.group(0) == label for m in STAR_MARK.finditer(line))
    return line.count(label)


def anchors(lines: Iterable[str], labels: Iterable[str]) -> List[str]:
    """Return inline anchors of the given labels in non-note lines, in text order."""
    wanted = sorted(set(labels), key=len, reverse=True)
    found = []
    for line in lines:
        if NOTE_LINE.match(line):
            continue
        hits = []
        for label in wanted:
            if STAR_MARK.fullmatch(label):
                hits.extend((m.start(), label) for m in STAR_MARK.finditer(line) if m.group(0) == label)
            else:
                start = line.find(label)
                while start != -1:
                    hits.append((start, label))
                    start = line.find(label, start + len(label))
        found.extend(label for _, label in sorted(hits))
    return found


def paired_labels(lines: Iterable[str]) -> Set[str]:
    """Labels that have both a note line and at least one inline anchor."""
    lines = list(lines)
    labels = set(note_labels(lines))
    return {label for label in labels
            if any(_occurrences(line, label) for line in lines if not NOTE_LINE.match(line))}


def mask_marks(line: str, paired: Set[str]) -> str:
    """Blank paired star marks (and a paired note label) so debris scans skip them.

    Positions are preserved. Unpaired marks stay visible and remain debris.
    """
    note = NOTE_LINE.match(line)
    if note and note.group(1) in paired and STAR_MARK.fullmatch(note.group(1)):
        start, end = note.span(1)
        line = line[:start] + " " * (end - start) + line[end:]
    return STAR_MARK.sub(lambda m: " " * len(m.group(0)) if m.group(0) in paired else m.group(0), line)
