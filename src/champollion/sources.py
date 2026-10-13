"""Offline source records and byte-preserving snapshot ingestion."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import re
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .findings import ChampollionError


def _pairs(pairs: list) -> dict:
    obj: dict = {}
    for key, value in pairs:
        if key in obj:
            raise ChampollionError(f"duplicate JSON key {key!r}", cause="schema")
        obj[key] = value
    return obj


def _constant(value: str) -> None:
    raise ChampollionError(f"nonfinite JSON number {value}", cause="schema")


def read_json(path: Path) -> Any:
    """Read strict UTF-8 JSON, naming malformed input and IO failures."""
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant)
    except (OSError, UnicodeError) as exc:
        raise ChampollionError(f"{path}: {exc}", cause="IO") from exc
    except (ValueError, ChampollionError) as exc:
        raise ChampollionError(f"{path}: {exc}", cause="schema") from exc


def write_bytes_atomic(path: Path, data: bytes) -> None:
    """Replace a local regular file atomically, refusing symlink destinations."""
    temporary = None
    try:
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
            raise ChampollionError(f"{path}: refusing a symlink write path", cause="IO")
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.champollion-', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        raise ChampollionError(f"{path}: {exc}", cause="IO") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_json(path: Path, obj: Any) -> None:
    """Write deterministic JSON with an atomic replacement and terminal newline."""
    try:
        payload = (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode('utf-8')
        write_bytes_atomic(path, payload)
    except (UnicodeError, ValueError, TypeError) as exc:
        raise ChampollionError(f"{path}: {exc}", cause="IO") from exc


def local_path(root: Path, value: str) -> Path:
    """Resolve a project-relative evidence path without traversal or URLs."""
    if not isinstance(value, str) or not value or "://" in value:
        raise ChampollionError(f"invalid local path {value!r}", cause="configuration")
    candidate = (root / value).resolve()
    if Path(value).is_absolute() or root.resolve() not in candidate.parents:
        raise ChampollionError(f"path outside project root: {value}", cause="configuration")
    return candidate


def _records(obj: Any, path: Path) -> list:
    if not isinstance(obj, dict):
        raise ChampollionError(f"{path}: expected source record object", cause="schema")
    records = obj.get("records", [obj] if "id" in obj else None)
    if not isinstance(records, list):
        raise ChampollionError(f"{path}: records must be an array", cause="schema")
    seen: set = set()
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str) or not record["id"]:
            raise ChampollionError(f"{path}: record requires nonempty id", cause="schema")
        if record["id"] in seen:
            raise ChampollionError(f"{path}: duplicate source id {record['id']}", cause="schema")
        seen.add(record["id"])
    return records


def load_sources(root: str, works: Optional[Iterable[Any]] = None) -> Dict[str, dict]:
    """Load local referenced records; missing records remain checkable findings."""
    base = Path(root).resolve()
    documents = list(works or ())
    paths = {base / "sources" / "manifest.json"}
    for work in documents:
        reference = work.front.get("source", "")
        if reference:
            paths.add(local_path(base, reference.split("#", 1)[0]))
    result: Dict[str, dict] = {}
    for path in sorted(paths):
        if not path.exists():
            continue
        for record in _records(read_json(path), path):
            key = record["id"]
            if key in result and result[key] != record:
                raise ChampollionError(f"{path}: conflicting source id {key}", cause="schema")
            result[key] = record
    for work in documents:
        reference = work.front.get("source", "")
        selector = reference.split("#", 1)[1] if "#" in reference else work.front.get("source_id", "")
        if selector and selector in result:
            result[reference] = result[selector]
            if work.slug not in result:
                result[work.slug] = result[selector]
    return result


def add_source(root: str, profile: Any, *, id: str, file: Optional[str] = None,
               url: Optional[str] = None, provider: str, edition: str, revision: str,
               rights: str, note: str = "", replace: bool = False) -> dict:
    """Store unchanged bytes and their SHA-256, refusing unapproved rights."""
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", id):
        raise ChampollionError(f"source id {id!r}: expected a lowercase slug", cause="configuration")
    if (file is None) == (url is None):
        raise ChampollionError("source add requires exactly one of --file or --url", cause="usage")
    if url is not None:
        filename = f"{id}.source"
        command = (f"curl --fail --location --output {shlex.quote(filename)} {shlex.quote(url)} && "
                   f"champollion source add --id {shlex.quote(id)} --file {shlex.quote(filename)} "
                   f"--provider {shlex.quote(provider)} --edition {shlex.quote(edition)} "
                   f"--revision {shlex.quote(revision)} --rights {shlex.quote(rights)} "
                   f"--root {shlex.quote(str(root))}")
        if note:
            command += f" --note {shlex.quote(note)}"
        if replace:
            command += " --replace"
        raise ChampollionError("source acquisition is a separate operation; fetch, then re-run:\n" + command,
                               cause="source-acquisition")
    allowed = profile.rights["allowed"]
    if rights not in allowed:
        raise ChampollionError(f"rights id {rights!r} is not allowed by profile {profile.name}", cause="SRC-RIGHTS")
    for name, value in (("provider", provider), ("edition", edition), ("revision", revision)):
        if not value.strip():
            raise ChampollionError(f"source {id}: {name} must not be empty", cause="schema")
    try:
        data = Path(file).read_bytes()
    except OSError as exc:
        raise ChampollionError(f"{file}: {exc}", cause="IO") from exc
    if not data:
        raise ChampollionError(f"{file}: source snapshot is empty", cause="SRC-8")
    digest = hashlib.sha256(data).hexdigest()
    base = Path(root).resolve()
    manifest = base / "sources" / "manifest.json"
    obj = read_json(manifest) if manifest.exists() else {"records": []}
    records = _records(obj, manifest)
    previous = next((record for record in records if record["id"] == id), None)
    if previous and previous.get("sha256") != digest and not replace:
        raise ChampollionError(f"source {id}: different sha256; use --replace to replace the record", cause="source-conflict")
    # A replaced manifest reference must not erase its previous raw witness.
    destination = base / f'sources/raw/{id}/{id}.{digest}.source'
    if any(part.is_symlink() for part in (destination, *destination.parents)):
        raise ChampollionError(f'{destination}: refusing a symlink snapshot path', cause='IO')
    destination = local_path(base, destination.relative_to(base).as_posix())
    try:
        if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() != digest and not replace:
            raise ChampollionError(f"{destination}: existing snapshot differs; use --replace", cause="source-conflict")
        write_bytes_atomic(destination, data)
        stored_digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    except OSError as exc:
        raise ChampollionError(f"{destination}: {exc}", cause="IO") from exc
    if stored_digest != digest:
        raise ChampollionError(f"{destination}: stored bytes changed during ingestion", cause="SRC-HASH-MISMATCH")
    record = {"id": id, "provider": provider, "edition": edition, "revision": revision,
              "rights": rights, "sha256": stored_digest, "path": destination.relative_to(base).as_posix(),
              "raw_snapshot": destination.relative_to(base).as_posix(), "url": "", "note": note,
              "added": datetime.now(timezone.utc).date().isoformat()}
    obj["records"] = sorted([r for r in records if r["id"] != id] + [record], key=lambda r: r["id"])
    write_json(manifest, obj)
    return record
