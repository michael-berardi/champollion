"""Offline source-record, revision, rights and stored-byte integrity gates."""
import hashlib
from pathlib import Path
import re
from typing import Any, List

from ..findings import ChampollionError, Finding
from . import Check, Context, finding, gate_status, source_record


def enabled(profile: Any) -> bool:
    """Local source evidence is mandatory for every profile."""
    return True


def _record_path(ctx: Context) -> str:
    return ctx.work.front.get("source", "") or f"sources/{ctx.work.slug}.json"


def _snapshot(ctx: Context, record: dict) -> tuple:
    value = record.get("raw_snapshot") or record.get("path")
    if not isinstance(value, str) or not value.strip():
        return None, "source record has no raw_snapshot/path"
    root = Path(ctx.root).resolve()
    path = Path(value)
    if path.is_absolute():
        return None, "snapshot path must be project-relative: " + value
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None, "snapshot path escapes project root: " + value
    return resolved, ""


def _pinned(revision: Any) -> bool:
    if not isinstance(revision, str) or not revision.strip():
        return False
    value = revision.strip()
    if value.lower() in ("head", "main", "master", "latest", "current", "trunk", "unknown", "none"):
        return False
    if value.lower().startswith("urn:"):
        return False
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", value):
        return bool(re.search(r"(?:[?&]oldid=\d+|/commit/[0-9a-fA-F]{7,64}(?:/|$))", value))
    return True


def _licenses(record: dict) -> list:
    rights = record.get("rights")
    if isinstance(rights, dict):
        return [(key, rights.get(key)) for key in ("work", "transcription")]
    result = [("rights", rights)]
    for key in ("work_rights", "transcription_rights"):
        if key in record:
            result.append((key, record[key]))
    return result


def run(ctx: Context) -> List[Finding]:
    """Verify only referenced local evidence, without acquiring or repairing it."""
    record = source_record(ctx)
    if record is None:
        path = _record_path(ctx)
        return [finding(ctx, "SRC-8", "SRC-8", f"no local source record for {path}",
                        evidence={"record": path, "work": ctx.work.slug})]
    if not isinstance(record, dict):
        raise ChampollionError(f"source record {_record_path(ctx)} must be an object", cause="SRC-8")
    result: List[Finding] = []
    revision = record.get("revision") or record.get("immutable_revision")
    if not _pinned(revision):
        result.append(finding(ctx, "SRC-NO-PIN", "SRC-2", "source has no immutable revision evidence",
                              evidence={"revision": revision, "record": _record_path(ctx)}))
    provider = record.get("provider")
    if not isinstance(provider, str) or not provider.strip():
        result.append(finding(ctx, "SRC-7", "SRC-7", "source has no provider reference",
                              evidence={"record": _record_path(ctx)}))
    allowed = ctx.profile.rights["allowed"]
    if not isinstance(record.get('rights'), dict) and not (record.get('work_rights') and record.get('transcription_rights')):
        result.append(finding(ctx, 'SRC-RIGHTS', 'SRC-4',
                              'source record must separately identify underlying-work and transcription rights'))
    for key, license_id in _licenses(record):
        if license_id not in allowed:
            result.append(finding(ctx, "SRC-RIGHTS", "SRC-4",
                                  f"source rights {license_id!r} are not in profile.rights.allowed",
                                  evidence={"rights": license_id, "field": key, "allowed": list(allowed)}))
    path, cause = _snapshot(ctx, record)
    declared = ctx.work.front.get("raw_snapshot", "")
    if declared:
        front_path, front_cause = _snapshot(ctx, {"raw_snapshot": declared})
        if front_path is None:
            result.append(finding(ctx, "SRC-8", "SRC-8", front_cause,
                                  evidence={"raw_snapshot": declared}))
        elif path is not None and front_path != path:
            result.append(finding(ctx, "SRC-8", "SRC-8",
                                  "front-matter raw_snapshot differs from the source record",
                                  evidence={"declared": declared, "record_snapshot": str(path)}))
    expected = record.get("sha256")
    if isinstance(expected, str) and expected.startswith("sha256:"):
        expected = expected[7:]
    if path is None:
        result.append(finding(ctx, "SRC-8", "SRC-8", cause, evidence={"record": _record_path(ctx)}))
    elif not path.is_file():
        result.append(finding(ctx, "SRC-8", "SRC-8", f"missing snapshot file: {path}",
                              evidence={"snapshot": str(path), "expected_sha256": expected}))
    elif path.stat().st_size == 0:
        result.append(finding(ctx, 'SRC-8', 'SRC-8', 'source snapshot is empty', evidence={'snapshot': str(path)}))
    else:
        try:
            with path.open("rb") as stream:
                digest = hashlib.sha256()
                for block in iter(lambda: stream.read(65536), b""):
                    digest.update(block)
                actual = digest.hexdigest()
        except OSError as exc:
            raise ChampollionError(f"cannot read snapshot {path}: {exc}", cause="SRC-8") from exc
        evidence = {"snapshot": str(path), "expected_sha256": expected, "computed_sha256": actual}
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
            result.append(finding(ctx, "SRC-8", "SRC-8", "source has no valid snapshot sha256", evidence=evidence))
        elif expected.lower() != actual:
            result.append(finding(ctx, "SRC-HASH-MISMATCH", "SRC-8", "snapshot sha256 does not match source record",
                                  evidence=evidence))
    return result


def statuses(ctx: Context, findings: List[Finding]) -> List[dict]:
    """Name the expected record and disclose incomplete rights separation."""
    record = source_record(ctx)
    result = [gate_status("rights", "failed" if findings else "ran", detail=(
        "expected source record: " + _record_path(ctx) if record is None else "local source record: " + _record_path(ctx)))]
    if record is not None and not isinstance(record.get("rights"), dict) and not (
            record.get("work_rights") and record.get("transcription_rights")):
        result.append(gate_status("rights.separation", "unsupported", detail=
                                  "source record does not separately identify underlying-work and transcription rights"))
    return result


CHECK = Check("rights", enabled, run, statuses)
