"""Declared ordered reference-marker support and line-for-line checking."""
import re
from typing import Any, List, Optional, Union

from ..findings import ChampollionError, Finding
from . import Check, Context, finding, gate_status, house_sections, source_record

SUPPORTED_NOTATIONS = ("leading-number", "decimal", "bracket-decimal", "parenthesis-decimal",
                       "bare-number", "word-number", "double-danda", "folio", "bekker")


def _notation_id(name: str) -> str:
    aliases = {"N.": "leading-number", "N.N": "decimal", "[N.N]": "bracket-decimal",
               "(N.N)": "parenthesis-decimal", "NNN": "bare-number",
               "[<word> N]": "word-number", "॥…॥": "double-danda",
               "[17b]": "folio", "[Bekker 1447a line 8]": "bekker"}
    return aliases.get(name, name.lower())


def _selected(notation: Optional[Union[str, List[str]]]) -> tuple:
    if notation is None or notation == "auto":
        return SUPPORTED_NOTATIONS, []
    names = [s.strip() for s in notation.split(",")] if isinstance(notation, str) else notation
    if not isinstance(names, (list, tuple)) or not all(isinstance(n, str) for n in names):
        return (), [repr(notation)]
    ids = tuple(_notation_id(name) for name in names)
    return ids, [name for name, ident in zip(names, ids) if ident not in SUPPORTED_NOTATIONS]


def extract_markers(text: str, notation: Optional[Union[str, List[str]]] = None) -> List[str]:
    """Return supported marker lexemes in order, refusing unknown notation."""
    selected, unsupported = _selected(notation)
    if unsupported:
        raise ChampollionError("unsupported numbering notation: " + ", ".join(unsupported), cause="SEG-NUMBERING")
    patterns = {
        "leading-number": r"^[ \t]*\d+\.(?!\d)",
        "decimal": r"^[ \t]*\d+(?:\.\d+)+(?:\.(?!\d))?(?=\s|$)",
        "bracket-decimal": r"\[\d+(?:\.\d+)+\]",
        "parenthesis-decimal": r"\(\d+(?:\.\d+)+\)",
        "bare-number": r"^[ \t]*\d+(?=[ \t]+|$)",
        "word-number": r"\[[^\W\d_]+[ \t]+\d+\]",
        "double-danda": r"॥[^॥\n]+॥",
        "folio": r"\[\d+[a-zA-Z]\]",
        "bekker": r"\[Bekker[ \t]+\d+[ab][ \t]+line[ \t]+\d+\]",
    }
    hits = []
    clean = re.sub(r"<!--[\s\S]*?-->", "", text)
    for name in selected:
        for match in re.finditer(patterns[name], clean, flags=re.M):
            hits.append((match.start(), match.end(), match.group(0).strip()))
    # Prefer the longest match at a position; numeric-prefix patterns overlap.
    hits.sort(key=lambda hit: (hit[0], -hit[1]))
    result = []
    last_end = -1
    for start, end, marker in hits:
        if start >= last_end:
            result.append(marker)
            last_end = end
    return result


def _policy(ctx: Context) -> tuple:
    record = source_record(ctx) or {}
    policy = record.get("numbering", {})
    if not isinstance(policy, dict):
        return policy, False
    notation = ctx.work.front.get("numbering_notation") or record.get("numbering_notation") or policy.get("notation")
    line_for_line = record.get("line_for_line", policy.get("line_for_line", False))
    front_line_policy = ctx.work.front.get("line_for_line")
    if front_line_policy is not None:
        if front_line_policy.casefold() not in ('true', 'false'):
            raise ChampollionError('line_for_line must be true or false', cause='schema')
        line_for_line = front_line_policy.casefold() == 'true'
    if type(line_for_line) is not bool:
        raise ChampollionError('source line_for_line policy must be a boolean', cause='schema')
    return notation, line_for_line


def enabled(profile: Any) -> bool:
    """Return whether numbering continuity is selected."""
    return profile.checks.numbering


def _lines(text: str) -> int:
    clean = re.sub(r"<!--[\s\S]*?-->", "", text)
    return sum(1 for line in clean.splitlines() if line.strip())


def run(ctx: Context) -> List[Finding]:
    """Compare each paired unit's marker sequence and declared line count."""
    notation, line_for_line = _policy(ctx)
    _, unsupported = _selected(notation)
    if unsupported:
        return []
    original = ctx.work.section("Original")
    if original is None:
        return []
    result: List[Finding] = []
    for register, section in house_sections(ctx):
        for index, source in enumerate(original.units):
            target = section.units[index] if index < len(section.units) else None
            expected = extract_markers(source.text, notation)
            actual = [] if target is None else extract_markers(target.text, notation)
            if expected != actual:
                result.append(finding(ctx, "SEG-NUMBERING", "SEG-5",
                                      "target marker sequence differs from Original",
                                      unit=source.title, register=register.id,
                                      line=source.line if target is None else target.line,
                                      evidence={"expected": expected, "actual": actual,
                                                "supported_notations": list(SUPPORTED_NOTATIONS)}))
            if line_for_line and _lines(source.text) != (0 if target is None else _lines(target.text)):
                result.append(finding(ctx, "SEG-NUMBERING", "SEG-6",
                                      "target line count differs from Original under line-for-line policy",
                                      unit=source.title, register=register.id,
                                      line=source.line if target is None else target.line,
                                      evidence={"expected": _lines(source.text),
                                                "actual": 0 if target is None else _lines(target.text)}))
    return result


def statuses(ctx: Context, findings: List[Finding]) -> List[dict]:
    """Declare notation support and never call unavailable marker evidence a pass."""
    registers = [r.id for r, _ in house_sections(ctx)]
    detail = "supported notations: " + ", ".join(SUPPORTED_NOTATIONS)
    if not enabled(ctx.profile):
        return [gate_status("numbering", "disabled", registers, detail)]
    notation, line_for_line = _policy(ctx)
    _, unsupported = _selected(notation)
    if unsupported:
        return [gate_status("numbering", "unsupported", registers,
                            "unsupported numbering notation: " + ", ".join(unsupported) + "; " + detail)]
    original = ctx.work.section("Original")
    if findings:
        return [gate_status("numbering", "failed", registers, detail)]
    if original is None or not original.units or not registers:
        return [gate_status("numbering", "inapplicable", registers, "no paired source/target units; " + detail)]
    if not line_for_line and not any(extract_markers(u.text, notation) for u in original.units):
        return [gate_status("numbering", "inapplicable", registers, "no recognized source markers; " + detail)]
    return [gate_status("numbering", "ran", registers, detail)]


CHECK = Check("numbering", enabled, run, statuses)
