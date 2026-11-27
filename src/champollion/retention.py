"""Bounded retention for the local files the toolkit writes.

Every local write has a lifetime. Project, packet, review and export files last
until you delete them; the update cache is rewritten in place and the install log
is capped; install staging is removed on success, failure or timeout; and the one
installer rollback copy is removed after the installed version has run
successfully once, or seven days after the install at the latest. This module
enforces the mechanical lifetimes only: it reads no work document, opens no
socket and starts no process.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

from . import __version__, updates
from .findings import ChampollionError
from .sources import read_json

# Contract §4a: the rollback copy goes at the latest seven days after the swap.
ROLLBACK_MAX_AGE = 7 * 24 * 60 * 60
FIRST_RUN_MARKER = "venv.first-run.json"
ROLLBACK_SWAP = "venv.rollback-swap"
MARKER_SCHEMA = "champollion-first-run/1"
# An export that is killed cannot remove its temporary browser profile itself.
EXPORT_TMP_PREFIX = "champollion-"
EXPORT_TMP_MAX_AGE = 24 * 60 * 60


def _remove(path: Path) -> bool:
    """Remove one entry without ever following a symlink."""
    try:
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        else:
            return False
    except OSError:
        return False
    return True


def _age(path: Path, now: float) -> Optional[float]:
    try:
        return now - path.lstat().st_mtime
    except OSError:
        return None


def _marker_data(marker: Path) -> dict:
    if not marker.is_file() or marker.is_symlink():
        return {}
    try:
        data = read_json(marker)
    except ChampollionError:
        return {}
    return data if isinstance(data, dict) else {}


def _runs_from(home: Path, running_prefix: Optional[Any] = None) -> bool:
    """True only when this process runs the installer-managed environment.

    A checkout, a pip install or a test run must never delete another install's
    rollback copy: the first successful run is observed by the code that the
    swap put in place.
    """
    candidate = Path(running_prefix) if running_prefix is not None else Path(sys.prefix)
    try:
        return candidate.resolve() == (home / "venv").resolve()
    except OSError:
        return False


def mark_pending_first_run(home: Any, version: str, now: Optional[float] = None) -> bool:
    """Record a completed swap; the next successful run drops the rollback copy."""
    path = Path(home) / FIRST_RUN_MARKER
    record = {"schema": MARKER_SCHEMA, "version": str(version),
              "at": time.time() if now is None else float(now)}
    temporary = None
    try:
        if path.is_symlink():
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".first-run.", dir=str(path.parent))
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(record, handle, sort_keys=True)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        temporary = None
    except (OSError, TypeError, ValueError):
        return False
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass
    return True


def clear_pending_first_run(home: Any) -> bool:
    """A rollback restores the previous install, so no first run is pending."""
    return _remove(Path(home) / FIRST_RUN_MARKER)


def _rollback_retention(home: Path, now: float, successful: bool,
                        managed: bool) -> tuple:
    """Apply the rollback lifetime; returns (previous_removed, marker_cleared)."""
    previous = home / "venv.previous"
    marker = home / FIRST_RUN_MARKER
    data = _marker_data(marker)
    installed = str(data.get("version") or "")
    first_run = bool(successful and managed and installed and installed == __version__)
    recorded = data.get("at")
    has_marker = marker.exists() or marker.is_symlink()
    if isinstance(recorded, (int, float)) and not isinstance(recorded, bool):
        # The marker records the install/swap time. The old venv's mtime may be
        # years old and must not expire a copy that the swap just made current.
        age = now - float(recorded)
    elif has_marker:
        # A present but unreadable or undated marker gives no install time. It
        # must still not extend the bound: fall back to the marker file's own
        # modification time, and expire conservatively when even that is gone.
        age = _age(marker, now)
        if age is None:
            age = float(ROLLBACK_MAX_AGE)
    else:
        # Legacy installs without a marker still get the bounded folder clock.
        age = _age(previous, now)
    expired = bool(age is not None and age >= ROLLBACK_MAX_AGE)
    removed = False
    if previous.exists() or previous.is_symlink():
        if first_run or (managed and expired):
            removed = _remove(previous)
    cleared = False
    if managed and (first_run or expired or not previous.exists()):
        leftover = home / ROLLBACK_SWAP
        if leftover.exists() or leftover.is_symlink():
            _remove(leftover)
        if marker.exists() or marker.is_symlink():
            cleared = _remove(marker)
    return removed, cleared


def prune_export_temp(root: Optional[Any] = None, now: Optional[float] = None) -> int:
    """Remove abandoned export temporary profiles; never follow a symlink.

    Export removes its own temporary folder in a ``with`` block. A killed
    process cannot, so the next successful command clears anything this user
    left in the system temporary folder at least a day ago.
    """
    base = Path(root) if root is not None else Path(tempfile.gettempdir())
    if base.is_symlink() or not base.is_dir():
        return 0
    now = time.time() if now is None else float(now)
    uid = os.getuid() if hasattr(os, "getuid") else None
    try:
        candidates = sorted(base.glob(EXPORT_TMP_PREFIX + "*"))
    except OSError:
        return 0
    removed = 0
    for candidate in candidates:
        try:
            info = candidate.lstat()
        except OSError:
            continue
        if uid is not None and info.st_uid != uid:
            continue
        if now - info.st_mtime < EXPORT_TMP_MAX_AGE:
            continue
        removed += 1 if _remove(candidate) else 0
    return removed


def prune(home: Optional[Any] = None, now: Optional[float] = None, successful: bool = True,
          running_prefix: Optional[Any] = None) -> dict:
    """Apply every local lifetime; bounded work only, safe to call after any command."""
    base = Path(home) if home is not None else updates._install_home()
    now = time.time() if now is None else float(now)
    report = {"home": str(base), "managed": False, "staging_removed": 0,
              "previous_removed": False, "marker_cleared": False,
              "export_temp_removed": 0}
    if base.is_dir() and not base.is_symlink():
        report["managed"] = _runs_from(base, running_prefix)
    # Every automatic deletion below belongs to the installer-managed copy.
    # A checkout, pip install or test run must not prune somebody's real install
    # home or the machine-wide temporary folder.
    if report["managed"]:
        report["staging_removed"] = updates.cleanup_staging(
            base, min_age=updates.INSTALL_TIMEOUT + 60.0)
        removed, cleared = _rollback_retention(base, now, successful, True)
        report["previous_removed"] = removed
        report["marker_cleared"] = cleared
        report["export_temp_removed"] = prune_export_temp(now=now)
    return report
