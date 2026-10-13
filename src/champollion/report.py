"""Mechanical reports with explicit exception debt and separate judgement records."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable, List

from . import __version__
from .checks import run_checks, sort_findings
from .findings import ChampollionError, Finding, format_finding
from .format import parse_work
from .profile import profile_json
from .sources import load_sources, local_path, read_json

VERSION = "1.0.0"


def _record(work: Any, sources: dict) -> dict:
    reference = work.front.get("source", "")
    selector = reference.split("#", 1)[1] if "#" in reference else ""
    for key in (selector, work.front.get("source_id", ""), work.slug, reference):
        if key and key in sources:
            return sources[key]
    return {}


def _source_evidence(record: dict, root: Path) -> dict:
    evidence = dict(record)
    snapshot = record.get("raw_snapshot", record.get("path", ""))
    evidence["expected_sha256"] = record.get("sha256", "")
    evidence["computed_sha256"] = None
    if snapshot:
        path = local_path(root, snapshot)
        if path.exists():
            try:
                evidence["computed_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError as exc:
                raise ChampollionError(f"{path}: {exc}", cause="IO") from exc
    return evidence


def _reviews(work: Any, record: dict, root: Path) -> List[dict]:
    records = record.get("reviews", [])
    if not isinstance(records, list):
        raise ChampollionError(f"{work.path}: reviews must be an array", cause="schema")
    records = list(records)
    reference = work.front.get("review_record", "")
    if reference:
        path = local_path(root, reference)
        obj = read_json(path)
        records.extend(obj.get("reviews", [obj]) if isinstance(obj, dict) else obj if isinstance(obj, list) else [obj])
    for review in records:
        if not isinstance(review, dict):
            raise ChampollionError(f"{work.path}: review record must be an object", cause="VER-11")
        for key in ("reviewer", "date", "protocol_version", "work", "units", "registers", "findings", "resolutions"):
            if key not in review:
                raise ChampollionError(f"{work.path}: review missing {key}", cause="VER-11")
        for key in ("reviewer", "date", "protocol_version", "work"):
            if not isinstance(review[key], str) or not review[key].strip():
                raise ChampollionError(f"{work.path}: review {key} must be a nonempty string", cause="VER-11")
        for key in ("units", "registers", "findings", "resolutions"):
            if not isinstance(review[key], list):
                raise ChampollionError(f"{work.path}: review {key} must be an array", cause="VER-11")
        for key in ("units", "registers"):
            if any(not isinstance(value, str) or not value.strip() for value in review[key]):
                raise ChampollionError(f"{work.path}: review {key} entries must be nonempty strings", cause="VER-11")
        try:
            parsed = date.fromisoformat(review["date"])
            if parsed.isoformat() != review["date"]:
                raise ValueError("expected YYYY-MM-DD")
        except ValueError as exc:
            raise ChampollionError(f"{work.path}: invalid review date: {exc}", cause="VER-11") from exc
    return records


def _exception_states(profile: Any, findings: list, today: str) -> list:
    states = []
    for exception in profile.exceptions:
        item = asdict(exception)
        item["matched"] = any((f.code, f.work, f.unit) == (exception.code, exception.work, exception.unit)
                              for f in findings)
        item["overdue"] = today > exception.expires
        item["applied"] = item["matched"] and not item["overdue"] and not exception.code.startswith("SRC-")
        if exception.code.startswith("SRC-"):
            item["detail"] = "exceptions cannot supply missing source evidence or authorize rights"
        states.append(item)
    return states


def _finding_dict(finding: Finding, exceptions: list) -> dict:
    obj = asdict(finding)
    matched = next((e for e in exceptions if (e["code"], e["work"], e["unit"]) ==
                    (finding.code, finding.work, finding.unit)), None)
    obj["exception"] = matched
    obj["effective_severity"] = "warn" if matched and matched["applied"] else finding.severity
    return obj


def build_report(works: Iterable[Any], profile: Any, root: str, today: str) -> dict:
    """Check local works and report mechanical results without certifying sense."""
    try:
        if date.fromisoformat(today).isoformat() != today:
            raise ValueError("expected YYYY-MM-DD")
    except (TypeError, ValueError) as exc:
        raise ChampollionError(f"invalid run date {today!r}: {exc}", cause="configuration") from exc
    base = Path(root).resolve()
    documents = [parse_work(w) if isinstance(w, (str, Path)) else w for w in works]
    documents.sort(key=lambda w: (w.slug, w.path))
    slugs: set = set()
    for work in documents:
        if work.slug in slugs:
            raise ChampollionError(f"duplicate work slug {work.slug}", cause="configuration")
        slugs.add(work.slug)
    adapter_records = {}
    scope = None
    if profile.name.casefold() == "mouseia":
        from .adapters.mouseia import adapt_work, speech_work_scope
        adapted = []
        for work in documents:
            copied, mappings = adapt_work(work, profile)
            adapted.append(copied)
            adapter_records[work.slug] = mappings
        documents = adapted
        scope = speech_work_scope()
    sources = load_sources(str(base), documents)
    findings = []
    work_records = []
    for work in documents:
        if scope is None:
            found, gates = run_checks(work, profile, str(base), today, sources)
        else:
            found, gates = run_checks(work, profile, str(base), today, sources, work_scope=scope)
        for gate in gates:
            if gate["status"] == "unsupported" and (gate["check"] == "language" or gate["check"].startswith("language.")):
                raise ChampollionError(gate["detail"], cause="unsupported-language-policy")
        findings.extend(found)
        record = _record(work, sources)
        reviews = _reviews(work, record, base)
        registers = []
        for register in profile.registers:
            section = work.register_section(profile, register.id)
            registers.append({"id": register.id, "label": register.label, "required": register.required,
                              "alignment": register.alignment, "present": section is not None,
                              "units": [u.title for u in section.units] if section else []})
        try:
            work_sha256 = hashlib.sha256(Path(work.path).read_bytes()).hexdigest()
        except OSError as exc:
            raise ChampollionError(f"{work.path}: {exc}", cause="IO") from exc
        work_records.append({"path": work.path, "slug": work.slug, "work_sha256": work_sha256, "registers": registers,
                             "source": _source_evidence(record, base), "source_reference": work.front.get("source", ""),
                             "editions": {r.id: {"translator": work.front.get(r.id + "_translator", ""),
                                                  "note": work.front.get(r.id + "_note", "")} for r in profile.registers},
                             "gates": gates, "adapter": adapter_records.get(work.slug, []), "review_records": reviews})
    exceptions = _exception_states(profile, findings, today)
    for exception in exceptions:
        if exception["overdue"]:
            findings.append(Finding(code="VER-12", rule="VER-12", severity="error", work=exception["work"],
                                    unit=exception["unit"], message=f"overdue exception owned by {exception['owner']} expired {exception['expires']}",
                                    evidence={"exception": exception}))
    ordered = sort_findings(findings, work=documents, profile=profile)
    rows = [_finding_dict(f, exceptions) for f in ordered]
    errors = sum(row["effective_severity"] == "error" for row in rows)
    warnings = sum(row["effective_severity"] == "warn" for row in rows)
    core_enabled = all(getattr(profile.checks, name) for name in ("structure", "coverage", "numbering"))
    for item in work_records:
        item["findings"] = [row for row in rows if row["work"] == item["slug"]]
        blockers = []
        if any(row["effective_severity"] == "error" for row in item["findings"]):
            blockers.append("blocking mechanical findings")
        if not core_enabled:
            blockers.append("mandatory core gates disabled")
        if any(g["status"] == "unsupported" or (g["status"] == "failed" and not item["findings"])
               for g in item["gates"]):
            blockers.append("failed or unsupported gates without an applicable exception")
        valid_reviews = [r for r in item["review_records"]
                         if r["work"] == item["slug"] and r["protocol_version"] == VERSION
                         and r['date'] <= today
                         and r.get('work_sha256') == item['work_sha256']
                         and r.get('profile_fingerprint') == profile.fingerprint
                         and r.get('source_sha256') == item['source'].get('computed_sha256')
                         and item['source'].get('computed_sha256') is not None]
        if not valid_reviews:
            blockers.append("VER-11: current judgement review record absent or not bound to these work, source and profile bytes")
        else:
            original = next(w for w in documents if w.slug == item["slug"]).section("original")
            required_units = {u.title for u in original.units} if original else set()
            for register in item["registers"]:
                if register["required"] and register["alignment"] == "same-units":
                    reviewed_units = {u for r in valid_reviews if register["id"] in r["registers"] for u in r["units"]}
                    if not required_units.issubset(reviewed_units):
                        blockers.append(f"VER-10: incomplete judgement coverage for {register['id']}")
            if any(r.get("unresolved_blockers") or r.get("unresolved_findings") or
                   (r["findings"] and len(r["resolutions"]) < len(r["findings"])) for r in valid_reviews):
                blockers.append("unresolved judgement blockers")
        item["publication_gate"] = {"status": "blocked" if blockers else "eligible", "blockers": blockers,
                                    "detail": "mechanical checks do not certify translation sense"}
    review_records = [review for item in work_records for review in item["review_records"]]
    counts = {"works": len(documents), "errors": errors, "warnings": warnings, "exceptions": len(exceptions),
              "exception_debt": len(exceptions), "overdue": sum(e["overdue"] for e in exceptions),
              "unmatched_exceptions": sum(not e["matched"] for e in exceptions)}
    return {"protocol_version": VERSION, "checker_version": __version__, "run_date": today, "root": str(base),
            "profile": {"name": profile.name, "path": str(profile.path), "fingerprint": profile.fingerprint,
                        "settings": profile_json(profile)}, "works": work_records, "findings": rows,
            "counts": counts, "exceptions": exceptions, "incomplete": False,
            "mechanical": {"findings": rows, "gates": [{"work": w["slug"], **g} for w in work_records for g in w["gates"]]},
            "judgement": {"review_records": review_records, "certifies_sense": False}, "review_records": review_records,
            "publication_gate": {"status": "blocked" if any(w["publication_gate"]["status"] == "blocked" for w in work_records)
                                 or errors or not documents else "eligible"}}


def render_text(report: dict, verbose: bool = False, json_mode: bool = False) -> str:
    """Render findings through the shared formatter, then summary and gate states."""
    if json_mode:
        return json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    lines = []
    keys = ("code", "rule", "severity", "message", "work", "unit", "register", "line", "evidence")
    for row in report["findings"]:
        finding = Finding(**{key: row[key] for key in keys})
        exception = row.get("exception")
        lines.append(format_finding(finding, exception=exception if exception and exception["applied"] else None))
    counts = report["counts"]
    lines.append(f"champollion {report['checker_version']} — {counts['works']} works, {counts['errors']} errors, "
                 f"{counts['warnings']} warnings, {counts['exceptions']} exceptions ({counts['overdue']} overdue)")
    if verbose:
        for gate in report["mechanical"]["gates"]:
            lines.append(f"{gate['work']} {gate['check']}: {gate['status']} — {gate['detail']}")
    return "\n".join(lines)
