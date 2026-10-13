"""Read-only parsing of the champollion/1 scalar-front-matter work format."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Optional, TYPE_CHECKING, Union

from .findings import ChampollionError

if TYPE_CHECKING:
    from .profile import Profile

_FIELD = re.compile(r"^([a-z][a-z0-9_]*):[ \t]*(.*)$")
_SECTION = re.compile(r"^##(?:[ \t]+(.*))?$")
_UNIT = re.compile(r"^###(?:[ \t]+(.*))?$")
_COMMENT = re.compile(r"<!--[\s\S]*?-->")


class WorkFormatError(ChampollionError):
    """A named work-schema error with a file, source line, and finding code."""

    def __init__(self, message: str, cause: str = "SEG-FRONT-MATTER", *,
                 path: str = "", line: int = 0, code: str = "") -> None:
        self.code = code or cause
        self.path = path
        self.line = line
        super().__init__(message, self.code)


def _fail(path: str, line: int, message: str, code: str = "SEG-FRONT-MATTER") -> None:
    raise WorkFormatError(f"{path}: line {line}: {code}: {message}", code, path=path, line=line)


def normalize_label(s: str) -> str:
    """Normalize only outer whitespace and case for section matching."""
    return s.strip().casefold()


@dataclass
class Unit:
    """An explicitly headed unit; raw lines retain document line numbers."""

    title: str
    lines: list[tuple[int, str]]
    text: str
    line: int


@dataclass
class Section:
    """A preserved document section and its explicitly headed units."""

    label: str
    units: list[Unit]
    line: int
    preamble: list[tuple[int, str]] = field(default_factory=list, repr=False)


def _validate_preamble(section: Section, path: str) -> None:
    text = _COMMENT.sub(lambda match: "\n" * match.group(0).count("\n"),
                        "\n".join(line for _, line in section.preamble))
    if text.strip():
        index = next(i for i, line in enumerate(text.split("\n")) if line.strip())
        number = section.preamble[index][0]
        _fail(path, number, f"reader-facing text before first unit in {section.label!r}", "SEG-PARITY")


@dataclass
class Work:
    """A parsed work, including unknown scalar fields and unknown sections."""

    path: str
    slug: str
    front: dict[str, str]
    sections: list[Section]

    def section(self, label: str) -> Optional[Section]:
        """Find a section by trimmed, case-insensitive label."""
        normalized = normalize_label(label)
        matches = [s for s in self.sections if normalize_label(s.label) == normalized]
        if len(matches) > 1:
            _fail(self.path, matches[1].line, f"duplicate section {label!r}", "SEG-PARITY")
        return matches[0] if matches else None

    def original(self) -> Section:
        """Return Original, or raise a named missing-source-section error."""
        original = self.section("original")
        if original is None:
            _fail(self.path, 0, "no Original section", "SEG-PARITY")
        return original

    def register_section(self, profile: "Profile", register_id: str) -> Optional[Section]:
        """Resolve explicit aliases only, refusing duplicate register mappings."""
        registers = [r for r in profile.registers if r.id == register_id]
        if not registers:
            raise WorkFormatError(f"{self.path}: undeclared register {register_id!r}",
                                  "REG-1", path=self.path)
        aliases = {normalize_label(a) for a in registers[0].sections}
        matches = [s for s in self.sections if normalize_label(s.label) in aliases]
        if len(matches) > 1:
            _fail(self.path, matches[1].line, f"multiple sections resolve to register {register_id!r}", "SEG-PARITY")
        if matches:
            _validate_preamble(matches[0], self.path)
        return matches[0] if matches else None

    def unit_titles(self, profile: "Profile", register_id: str) -> list[str]:
        """Return exact unit titles for a register, or an empty list if absent."""
        section = self.register_section(profile, register_id)
        return [u.title for u in section.units] if section is not None else []


def parse_front_matter(text: str, path: str) -> tuple[dict[str, str], int]:
    """Parse scalar fields and return the 1-based first body-line number."""
    path = str(path)
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0] != "---":
        _fail(path, 1, "missing opening front-matter delimiter")
    front = {}
    for index, line in enumerate(lines[1:], 2):
        if line == "---":
            if not front:
                _fail(path, index, "front matter requires at least one scalar field")
            return front, index + 1
        match = _FIELD.fullmatch(line)
        if match is None:
            _fail(path, index, "malformed scalar field line")
        key, value = match.groups()
        if key in front:
            _fail(path, index, f"duplicate front-matter key {key!r}")
        value = value.strip()
        if value.startswith('"'):
            try:
                parsed = json.loads(value)
            except (ValueError, RecursionError) as exc:
                _fail(path, index, f"field {key!r}: invalid quoted string: {exc}")
            if type(parsed) is not str or "\n" in parsed or "\r" in parsed:
                _fail(path, index, f"field {key!r}: quoted value must be a single-line string")
            value = parsed
        elif value.startswith(("[", "{", "- ", "|", ">")):
            _fail(path, index, f"field {key!r}: compound values and comments must be quoted")
        if "\r" in value:
            _fail(path, index, f"field {key!r}: literal newline is forbidden")
        front[key] = value
    _fail(path, len(lines), "missing closing front-matter delimiter")


def parse_work(path: Union[str, Path]) -> Work:
    """Read and parse a UTF-8 work without synthesizing or changing units."""
    name = str(path)
    try:
        text = Path(path).read_bytes().decode("utf-8").replace("\r\n", "\n")
    except (OSError, UnicodeError) as exc:
        raise WorkFormatError(f"{name}: cannot read UTF-8 work: {exc}", "WORK-IO", path=name) from exc
    front, start = parse_front_matter(text, name)
    sections, labels = [], set()
    section, unit = None, None
    titles = set()
    for number, line in enumerate(text.split("\n")[start - 1:], start):
        heading = _SECTION.fullmatch(line)
        if heading is not None:
            label = (heading.group(1) or "").strip()
            if not label:
                _fail(name, number, "empty section label", "SEG-PARITY")
            normalized = normalize_label(label)
            if normalized in labels:
                _fail(name, number, f"duplicate section label {label!r}", "SEG-PARITY")
            labels.add(normalized)
            section = Section(label, [], number)
            sections.append(section)
            unit, titles = None, set()
            continue
        heading = _UNIT.fullmatch(line)
        if heading is not None:
            title = (heading.group(1) or "").strip()
            if not title:
                _fail(name, number, "empty unit title", "SEG-PARITY")
            if section is None:
                _fail(name, number, "unit heading outside a section", "SEG-PARITY")
            if title in titles:
                _fail(name, number, f"duplicate unit title {title!r}", "SEG-PARITY")
            titles.add(title)
            unit = Unit(title, [], "", number)
            section.units.append(unit)
            continue
        if unit is not None:
            unit.lines.append((number, line))
        elif section is not None:
            section.preamble.append((number, line))
    for section in sections:
        if normalize_label(section.label) == "original":
            _validate_preamble(section, name)
        for unit in section.units:
            unit.text = _COMMENT.sub("", "\n".join(line for _, line in unit.lines)).strip()
    # The filename identifies the work even when its declared slug is invalid;
    # provenance validation diagnoses that value without manufacturing a field.
    return Work(name, Path(path).stem, front, sections)
