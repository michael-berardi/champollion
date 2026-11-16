"""Offline validation of study-guide summaries against an edition."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

from .findings import Finding, ChampollionError
from .format import normalize_label, parse_front_matter


class _Section:
    def __init__(self, label, line):
        self.label, self.line = label, line


class SummaryWork:
    """Front matter and section boundaries only.

    A summary describes an edition; it does not re-run the structural gate on the
    Original, so works accepted by a project's own (legacy) gate can be summarised.
    """

    def __init__(self, path):
        self.path = str(path)
        try:
            text = Path(path).read_bytes().decode("utf-8").replace("\r\n", "\n")
        except (OSError, UnicodeError) as exc:
            raise ChampollionError(f"{path}: cannot read UTF-8 work: {exc}", cause="WORK-IO") from exc
        self.front, start = parse_front_matter(text, self.path)
        self.slug = Path(path).stem
        self.sections = []
        for number, line in enumerate(text.split("\n")[start - 1:], start):
            m = re.fullmatch(r"##[ \t]+(.+?)[ \t]*", line)
            if m:
                self.sections.append(_Section(m.group(1), number))


def load_work(path):
    return SummaryWork(path)


def _section(work, register_id, profile):
    registers = [r for r in profile.registers if r.id == register_id]
    if not registers:
        raise ChampollionError(f"undeclared register {register_id!r}", cause="REG-1")
    aliases = {normalize_label(s) for s in registers[0].sections}
    found = [s for s in work.sections if normalize_label(s.label) in aliases]
    if len(found) != 1:
        raise ChampollionError(f"{work.path}: expected one section for {register_id}", cause="SEG-PARITY")
    section = found[0]
    lines = Path(work.path).read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    end = next((s.line - 1 for s in work.sections if s.line > section.line), len(lines))
    return "\n".join(lines[section.line:end])


def basis_hash(text):
    text = re.sub(r"<!--[\s\S]*?-->", "", text.replace("\r\n", "\n")).strip()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def section_units(work, register_id, profile):
    body = re.sub(r"<!--[\s\S]*?-->", "", _section(work, register_id, profile))
    parts = re.split(r"(?m)^###[ \t]+([^\n]*?)[ \t]*$", body)
    units = []
    if parts[0].strip() or len(parts) == 1:
        units.append((len(units) + 1, "", parts[0].strip()))
    for label, text in zip(parts[1::2], parts[2::2]):
        units.append((len(units) + 1, label.strip(), text.strip()))
    return units


_CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
# Inline reference markers: [12], [17a], [1.2], [^note], [B 443], [B xii], [AA V 12], [§ 4], [Bekker 1094a line 3], [1807 xii].
_MARKERS = re.compile(r"\[(?:\^[^\]\s]+|B [ivxlcdmIVXLCDM]+|\d{4} [0-9A-Za-z]+|(?:[A-Z§][A-Za-z]{0,6} (?:[IVX]+ )?)?\d+[a-z]?(?:\.\d+)*(?: line \d+[a-z]?)?)\]")
_LINE_NUMBER = re.compile(r"(?m)^\s*\[?\d+(?:\.\d+)*[a-e]?\]?[.)]?\s+")
_EMPHASIS = re.compile(r"(?<!\w)(\*\*|\*|_)(?=\S)(.+?)(?<=\S)\1(?!\w)")


def word_count(text):
    """Count CJK ideographs and other letter- or digit-bearing tokens."""
    count = len(_CJK.findall(text))
    remainder = _CJK.sub(" ", text)
    return (count * 10 + 16) // 17 + sum(any(c.isalnum() for c in token) for token in remainder.split())


# A stored quotation is clean text: an explicit list or reference number at its start is markup, a bare number is not.
_QUOTE_NUMBER = re.compile(r"^\s*(?:\[\d+(?:\.\d+)*[a-e]?\]|\d+(?:\.\d+)*[.)])\s+")


def _fold(text):
    return " ".join(text.translate(str.maketrans({'“':'"','”':'"','‘':"'",'’':"'",'—':'-','–':'-'})).split())


def _contains_run(haystack, needle):
    """A contiguous run of whole words: a Latin-script edge must not split a word; CJK has no word spaces."""
    def edge(c): return c.isalnum() and not _CJK.match(c)
    left = r"(?<![^\W\u3400-\u9fff\uf900-\ufaff])" if edge(needle[0]) else ""
    right = r"(?![^\W\u3400-\u9fff\uf900-\ufaff])" if edge(needle[-1]) else ""
    return re.search(left + re.escape(needle) + right, haystack) is not None


def _normalise_passage(text):
    text = text.translate(str.maketrans({'“':'"','”':'"','‘':"'",'’':"'",'—':'-','–':'-'}))
    text = _LINE_NUMBER.sub("", text)
    text = _MARKERS.sub("", text)
    text = re.sub(r"[\u1d2c-\u1d6a\u2070-\u209f\u00b9\u00b2\u00b3]", "", text)  # superscript note calls
    text = _EMPHASIS.sub(r"\2", text)
    return " ".join(text.split())


def passage_key(text):
    """The comparison form of a passage or unit: numbering, reference markers and emphasis marks set aside."""
    return _normalise_passage(text)


def clean_quote(text):
    """A quotation as stored: reader text without emphasis marks, reference markers or line numbers."""
    text = "\n".join(_QUOTE_NUMBER.sub("", line) for line in str(text).split("\n"))
    text = _MARKERS.sub("", text)
    text = re.sub(r"[\u1d2c-\u1d6a\u2070-\u209f\u00b9\u00b2\u00b3]", "", text)
    previous = None
    while previous != text:
        previous, text = text, _EMPHASIS.sub(r"\2", text)
    return re.sub(r"\s+([,.;:!?])", r"\1", " ".join(text.split()))


def quote_markup(text):
    """True when a stored quotation still carries emphasis marks, a reference marker or a leading number."""
    return bool(_EMPHASIS.search(text) or _MARKERS.search(text) or _QUOTE_NUMBER.search(text))


def passage_in(quote, unit_text):
    """True when the quotation is a contiguous run of the unit's words, as written or with markup set aside."""
    for norm in (_fold, _normalise_passage):
        q = norm(quote)
        if q and _contains_run(norm(unit_text), q): return True
    return False


