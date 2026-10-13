"""Strict validation of the frozen champollion-profile/1 JSON schema."""

from dataclasses import asdict, dataclass, replace
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Optional, Union

from .findings import ChampollionError


@dataclass(frozen=True)
class Register:
    """A declared register and its explicit section aliases."""

    id: str
    label: str
    required: bool
    alignment: str
    sections: tuple[str, ...]


@dataclass(frozen=True)
class Checks:
    """The complete effective check configuration, with no implicit defaults."""

    structure: bool
    coverage: bool
    numbering: bool
    copy_ratio: Optional[float]
    speech_marks: tuple[str, ...]
    archaisms: str
    plain_archaisms: bool
    spelling_profile: Optional[str]
    name_table: Optional[str]
    debris: bool
    ellipsis: str
    short_unit_ratio: Optional[float]
    min_source_chars: int
    min_units_for_ratio: int
    min_sentences: int
    min_sentence_chars: int


@dataclass(frozen=True)
class ExceptionRecord:
    """An exact finding selector and its accountable, expiring review."""

    code: str
    work: str
    unit: str
    owner: str
    reason: str
    recorded: str
    expires: str


@dataclass(frozen=True)
class Profile:
    """A fully validated profile and its local byte-level identity."""

    kind: str
    name: str
    description: str
    source: Optional[dict[str, str]]
    target: Optional[dict[str, str]]
    target_locale: Optional[str]
    registers: tuple[Register, ...]
    checks: Checks
    rights: dict[str, list[str]]
    exceptions: tuple[ExceptionRecord, ...]
    path: str
    fingerprint: str


def _fail(path: str, field: str, reason: str) -> None:
    raise ChampollionError(f"{path}: {field}: {reason}", cause="PROFILE-SCHEMA")


def _object(value: Any, path: str, field: str, required: set[str],
            optional: Optional[set[str]] = None) -> dict:
    if type(value) is not dict:
        _fail(path, field, "expected an object")
    unknown = set(value) - required - (optional or set())
    if unknown:
        _fail(path, field, f"unknown field {sorted(unknown, key=str)[0]!r}")
    missing = required - set(value)
    if missing:
        _fail(path, f"{field}.{sorted(missing)[0]}", "required field missing")
    return value


def _string(value: Any, path: str, field: str) -> str:
    if type(value) is not str or not value.strip():
        _fail(path, field, "expected a nonempty string")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        _fail(path, field, f"invalid Unicode string: {exc}")
    return value


def _boolean(value: Any, path: str, field: str) -> bool:
    if type(value) is not bool:
        _fail(path, field, "expected a boolean")
    return value


def _array(value: Any, path: str, field: str) -> list:
    if type(value) is not list:
        _fail(path, field, "expected an array")
    return value


def _choice(value: Any, path: str, field: str, choices: tuple) -> Any:
    if value is not None and type(value) is not str:
        _fail(path, field, f"expected one of {choices!r}")
    if value not in choices:
        _fail(path, field, f"expected one of {choices!r}")
    return value


def _ratio(value: Any, path: str, field: str, positive: bool) -> Optional[float]:
    if value is None:
        return None
    if type(value) not in (int, float):
        _fail(path, field, "expected null or a finite number")
    if type(value) is float and not math.isfinite(value):
        _fail(path, field, "expected a finite number")
    # An arbitrarily large JSON integer need not be converted to float to reject it.
    if not 0 <= value <= 1 or (positive and value == 0):
        _fail(path, field, "expected 0 < number <= 1" if positive else "expected 0 <= number <= 1")
    return value


def _integer(value: Any, path: str, field: str, minimum: int) -> int:
    if type(value) is not int or value < minimum:
        _fail(path, field, f"expected an integer >= {minimum}")
    return value


