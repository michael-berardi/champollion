"""Profile-selected house-register archaism, spelling and name gates."""
from pathlib import Path
from typing import Any, List

from ..findings import ChampollionError, Finding
from ..language.en import ARCHAIC_ALL, ARCHAIC_PLAIN, americanize, load_name_table, normalize
from . import Check, Context, finding, gate_status, house_sections, legacy_label


def enabled(profile: Any) -> bool:
    """Return whether any language or name policy is selected."""
    checks = profile.checks
    return (checks.archaisms != "off" or checks.plain_archaisms or
            checks.spelling_profile is not None or checks.name_table is not None)


def _english(ctx: Context) -> bool:
    target = ctx.profile.target
    return target is None or target["tag"].split("-")[0].lower() == "en"


def _name_table(ctx: Context) -> dict:
    value = ctx.profile.checks.name_table
    root = Path(ctx.root).resolve()
    selected = Path(value)
    if selected.is_absolute():
        raise ChampollionError(f"name_table must be project-relative: {value}", cause="REG-NAME-VARIANT")
    path = (root / selected).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ChampollionError(f"name_table escapes project root: {value}", cause="REG-NAME-VARIANT") from exc
    return load_name_table(str(path))


def run(ctx: Context) -> List[Finding]:
    """Use the language helpers for exact legacy counts and first matches."""
    result: List[Finding] = []
    checks = ctx.profile.checks
    table = _name_table(ctx) if checks.name_table is not None else None
    english = _english(ctx)
    for register, section in house_sections(ctx):
        label = legacy_label(register)
        for unit in section.units:
            for number, line in unit.lines:
                if line.lstrip().startswith("<!--"):
                    continue
                args = {"unit": unit.title, "register": register.id, "line": number}
                if english and checks.archaisms == "en-modern":
                    match = ARCHAIC_ALL.search(line)
                    if match:
                        result.append(finding(ctx, "REG-ARCHAISM", "REG-7",
                                              f"{label} line {number}: “{match.group(0)}”", **args))
                if english and checks.plain_archaisms and register.id == "plain":
                    match = ARCHAIC_PLAIN.search(line)
                    if match:
                        # Legacy report supplies the slug; the message has no label.
                        result.append(finding(ctx, "REG-PLAIN-ARCHAISM", "REG-7",
                                              f"line {number}: “{match.group(0)}”", **args))
            if english and checks.spelling_profile == "en-US":
                _, count = americanize(unit.text)
                if count:
                    result.append(finding(ctx, "REG-SPELLING", "REG-10",
                                          f"{label}: {count} British spellings (run scripts/americanize.py)",
                                          unit=unit.title, register=register.id, line=unit.line,
                                          evidence={"count": count, "policy": "en-US"}))
            if table is not None:
                _, count = normalize(ctx.work.slug, unit.text, table)
                if count:
                    result.append(finding(ctx, "REG-NAME-VARIANT", "REG-8",
                                          f"{label}: {count} non-house name spellings (run scripts/normalize_names.py)",
                                          unit=unit.title, register=register.id, line=unit.line,
                                          evidence={"count": count, "name_table": checks.name_table}))
    return result


def statuses(ctx: Context, findings: List[Finding]) -> List[dict]:
    """Expose each selected policy, including an unavailable Spanish list."""
    checks = ctx.profile.checks
    registers = [r.id for r, _ in house_sections(ctx)]
    policies = []
    for name, selected, codes in (
        ("archaisms", checks.archaisms != "off", ("REG-ARCHAISM",)),
        ("plain_archaisms", checks.plain_archaisms, ("REG-PLAIN-ARCHAISM",)),
        ("spelling_profile", checks.spelling_profile is not None, ("REG-SPELLING",)),
        ("name_table", checks.name_table is not None, ("REG-NAME-VARIANT",)),
    ):
        current_registers = [r for r in registers if r == "plain"] if name == "plain_archaisms" else registers
        detail = ""
        if not selected:
            status, detail = "disabled", name + " is not selected"
        elif name == "spelling_profile" and checks.spelling_profile == "es":
            # SPEC §3.3 requires a configuration error for unavailable selected policies.
            status, detail = "unsupported", "no Spanish variant list in 1.0"
        elif name in ("archaisms", "plain_archaisms", "spelling_profile") and not _english(ctx):
            status, detail = "unsupported", "English policy is incompatible with the declared target language"
        elif not current_registers:
            status, detail = "inapplicable", "no applicable house register is present"
        else:
            status = "failed" if any(f.code in codes for f in findings) else "ran"
        policies.append(gate_status("language." + name, status, current_registers, detail))
    base = "disabled" if not enabled(ctx.profile) else (
        "unsupported" if any(p["status"] == "unsupported" for p in policies) else
        "failed" if findings else "ran")
    detail = "; ".join(p["check"] + ": " + p["detail"] for p in policies if p["status"] == "unsupported")
    if base == "ran" and not registers:
        base, detail = "inapplicable", "no applicable house register is present"
    return [gate_status("language", base, registers, detail)] + policies


CHECK = Check("language", enabled, run, statuses)