_CLOSERS = "\"'”’»」』）)]}〉》】"


def ending_problem(text, sentence=False):
    """Why a reader-facing text ends badly ("" when it does not).

    Cut off: it ends with an ellipsis, a comma, semicolon, colon or dash. With
    ``sentence`` it must also end with sentence punctuation. A quotation that
    itself ends in an ellipsis, inside closing quotes, is not cut off.
    """
    if not isinstance(text, str) or not text.strip(): return ""
    text = text.rstrip()
    if re.search(r"(?:…|\.{3,})[" + re.escape(_CLOSERS) + r"]\s*$", text): return ""
    end = text.rstrip(_CLOSERS + " \t\r\n")
    if re.search(r"(?:…|\.{3,}|[,;:，；：、—–])$", end): return "ends cut off"
    if sentence and not re.search(r"[.!?。！？]$", end): return "does not end a sentence"
    return ""


def blurb_limit(text):
    """Character limit of a search blurb: 80 when the text is mostly CJK, else 160."""
    return 80 if len(_CJK.findall(text)) * 2 > sum(c.isalnum() for c in text) else 160


def _str(): return {"type": "string", "minLength": 1}
def _arr(item, minimum=0, maximum=None):
    result = {"type": "array", "items": item, "minItems": minimum}
    if maximum is not None: result["maxItems"] = maximum
    return result

def _obj(props, required=None):
    return {"type": "object", "properties": props, "required": list(props) if required is None else required, "additionalProperties": False}