def _tag(value: Any, path: str, field: str) -> str:
    tag = _string(value, path, field)
    # RFC 5646 syntactic language tags, including private use and grandfathered tags.
    grandfathered = frozenset(("en-gb-oed", "i-ami", "i-bnn", "i-default", "i-enochian",
        "i-hak", "i-klingon", "i-lux", "i-mingo", "i-navajo", "i-pwn", "i-tao", "i-tay",
        "i-tsu", "sgn-be-fr", "sgn-be-nl", "sgn-ch-de", "art-lojban", "cel-gaulish",
        "no-bok", "no-nyn", "zh-guoyu", "zh-hakka", "zh-min", "zh-min-nan", "zh-xiang"))
    pattern = (r"(?:[A-Za-z]{2,3}(?:-[A-Za-z]{3}){0,3}|[A-Za-z]{4}|[A-Za-z]{5,8})"
               r"(?:-[A-Za-z]{4})?(?:-(?:[A-Za-z]{2}|[0-9]{3}))?"
               r"(?:-(?:[A-Za-z0-9]{5,8}|[0-9][A-Za-z0-9]{3}))*"
               r"(?:-[0-9A-WY-Za-wy-z](?:-[A-Za-z0-9]{2,8})+)*"
               r"(?:-[xX](?:-[A-Za-z0-9]{1,8})+)?")
    if tag.lower() in grandfathered or re.fullmatch(r"[xX](?:-[A-Za-z0-9]{1,8})+", tag):
        return tag
    if not re.fullmatch(pattern, tag):
        _fail(path, field, "expected a BCP-47 tag")
    parts = tag.lower().split("-")
    singletons = [p for p in parts[1:] if len(p) == 1 and p != "x"]
    if "x" in parts:
        singletons = [p for p in parts[1:parts.index("x")] if len(p) == 1]
    if len(singletons) != len(set(singletons)):
        _fail(path, field, "duplicate BCP-47 extension singleton")
    boundary = next((i for i, part in enumerate(parts[1:], 1) if len(part) == 1), len(parts))
    variants = [part for part in parts[1:boundary] if len(part) >= 5 or
                (len(part) == 4 and part[0].isdigit())]
    if len(variants) != len(set(variants)):
        _fail(path, field, "duplicate BCP-47 variant")
    return tag


def _language(value: Any, path: str, field: str) -> Optional[dict[str, str]]:
    if value is None:
        return None
    obj = _object(value, path, field, {"tag", "name"})
    return {"tag": _tag(obj["tag"], path, field + ".tag"),
            "name": _string(obj["name"], path, field + ".name")}


def _date(value: Any, path: str, field: str) -> str:
    value = _string(value, path, field)
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        _fail(path, field, "expected a Gregorian YYYY-MM-DD date")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        _fail(path, field, f"invalid Gregorian date: {exc}")
    return value


def _registers(value: Any, path: str) -> tuple[Register, ...]:
    result, ids, aliases = [], set(), set()
    for i, item in enumerate(_array(value, path, "registers")):
        field = f"registers[{i}]"
        obj = _object(item, path, field, {"id", "label", "required", "alignment", "sections"})
        ident = _string(obj["id"], path, field + ".id")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", ident) or ident == "original":
            _fail(path, field + ".id", "invalid or reserved register ID")
        if ident in ids:
            _fail(path, field + ".id", "duplicate register ID")
        ids.add(ident)
        sections = _array(obj["sections"], path, field + ".sections")
        if not sections:
            _fail(path, field + ".sections", "at least one alias required")
        for j, alias in enumerate(sections):
            normalized = _string(alias, path, f"{field}.sections[{j}]").strip().casefold()
            if normalized == "original" or normalized in aliases:
                _fail(path, f"{field}.sections[{j}]", "reserved or duplicate section alias")
            aliases.add(normalized)
        result.append(Register(ident, _string(obj["label"], path, field + ".label"),
            _boolean(obj["required"], path, field + ".required"),
            _choice(obj["alignment"], path, field + ".alignment", ("same-units", "by-position", "none")),
            tuple(sections)))
    if sum(r.required and r.alignment == "same-units" for r in result) < 2:
        _fail(path, "registers", "at least two required same-units registers required")
    return tuple(result)


def _checks(value: Any, path: str, registers: tuple[Register, ...]) -> Checks:
    obj = _object(value, path, "checks", set(Checks.__dataclass_fields__))
    result = dict(obj)
    for field in ("structure", "coverage", "numbering", "plain_archaisms", "debris"):
        result[field] = _boolean(obj[field], path, "checks." + field)
    for field, choices in (("archaisms", ("off", "en-modern")),
                           ("spelling_profile", (None, "en-US", "es")),
                           ("ellipsis", ("off", "warn", "error"))):
        result[field] = _choice(obj[field], path, "checks." + field, choices)
    for field in ("copy_ratio", "short_unit_ratio"):
        result[field] = _ratio(obj[field], path, "checks." + field, field == "short_unit_ratio")
    for field in ("min_source_chars", "min_units_for_ratio", "min_sentences", "min_sentence_chars"):
        result[field] = _integer(obj[field], path, "checks." + field, 3 if field == "min_units_for_ratio" else 1)
    ids = {r.id for r in registers}
    selections = _array(obj["speech_marks"], path, "checks.speech_marks")
    selected = set()
    for i, value in enumerate(selections):
        value = _string(value, path, f"checks.speech_marks[{i}]")
        if value not in ids or value in selected:
            _fail(path, f"checks.speech_marks[{i}]", "undeclared or duplicate register ID")
        selected.add(value)
    result["speech_marks"] = tuple(selections)
    if obj["plain_archaisms"] and (obj["archaisms"] != "en-modern" or "plain" not in ids):
        _fail(path, "checks.plain_archaisms", "requires en-modern archaisms and a declared plain register")
    if obj["name_table"] is not None:
        table = _string(obj["name_table"], path, "checks.name_table")
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", table) or "\x00" in table:
            _fail(path, "checks.name_table", "expected a local path, not a URI")
    return Checks(**result)


