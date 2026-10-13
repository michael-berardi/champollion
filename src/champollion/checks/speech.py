"""Straight-double-quote balance, with optional adapter-owned work scope."""
from typing import Any, List

from ..findings import Finding
from . import Check, Context, finding, gate_status


def enabled(profile: Any) -> bool:
    """Return whether any register requests speech-mark checking."""
    return bool(profile.checks.speech_marks)


def run(ctx: Context) -> List[Finding]:
    """Apply Mouseia's opening/closing classification and unit state exactly."""
    result: List[Finding] = []
    if ctx.work_scope is not None and ctx.work.slug not in ctx.work_scope:
        return result
    selected = set(ctx.profile.checks.speech_marks)
    for register in ctx.profile.registers:
        if register.id not in selected:
            continue
        section = ctx.work.register_section(ctx.profile, register.id)
        if section is None:
            continue
        label = "Plain" if register.id == "plain" else register.label
        for unit in section.units:
            open_at = None
            for number, line in unit.lines:
                for index, char in enumerate(line):
                    if char != '"':
                        continue
                    opening = index == 0 or line[index - 1] in " (—"
                    args = {"unit": unit.title, "register": register.id, "line": number,
                            "evidence": {"opening_line": open_at, "column": index + 1}}
                    if opening and open_at:
                        result.append(finding(ctx, "VER-SPEECH-MARKS", "VER-8",
                                              f"{label} line {number}: new speech opens while the one "
                                              f"from line {open_at} is unclosed", **args))
                    if not opening and not open_at:
                        result.append(finding(ctx, "VER-SPEECH-MARKS", "VER-8",
                                              f"{label} line {number}: closing mark with no open speech", **args))
                    open_at = number if opening else None
            if open_at:
                result.append(finding(ctx, "VER-SPEECH-MARKS", "VER-8",
                                      f"{label} line {open_at}: speech never closed",
                                      unit=unit.title, register=register.id, line=open_at,
                                      evidence={"opening_line": open_at}))
    return result


def statuses(ctx: Context, findings: List[Finding]) -> List[dict]:
    """Name an adapter's scope whenever it limits the gate."""
    registers = list(ctx.profile.checks.speech_marks)
    scope = "" if ctx.work_scope is None else "work scope: " + ", ".join(sorted(ctx.work_scope))
    if not enabled(ctx.profile):
        return [gate_status("speech", "disabled", registers, "speech_marks is empty")]
    if ctx.work_scope is not None and ctx.work.slug not in ctx.work_scope:
        return [gate_status("speech", "inapplicable", registers, scope)]
    present = [r for r in registers if ctx.work.register_section(ctx.profile, r) is not None]
    if not present:
        return [gate_status("speech", "inapplicable", registers, "no selected register is present; " + scope)]
    return [gate_status("speech", "failed" if findings else "ran", present, scope)]


CHECK = Check("speech", enabled, run, statuses)
