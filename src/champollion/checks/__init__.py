"""Ordered mechanical gates and deterministic finding ordering."""
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from ..findings import Finding


@dataclass
class Context:
    """Read-only inputs and source-unit locations for one checked work."""

    work: Any
    profile: Any
    root: str
    today: str
    sources: Dict[str, dict]
    line_for_unit: dict
    work_scope: Optional[Set[str]] = None


@dataclass(frozen=True)
class Check:
    """One registered check with explicit applicability reporting."""

    name: str
    enabled_fn: Callable[[Any], bool]
    run_fn: Callable[[Context], List[Finding]]
    statuses_fn: Optional[Callable[[Context, List[Finding]], List[dict]]] = None

    def enabled(self, profile: Any) -> bool:
        """Return whether any policy in this family is selected."""
        return self.enabled_fn(profile)

    def run(self, ctx: Context) -> List[Finding]:
        """Evaluate the selected policies without changing a document."""
        return self.run_fn(ctx)

    def statuses(self, ctx: Context, findings: List[Finding]) -> List[dict]:
        """Describe the actual gate disposition, not a claim of conformance."""
        if self.statuses_fn is not None:
            return self.statuses_fn(ctx, findings)
        registers = [r.id for r, _ in house_sections(ctx)]
        status = "disabled" if not self.enabled(ctx.profile) else (
            "failed" if any(f.severity == "error" for f in findings) else "ran")
        return [gate_status(self.name, status, registers)]


def gate_status(name: str, status: str, registers: Iterable[str] = (),
                detail: str = "") -> dict:
    """Create the stable gate-status record."""
    return {"check": name, "status": status, "registers": list(registers), "detail": detail}


def house_sections(ctx: Context) -> list:
    """Return present same-units registers in profile order."""
    result = []
    for register in ctx.profile.registers:
        if register.alignment != "same-units":
            continue
        section = ctx.work.register_section(ctx.profile, register.id)
        if section is not None:
            result.append((register, section))
    return result


def legacy_label(register: Any) -> str:
    """Retain Mouseia's Plain label while using other declared display labels."""
    return "Plain" if register.id == "plain" else register.label


def finding(ctx: Context, code: str, rule: str, message: str, unit: str = "",
            register: str = "", line: int = 0, severity: str = "error",
            evidence: Optional[dict] = None) -> Finding:
    """Attach the current work and available evidence to a finding."""
    return Finding(code=code, rule=rule, severity=severity, message=message,
                   work=ctx.work.slug, unit=unit, register=register, line=line,
                   evidence={} if evidence is None else evidence)


def source_record(ctx: Context) -> Optional[dict]:
    """Resolve a local source entry by explicit reference or work identity."""
    reference = ctx.work.front.get("source", "")
    entry = reference.rsplit("#", 1)[1] if "#" in reference else ""
    for key in (ctx.work.front.get("source_id", ""), entry, reference, ctx.work.slug):
        if key and key in ctx.sources:
            return ctx.sources[key]
    return None


def _class_rank(code: str) -> int:
    if code in ("SEG-FRONT-MATTER", "REG-1"):
        return 0
    if code == "SEG-PARITY":
        return 1
    if code in ("SEG-COVERAGE", "VER-SHORT-UNIT"):
        return 2
    if code == "SEG-NUMBERING":
        return 3
    if code in ("VER-OCR-MARKER", "VER-DEBRIS", "VER-DOUBLED-WORD",
                "REG-ARCHAISM", "REG-PLAIN-ARCHAISM", "VER-ELLIPSIS"):
        return 4
    if code in ("REG-SPELLING", "REG-NAME-VARIANT"):
        return 4
    if code == "VER-SPEECH-MARKS":
        return 6
    if code == "REG-PLAIN-COPY":
        return 7
    if code.startswith("SRC-"):
        return 8
    if code.startswith("PRV-"):
        return 9
    return 10


def sort_findings(findings: Iterable[Finding], work: Any = None,
                  profile: Any = None) -> List[Finding]:
    """Sort by work, original position, gate class and legacy scan ordering."""
    works = [] if work is None else ([work] if hasattr(work, "sections") else list(work))
    positions = {}
    for item in works:
        original = item.section("Original")
        if original is not None:
            positions[item.slug] = {u.title: i + 1 for i, u in enumerate(original.units)}
    registers = {} if profile is None else {r.id: i for i, r in enumerate(profile.registers)}
    line_codes = ("VER-OCR-MARKER", "VER-DEBRIS", "VER-DOUBLED-WORD",
                  "REG-ARCHAISM", "REG-PLAIN-ARCHAISM", "VER-ELLIPSIS")

    def key(f: Finding) -> tuple:
        position = 0 if not f.unit else positions.get(f.work, {}).get(f.unit, 10**9)
        rank = _class_rank(f.code)
        register = registers.get(f.register, 10**9)
        subrank = line_codes.index(f.code) if f.code in line_codes else (
            0 if f.code == "REG-SPELLING" else 1 if f.code == "REG-NAME-VARIANT" else 0)
        aggregate = f.code in ("REG-SPELLING", "REG-NAME-VARIANT")
        return (f.work, position, rank, register if rank in (2, 4, 5, 6) else 0,
                1 if aggregate else 0, 0 if aggregate else f.line, subrank, f.code, f.message)

    return sorted(findings, key=key)


def run_checks(work: Any, profile: Any, root: str, today: str,
               sources: Dict[str, dict], work_scope: Optional[Set[str]] = None
               ) -> Tuple[List[Finding], List[dict]]:
    """Run all families and report disabled or inapplicable gates explicitly."""
    original = work.section("Original")
    lines = {} if original is None else {u.title: u.line for u in original.units}
    ctx = Context(work, profile, root, today, sources, lines, work_scope)
    findings: List[Finding] = []
    statuses: List[dict] = []
    for check in CHECKS:
        current = check.run(ctx) if check.enabled(profile) else []
        findings.extend(current)
        statuses.extend(check.statuses(ctx, current))
    return sort_findings(findings, work, profile), statuses


# Imports follow the shared types so individual modules can use them safely.
from . import structure, provenance, rights, coverage, numbering, language, hygiene, speech, register

CHECKS: List[Check] = [structure.CHECK, provenance.CHECK, rights.CHECK, coverage.CHECK,
                      numbering.CHECK, language.CHECK, hygiene.CHECK, speech.CHECK,
                      register.CHECK]
