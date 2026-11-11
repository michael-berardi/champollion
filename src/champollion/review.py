"""Offline source-language review: parallel passages, two readings, guarded application.

Champollion never calls a model here. `packets` writes one deterministic reviewer
packet per passage; an operator runs any reviewer and stores the replies;
`verify-packets` validates findings and writes an independent second-reader
packet per passage with locatable proposals; `apply` writes only findings the
second reader confirmed or amended, refusing unsafe replacements; `record`
writes a VER-11-shaped review record. The Original section is never edited.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .checks.numbering import extract_markers
from .findings import ChampollionError
from .format import parse_work
from .packets import numbering_policy, register_definition
from .report import VERSION as PROTOCOL_VERSION
from .sources import load_sources, local_path, read_json, write_bytes_atomic, write_json

REVIEW_VERSION = "champollion-review/1"
PIECE_CHARS = 5000
FINDING_TYPES = ("mistranslation", "omission", "addition", "name", "number",
                 "reference", "term", "garbled", "untranslated")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def piece_id(piece: dict) -> str:
    """Stable sortable passage identifier independent of locale and timestamps."""
    return f"{piece['unit']:04d}-{piece['piece']:03d}"


# ---------------------------------------------------------------- alignment

def _segments(text: str, start: int, end: int, by_line: bool = False) -> list:
    """Paragraph (or nonempty line) spans inside [start, end)."""
    body = text[start:end]
    pattern = r"[^\n]*\S[^\n]*" if by_line else r"(?:[^\n]*\S[^\n]*\n?)+"
    return [(start + m.start(), start + m.end()) for m in re.finditer(pattern, body)]


def _group(segments: list, limit: int) -> list:
    """Group consecutive source segments into runs of at most `limit` characters."""
    out, first, size = [], 0, 0
    for i, (s, e) in enumerate(segments):
        if i > first and size + (e - s) > limit:
            out.append((first, i))
            first, size = i, 0
        size += e - s
    if segments:
        out.append((first, len(segments)))
    return out


def align(text: str, spans: list, limit: int) -> list:
    """Cut one unit of the source (span 0) and of each register into parallel passages.

    Returns [{"spans": [(s, e) per text], "exact": [bool per register]}]. A register
    whose paragraphs (or lines) do not correspond one to one with the source's is cut
    proportionally at its own paragraph boundaries, widened by one paragraph each
    side, and marked inexact.
    """
    if limit < 1:
        raise ChampollionError("piece size must be a positive character count", cause="usage")
    s0, e0 = spans[0]
    if e0 - s0 <= limit:
        return [{"spans": list(spans), "exact": [True] * (len(spans) - 1)}]
    segments = None
    for by_line in (False, True):
        candidate = [_segments(text, s, e, by_line) for s, e in spans]
        if (candidate[0] and max(e - s for s, e in candidate[0]) <= limit * 2
                and any(len(c) == len(candidate[0]) for c in candidate[1:])):
            segments = candidate
            break
    if segments is None:
        segments = [_segments(text, s, e) for s, e in spans]
        if not segments[0] or max(e - s for s, e in segments[0]) > limit * 2:
            segments = [_segments(text, s, e, True) for s, e in spans]
    if not segments[0]:
        return []
    runs = _group(segments[0], limit)
    total = segments[0][-1][1] - segments[0][0][0]
    out = []
    for a, b in runs:
        piece = {"spans": [(segments[0][a][0], segments[0][b - 1][1])], "exact": []}
        fa = (segments[0][a][0] - segments[0][0][0]) / total
        fb = (segments[0][b - 1][1] - segments[0][0][0]) / total
        for k in range(1, len(spans)):
            sk = segments[k]
            if not sk:
                piece["spans"].append((spans[k][0], spans[k][0]))
                piece["exact"].append(False)
            elif len(sk) == len(segments[0]):
                piece["spans"].append((sk[a][0], sk[b - 1][1]))
                piece["exact"].append(True)
            else:
                lo, hi = sk[0][0], sk[-1][1]
                pa, pb = lo + fa * (hi - lo), lo + fb * (hi - lo)
                ia = max((i for i, (s, e) in enumerate(sk) if s <= pa), default=0)
                ib = min((i for i, (s, e) in enumerate(sk) if e >= pb), default=len(sk) - 1)
                ia, ib = max(0, ia - 1), min(len(sk) - 1, ib + 1)
                piece["spans"].append((sk[ia][0], sk[ib][1]))
                piece["exact"].append(a == 0 and b == len(segments[0]))
        out.append(piece)
    return out


# ---------------------------------------------------------------- work model

class ReviewWork:
    """A parsed work plus byte spans, so a confirmed fix can replace an exact quotation."""

    def __init__(self, path: Any, profile: Any, root: str) -> None:
        self.path = Path(path)
        self.profile = profile
        self.root = str(root)
        self.work = parse_work(self.path)
        try:
            self.raw = self.path.read_bytes()
            self.text = self.raw.decode("utf-8").replace("\r\n", "\n")
        except (OSError, UnicodeError) as exc:
            raise ChampollionError(f"{self.path}: {exc}", cause="IO") from exc
        offsets = [0] + [m.end() for m in re.finditer("\n", self.text)]

        def line_start(number: int) -> int:
            return offsets[number - 1] if number - 1 < len(offsets) else len(self.text)

        def body_span(unit: Any) -> tuple:
            start = line_start(unit.line + 1)
            end = line_start(unit.lines[-1][0] + 1) if unit.lines else start
            return start, end

        original = self.work.original()
        if not original.units:
            raise ChampollionError("Original requires nonempty headed units", cause="WRK-1")
        self.original_span = (line_start(original.line),
                                line_start(original.units[-1].lines[-1][0] + 1) if original.units[-1].lines
                                else line_start(original.units[-1].line + 1))
        self.registers = []
        for register in profile.registers:
            section = self.work.register_section(profile, register.id)
            if section is None:
                if register.required and register.alignment == "same-units":
                    raise ChampollionError(f"{self.path}: register {register.id}: section missing for review", cause="REG-1")
                continue
            if register.alignment == "none":
                continue
            if register.alignment == "same-units" and [u.title for u in section.units] != [u.title for u in original.units]:
                raise ChampollionError(f"{self.path}: register {register.id}: unit titles differ from Original", cause="SEG-PARITY")
            self.registers.append((register, section))
        if not self.registers:
            raise ChampollionError(f"{self.path}: no aligned register section to review", cause="configuration")
        self.units = []
        for index, unit in enumerate(original.units):
            spans = [body_span(unit)]
            for register, section in self.registers:
                if index < len(section.units):
                    spans.append(body_span(section.units[index]))
                else:
                    at = line_start(section.line + 1)
                    spans.append((at, at))
            self.units.append({"unit": index + 1, "title": unit.title, "empty": not unit.text.strip(), "spans": spans})

    @property
    def register_ids(self) -> list:
        return [register.id for register, _ in self.registers]

    def pieces(self, piece_chars: int = PIECE_CHARS) -> list:
        """Every nonempty source unit cut into parallel passages, in document order."""
        out = []
        for unit in self.units:
            if unit["empty"]:
                continue
            for index, piece in enumerate(align(self.text, unit["spans"], piece_chars), 1):
                out.append({**piece, "unit": unit["unit"], "piece": index, "title": unit["title"]})
        return out

    def passage(self, piece: dict, k: int) -> str:
        s, e = piece["spans"][k]
        return self.text[s:e]

    def key(self, piece: dict) -> str:
        joined = "\x00".join(self.passage(piece, k) for k in range(len(piece["spans"])))
        return _sha(joined + "\x00" + REVIEW_VERSION)

    def edition_index(self, edition: str) -> int:
        return 0 if edition == "original" else 1 + self.register_ids.index(edition)


# ---------------------------------------------------------------- reply parsing

def parse_reply(raw: str) -> Any:
    """Read a reply JSON, tolerant of a <<<BEGIN>>>/<<<END>>> wrapper and code fences."""
    match = re.search(r"<<<BEGIN>>>\s*(.*?)\s*(?:<<<END>>>|\Z)", raw, re.S)
    body = (match.group(1) if match else raw).strip()
    body = re.sub(r"^```(?:json)?\s*|\s*```$", "", body).strip()
    try:
        return json.loads(body)
    except (ValueError, RecursionError):
        return None


def _read_reply(path: Path) -> Any:
    try:
        return parse_reply(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise ChampollionError(f"{path}: {exc}", cause="IO") from exc


def _read_index(directory: str, explicit: Optional[str], stage: str, work: ReviewWork) -> dict:
    path = Path(explicit) if explicit else Path(directory) / "index.json"
    obj = read_json(path)
    if (not isinstance(obj, dict) or obj.get("review") != REVIEW_VERSION or obj.get("stage") != stage
            or not isinstance(obj.get("pieces"), list) or not isinstance(obj.get("piece_chars"), int)
            or obj.get("piece_chars") < 1):
        raise ChampollionError(f"{path}: not a {stage} index for {REVIEW_VERSION}", cause="schema")
    if obj.get("work") != work.work.slug or obj.get("registers") != work.register_ids:
        raise ChampollionError(f"{path}: index does not match work {work.work.slug!r} and its registers", cause="schema")
    return obj


def _pieces_by_id(work: ReviewWork, index: dict) -> dict:
    return {piece_id(p): p for p in work.pieces(index["piece_chars"])}


# ---------------------------------------------------------------- packets

def _review_packet(work: ReviewWork, piece: dict, definitions: dict) -> str:
    front = work.work.front
    ids = work.register_ids
    inexact = [ids[i] for i, exact in enumerate(piece["exact"]) if not exact]
    editions = ", ".join(repr(i) for i in ids)
    parts = [
        f"# Source-language review packet: {work.work.slug} / {piece['title']} (piece {piece_id(piece)})",
        f"Work: {front.get('title', '')} — {front.get('author', '')}. Source language: {front.get('language', 'unspecified')}. "
        f"Target language: {work.profile.target['name'] if work.profile.target else 'unspecified'}.",
        "You are the source-language reviewer. Read the source passage below sentence by sentence against each register "
        "edition and report every real error. Each edition is an independent, complete translation of SOURCE in its own "
        "register; neither is a summary.",
        "Registers:\n" + "\n".join(f"- `{i}` ({work.registers[k][0].label}): {definitions[i]}" for k, i in enumerate(ids)),
        "Report an error only when you are confident, having checked the source wording, that the edition says something "
        "the source does not say, or fails to say something the source says:\n"
        "- mistranslation: wrong sense, wrong subject/object, wrong tense or negation that changes meaning, false friend, misread idiom, wrong technical term\n"
        "- omission: a clause, sentence, list item or qualifier of the source that is missing\n"
        "- addition: content, explanation or gloss that is not in the source\n"
        "- name / number / reference: a wrong or inconsistent proper name, a wrong number, date, quantity or unit, a wrong, missing or misplaced reference marker\n"
        "- term: a wrong or inconsistent technical term\n"
        "- garbled: broken, duplicated, truncated or nonsensical text, stray markup or leftover scan debris\n"
        "- untranslated: source-language words left untranslated where a translation is required\n"
        "Do NOT report: style or word-choice preferences; a defensible reading of a genuinely ambiguous or contested passage; "
        "freer syntax that keeps the sense; a plain register explaining an idiom in ordinary words; differences between "
        "registers that are both faithful; spelling or punctuation conventions. Where the registers disagree about what the "
        "source means, work out from the source which is right. If you are not sure, leave it out. An empty list is a good "
        "answer for a sound passage.",
        "Also report defects in how SOURCE itself is presented (edition \"original\"): an obvious transcription or scan error "
        "(a misspelled word that is not period orthography, a broken or duplicated line, a lost or doubled word, leftover page "
        "furniture, mangled markup, wrong characters). Never \"correct\" authentic period spelling, dialect, or an author's own "
        "usage. Findings on the source are recorded for the editor and never applied automatically.",
        "For each error give an object with:\n"
        f"  \"edition\": one of {editions} or \"original\"\n"
        f"  \"type\": one of {', '.join(FINDING_TYPES)}\n"
        "  \"severity\": \"major\" (changes what a reader understands) or \"minor\"\n"
        "  \"source\": the exact source words concerned (short quotation)\n"
        "  \"quote\": an EXACT, contiguous quotation copied character for character from the named edition (or from SOURCE for "
        "\"original\"), long enough to occur only once in the passage and no longer than needed; it is the text to be replaced\n"
        "  \"fix\": the corrected text that replaces \"quote\" exactly: same register and style as the surrounding edition, same "
        "reference markers, Markdown and line breaks, nothing else changed\n"
        "  \"reason\": one sentence saying what the source says and why the quotation is wrong",
    ]
    if inexact:
        parts.append("Alignment note: register " + " and ".join(f"`{i}`" for i in inexact) +
                     " could not be cut at exactly the same points as the source, so its excerpt may begin a little before or "
                     "end a little after the source passage. Ignore the unmatched text at its two ends; never report an omission "
                     "or addition there.")
    parts.append('Return ONLY JSON between a line <<<BEGIN>>> and a line <<<END>>>: {"findings": [ ... ]} '
                 '(use {"findings": []} when there is nothing to report).')
    parts.append("SOURCE:\n<<<SOURCE>>>\n" + work.passage(piece, 0) + "\n<<<END SOURCE>>>")
    for k, i in enumerate(ids, 1):
        parts.append(f"EDITION `{i}`:\n<<<{i}>>>\n" + work.passage(piece, k) + f"\n<<<END {i}>>>")
    return "\n\n".join(parts) + "\n"


def _write_guarded(path: Path, payload: bytes, work: ReviewWork) -> None:
    if path.resolve() == work.path.resolve():
        raise ChampollionError(f"{path}: review output cannot replace a work", cause="WRK-1")
    if path.is_symlink():
        raise ChampollionError(f"{path}: refusing to replace a symlink", cause="WRK-1")
    if path.exists():
        if path.read_bytes() != payload:
            raise ChampollionError(f"{path}: existing review file differs; choose a fresh output directory", cause="WRK-1")
        return
    write_bytes_atomic(path, payload)


def write_review_packets(work: ReviewWork, out: str, piece_chars: int = PIECE_CHARS) -> dict:
    """Write one deterministic reviewer packet per passage plus a binding index."""
    definitions = {register.id: register_definition(work.profile, register, work.root)
                   for register, _ in work.registers}
    pieces = work.pieces(piece_chars)
    destination = Path(out).resolve()
    entries = []
    try:
        destination.mkdir(parents=True, exist_ok=True)
        for piece in pieces:
            filename = piece_id(piece) + ".review.md"
            _write_guarded(destination / filename, _review_packet(work, piece, definitions).encode("utf-8"), work)
            entries.append({"id": piece_id(piece), "unit": piece["unit"], "piece": piece["piece"],
                            "title": piece["title"], "file": filename, "key": work.key(piece),
                            "exact": dict(zip(work.register_ids, piece["exact"])),
                            "sha256": {"original": _sha(work.passage(piece, 0)),
                                       **{i: _sha(work.passage(piece, k)) for k, i in enumerate(work.register_ids, 1)}}})
        not_reviewed = [{"unit": u["unit"], "title": u["title"], "reason": "empty source unit"}
                        for u in work.units if u["empty"]]
        index = {"review": REVIEW_VERSION, "stage": "packets", "work": work.work.slug,
                 "piece_chars": piece_chars, "registers": work.register_ids,
                 "pieces": entries, "not_reviewed": not_reviewed}
        _write_guarded(destination / "index.json",
                       (json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"), work)
    except (OSError, UnicodeError) as exc:
        raise ChampollionError(f"{destination}: {exc}", cause="IO") from exc
    return {"work": work.work.slug, "out": str(destination), "piece_chars": piece_chars,
            "registers": work.register_ids, "pieces": entries, "not_reviewed": not_reviewed}


# ---------------------------------------------------------------- second reading

def _context(text: str, quote: str, pad: int = 700) -> str:
    i = text.find(quote)
    if i < 0:
        return text[: pad * 2]
    return text[max(0, i - pad): i + len(quote) + pad]


def _verify_packet(work: ReviewWork, piece: dict, proposals: list) -> str:
    front = work.work.front
    parts = [
        f"# Second-reader review packet: {work.work.slug} / {piece['title']} (piece {piece_id(piece)})",
        "You are the second, independent reader. A first reviewer proposed the corrections below to a translation of a "
        f"{front.get('language', 'unspecified')} source ({front.get('title', '')} — {front.get('author', '')}). "
        "Your job is to protect the edition from wrong or needless changes.",
        "For each proposal, read the source passage yourself and decide:\n"
        '- "confirm": the current text is really wrong against the source (wrong sense, missing or added content, wrong name, '
        "number or reference, garbled text), and the proposed fix is faithful to the source, complete, natural in the same "
        "register as the surrounding text, and changes nothing else;\n"
        '- "amend": the current text is really wrong, but the proposed fix is itself inaccurate, incomplete, unnatural or '
        'changes too much: give a better "fix" that replaces the same quotation;\n'
        '- "reject": the current text is a defensible translation, the proposal is a style preference, the reviewer misread '
        "the source, or you are not sure.\n"
        "Be strict: when in doubt, reject. A fix must keep every reference marker, Markdown mark and line break of the "
        "quotation it replaces.",
        'Return ONLY JSON between a line <<<BEGIN>>> and a line <<<END>>>: '
        '{"verdicts": [{"n": 1, "verdict": "confirm" | "amend" | "reject", "fix": "<only for amend>", "why": "<one short sentence>"}, ...]} '
        "with one entry per proposal.",
        "SOURCE PASSAGE:\n<<<SOURCE>>>\n" + work.passage(piece, 0) + "\n<<<END SOURCE>>>",
    ]
    for f in proposals:
        k = work.edition_index(f["edition"])
        label = work.registers[k - 1][0].label
        parts.append(
            f"PROPOSAL {f['n']} (register: {label} `{f['edition']}`; type: {f['type']})\n"
            f"Translation in context:\n<<<CONTEXT>>>\n{_context(work.passage(piece, k), f['quote'])}\n<<<END CONTEXT>>>\n"
            f"Text to replace:\n<<<QUOTE>>>\n{f['quote']}\n<<<END QUOTE>>>\n"
            f"Proposed replacement:\n<<<FIX>>>\n{f['fix']}\n<<<END FIX>>>\n"
            f"Reviewer's source quotation: {f.get('source', '')}\nReviewer's reason: {f.get('reason', '')}")
    return "\n\n".join(parts) + "\n"


def _clean_findings(work: ReviewWork, piece: dict, data: Any) -> Optional[list]:
    """Normalize one reviewer reply; None when the reply shape itself is invalid."""
    if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
        return None
    out = []
    for f in data["findings"]:
        base = {"id": piece_id(piece), "unit": piece["unit"], "piece": piece["piece"], "title": piece["title"]}
        if not isinstance(f, dict) or (f.get("edition") != "original" and f.get("edition") not in work.register_ids):
            out.append({**base, "status": "invalid", "reason": "unknown edition", "raw": str(f)[:200]})
            continue
        quote, fix = f.get("quote"), f.get("fix")
        if not isinstance(quote, str) or not isinstance(fix, str) or not quote.strip() or quote == fix:
            out.append({**base, "status": "invalid", "reason": "quote and fix must be different nonempty strings", "raw": str(f)[:200]})
            continue
        if f.get("type") not in FINDING_TYPES or f.get("severity") not in ("major", "minor"):
            out.append({**base, "status": "invalid", "reason": "unknown type or severity", "raw": str(f)[:200]})
            continue
        entry = {**base, **{key: str(f.get(key, "")) for key in ("edition", "type", "severity", "source", "reason")},
                 "quote": quote, "fix": fix}
        if entry["edition"] == "original":
            entry["status"] = "source"
        elif work.passage(piece, work.edition_index(entry["edition"])).count(quote) == 1:
            entry["status"] = "proposed"
        else:
            entry["status"] = "not-located"
            entry["reason_detail"] = "quotation not found or not unique in the passage"
        out.append(entry)
    return out


def verify_packets(work: ReviewWork, replies: str, out: str, index: Optional[str] = None) -> dict:
    """Validate reviewer replies and write one second-reader packet per passage with proposals."""
    binding = _read_index(replies, index, "packets", work)
    replies_dir = Path(replies)
    by_id = _pieces_by_id(work, binding)
    destination = Path(out).resolve()
    entries, invalid, packets_written, proposals_total = [], [], 0, 0
    not_reviewed = list(binding.get("not_reviewed", []))
    try:
        destination.mkdir(parents=True, exist_ok=True)
        for entry in binding["pieces"]:
            piece = by_id.get(entry["id"])
            base = {key: entry[key] for key in ("id", "unit", "piece", "title", "key")}
            if piece is None or work.key(piece) != entry["key"]:
                not_reviewed.append({**base, "reason": "passage changed since review"})
                continue
            reply_path = replies_dir / (entry["id"] + ".review.json")
            if not reply_path.is_file():
                not_reviewed.append({**base, "reason": "no reviewer reply"})
                continue
            findings = _clean_findings(work, piece, _read_reply(reply_path))
            if findings is None:
                invalid.append({"file": str(reply_path), "reason": "unparseable reviewer reply"})
                not_reviewed.append({**base, "reason": "unparseable reviewer reply"})
                continue
            n = 0
            for f in findings:
                if f["status"] == "proposed":
                    n += 1
                    f["n"] = n
            proposals = [f for f in findings if f["status"] == "proposed"]
            filename = None
            if proposals:
                filename = entry["id"] + ".verify.md"
                _write_guarded(destination / filename, _verify_packet(work, piece, proposals).encode("utf-8"), work)
                packets_written += 1
                proposals_total += len(proposals)
            entries.append({**base, "file": filename, "findings": findings})
        index_obj = {"review": REVIEW_VERSION, "stage": "verify", "work": work.work.slug,
                     "piece_chars": binding["piece_chars"], "registers": work.register_ids,
                     "pieces": entries, "not_reviewed": not_reviewed}
        _write_guarded(destination / "index.json",
                       (json.dumps(index_obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"), work)
    except (OSError, UnicodeError) as exc:
        raise ChampollionError(f"{destination}: {exc}", cause="IO") from exc
    return {"work": work.work.slug, "out": str(destination), "packets": packets_written,
            "proposals": proposals_total,
            "source_findings": sum(1 for e in entries for f in e["findings"] if f["status"] == "source"),
            "not_located": sum(1 for e in entries for f in e["findings"] if f["status"] == "not-located"),
            "invalid_findings": [f for e in entries for f in e["findings"] if f["status"] == "invalid"],
            "invalid_replies": invalid, "not_reviewed": not_reviewed}


# ---------------------------------------------------------------- guarded application

def _refusal_reason(quote: str, fix: str, kind: str, notation: Any) -> Optional[str]:
    """Reasons a replacement is refused however confident the readers were."""
    if extract_markers(quote, notation) != extract_markers(fix, notation):
        return "reference markers differ"
    if quote.count("\n") != fix.count("\n"):
        return "line breaks differ"
    if re.findall(r"^#+ .*$", quote, re.M) != re.findall(r"^#+ .*$", fix, re.M):
        return "headings differ"
    if len(fix) > max(3 * len(quote), len(quote) + (1500 if kind == "omission" else 500)):
        return "replacement far longer than the quotation"
    if kind != "addition" and len(fix) < len(quote) * 0.3:
        return "replacement far shorter than the quotation"
    if "<<<" in fix or ">>>" in fix:
        return "packet delimiters in the replacement"
    return None


def _verdicts(data: Any, proposals: list) -> Optional[dict]:
    if not isinstance(data, dict) or not isinstance(data.get("verdicts"), list):
        return None
    got = {}
    for v in data["verdicts"]:
        if isinstance(v, dict) and isinstance(v.get("n"), int) and v.get("verdict") in ("confirm", "amend", "reject"):
            got[v["n"]] = v
    return got if set(got) == {f["n"] for f in proposals} else None


def _finding_meta(f: dict) -> dict:
    return {key: f[key] for key in ("id", "unit", "piece", "title", "edition", "type", "severity", "source", "quote", "fix", "reason")
            if key in f}


def apply_findings(work: ReviewWork, replies: str, index: Optional[str] = None, write: bool = True) -> dict:
    """Apply only second-reader-confirmed findings by exact single-match replacement."""
    binding = _read_index(replies, index, "verify", work)
    replies_dir = Path(replies)
    by_id = _pieces_by_id(work, binding)
    notation, _ = numbering_policy(work.work, work.root)
    dispositions, edits, invalid, reviewed = [], [], [], []
    not_reviewed = list(binding.get("not_reviewed", []))
    for entry in binding["pieces"]:
        piece = by_id.get(entry["id"])
        stale = piece is None or work.key(piece) != entry["key"]
        proposals = [f for f in entry["findings"] if f["status"] == "proposed"]
        for f in entry["findings"]:
            if f["status"] == "source":
                dispositions.append((_finding_meta(f), {"status": "source-finding", "reason": "left for the editor; the Original is never auto-applied"}))
            elif f["status"] == "not-located":
                dispositions.append((_finding_meta(f), {"status": "refused", "reason": f.get("reason_detail", "quotation not found or not unique in the passage")}))
            elif f["status"] == "invalid":
                dispositions.append((_finding_meta(f), {"status": "refused", "reason": f.get("reason", "invalid finding")}))
        if not proposals:
            if not stale:
                reviewed.append(entry)
            continue
        if stale:
            not_reviewed.append({**{key: entry[key] for key in ("id", "unit", "piece", "title")}, "reason": "passage changed since review"})
            for f in proposals:
                dispositions.append((_finding_meta(f), {"status": "refused", "reason": "passage changed since review"}))
            continue
        reviewed.append(entry)
        reply_path = replies_dir / (entry["id"] + ".verify.json")
        data = _read_reply(reply_path) if reply_path.is_file() else None
        got = _verdicts(data, proposals) if data is not None else None
        if got is None:
            reason = "no second-reader reply" if not reply_path.is_file() else "invalid second-reader reply"
            if reply_path.is_file():
                invalid.append({"file": str(reply_path), "reason": reason})
            for f in proposals:
                dispositions.append((_finding_meta(f), {"status": "refused", "reason": reason}))
            continue
        for f in proposals:
            v = got[f["n"]]
            fix = v.get("fix") if v["verdict"] == "amend" and isinstance(v.get("fix"), str) and v["fix"].strip() else f["fix"]
            verdict = "reject" if v["verdict"] == "amend" and fix == f["fix"] and not v.get("fix") else v["verdict"]
            meta = {**_finding_meta(f), "fix": fix}
            if verdict == "reject":
                dispositions.append((meta, {"status": "rejected", "reason": str(v.get("why", "")) or "rejected by second reader"}))
                continue
            k = work.edition_index(f["edition"])
            text = work.passage(piece, k)
            why = _refusal_reason(f["quote"], fix, f["type"], notation)
            if why is None and text.count(f["quote"]) != 1:
                why = "quotation not unique in the passage"
            if why:
                dispositions.append((meta, {"status": "refused", "reason": why}))
                continue
            s, e = piece["spans"][k]
            at = s + text.find(f["quote"])
            if at + len(f["quote"]) <= work.original_span[0] or at >= work.original_span[1]:
                edits.append((at, at + len(f["quote"]), fix, meta, verdict, str(v.get("why", ""))))
            else:
                dispositions.append((meta, {"status": "refused", "reason": "edit inside the Original section"}))
    edits.sort(key=lambda edit: edit[0])
    kept, last = [], -1
    for edit in edits:
        if edit[0] >= last:
            kept.append(edit)
            last = edit[1]
            dispositions.append(({**edit[3], "verdict": edit[4]}, {"status": "applied", "reason": edit[5] or "confirmed by second reader"}))
        else:
            dispositions.append((edit[3], {"status": "refused", "reason": "overlaps an earlier correction"}))
    output = None
    if kept:
        text = work.text
        for s, e, fix, *_ in reversed(kept):
            text = text[:s] + fix + text[e:]
        if write:
            if work.raw != work.text.encode("utf-8"):
                raise ChampollionError(f"{work.path}: CRLF work bytes would change outside the reviewed passages; normalize line endings first", cause="IO")
            write_bytes_atomic(work.path, text.encode("utf-8"))
            output = str(work.path)
    applied = [m for m, r in dispositions if r["status"] == "applied"]
    return {"work": work.work.slug, "dry_run": not write, "output": output,
            "applied": applied,
            "rejected": [m for m, r in dispositions if r["status"] == "rejected"],
            "refused": [{**m, "refusal": r["reason"]} for m, r in dispositions if r["status"] == "refused"],
            "source_findings": [m for m, r in dispositions if r["status"] == "source-finding"],
            "invalid_replies": invalid, "not_reviewed": not_reviewed,
            "reviewed_units": sorted({e["title"] for e in reviewed}),
            "registers": binding["registers"],
            "dispositions": [{"finding": m, "resolution": r} for m, r in dispositions]}


# ---------------------------------------------------------------- record

def review_record(work: ReviewWork, replies: str, reviewer: str, out: str,
                  index: Optional[str] = None, today: Optional[str] = None) -> dict:
    """Write a VER-11-shaped record of the review without changing the work."""
    if not reviewer.strip():
        raise ChampollionError("reviewer identity must be a nonempty string", cause="usage")
    result = apply_findings(work, replies, index, write=False)
    records = load_sources(work.root, [work.work])
    front = work.work.front
    reference = front.get("source", "")
    record = records.get(reference) or records.get(work.work.slug) or records.get(front.get("source_id", "")) or {}
    source_sha256 = None
    snapshot = record.get("raw_snapshot", record.get("path", ""))
    if snapshot:
        path = local_path(Path(work.root), snapshot)
        if path.exists():
            try:
                source_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError as exc:
                raise ChampollionError(f"{path}: {exc}", cause="IO") from exc
    findings = [d["finding"] for d in result["dispositions"]]
    resolutions = [d["resolution"] for d in result["dispositions"]]
    unresolved = [d["finding"] for d in result["dispositions"]
                  if d["resolution"]["status"] in ("refused", "source-finding")]
    obj = {"reviewer": reviewer,
           "date": today or datetime.now(timezone.utc).date().isoformat(),
           "protocol_version": PROTOCOL_VERSION,
           "review_version": REVIEW_VERSION,
           "work": work.work.slug,
           "work_sha256": hashlib.sha256(work.raw).hexdigest(),
           "profile_fingerprint": work.profile.fingerprint,
           "source_sha256": source_sha256,
           "units": result["reviewed_units"],
           "registers": result["registers"],
           "findings": findings,
           "resolutions": resolutions,
           "unresolved_findings": unresolved,
           "passages_not_reviewed": result["not_reviewed"]}
    write_json(Path(out).resolve(), obj)
    return {"work": work.work.slug, "out": str(Path(out).resolve()), "findings": len(findings),
            "applied": len(result["applied"]), "rejected": len(result["rejected"]),
            "refused": len(result["refused"]), "source_findings": len(result["source_findings"]),
            "unresolved": len(unresolved), "record": obj}