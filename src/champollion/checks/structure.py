"""Required sections, explicit units and positional alignment."""
from pathlib import Path
from typing import Any, List

from ..findings import Finding
from . import Check, Context, finding


def enabled(profile: Any) -> bool:
    """Return whether structural parity is selected."""
    return profile.checks.structure


def run(ctx: Context) -> List[Finding]:
    """Check required sections and exact declared alignment."""
    result: List[Finding] = []
    stem = Path(ctx.work.path).stem
    if ctx.work.front.get("slug", "") != stem:
        result.append(finding(ctx, "SEG-FRONT-MATTER", "SEG-1",
                              f"slug does not match filename stem {stem!r}",
                              evidence={"expected": stem, "actual": ctx.work.front.get("slug", "")}))
    original = ctx.work.section("Original")
    if original is None:
        result.append(finding(ctx, "SEG-PARITY", "SEG-2", "no Original section"))
    elif not original.units:
        result.append(finding(ctx, "SEG-PARITY", "SEG-1", "Original section has no units",
                              line=original.line))
    else:
        for unit in original.units:
            if not unit.text.strip():
                result.append(finding(ctx, "SEG-PARITY", "SEG-1", "Original unit has empty text",
                                      unit=unit.title, line=unit.line))
    for register in ctx.profile.registers:
        section = ctx.work.register_section(ctx.profile, register.id)
        if section is None:
            if register.required:
                result.append(finding(ctx, "REG-1", "REG-1", f"no {register.label} section",
                                      register=register.id))
            continue
        if not section.units:
            result.append(finding(ctx, "REG-1", "REG-1", f"{register.label} section has no units",
                                  register=register.id, line=section.line))
        for unit in section.units:
            if not unit.text.strip():
                result.append(finding(ctx, "REG-1", "REG-1", f"{register.label} unit has empty text",
                                      unit=unit.title, register=register.id, line=unit.line))
        if original is None:
            continue
        expected = [u.title for u in original.units]
        actual = [u.title for u in section.units]
        if register.alignment == "same-units" and expected != actual:
            index = next((i for i, pair in enumerate(zip(expected, actual))
                          if pair[0] != pair[1]), min(len(expected), len(actual)))
            wanted = expected[index] if index < len(expected) else "<end>"
            found = actual[index] if index < len(actual) else "<end>"
            result.append(finding(ctx, "SEG-PARITY", "SEG-2",
                                  f"{register.label} unit {index + 1}: expected {wanted!r}, found {found!r}",
                                  unit=wanted if wanted != "<end>" else found,
                                  register=register.id,
                                  line=section.units[index].line if index < len(actual) else section.line,
                                  evidence={"expected": expected, "actual": actual, "position": index + 1}))
        elif register.alignment == "by-position" and len(expected) != len(actual):
            result.append(finding(ctx, "SEG-PARITY", "SEG-7",
                                  f"{register.label} unit count differs from Original: {len(actual)} != {len(expected)}",
                                  register=register.id, line=section.line,
                                  evidence={"expected": len(expected), "actual": len(actual)}))
    return result


CHECK = Check("structure", enabled, run)
