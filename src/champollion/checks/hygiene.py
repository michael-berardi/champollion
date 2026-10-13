"""Mouseia's scan-debris, OCR, repetition and ellipsis gates."""
import re
from typing import Any, List

from ..findings import Finding
from . import Check, Context, finding, gate_status, house_sections, legacy_label

OCR_MARKER = re.compile(r"\[OCR unclear", re.I)
DEBRIS = re.compile(r"[\^|«»{}~\\]|\*\*|__|&(?:lt|gt|amp|nbsp|quot|#\d+);")
DOUBLED = re.compile(r"\b([A-Za-z][a-z]+)\s+\1\b")
DOUBLED_OK = frozenset({
    "cao", "yan", "had", "that", "very", "far", "so", "on", "o", "ah", "woe", "come", "go", "again",
    "by", "out", "more", "round", "ever", "two", "one", "deep", "do", "yes", "no", "is", "long", "little",
    "many", "fast", "slowly", "away", "well", "in", "cry", "imitate", "happens", "ambition", "it", "hope",
    "all", "up", "down", "back", "high", "now", "here", "there", "soon", "blessed", "holy", "kill",
    "strike", "burn", "hear", "listen", "look", "see", "alas", "oh", "ha", "hush", "quick"
})
# The strict checker enforces REG-9; compat.mouseia retains legacy patterns.
ELLIPSIS = re.compile(r"\.{2,}|\(\.\.\)")
NEUTRAL_DEBRIS = re.compile(r"\*\*|__|&(?:lt|gt|amp|nbsp|quot|#\d+);")


def enabled(profile: Any) -> bool:
    """Return whether any hygiene policy is selected."""
    return profile.checks.debris or profile.checks.ellipsis != "off"


def _english(ctx: Context) -> bool:
    target = ctx.profile.target
    return (target is not None and target["tag"].split("-")[0].lower() == "en") or (
        target is None and (ctx.profile.checks.archaisms == 'en-modern' or
                            ctx.profile.checks.spelling_profile == 'en-US'))


def run(ctx: Context) -> List[Finding]:
    """Scan house-register lines in legacy order, ignoring comment-start lines."""
    result: List[Finding] = []
    for register, section in house_sections(ctx):
        label = legacy_label(register)
        for unit in section.units:
            for number, line in unit.lines:
                if line.lstrip().startswith("<!--"):
                    continue
                args = {"unit": unit.title, "register": register.id, "line": number}
                if ctx.profile.checks.debris:
                    if OCR_MARKER.search(line):
                        result.append(finding(ctx, "VER-OCR-MARKER", "SEG-8",
                                              f"{label} line {number}: raw [OCR unclear] marker", **args))
                    # Quote conventions and mathematical punctuation are not universal debris.
                    debris = (DEBRIS if _english(ctx) else NEUTRAL_DEBRIS).search(line)
                    if debris:
                        context = line[max(0, debris.start() - 30):debris.end() + 30]
                        result.append(finding(ctx, "VER-DEBRIS", "VER-6",
                                              f"{label} line {number}: {debris.group(0)!r} in “…{context}…”", **args))
                    if _english(ctx):
                        for match in DOUBLED.finditer(line):
                            if match.group(1).lower() not in DOUBLED_OK:
                                result.append(finding(ctx, "VER-DOUBLED-WORD", "REG-9",
                                                      f"{label} line {number}: “{match.group(0)}”", **args))
                if ctx.profile.checks.ellipsis != "off" and ELLIPSIS.search(line):
                    result.append(finding(ctx, "VER-ELLIPSIS", "REG-9",
                                          f"{label} line {number}: use a single “…”",
                                          severity=ctx.profile.checks.ellipsis, **args))
    return result


def statuses(ctx: Context, findings: List[Finding]) -> List[dict]:
    """Keep disabled subpolicies and non-English repetition limitations visible."""
    registers = [r.id for r, _ in house_sections(ctx)]
    base = "disabled" if not enabled(ctx.profile) else ("failed" if any(
        f.severity == "error" for f in findings) else "ran" if registers else "inapplicable")
    result = [gate_status("hygiene", base, registers,
                          "no house register is present" if base == "inapplicable" else "")]
    if not ctx.profile.checks.debris:
        result.append(gate_status("hygiene.debris", "disabled", registers, "debris is false"))
    elif not _english(ctx):
        result.append(gate_status("hygiene.doubled_word", "inapplicable", registers,
                                  "English doubled-word list does not apply to the declared target language"))
    if ctx.profile.checks.ellipsis == "off":
        result.append(gate_status("hygiene.ellipsis", "disabled", registers, "ellipsis is off"))
    return result


CHECK = Check("hygiene", enabled, run, statuses)