def summary_prompt_spec():
    """Return the draft-2020-12 schema for operator-supplied content."""
    s, number = _str(), {"type": "integer", "minimum": 1}
    numbers, strings = _arr(number), _arr(s)
    idea = _obj({"id": s, "title": s, "explanation": s, "units": numbers})
    unit = _obj({"n": number, "label": {"type": "string"}, "summary": s, "ideas": strings})
    figure = _obj({"name": s, "role": s, "units": numbers})
    term = _obj({"term": s, "source_term": {"type": "string"}, "meaning": s, "units": numbers})
    passage = _obj({"unit": number, "text": s, "why": s})
    facts = _obj({k: {"type": "string"} for k in ("form", "genre", "composed", "setting", "narrator", "structure")}, [])
    summary = _obj({"gist": s, "overview": s, "context": s, "key_facts": facts,
                    "key_ideas": _arr(idea, 3, 12), "units": _arr(unit, 1), "figures": _arr(figure, 0, 40),
                    "terms": _arr(term, 0, 30), "passages": _arr(passage, 0, 10), "blurb": s},
                   ["gist", "overview", "context", "key_facts", "key_ideas", "units", "figures", "terms", "passages"])
    related = _obj({"work": s, "relation": {"type": "string", "enum": ["same-author", "responds-to", "answered-by", "influenced-by", "influences", "shares-theme", "same-tradition", "same-form"]}, "note": s})
    index = _obj({"genres": strings, "forms": strings, "themes": _arr(s, 3, 15), "concepts": _arr(s, 0, 20),
                  "people": strings, "places": strings, "period": s, "keywords": _arr(s, 0, 25), "related": _arr(related)})
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **_obj({"summary": summary, "index": index})}


