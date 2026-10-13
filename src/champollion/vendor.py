"""Vendoring with complete, locally verifiable byte-integrity manifests."""
from __future__ import annotations

import hashlib
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from .findings import ChampollionError
from .sources import read_json, write_json

VERSION = "1.0.0"


def profile_directory() -> Path:
    """Locate profiles in an installed source tree or path-executable vendor."""
    package = Path(__file__).resolve().parent
    candidates = (package / "profiles", package.parent.parent / "profiles")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise ChampollionError("shipped profiles directory missing", cause="configuration")


def _files(directory: Path) -> list:
    return sorted((p for p in directory.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                   and p.suffix not in (".pyc", ".pyo") and p.name != "VENDOR.json"),
                  key=lambda p: p.relative_to(directory).as_posix())


def vendor(into: str, tag: Optional[str] = None, today: Optional[str] = None) -> dict:
    """Copy the implementation and profiles, hashing every copied file."""
    source = Path(__file__).resolve().parent
    profiles = profile_directory()
    destination = Path(into).resolve() / "champollion"
    if destination == source or source in destination.parents or destination in source.parents:
        raise ChampollionError(f"{destination}: vendor destination overlaps source", cause="configuration")
    if destination.exists():
        raise ChampollionError(f"{destination}: vendor destination already exists", cause="IO")
    generated = today or datetime.now(timezone.utc).date().isoformat()
    try:
        destination.mkdir(parents=True)
        copies = [(path, destination / path.relative_to(source)) for path in _files(source)]
        if source not in profiles.parents:
            copies.extend((path, destination / "profiles" / path.relative_to(profiles)) for path in _files(profiles))
        copied: set = set()
        for original, target in copies:
            if original.is_symlink():
                raise ChampollionError(f"{original}: source symlink cannot be vendored", cause="IO")
            if target in copied:
                raise ChampollionError(f"{target}: duplicate vendor destination", cause="configuration")
            copied.add(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
        files = {path.relative_to(destination).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in sorted(copied)}
    except OSError as exc:
        raise ChampollionError(f"{destination}: {exc}", cause="IO") from exc
    manifest = {"upstream": tag or VERSION, "version": VERSION, "generated": generated, "files": files}
    write_json(destination / "VENDOR.json", manifest)
    return {"directory": str(destination), "manifest": manifest}


def verify_vendor(directory: str = ".") -> dict:
    """Detect missing, modified and untracked files without changing the vendor."""
    destination = Path(directory).resolve()
    if not (destination / "VENDOR.json").exists() and (destination / "champollion" / "VENDOR.json").exists():
        destination /= "champollion"
    manifest = read_json(destination / "VENDOR.json")
    if not isinstance(manifest, dict) or set(manifest) != {"upstream", "version", "generated", "files"}:
        raise ChampollionError(f"{destination}/VENDOR.json: invalid manifest fields", cause="schema")
    for field in ("upstream", "version", "generated"):
        if not isinstance(manifest[field], str) or not manifest[field].strip():
            raise ChampollionError(f"{destination}/VENDOR.json: {field} must be a nonempty string", cause="schema")
    try:
        if date.fromisoformat(manifest["generated"]).isoformat() != manifest["generated"]:
            raise ValueError("expected YYYY-MM-DD")
    except ValueError as exc:
        raise ChampollionError(f"{destination}/VENDOR.json: generated: {exc}", cause="schema") from exc
    expected = manifest["files"]
    if not isinstance(expected, dict):
        raise ChampollionError(f"{destination}/VENDOR.json: files must be an object", cause="schema")
    for name, digest in expected.items():
        if not isinstance(name, str):
            raise ChampollionError(f"{destination}/VENDOR.json: file names must be strings", cause="schema")
        path = Path(name)
        if (not name or path.is_absolute() or ".." in path.parts or name == "VENDOR.json"
                or path.as_posix() != name or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ChampollionError(f"{destination}/VENDOR.json: invalid files entry {name!r}", cause="schema")
    try:
        actual = {p.relative_to(destination).as_posix(): p for p in destination.rglob("*") if p.is_file()
                  and p.relative_to(destination).as_posix() != "VENDOR.json"}
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        mismatches = sorted(name for name in set(expected) & set(actual)
                            if hashlib.sha256(actual[name].read_bytes()).hexdigest() != expected[name])
        symlinks = sorted(p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_symlink())
    except OSError as exc:
        raise ChampollionError(f"{destination}: {exc}", cause="IO") from exc
    differences = {"missing": missing, "extra": extra, "mismatches": mismatches, "symlinks": symlinks}
    return {"directory": str(destination), "valid": not any(differences.values()), **differences}
