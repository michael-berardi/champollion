"""Nonempty target coverage and the legacy upper-middle length heuristic."""
import re
from typing import Any, List

from ..findings import Finding
from . import Check, Context, finding, gate_status, house_sections, legacy_label, source_record


def enabled(profile: Any) -> bool:
    """Return whether structural coverage is selected."""
    return profile.checks.coverage


def _clean(text: str) -> str:
    return re.sub(r"<!--[\s\S]*?-->", "", text).strip()


def _eligible_pairs(ctx: Context) -> list:
    original = ctx.work.section("Original")
    sections = house_sections(ctx)
    if original is None or not sections:
        return []
    # Shared positional tuples preserve Mouseia's Original/Musean/Plain zip.
    return [units for units in zip(original.units, *(s.units for _, s in sections))
            if len(_clean(units[0].text)) >= ctx.profile.checks.min_source_chars]


def run(ctx: Context) -> List[Finding]:
    """Check endpoint existence, blank preservation and length outliers."""
    result: List[Finding] = []
    original = ctx.work.section("Original")
    if original is None:
        return result
    sections = house_sections(ctx)
    for register, section in sections:
        for index, source in enumerate(original.units):
            target = section.units[index] if index < len(section.units) else None
            if target is None or not _clean(target.text):
                result.append(finding(ctx, "SEG-COVERAGE", "VER-3",
                                      f"{register.label} source unit has no nonempty target text",
                                      unit=source.title, register=register.id,
                                      line=source.line if target is None else target.line,
                                      evidence={"source_unit": source.title, "target_present": target is not None}))
                continue
            nonempty = [line for line in _clean("\n".join(text for _, text in target.lines)).splitlines()
                        if line.strip()]
            if not nonempty:
                result.append(finding(ctx, "SEG-COVERAGE", "VER-3",
                                      f"{register.label} target unit has no nonempty line",
                                      unit=source.title, register=register.id, line=target.line,
                                      evidence={"source_unit": source.title, "nonempty_lines": 0}))
            blanks = _clean(source.text).count("——")
            target_blanks = _clean(target.text).count("——")
            if blanks != target_blanks:
                result.append(finding(ctx, "SEG-COVERAGE", "SEG-9",
                                      f"{register.label} deliberate blank count differs from Original",
                                      unit=source.title, register=register.id, line=target.line,
                                      evidence={"expected": blanks, "actual": target_blanks}))
    threshold = ctx.profile.checks.short_unit_ratio
    if threshold is None:
        return result
    tuples = _eligible_pairs(ctx)
    if len(tuples) < ctx.profile.checks.min_units_for_ratio:
        return result
    for index, (register, _) in enumerate(sections, start=1):
        ratios = sorted(len(_clean(t[index].text)) / len(_clean(t[0].text)) for t in tuples)
        median = ratios[len(ratios) // 2]
        for units in tuples:
            ratio = len(_clean(units[index].text)) / len(_clean(units[0].text))
            if ratio < threshold * median:
                label = legacy_label(register)
                result.append(finding(ctx, "VER-SHORT-UNIT", "VER-3",
                                      f"{label} English/source length is {ratio:.2f}, work median {median:.2f}; "
                                      "check for omitted or misaligned text",
                                      unit=units[0].title, register=register.id, line=units[index].line,
                                      evidence={"ratio": ratio, "median": median, "threshold": threshold,
                                                "eligible_units": len(tuples)}))
    return result


def statuses(ctx: Context, findings: List[Finding]) -> List[dict]:
    """Expose structural coverage separately from the optional heuristic."""
    registers = [r.id for r, _ in house_sections(ctx)]
    applicable = ctx.work.section("Original") is not None and bool(registers)
    base = "disabled" if not enabled(ctx.profile) else (
        "failed" if any(f.code == "SEG-COVERAGE" for f in findings) else
        "ran" if applicable else "inapplicable")
    if not enabled(ctx.profile) or ctx.profile.checks.short_unit_ratio is None:
        ratio_status, detail = "disabled", "short_unit_ratio is null" if enabled(ctx.profile) else "coverage is disabled"
    elif len(_eligible_pairs(ctx)) < ctx.profile.checks.min_units_for_ratio:
        ratio_status, detail = "inapplicable", "fewer than min_units_for_ratio eligible units"
    else:
        ratio_status, detail = ("failed" if any(f.code == "VER-SHORT-UNIT" for f in findings) else "ran"), ""
    result = [gate_status("coverage", base, registers,
                          "no paired source/target sections" if base == "inapplicable" else ""),
              gate_status("coverage.short_unit_ratio", ratio_status, registers, detail)]
    record = source_record(ctx) or {}
    policy = record.get("source_form", {})
    if enabled(ctx.profile) and policy:
        result.append(gate_status("coverage.source_form", "unsupported", registers,
                                  "declared source_form policy is not implemented in 1.0: " + repr(policy)))
    return result


CHECK = Check("coverage", enabled, run, statuses)
