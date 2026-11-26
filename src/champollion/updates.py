"""Anonymous release checks and opt-in updates for the Champollion CLI.

The automatic path is deliberately small: one anonymous GET to the repository's
public GitHub "latest release" record, at most once per day, only in an
interactive terminal, with a short timeout. Every preference and every result is
written through the owner-only atomic helpers in :mod:`champollion.sources`.
Nothing here touches a work document or a running export.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from . import __repository__, __version__
from .findings import ChampollionError
from .sources import mkdir_private, read_json, write_bytes_atomic, write_json

TOOL = "champollion"
PACKAGE = "champollion-protocol"
USER_AGENT = "champollion-update-check"
DAY_SECONDS = 24 * 60 * 60
CHECK_TIMEOUT = 3.0
MAX_RELEASE_BYTES = 256 * 1024
UPDATE_EXIT = 10

CONFIG_DEFAULTS: dict = {
    "schema": "champollion-updates/1",
    "check": True,
    "auto": False,
    "auto_prompted": False,
    "skipped_version": "",
}
CACHE_DEFAULTS: dict = {
    "schema": "champollion-update-cache/1",
    "checked_at": 0.0,
    "latest_version": "",
    "latest_notes": "",
    "latest_url": "",
    "last_error": "",
    "last_error_stage": "",
    "last_shown_version": "",
    "last_shown_at": 0.0,
    "last_install": {},
}

# Agent hosts and print/headless modes have their own presentation. The CLI
# never guesses from a process tree: an explicit switch is the only signal.
AGENT_ENV = (
    "CHAMPOLLION_AGENT", "AGENT_MODE", "CLAUDECODE", "CODEX_CLI",
    "PI_AGENT", "ANTIGRAVITY_AGENT", "DSH_AGENT",
)
OPT_OUT_ENV = "CHAMPOLLION_NO_UPDATE_CHECK"

_VERSION = re.compile(r"^[vV]?(\d+)\.(\d+)\.(\d+)$")
_GITHUB = re.compile(r"^(?:https?://)?github\.com/([^/\s]+)/([^/\s#?]+?)(?:\.git)?/?$", re.IGNORECASE)


def _flag(name: str) -> bool:
    value = os.environ.get(name, "").strip().lower()
    return bool(value) and value not in ("0", "false", "no", "off")


def config_dir() -> Path:
    override = os.environ.get("CHAMPOLLION_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "Champollion"
    return Path(os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")) / TOOL


def cache_dir() -> Path:
    override = os.environ.get("CHAMPOLLION_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "Champollion" / "Cache"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / TOOL
    return Path(os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")) / TOOL


def config_path() -> Path:
    return config_dir() / "config.json"


def cache_path() -> Path:
    return cache_dir() / "updates.json"


def install_log_path() -> Path:
    return cache_dir() / "updates-install.log"


def _read_object(path: Path, defaults: dict) -> dict:
    result = dict(defaults)
    if not path.is_file():
        return result
    try:
        obj = read_json(path)
    except ChampollionError:
        return result
    if not isinstance(obj, dict):
        return result
    for key in defaults:
        if key in obj:
            result[key] = obj[key]
    for key in ("check", "auto", "auto_prompted"):
        if key in result and not isinstance(result[key], bool):
            result[key] = defaults[key]
    for key in ("skipped_version", "latest_version", "latest_notes", "latest_url",
                "last_error", "last_error_stage", "last_shown_version"):
        if key in result and not isinstance(result[key], str):
            result[key] = defaults[key]
    if not isinstance(result.get("last_install"), dict):
        result["last_install"] = {}
    return result


def load_config(path: Optional[Path] = None) -> dict:
    return _read_object(Path(path) if path else config_path(), CONFIG_DEFAULTS)


def save_config(config: dict, path: Optional[Path] = None) -> dict:
    target = Path(path) if path else config_path()
    payload = dict(CONFIG_DEFAULTS)
    payload.update({key: config[key] for key in CONFIG_DEFAULTS if key in config})
    write_json(target, payload)
    return payload


def load_cache(path: Optional[Path] = None) -> dict:
    return _read_object(Path(path) if path else cache_path(), CACHE_DEFAULTS)


def save_cache(cache: dict, path: Optional[Path] = None) -> dict:
    target = Path(path) if path else cache_path()
    payload = dict(CACHE_DEFAULTS)
    payload.update({key: cache[key] for key in CACHE_DEFAULTS if key in cache})
    write_json(target, payload)
    return payload


def set_auto(state: str, path: Optional[Path] = None) -> dict:
    if state not in ("on", "off"):
        raise ChampollionError("update --auto expects on or off", cause="usage")
    config = load_config(path)
    config["auto"] = state == "on"
    config["auto_prompted"] = True
    return save_config(config, path)


def set_check(enabled: bool, path: Optional[Path] = None) -> dict:
    config = load_config(path)
    config["check"] = bool(enabled)
    return save_config(config, path)


def skip_version(version: str, path: Optional[Path] = None) -> dict:
    config = load_config(path)
    config["skipped_version"] = version
    return save_config(config, path)


def parse_version(tag: str) -> Optional[tuple]:
    """Return (major, minor, patch) only for a stable x.y.z tag."""
    if not isinstance(tag, str):
        return None
    match = _VERSION.match(tag.strip())
    return tuple(int(part) for part in match.groups()) if match else None


def compare_versions(candidate: str, current: str) -> Optional[int]:
    """1 newer, 0 equal, -1 older; None when either tag is not stable x.y.z."""
    left, right = parse_version(candidate), parse_version(current)
    if left is None or right is None:
        return None
    return (left > right) - (left < right)


def repository_url() -> str:
    """Read the repository from installed package metadata, with a project default."""
    try:
        from importlib.metadata import metadata
        info = metadata(PACKAGE)
    except Exception:
        return __repository__
    urls = list(info.get_all("Project-URL") or [])
    for item in urls:
        label, _, value = item.partition(",")
        if label.strip().lower() in ("repository", "source", "homepage"):
            value = value.strip()
            if _GITHUB.match(value):
                return value
    homepage = (info.get("Homepage") or "").strip()
    return homepage if _GITHUB.match(homepage) else __repository__


def _api_url(repository: Optional[str] = None) -> str:
    match = _GITHUB.match(repository or repository_url())
    if not match:
        raise ChampollionError("package metadata has no GitHub repository", cause="configuration")
    owner, repo = match.groups()
    return f"https://api.github.com/repos/{owner}/{repo}/releases/latest"


def release_payload(repository: Optional[str] = None,
                    opener: Optional[Callable] = None,
                    timeout: float = CHECK_TIMEOUT) -> dict:
    """One anonymous GET; no identity, version, usage or machine data is sent."""
    request = urllib.request.Request(_api_url(repository), headers={"User-Agent": USER_AGENT})
    open_with = opener or urllib.request.urlopen
    try:
        response = open_with(request, timeout=min(float(timeout), 4.0))
        try:
            raw = response.read(MAX_RELEASE_BYTES + 1)
        finally:
            response.close()
    except Exception as exc:
        raise ChampollionError(f"release check failed: {type(exc).__name__}: {exc}", cause="check") from exc
    if len(raw) > MAX_RELEASE_BYTES:
        raise ChampollionError("release check failed: response too large", cause="check")
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise ChampollionError(f"release check failed: invalid JSON: {exc}", cause="check") from exc
    if not isinstance(obj, dict):
        raise ChampollionError("release check failed: expected a release record", cause="check")
    return obj


def _failure(current: str, cause: str, at: float) -> dict:
    return {"status": "failed", "current": current, "latest": "", "tag": "", "notes": "",
            "url": "", "assets": [], "cause": cause, "checked_at": at}


def check_now(repository: Optional[str] = None,
              opener: Optional[Callable] = None,
              timeout: float = CHECK_TIMEOUT,
              current: Optional[str] = None) -> dict:
    version = current or __version__
    at = time.time()
    try:
        release = release_payload(repository, opener, timeout)
    except ChampollionError as exc:
        return _failure(version, str(exc), at)
    tag = release.get("tag_name")
    if release.get("draft") or release.get("prerelease"):
        return {"status": "current", "current": version, "latest": "", "tag": str(tag or ""),
                "notes": "", "url": "", "assets": [], "cause": "", "checked_at": at}
    newest = parse_version(tag)
    if newest is None:
        # An unparseable tag is not newer; keep the cache free of a false prompt.
        return {"status": "current", "current": version, "latest": "", "tag": str(tag or ""),
                "notes": "", "url": "", "assets": [], "cause": "", "checked_at": at}
    comparison = compare_versions(tag, version)
    latest = ".".join(str(part) for part in newest)
    assets = [{"name": str(a.get("name") or ""), "url": str(a.get("browser_download_url") or "")}
              for a in release.get("assets", []) or [] if isinstance(a, dict)]
    if comparison != 1:
        return {"status": "current", "current": version, "latest": latest, "tag": str(tag),
                "notes": "", "url": str(release.get("html_url") or ""), "assets": assets,
                "cause": "", "checked_at": at}
    return {"status": "update", "current": version, "latest": latest, "tag": str(tag),
            "notes": str(release.get("body") or ""), "url": str(release.get("html_url") or ""),
            "assets": assets, "cause": "", "checked_at": at}


def record_check(result: dict, path: Optional[Path] = None) -> dict:
    cache = load_cache(path)
    cache["checked_at"] = result["checked_at"]
    cache["last_error"] = result.get("cause", "")
    cache["last_error_stage"] = "check" if result.get("cause") else ""
    if result.get("status") in ("current", "update") and result.get("latest"):
        cache["latest_version"] = result["latest"]
        cache["latest_notes"] = result.get("notes", "")
        cache["latest_url"] = result.get("url", "")
    return save_cache(cache, path)


def record_install(result: dict, path: Optional[Path] = None) -> dict:
    cache = load_cache(path)
    cache["last_install"] = {key: result.get(key, "") for key in ("ok", "version", "cause", "at", "kind")}
    cache["last_error"] = result.get("cause", "")
    cache["last_error_stage"] = "" if result.get("ok") else "install"
    if result.get("ok"):
        cache["last_shown_version"] = ""
        cache["last_shown_at"] = 0.0
    return save_cache(cache, path)


def record_shown(version: str, at: Optional[float] = None, path: Optional[Path] = None) -> dict:
    cache = load_cache(path)
    cache["last_shown_version"] = version
    cache["last_shown_at"] = time.time() if at is None else at
    return save_cache(cache, path)


def automatic_check_due(cache: Optional[dict] = None, now: Optional[float] = None) -> bool:
    cache = cache if cache is not None else load_cache()
    try:
        checked = float(cache.get("checked_at") or 0.0)
    except (TypeError, ValueError):
        return True
    return not checked or (time.time() if now is None else now) - checked >= DAY_SECONDS


def check_allowed(argv: Optional[Any] = None, config: Optional[dict] = None,
                  stdout: Optional[Any] = None, stderr: Optional[Any] = None) -> bool:
    """True only for an interactive, non-agent, non-JSON, opted-in terminal."""
    argv = list(argv or [])
    if any(str(arg) == "--json" for arg in argv):
        return False
    if argv and argv[0] == TOOL:
        argv = argv[1:]
    if argv and argv[0] == "update":
        return False
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    if not getattr(out, "isatty", lambda: False)() or not getattr(err, "isatty", lambda: False)():
        return False
    if _flag("CI") or any(_flag(name) for name in AGENT_ENV) or _flag(OPT_OUT_ENV):
        return False
    config = config if config is not None else load_config()
    return config.get("check") is True


def notice_lines(latest: str, current: Optional[str] = None) -> tuple:
    current = current or __version__
    return (
        f"{TOOL} {latest} available (you have {current}) · run: {TOOL} update",
        f"turn on automatic updates: {TOOL} update --auto on · skip: {TOOL} update --skip",
    )


def dim(line: str, stream: Optional[Any] = None) -> str:
    stream = stream if stream is not None else sys.stderr
    if os.environ.get("NO_COLOR") or not getattr(stream, "isatty", lambda: False)():
        return line
    return f"\x1b[2m{line}\x1b[0m"


def should_show_notice(result: dict, config: Optional[dict] = None,
                       cache: Optional[dict] = None, now: Optional[float] = None) -> bool:
    if result.get("status") != "update":
        return False
    config = config if config is not None else load_config()
    cache = cache if cache is not None else load_cache()
    latest = result.get("latest", "")
    if config.get("skipped_version") == latest:
        return False
    if cache.get("last_shown_version") == latest:
        try:
            shown = float(cache.get("last_shown_at") or 0.0)
        except (TypeError, ValueError):
            shown = 0.0
        if (time.time() if now is None else now) - shown < DAY_SECONDS:
            return False
    return True


def _utc(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="seconds")


def report_text(result: dict, config: Optional[dict] = None, cache: Optional[dict] = None) -> str:
    config = config if config is not None else load_config()
    cache = cache if cache is not None else load_cache()
    lines = [f"current: {result['current']}"]
    if result["status"] == "update":
        lines.append(f"available: {result['latest']}")
        if result.get("url"):
            lines.append(f"release: {result['url']}")
        notes = "\n".join(line.strip() for line in result.get("notes", "").splitlines()[:8] if line.strip())
        if notes:
            lines.append("notes:")
            lines.extend("  " + line for line in notes.splitlines())
    elif result["status"] == "current":
        lines.append("available: none (this is the latest stable release)")
    else:
        lines.append(f"check failed: {result['cause']}")
    lines.append(f"automatic checks: {'on' if config.get('check') else 'off'}; "
                 f"automatic installs: {'on' if config.get('auto') else 'off'}")
    if config.get("skipped_version"):
        lines.append(f"skipped version: {config['skipped_version']}")
    if cache.get("last_error"):
        lines.append(f"last recorded failure ({cache.get('last_error_stage') or 'check'}): {cache['last_error']}")
    last = cache.get("last_install") or {}
    if last:
        lines.append(f"last install: {_utc(float(last.get('at') or 0))} "
                     f"{'ok' if last.get('ok') else 'failed'} ({last.get('kind') or 'unknown'})")
        if last.get("cause"):
            lines.append(f"install cause: {last['cause']}")
    return "\n".join(lines)


def report_json(result: dict, config: Optional[dict] = None, cache: Optional[dict] = None) -> dict:
    config = config if config is not None else load_config()
    cache = cache if cache is not None else load_cache()
    return {
        "status": result["status"], "current": result["current"], "latest": result.get("latest", ""),
        "tag": result.get("tag", ""), "url": result.get("url", ""), "notes": result.get("notes", ""),
        "cause": result.get("cause", ""), "checked_at": _utc(float(result.get("checked_at") or 0)),
        "auto": bool(config.get("auto")), "check": bool(config.get("check")),
        "skipped_version": config.get("skipped_version", ""),
        "last_error": cache.get("last_error", ""), "last_install": cache.get("last_install", {}),
    }


def _install_home() -> Path:
    override = os.environ.get("CHAMPOLLION_HOME")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "Champollion"
    return Path.home() / ".champollion"


def _installer_managed() -> bool:
    home = _install_home()
    return (home / "venv").is_dir() or (home / "bin" / "champollion").is_file()


def _package_manager() -> str:
    try:
        from importlib.metadata import distribution
        installed_by = (distribution(PACKAGE).read_text("INSTALLER") or "").strip().lower()
    except Exception:
        installed_by = ""
    if "uv" in installed_by:
        return "uv"
    if installed_by:
        return installed_by.splitlines()[0]
    return ""


def install_plan(result: dict) -> dict:
    """Name the right command for package-manager installs; never overwrite their files."""
    version = result.get("latest", "")
    repository = repository_url().rstrip("/")
    if _installer_managed():
        return {"kind": "installer", "argv": [], "command": f"{TOOL} update"}
    manager = _package_manager()
    if manager == "uv":
        argv = ["uv", "tool", "upgrade", PACKAGE]
        kind = "uv"
    elif manager in ("pip", "pip3", "pipx"):
        requirement = f"{PACKAGE} @ git+{repository}.git@v{version}"
        argv = [sys.executable, "-m", "pip", "install", "--upgrade", requirement]
        kind = "pip"
    elif manager == "cargo":
        argv = ["cargo", "install", PACKAGE, "--tag", f"v{version}"]
        kind = "cargo"
    elif manager == "brew":
        argv = ["brew", "upgrade", TOOL]
        kind = "brew"
    else:
        argv = []
        kind = "unknown"
    command = shlex.join(argv) if argv else ""
    return {"kind": kind, "argv": argv, "command": command}


def parse_sums(text: str) -> dict:
    sums = {}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 2 or line.lstrip().startswith("#"):
            continue
        digest, name = fields[0].lower(), fields[1].lstrip("*")
        if re.fullmatch(r"[0-9a-f]{64}", digest):
            sums[name] = digest
    return sums


def verify_wheel(data: bytes, wheel_name: str, sums_text: str) -> None:
    expected = parse_sums(sums_text).get(wheel_name)
    if not expected:
        raise ChampollionError(f"no checksum for {wheel_name} in SHA256SUMS", cause="checksum")
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise ChampollionError(f"checksum mismatch for {wheel_name}; nothing was installed", cause="checksum")


def _get_asset(url: str, opener: Optional[Callable] = None, timeout: float = 10.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": TOOL + "-update-install"})
    open_with = opener or urllib.request.urlopen
    try:
        response = open_with(request, timeout=timeout)
        try:
            return response.read(64 * 1024 * 1024 + 1)
        finally:
            response.close()
    except Exception as exc:
        raise ChampollionError(f"download failed: {type(exc).__name__}: {exc}", cause="download") from exc


def swap_directories(current: Path, staged: Path, previous: Path) -> None:
    """Swap a staged install into place, keeping exactly one rollback directory."""
    for path in (current, staged, previous):
        if path.is_symlink():
            raise ChampollionError(f"{path}: refusing a symlink install path", cause="install")
    if previous.exists():
        if previous.is_dir() and not previous.is_symlink():
            shutil.rmtree(previous)
        else:
            previous.unlink()
    if current.exists():
        current.rename(previous)
    try:
        staged.rename(current)
    except OSError:
        if previous.exists():
            previous.rename(current)
        raise


def rollback(path: Optional[Path] = None) -> dict:
    home = Path(path) if path else _install_home()
    current, previous = home / "venv", home / "venv.previous"
    if not previous.is_dir() or previous.is_symlink():
        result = {"ok": False, "kind": "installer", "version": "", "cause": "no rollback install is kept",
                  "at": time.time()}
        record_install(result)
        return result
    try:
        if current.exists():
            failed = home / "venv.rollback-swap"
            if failed.exists():
                shutil.rmtree(failed) if failed.is_dir() else failed.unlink()
            current.rename(failed)
        previous.rename(current)
        if (home / "venv.rollback-swap").exists():
            (home / "venv.rollback-swap").rename(previous)
    except OSError as exc:
        result = {"ok": False, "kind": "installer", "version": "", "cause": f"rollback failed: {exc}",
                  "at": time.time()}
        record_install(result)
        return result
    result = {"ok": True, "kind": "installer", "version": "", "cause": "", "at": time.time()}
    record_install(result)
    return result


def install_release(result: dict, opener: Optional[Callable] = None, timeout: float = 10.0) -> dict:
    """Verify the release wheel, stage it, swap it, and keep the old venv once."""
    at = time.time()
    version = result.get("latest", "")
    plan = install_plan(result)
    if plan["kind"] not in ("installer", "pip", "uv", "cargo", "brew"):
        out = {"ok": False, "kind": "unknown", "version": version, "at": at,
               "cause": "no supported install method detected; see the release notes"}
        record_install(out)
        return out
    if plan["argv"]:
        try:
            subprocess.run(plan["argv"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except (OSError, subprocess.CalledProcessError) as exc:
            out = {"ok": False, "kind": plan["kind"], "version": version, "at": at,
                   "cause": f"{plan['command']} failed: {type(exc).__name__}: {exc}"}
            record_install(out)
            return out
        out = {"ok": True, "kind": plan["kind"], "version": version, "at": at, "cause": ""}
        record_install(out)
        return out
    try:
        assets = {a["name"]: a["url"] for a in result.get("assets", []) if a.get("name") and a.get("url")}
        sums_name = next((name for name in assets if name == "SHA256SUMS"), "")
        wheel_name = next((name for name in assets if re.fullmatch(
            r"champollion_protocol-\d+\.\d+\.\d+-py3-none-any\.whl", name)), "")
        if not sums_name or not wheel_name:
            raise ChampollionError("release has no verified wheel and SHA256SUMS", cause="install")
        sums_text = _get_asset(assets[sums_name], opener, timeout).decode("utf-8")
        wheel = _get_asset(assets[wheel_name], opener, timeout)
        verify_wheel(wheel, wheel_name, sums_text)
        home = _install_home()
        mkdir_private(home)
        with tempfile.TemporaryDirectory(prefix=".champollion-stage-", dir=home) as folder:
            stage_root = Path(folder)
            wheel_path = stage_root / wheel_name
            write_bytes_atomic(wheel_path, wheel)
            stage = home / ("venv.next.%d" % os.getpid())
            if stage.exists():
                shutil.rmtree(stage) if stage.is_dir() else stage.unlink()
            python = stage / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            subprocess.run([sys.executable, "-m", "venv", str(stage)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            subprocess.run([str(python), "-m", "pip", "install", "--no-index", "--no-deps",
                            "--no-cache-dir", "--disable-pip-version-check", "--quiet", str(wheel_path)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            subprocess.run([str(python), "-m", "champollion", "--help"], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            swap_directories(home / "venv", stage, home / "venv.previous")
    except (ChampollionError, OSError, ValueError, UnicodeError, subprocess.CalledProcessError) as exc:
        out = {"ok": False, "kind": "installer", "version": version, "at": at,
               "cause": f"{type(exc).__name__}: {exc}"}
        record_install(out)
        return out
    out = {"ok": True, "kind": "installer", "version": version, "at": at, "cause": ""}
    record_install(out)
    return out


def log_install(result: dict) -> None:
    entry = json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n"
    path = install_log_path()
    prior = path.read_text(encoding="utf-8") if path.is_file() else ""
    write_bytes_atomic(path, (prior + entry).encode("utf-8"))


def auto_install(result: dict, opener: Optional[Callable] = None) -> None:
    """Low-priority, logged install; a failure leaves the current version working."""
    try:
        if hasattr(os, "nice"):
            os.nice(10)
    except OSError:
        pass
    outcome = install_release(result, opener)
    try:
        log_install(outcome)
    except (ChampollionError, OSError):
        pass
    record_install(outcome)


def finish_background_check(argv: Optional[Any] = None, status: int = 0) -> None:
    """Run the daily check after a successful command; never print check noise."""
    try:
        if status != 0 or not check_allowed(argv):
            return
        config, cache = load_config(), load_cache()
        if not automatic_check_due(cache):
            return
        result = check_now()

        def work() -> None:
            try:
                record_check(result)
                if result["status"] != "update":
                    return
                if config.get("auto"):
                    auto_install(result)
                    latest = load_cache().get("last_install") or {}
                    if latest.get("ok"):
                        return
                if should_show_notice(result, config, load_cache()):
                    first, second = notice_lines(result["latest"], result["current"])
                    print(first, file=sys.stderr)
                    print(dim(second), file=sys.stderr)
                    record_shown(result["latest"])
            except Exception:
                return

        thread = threading.Thread(target=work, name="champollion-update-check", daemon=True)
        thread.start()
        thread.join(timeout=CHECK_TIMEOUT + 0.5)
    except Exception:
        return