def validate(summary_obj, work, profile, corpus_ids=set(), *, lang=None):
    """Return all observable summary findings; never certify interpretation."""
    findings = []
    wid = work.front.get("slug") or Path(work.path).stem
    def add(code, path, message, severity="error"):
        findings.append(Finding(code, code, severity, f"{path}: {message}", work=wid))
    prompt = summary_prompt_spec()
    props = dict(prompt["properties"])
    s = _str()
    props.update(schema={"type": "string", "const": "champollion-summary/1"}, work=s, title=s, author=s,
                 basis=_obj({"register": s, "sha256": s, "units": {"type": "integer", "minimum": 1}, "unit_sha256": _arr(s)}, ["register", "sha256", "units"]),
                 lang={"type": "string"}, model={"type": "string"}, edition_source_sha256={"type": "string"},
                 aid=s, generated=s, review=_obj({"status": s, "by": s, "date": s, "notes": s}, ["status"]))
    def check(value, schema, path):
        typ = schema.get("type")
        valid = (typ == "object" and isinstance(value, dict) or typ == "array" and isinstance(value, list) or
                 typ == "string" and isinstance(value, str) or typ == "integer" and type(value) is int)
        if not valid:
            add("SUM-SCHEMA", path, f"expected {typ}"); return
        if typ == "object":
            for key in schema.get("required", []):
                if key not in value: add("SUM-SCHEMA", f"{path}.{key}".lstrip("."), "missing field")
            for key, item in value.items():
                p = f"{path}.{key}".lstrip(".")
                if key not in schema["properties"]: add("SUM-SCHEMA", p, "unknown field")
                else: check(item, schema["properties"][key], p)
        elif typ == "array":
            if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
                add("SUM-SCHEMA", path, "invalid array length")
            for i, item in enumerate(value): check(item, schema["items"], f"{path}[{i}]")
        elif typ == "string":
            if schema.get("minLength") and not value.strip(): add("SUM-SCHEMA", path, "must not be empty")
            if "const" in schema and value != schema["const"] or "enum" in schema and value not in schema["enum"]:
                add("SUM-SCHEMA", path, "invalid value")
        elif value < schema.get("minimum", value): add("SUM-SCHEMA", path, "out of range")
    check(summary_obj, _obj(props, [k for k in props if k not in ("lang", "model", "edition_source_sha256")]), "")
    if not isinstance(summary_obj, dict): return findings
    obj = summary_obj
    for key, expected in (("work", wid), ("title", work.front.get("title", "")), ("author", work.front.get("author", ""))):
        if key in obj and obj[key] != expected: add("SUM-WORK", key, "does not match work")
    if lang is not None and obj.get("lang") != lang: add("SUM-WORK", "lang", "does not match edition")
    if "edition_source_sha256" in obj and work.front.get("source_sha256") and obj["edition_source_sha256"] != work.front["source_sha256"]: add("SUM-STALE", "edition_source_sha256", "does not match edition")
    review = obj.get("review")
    if isinstance(review, dict):
        if review.get("status") not in ("reviewed", "unreviewed"): add("SUM-SCHEMA", "review.status", "invalid status")
        if review.get("status") != "reviewed": add("SUM-REVIEW", "review.status", "not reviewed", "warn")
        else:
            for k in ("by", "date", "notes"):
                if not isinstance(review.get(k), str) or not review[k].strip(): add("SUM-SCHEMA", "review." + k, "required for reviewed summary")
    for path, value in (("generated", obj.get("generated")), ("review.date", review.get("date") if isinstance(review, dict) else None)):
        if value is not None:
            try:
                if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value: raise ValueError()
            except ValueError: add("SUM-SCHEMA", path, "expected YYYY-MM-DD")
    basis = obj.get("basis") if isinstance(obj.get("basis"), dict) else {}
    try:
        body = _section(work, basis.get("register", ""), profile)
        units = section_units(work, basis.get("register", ""), profile)
    except ChampollionError:
        add("SUM-SCHEMA", "basis.register", "unknown or unavailable register"); units = []; body = None
    if body is not None:
        if basis.get("sha256") != basis_hash(body): add("SUM-STALE", "basis.sha256", "does not match edition")
        if basis.get("units") != len(units): add("SUM-STALE", "basis.units", "does not match edition")
        hashes = basis.get("unit_sha256")
        if isinstance(hashes, list):
            if len(hashes) != len(units): add("SUM-STALE", "basis.unit_sha256", "unit count differs")
            else:
                changed = [str(n) for (n, _, text), digest in zip(units, hashes) if digest != basis_hash(text)]
                if changed:
                    suffix = f" +{len(changed)-12} more" if len(changed) > 12 else ""
                    add("SUM-STALE", "basis.unit_sha256", "units " + ", ".join(changed[:12]) + suffix + " changed")
    summary = obj.get("summary") if isinstance(obj.get("summary"), dict) else {}
    def length(value, limit, path):
        if isinstance(value, str) and word_count(value) > limit: add("SUM-LENGTH", path, f"exceeds {limit} words")
    for k, limit in (("gist",45),("overview",300),("context",180)): length(summary.get(k), limit, "summary."+k)
    blurb = summary.get("blurb")
    if isinstance(blurb, str):
        limit = blurb_limit(blurb)
        if len(blurb) > limit: add("SUM-LENGTH", "summary.blurb", f"exceeds {limit} characters")
    def truncated(value, path, sentence=False):
        problem = ending_problem(value, sentence)
        if problem: add("SUM-TRUNCATED", path, problem)
    for k in ("gist", "overview", "context", "blurb"):
        truncated(summary.get(k), "summary." + k, True)
    facts = summary.get("key_facts")
    if isinstance(facts, dict):
        for k,v in facts.items():
            length(v,30,"summary.key_facts."+k)
            truncated(v,"summary.key_facts."+k)
    def entries(key):
        a = summary.get(key); return a if isinstance(a, list) else []
    ideas = entries("key_ideas"); unit_items = entries("units")
    ids = {x.get("id") for x in ideas if isinstance(x, dict) and isinstance(x.get("id"), str)}
    if len(ids) != len([x for x in ideas if isinstance(x, dict) and isinstance(x.get("id"), str)]): add("SUM-XREF", "summary.key_ideas", "duplicate idea id")
    for i, idea in enumerate(ideas):
        if not isinstance(idea, dict): continue
        for key,limit in (("title",10),("explanation",110)): length(idea.get(key),limit,f"summary.key_ideas[{i}].{key}")
        truncated(idea.get("title"), f"summary.key_ideas[{i}].title")
        truncated(idea.get("explanation"), f"summary.key_ideas[{i}].explanation", True)
        if idea.get("units") == []: add("SUM-XREF", f"summary.key_ideas[{i}].units", "empty units", "warn")
        if isinstance(idea.get("id"), str) and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", idea["id"]): add("SUM-SCHEMA",f"summary.key_ideas[{i}].id","expected kebab slug")
    if body is not None and len(unit_items) != len(units): add("SUM-UNITS", "summary.units", "unit count differs")
    for i, u in enumerate(unit_items):
        if not isinstance(u, dict): continue
        if body is not None and (i >= len(units) or u.get("n") != units[i][0]): add("SUM-UNITS",f"summary.units[{i}].n","unit order differs")
        if body is not None and i < len(units) and u.get("label") != units[i][1]: add("SUM-UNITS",f"summary.units[{i}].label","heading differs")
        length(u.get("summary"),160,f"summary.units[{i}].summary")
        truncated(u.get("summary"), f"summary.units[{i}].summary", True)
        for ident in u.get("ideas", []) if isinstance(u.get("ideas"), list) else []:
            if not isinstance(ident, str) or ident not in ids: add("SUM-XREF",f"summary.units[{i}].ideas","unknown idea")
    for kind, field, limit in (("figures","role",50),("terms","meaning",60),("passages","text",80),("passages","why",60)):
        for i, item in enumerate(entries(kind)):
            if isinstance(item, dict):
                length(item.get(field),limit,f"summary.{kind}[{i}].{field}")
                if field != "text": truncated(item.get(field), f"summary.{kind}[{i}].{field}")
    for kind in ("key_ideas", "figures", "terms", "passages"):
        for i, item in enumerate(entries(kind)):
            if not isinstance(item, dict): continue
            nums = [item.get("unit")] if kind == "passages" else item.get("units", [])
            if not isinstance(nums, list): continue
            for n in nums:
                if type(n) is not int or n < 1 or (body is not None and n > len(units)):
                    add("SUM-XREF",f"summary.{kind}[{i}].{'unit' if kind == 'passages' else 'units'}","unit out of range")
                elif kind == "key_ideas" and n <= len(unit_items) and isinstance(unit_items[n-1], dict):
                    refs = unit_items[n-1].get("ideas", [])
                    if isinstance(refs, list) and item.get("id") not in refs: add("SUM-XREF",f"summary.key_ideas[{i}].units","unit does not refer back to idea")
            if kind == "passages" and body is not None and type(item.get("unit")) is int and 1 <= item["unit"] <= len(units) and isinstance(item.get("text"), str) and item["text"].strip():
                quote, unit_text = item["text"], units[item["unit"]-1][2]
                if quote_markup(quote): add("SUM-PASSAGE", f"summary.passages[{i}].text", "contains markup")
                if not passage_in(quote, unit_text): add("SUM-PASSAGE",f"summary.passages[{i}].text","not found in unit")
    for i, u in enumerate(unit_items):
        if not isinstance(u, dict) or not isinstance(u.get("ideas"), list): continue
        for ident in u["ideas"]:
            for idea in ideas:
                if isinstance(idea, dict) and idea.get("id") == ident and isinstance(idea.get("units"), list) and i+1 not in idea["units"]: add("SUM-XREF",f"summary.units[{i}].ideas","idea does not refer back to unit")
    index = obj.get("index") if isinstance(obj.get("index"), dict) else {}
    for key in ("genres","forms","themes","concepts"):
        for i, value in enumerate(index.get(key, []) if isinstance(index.get(key), list) else []):
            if isinstance(value, str) and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value): add("SUM-SLUG",f"index.{key}[{i}]","expected kebab slug")
    for i, item in enumerate(index.get("related", []) if isinstance(index.get("related"), list) else []):
        if not isinstance(item, dict): continue
        length(item.get("note"),30,f"index.related[{i}].note")
        truncated(item.get("note"), f"index.related[{i}].note")
        if isinstance(item.get("work"), str) and (item["work"] == wid or item["work"] not in corpus_ids): add("SUM-RELATED",f"index.related[{i}].work","must name another corpus work")
    return findings
