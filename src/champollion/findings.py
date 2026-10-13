"""Findings, named operational errors, and deterministic basic rendering."""

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Optional

SEVERITY_ERROR = "error"
SEVERITY_WARN = "warn"


@dataclass(frozen=True)
class Finding:
    """An observable protocol finding, separate from editorial judgement."""

    code: str
    rule: str
    severity: str
    message: str
    work: str = ""
    unit: str = ""
    register: str = ""
    line: int = 0
    evidence: dict = field(default_factory=dict)


class ChampollionError(Exception):
    """An operational failure with an explicit, inspectable cause."""

    def __init__(self, message: str, cause: str = "") -> None:
        self.cause = cause or message
        super().__init__(message)


def format_finding(f: Finding, exception: Optional[Any] = None) -> str:
    """Render a finding; the caller supplies only matched active exceptions."""
    severity = "WARN" if exception is not None or f.severity == SEVERITY_WARN else "ERROR"
    location = f" [{f.unit}]" if f.unit else ""
    suffix = " [exception]" if exception is not None else ""
    return f"{severity} {f.work}{location} {f.code}: {f.message}{suffix}"


def _class_order(code: str) -> int:
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
        return 5
    if code == "VER-SPEECH-MARKS":
        return 6
    if code == "REG-PLAIN-COPY":
        return 7
    if code.startswith("SRC-"):
        return 8
    if code.startswith("PRV-"):
        return 9
    return 10


def _line_order(code: str) -> int:
    legacy = ("VER-OCR-MARKER", "VER-DEBRIS", "VER-DOUBLED-WORD", "REG-ARCHAISM",
              "REG-PLAIN-ARCHAISM", "VER-ELLIPSIS", "REG-SPELLING", "REG-NAME-VARIANT")
    return legacy.index(code) if code in legacy else len(legacy)


def sort_findings(findings: Iterable[Finding]) -> list[Finding]:
    """Sort by work, class, source line, code, and message deterministically.

    Document-aware unit/register ordering belongs to the check runner; this
    standalone helper requires no work document and preserves the §1 contract.
    """
    return sorted(findings, key=lambda f: (f.work, _class_order(f.code), f.line,
                                           _line_order(f.code), f.code, f.message))


def findings_json(findings: Iterable[Finding]) -> list[dict]:
    """Return JSON-compatible finding records without dropping evidence."""
    return [asdict(f) for f in findings]
