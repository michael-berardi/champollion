"""The Champollion command-line interface and named operational failures."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

from .findings import ChampollionError
from .sources import add_source, read_json, write_json


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ChampollionError(message, cause="usage")


def _json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="print only the JSON result")


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="champollion", description="Offline mechanical translation-protocol checks")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("directory", nargs="?", default=".")
    _json_flag(init)
    source = commands.add_parser("source").add_subparsers(dest="source_command", required=True)
    add = source.add_parser("add")
    add.add_argument("--id", required=True)
    origin = add.add_mutually_exclusive_group(required=True)
    origin.add_argument("--file")
    origin.add_argument("--url")
    for flag in ("provider", "edition", "revision", "rights"):
        add.add_argument("--" + flag, required=True)
    add.add_argument("--note", default="")
    add.add_argument("--root", default=".")
    add.add_argument("--replace", action="store_true")
    _json_flag(add)
    for name in ("check", "lint"):
        check = commands.add_parser(name)
        check.add_argument("paths", nargs="*")
        check.add_argument("--root", default=".")
        check.add_argument("--profile")
        check.add_argument("--baseline")
        check.add_argument("--strict", action="store_true")
        check.add_argument("--quiet", action="store_true")
        _json_flag(check)
    packets = commands.add_parser("packets")
    packets.add_argument("--register", required=True)
    packets.add_argument("--units", required=True)
    packets.add_argument("--root", default=".")
    packets.add_argument("--out")
    _json_flag(packets)
    assemble = commands.add_parser("assemble")
    assemble.add_argument("--register", required=True)
    assemble.add_argument("--from", dest="directory", required=True)
    assemble.add_argument("--work")
    _json_flag(assemble)
    report = commands.add_parser("report")
    report.add_argument("--root", default=".")
    report.add_argument("--profile")
    _json_flag(report)
    _json_flag(commands.add_parser("rules"))
    validate = commands.add_parser("profile").add_subparsers(dest="profile_command", required=True).add_parser("validate")
    validate.add_argument("file")
    _json_flag(validate)
    export = commands.add_parser("export", help="typeset a work as PDF and EPUB (Kindle) books")
    export.add_argument("work", help="path of a work .md file")
    export.add_argument("--edition", action="append", help="original, musean, plain, historical (repeatable; default: every edition present)")
    export.add_argument("--format", action="append", choices=("pdf", "epub"), help="repeatable; default: both")
    export.add_argument("--out", required=True, help="output directory")
    export.add_argument("--publisher", default="Champollion")
    export.add_argument("--site-url", default="")
    export.add_argument("--motif", default="§", help="cover emblem")
    export.add_argument("--deep", default="#2b2118", help="cover colour")
    export.add_argument("--accent", default="#b8924a", help="accent colour")
    export.add_argument("--unit-noun", default="Part", help="what the work calls its divisions (Book, Chapter, ...)")
    export.add_argument("--font-css", help="@font-face stylesheet (absolute file: URLs) for PDF and cover rendering")
    export.add_argument("--epub-font", action="append", default=[], metavar="FAMILY=FILE", help="embed a font in Egyptian originals (repeatable)")
    export.add_argument("--assets-dir", default="", help="directory that resolves /figures/... image paths")
    export.add_argument("--colophon", default="")
    export.add_argument("--chrome", help="Chrome/Chromium binary (or $CHAMPOLLION_CHROME)")
    _json_flag(export)
    vendor = commands.add_parser("vendor")
    vendor.add_argument("--into", required=True)
    vendor.add_argument("--tag")
    _json_flag(vendor)
    verify = commands.add_parser("verify-vendor")
    verify.add_argument("directory", nargs="?", default=".")
    _json_flag(verify)
    return parser


def _profile(root: Path, explicit: Optional[str] = None) -> Any:
    from .profile import load_profile
    if explicit:
        path = Path(explicit)
    else:
        config_path = root / "champollion.json"
        config = read_json(config_path)
        if not isinstance(config, dict):
            raise ChampollionError(f"{config_path}: expected configuration object", cause="configuration")
        selected = config.get("profile_path", config.get("profile"))
        if not isinstance(selected, str) or not selected or selected == "champollion-profile/1":
            raise ChampollionError(f"{config_path}: missing profile_path", cause="configuration")
        path = Path(selected)
    return load_profile(path if path.is_absolute() else root / path)


def _baseline(profile: Any, filename: str, root: Path) -> Any:
    from .profile import profile_json, validate_profile
    path = Path(filename)
    path = path if path.is_absolute() else root / path
    obj = read_json(path)
    if isinstance(obj, list):
        exceptions = obj
    elif isinstance(obj, dict) and set(obj) == {"exceptions"}:
        exceptions = obj["exceptions"]
    else:
        raise ChampollionError(f"{path}: baseline requires dated exception records with owner and expiry; legacy baselines are not VER-12 records", cause="schema")
    settings = profile_json(profile)
    settings["exceptions"] = list(settings["exceptions"]) + exceptions if isinstance(exceptions, list) else exceptions
    validated = validate_profile(settings, str(path))
    digest = hashlib.sha256(json.dumps(settings, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest()
    return replace(validated, path=profile.path, fingerprint="sha256:" + digest)


def _works(root: Path, selected: Sequence[str] = ()) -> list:
    paths = []
    try:
        if selected:
            for item in selected:
                path = Path(item)
                path = path if path.is_absolute() else root / path
                if path.is_dir():
                    paths.extend(sorted(path.glob("*.md")))
                elif path.is_file():
                    paths.append(path)
                else:
                    raise ChampollionError(f"{path}: work path does not exist", cause="IO")
        else:
            directory = root / "works"
            if not directory.is_dir():
                raise ChampollionError(f"{directory}: works directory missing", cause="configuration")
            paths = sorted(directory.glob("*.md"))
    except OSError as exc:
        raise ChampollionError(f"{root}: {exc}", cause="IO") from exc
    if not paths:
        raise ChampollionError(f"{root}: no work documents selected", cause="configuration")
    identities = [str(p.resolve()) for p in paths]
    if len(identities) != len(set(identities)):
        raise ChampollionError("duplicate work path selected", cause="usage")
    return paths


def _one_work(root: Path, selected: Optional[str] = None) -> Any:
    from .format import parse_work
    paths = _works(root, [selected] if selected else [])
    if len(paths) != 1:
        raise ChampollionError("select one work: assemble requires --work when the root has more than one work; packets requires a single-work root", cause="usage")
    return parse_work(paths[0])


def _init(directory: str) -> dict:
    from .vendor import profile_directory
    root = Path(directory).resolve()
    paths = (root / "champollion.json", root / "sources" / "manifest.json")
    if any(path.exists() for path in paths):
        raise ChampollionError(f"{root}: scaffold already exists", cause="configuration")
    profile = profile_directory() / "generic.json"
    if not profile.is_file():
        raise ChampollionError(f"{profile}: generic profile missing", cause="configuration")
    try:
        (root / "works").mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ChampollionError(f"{root}: {exc}", cause="IO") from exc
    local_profile = root / "profiles" / "generic.json"
    if local_profile.exists():
        raise ChampollionError(f"{local_profile}: refusing to overwrite existing profile", cause="configuration")
    write_json(local_profile, read_json(profile))
    write_json(paths[0], {"profile": "champollion-profile/1", "name": root.name, "profile_path": "profiles/generic.json"})
    write_json(paths[1], {"records": []})
    return {"root": str(root), "created": ["champollion.json", "profiles/generic.json", "sources/manifest.json", "works/"]}


def _emit(obj: dict, json_mode: bool, text: str) -> None:
    print(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) if json_mode else text)


def _check(args: argparse.Namespace) -> int:
    from .report import build_report, render_text
    root = Path(args.root).resolve()
    profile = _profile(root, args.profile)
    if getattr(args, "baseline", None):
        profile = _baseline(profile, args.baseline, root)
    report = build_report(_works(root, getattr(args, "paths", ())), profile, str(root),
                          datetime.now(timezone.utc).date().isoformat())
    output = render_text(report, json_mode=args.json)
    if getattr(args, "quiet", False) and not args.json:
        output = "\n".join(output.splitlines()[:-1])
    if output:
        print(output)
    counts = report["counts"]
    return int(bool(counts["errors"] or (getattr(args, "strict", False) and counts["warnings"])))


def _dispatch(args: argparse.Namespace) -> int:
    command = args.command
    if command in ("check", "lint", "report"):
        return _check(args)
    if command == "init":
        result = _init(args.directory)
        _emit(result, args.json, f"initialized {result['root']}")
    elif command == "source":
        root = Path(args.root).resolve()
        profile = _profile(root) if args.url is None else None
        result = add_source(str(root), profile, id=args.id, file=args.file, url=args.url,
                            provider=args.provider, edition=args.edition, revision=args.revision,
                            rights=args.rights, note=args.note, replace=args.replace)
        _emit(result, args.json, f"stored source {result['id']} sha256:{result['sha256']}")
    elif command == "profile":
        from .profile import load_profile, profile_json
        profile = load_profile(args.file)
        _emit(profile_json(profile), args.json, f"valid profile {profile.name} {profile.fingerprint}")
    elif command == "rules":
        from .rules import rule_catalogue
        rules = rule_catalogue()
        _emit({"rules": rules}, args.json, "\n".join(f"{r['id']} {r['title']}" for r in rules))
    elif command == "packets":
        from .packets import packet_documents, write_packets
        root = Path(args.root).resolve()
        work = _one_work(root)
        profile = _profile(root)
        if args.out is not None:
            result = write_packets(work, profile, args.register, args.units, str(root), args.out)
            _emit(result, args.json, "\n".join(item["path"] for item in result["files"]))
        else:
            documents = packet_documents(work, profile, args.register, args.units, str(root))
            result = {"work": work.slug, "register": args.register, "packets": documents}
            _emit(result, args.json, "\n".join(item["text"] for item in documents))
    elif command == "assemble":
        from .assemble import assemble_work
        root = Path.cwd()
        result = assemble_work(_one_work(root, args.work), _profile(root), args.register, args.directory, str(root))
        _emit(result, args.json, f"assembled {result['output']}")
    elif command == "export":
        from .export.build import export_book
        from .export.model import available_editions
        from .export.typeset import Options, Theme
        opts = Options(publisher=args.publisher, site_url=args.site_url, unit_noun=args.unit_noun, font_css=args.font_css or "",
                       assets_dir=args.assets_dir, colophon=args.colophon, theme=Theme(deep=args.deep, accent=args.accent, motif=args.motif))
        editions = args.edition or available_editions(args.work)
        formats = args.format or ["epub", "pdf"]
        files = []
        for edition in editions:
            files.extend(export_book(args.work, edition, formats, args.out, opts, args.chrome, args.epub_font))
        _emit({"work": args.work, "files": files}, args.json,
              "\n".join(f"{f['path']} ({f['bytes']} bytes)" for f in files))
    elif command == "vendor":
        from .vendor import vendor
        result = vendor(args.into, args.tag)
        _emit(result, args.json, f"vendored {result['directory']}")
    elif command == "verify-vendor":
        from .vendor import verify_vendor
        result = verify_vendor(args.directory)
        lines = [f"{kind}: {name}" for kind in ("missing", "extra", "mismatches", "symlinks") for name in result[kind]]
        _emit(result, args.json, "\n".join(lines) if lines else f"verified {result['directory']}")
        return int(not result["valid"])
    else:
        raise ChampollionError(f"unknown command {command}", cause="usage")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run a documented command, returning 0/1/2 and naming operational errors."""
    try:
        try:
            args = _parser().parse_args(argv)
        except SystemExit as exc:
            return int(exc.code)
        return _dispatch(args)
    except ChampollionError as exc:
        print(f"champollion: {exc.cause or 'operational-error'}: {exc}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError) as exc:
        print(f"champollion: IO: {exc}", file=sys.stderr)
        return 2
    except (ValueError, TypeError) as exc:
        print(f"champollion: schema: {exc}", file=sys.stderr)
        return 2