def _exceptions(value: Any, path: str) -> tuple[ExceptionRecord, ...]:
    result, selectors = [], set()
    fields = set(ExceptionRecord.__dataclass_fields__)
    for i, item in enumerate(_array(value, path, "exceptions")):
        field = f"exceptions[{i}]"
        obj = _object(item, path, field, fields)
        for key in sorted(fields):
            _string(obj[key], path, field + "." + key)
        if not re.fullmatch(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+", obj["code"]):
            _fail(path, field + ".code", "expected an uppercase family-prefixed finding code")
        recorded = _date(obj["recorded"], path, field + ".recorded")
        expires = _date(obj["expires"], path, field + ".expires")
        if expires <= recorded:
            _fail(path, field + ".expires", "must be later than recorded")
        selector = (obj["code"], obj["work"], obj["unit"])
        if selector in selectors:
            _fail(path, field, "duplicate exception selector")
        selectors.add(selector)
        result.append(ExceptionRecord(**obj))
    return tuple(result)


def validate_profile(obj: dict, path: str) -> Profile:
    """Validate every field, naming the supplied file and any offending field."""
    path = str(path)
    obj = _object(obj, path, "profile", {"profile", "name", "description", "registers", "checks", "rights", "exceptions"},
                  {"source", "target", "target_locale"})
    kind = _choice(obj["profile"], path, "profile", ("champollion-profile/1",))
    name = _string(obj["name"], path, "name")
    description = _string(obj["description"], path, "description")
    source, target = (_language(obj.get(field), path, field) for field in ("source", "target"))
    locale = obj.get("target_locale")
    if locale is not None:
        locale = _tag(locale, path, "target_locale")
        if target is not None and locale.split("-")[0].casefold() != target["tag"].split("-")[0].casefold():
            _fail(path, "target_locale", "incompatible with target language")
    registers = _registers(obj["registers"], path)
    checks = _checks(obj["checks"], path, registers)
    rights = _object(obj["rights"], path, "rights", {"allowed"})
    allowed = _array(rights["allowed"], path, "rights.allowed")
    if not allowed:
        _fail(path, "rights.allowed", "at least one license identifier required")
    seen = set()
    for i, value in enumerate(allowed):
        value = _string(value, path, f"rights.allowed[{i}]")
        if value in seen:
            _fail(path, f"rights.allowed[{i}]", "duplicate license identifier")
        seen.add(value)
    exceptions = _exceptions(obj["exceptions"], path)
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return Profile(kind, name, description, source, target, locale, registers, checks,
                   {"allowed": list(allowed)}, exceptions, path, "sha256:" + hashlib.sha256(payload).hexdigest())


def load_profile(path: Union[str, Path]) -> Profile:
    """Load UTF-8 JSON, rejecting duplicate keys and fingerprinting exact bytes."""
    name = str(path)
    try:
        payload = Path(path).read_bytes()
        text = payload.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise ChampollionError(f"{name}: profile: cannot read UTF-8 JSON: {exc}", "PROFILE-IO") from exc

    def pairs(items: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in items:
            if key in result:
                _fail(name, key, "duplicate JSON object key")
            result[key] = value
        return result

    def constant(value: str) -> None:
        _fail(name, "profile", f"nonfinite JSON number {value}")

    try:
        obj = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, RecursionError) as exc:
        raise ChampollionError(f"{name}: profile: invalid JSON: {exc}", "PROFILE-JSON") from exc
    profile = validate_profile(obj, name)
    return replace(profile, fingerprint="sha256:" + hashlib.sha256(payload).hexdigest())


def profile_json(p: Profile) -> dict:
    """Return the validated schema, without internal path/fingerprint fields."""
    obj = asdict(p)
    obj["profile"] = obj.pop("kind")
    obj.pop("path")
    obj.pop("fingerprint")
    obj["registers"] = [dict(asdict(r), sections=list(r.sections)) for r in p.registers]
    obj["checks"]["speech_marks"] = list(p.checks.speech_marks)
    obj["exceptions"] = [asdict(e) for e in p.exceptions]
    return obj
