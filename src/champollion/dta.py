"""Text-level helpers for Deutsches Textarchiv (DTA) TEI extractions (docs/sourcing.md).

These operate on text already flattened from TEI, with emphasis written as
``*...*``, page milestones as ``[YYYY page]`` and author-note anchors such as ``*)``.
They never parse XML or fetch anything; a project's extractor calls them.
"""
from __future__ import annotations

import re
from typing import List, Tuple

HYPHEN_SIGN = "¬"  # ¬, DTA's line-end hyphenation sign
DEFAULT_MARKER = r"\[[0-9]{4} [^\]\s]+\]"
DEFAULT_ANCHOR = r"(?<!\*)\*{1,4}\)|\([a-z]\)"
_LETTER = r"[^\W\d_]"


def page_label(n: str) -> str:
    """Return the page label of a ``<pb n=...>`` value.

    DTA brackets a number the transcribers supplied: ``[354]`` is unprinted page 354,
    and ``35 [354]`` is a misprinted folio 35 corrected to 354. The supplied number
    wins; keep the printed form in the source record if it matters.
    """
    value = n.strip()
    match = re.fullmatch(r"[^\[\]]*\[([^\[\]]+)\]", value)
    return (match.group(1) if match else value).strip()


def join_hyphen_signs(text: str, marker: str = DEFAULT_MARKER, anchor: str = DEFAULT_ANCHOR) -> Tuple[str, List[str]]:
    """Join words split by ``¬`` and return (text, residuals needing review).

    Handles a split across an emphasis boundary (``*Ueber*¬ *zeugung*``), emphasis
    closed right after the sign (``*Bie¬* nen``), a mixed-emphasis word
    (``*Ke*i¬ *ner*``), and page markers or note anchors between the halves:
    page markers move before the joined word, note anchors after it. A word whose
    emphasis cannot be resolved, and any sign left unjoined, is returned as a
    residual instead of being guessed.
    """
    between = rf"(?:(?:{marker}|{anchor})\s*)*"
    pattern = re.compile(
        rf"(?P<left>(?<![\w*'’])[\w*'’]*{_LETTER}['’]?\*?){HYPHEN_SIGN}(?P<close>\*)?\s*"
        rf"(?P<between>{between})(?P<right>\*?{_LETTER}[\w*]*)")
    residuals: List[str] = []

    def join(m: "re.Match[str]") -> str:
        left, right = m.group("left"), m.group("right")
        if m.group("close") and not right.startswith("*"):
            word = left + right + "*"
        elif left.endswith("*") and right.startswith("*"):
            word = left[:-1] + right[1:]
        else:
            word = left + right
        if re.search(rf"{_LETTER}\*+{_LETTER}", word):
            core = word.strip("*")
            if word.startswith("*") and word.endswith("*") and word.count("*") % 2 == 0:
                word = "*" + core.replace("*", "") + "*"
            else:
                residuals.append(word)
        moved = m.group("between")
        pages = " ".join(re.findall(marker, moved))
        notes = " ".join(re.findall(anchor, re.sub(marker, " ", moved)))
        return (pages + " " if pages else "") + word + (" " + notes if notes else "")

    joined = pattern.sub(join, text)
    for match in re.finditer(HYPHEN_SIGN, joined):
        residuals.append(joined[max(0, match.start() - 20):match.end() + 20])
    return joined, residuals
