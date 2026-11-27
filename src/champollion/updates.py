"""Anonymous release checks and opt-in updates for the Champollion CLI.

The check is one anonymous GET, with a fixed User-Agent, to the public GitHub
"latest release" record of the repository named in the package's own metadata.
Texts, profiles, reports and machine details never leave the machine. Installs
happen only on request, or after the user turns automatic installs on.

Everything the check remembers lives in one small owner-only file,
``update.json`` in the platform cache folder.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Optional, Sequence
from urllib.parse import urlsplit

from . import __version__
from .findings import ChampollionError

PACKAGE = "champollion-protocol"
DAY = 24 * 60 * 60
ROLLBACK_MAX_AGE = 7 * DAY
TIMEOUT = 4.0
USER_AGENT = "champollion-update-check"
LOG_LIMIT = 256 * 1024
# install_release stages ``venv.tmp.<pid>`` (as the installers do) and rollback_install parks the current venv as
# ``venv.rollback.<pid>``; both are removed by the step that made them. Anything older than this is abandoned debris.
STAGING_MAX_AGE = 6 * 60
STAGE_PREFIXES = ("venv.tmp.", "venv.rollback.")
# Written after a swap; retention removes venv.previous after the first successful run it names.
FIRST_RUN_MARKER = "venv.first-run.json"
MANAGERS = ("pip", "uv", "pipx")
# Agent hosts and worker runs set one of these; the check then stays off.
AGENT_FLAGS = ("CHAMPOLLION_AGENT", "AGENT", "CLAUDECODE", "CODEX_SANDBOX", "GEMINI_CLI", "PI_AGENT", "DSH_AGENT")
_VERSION = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")
_WHEEL = re.compile(r"champollion_protocol-[^/\\\s]+-py3-none-any\.whl")
_DIGEST = re.compile(r"[0-9a-fA-F]{64}")


# --- state -----------------------------------------------------------------

def cache_dir() -> Path:
    """The platform cache folder for ``update.json`` and the automatic-install log."""
    if os.name == "nt":
        # Inside the installer folder, so removing %LOCALAPPDATA%\\Champollion removes it too.
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Champollion" / "Cache"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "champollion"
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "champollion"


def state_path() -> Path:
    return cache_dir() / "update.json"


def log_path() -> Path:
    return cache_dir() / "update.log"


def load_state() -> dict:
    try:
        value = json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def save_state(**changes: Any) -> dict:
    """Merge changes into the state file through an owner-only temporary file and an atomic rename."""
    state = load_state()
    state.update(changes)
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".update.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(state, handle, sort_keys=True)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return state


def auto_status() -> dict:
    state = load_state()
    return {"check_automatically": state.get("check") is not False,
            "install_automatically": bool(state.get("auto")),
            "current": __version__,
            "last_auto_error": str(state.get("auto_error") or "")}


# --- versions and the release record ----------------------------------------

def parse_version(text: Any) -> Optional[tuple]:
    match = _VERSION.fullmatch(text) if isinstance(text, str) else None
    return tuple(int(part) for part in match.groups()) if match else None


def is_newer(candidate: Any, current: str = __version__) -> bool:
    """Only a stable ``x.y.z`` strictly above the running version counts; anything unparseable is not newer."""
    new, old = parse_version(candidate), parse_version(current)
    return bool(new and old and new > old)


def repository_url() -> str:
    """The repository the package declares: installed metadata, else this checkout's pyproject."""
    try:
        from importlib.metadata import metadata

        for entry in metadata(PACKAGE).get_all("Project-URL") or ():
            label, _, url = entry.partition(",")
            if label.strip().lower() == "repository":
                return url.strip().rstrip("/")
    except Exception:  # not installed, or unreadable metadata: fall back to the checkout
        pass
    try:
        text = (Path(__file__).resolve().parents[2] / "pyproject.toml").read_text(encoding="utf-8")
    except OSError:
        text = ""
    match = re.search(r'^Repository\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match or not re.search(r'^name\s*=\s*"%s"' % PACKAGE, text, re.MULTILINE):
        raise ChampollionError("the package declares no repository URL", cause="update")
    return match.group(1).rstrip("/")


def api_url() -> str:
    override = os.environ.get("CHAMPOLLION_UPDATE_API")
    if override:
        return override
    parts = urlsplit(repository_url())
    path = [part for part in parts.path.split("/") if part]
    if parts.netloc.lower() != "github.com" or len(path) != 2:
        raise ChampollionError("the package repository is not on GitHub", cause="update")
    return f"https://api.github.com/repos/{path[0]}/{path[1].removesuffix('.git')}/releases/latest"


def release_base(tag: str) -> str:
    """Where a release's SHA256SUMS and wheel live; CHAMPOLLION_RELEASE_BASE overrides it as for the installers."""
    return (os.environ.get("CHAMPOLLION_RELEASE_BASE") or f"{repository_url()}/releases/download/{tag}").rstrip("/")


def fetch(url: str, timeout: float = TIMEOUT) -> bytes:
    """One anonymous GET: no cookies, no credentials, no query, only the fixed User-Agent."""
    from urllib.request import Request, urlopen

    if urlsplit(url).scheme not in ("https", "http"):
        raise ChampollionError(f"unsupported update URL: {url}", cause="update")
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout) as response:
        return response.read()


def parse_release(record: Any) -> dict:
    """Reduce a release record to a status; drafts, prereleases and odd tags are never newer."""
    if not isinstance(record, dict):
        raise ValueError("the release record is not a JSON object")
    tag = record.get("tag_name")
    if record.get("draft") or record.get("prerelease") or not is_newer(tag):
        return {"status": "current", "latest": "", "tag": "", "cause": ""}
    return {"status": "available", "latest": tag.lstrip("v"), "tag": tag, "cause": "",
            "notes": str(record.get("body") or "")}


def _failed(cause: str) -> dict:
    return {"status": "failed", "latest": "", "tag": "", "cause": cause}


def _cause(exc: BaseException) -> str:
    return str(exc) or type(exc).__name__


def _ask_release() -> dict:
    try:
        return parse_release(json.loads(fetch(api_url())))
    except Exception as exc:  # every failure is recorded with its cause, never raised or retried
        return _failed(_cause(exc))


def record_check(outcome: dict) -> dict:
    """Store a check result and its time (never the release notes); return the merged state."""
    stored = {key: outcome.get(key, "") for key in ("status", "latest", "tag", "cause")}
    return dict(save_state(checked_at=time.time(), **stored), notes=outcome.get("notes", ""))


def check_now() -> dict:
    """An explicit check (``update``, ``update --check``): one fresh request, cached like the daily one."""
    return record_check(_ask_release())


def release_notes(body: str) -> str:
    lines = [line.strip() for line in (body or "").splitlines() if line.strip()]
    return "\n".join(line[:160] for line in lines[:8])


# --- the daily check and the notice -----------------------------------------

def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() not in ("", "0", "false", "no", "off")


def _fresh(state: dict, now: float) -> bool:
    checked = state.get("checked_at")
    return isinstance(checked, (int, float)) and 0 <= now - checked < DAY and state.get("status") in (
        "current", "available", "failed")


class BackgroundCheck:
    """The daily request runs on a daemon thread; only the main thread writes the state file."""

    def __init__(self, state: dict) -> None:
        self.state = state
        self.started = time.monotonic()
        self.outcome: Optional[dict] = None
        self.thread = None
        if not _fresh(state, time.time()):
            import threading

            self.thread = threading.Thread(target=self._run, name="champollion-update-check", daemon=True)
            self.thread.start()

    def _run(self) -> None:
        self.outcome = _ask_release()

    def finish(self) -> dict:
        if self.thread is None:
            return self.state
        self.thread.join(max(0.0, TIMEOUT - (time.monotonic() - self.started)))
        return record_check(self.outcome or _failed(f"no answer within {TIMEOUT:g} s"))


def start_check(argv: Sequence[str]) -> Optional[BackgroundCheck]:
    """Begin the daily check only for an interactive, human, non-JSON, opted-in run of an updatable copy."""
    try:
        if not argv or argv[0] == "update" or any(item == "--json" or item.startswith("--json=") for item in argv):
            return None
        if not (sys.stdout.isatty() and sys.stderr.isatty()):
            return None
        if any(_truthy(name) for name in ("CI", "CHAMPOLLION_NO_UPDATE_CHECK") + AGENT_FLAGS):
            return None
        if detect_install_kind() == "source":
            return None
        state = load_state()
        return None if state.get("check") is False else BackgroundCheck(state)
    except Exception:  # an update problem never changes the user's command
        return None


def notice_lines(latest: str, kind: str, auto: bool = False) -> list:
    first = f"champollion {latest} available (you have {__version__}) · run: {upgrade_hint(kind)}"
    if auto or not can_self_update(kind):
        second = "skip: champollion update --skip"
    else:
        second = "turn on automatic updates: champollion update --auto on · skip: champollion update --skip"
    if sys.stderr.isatty() and not os.environ.get("NO_COLOR"):
        second = f"\x1b[2m{second}\x1b[0m"
    return [first, second]


def _notify(state: dict) -> None:
    latest = state.get("latest")
    if state.get("status") != "available" or not is_newer(latest) or state.get("skip") == latest:
        return
    kind = detect_install_kind()
    if state.get("auto") and state.get("auto_tried") != latest and can_self_update(kind):
        launch_auto_install(latest)
        return
    now, shown = time.time(), state.get("notified_at")
    if state.get("notified") == latest and isinstance(shown, (int, float)) and 0 <= now - shown < DAY:
        return
    for line in notice_lines(latest, kind, bool(state.get("auto"))):
        print(line, file=sys.stderr)
    save_state(notified=latest, notified_at=now)


def after_command(pending: Optional[BackgroundCheck], command: str, code: int) -> None:
    """After the user's command: drop a proven rollback copy, then show the notice; never raises."""
    try:
        if command != "update":
            drop_rollback(ran_ok=code == 0)
        if pending is not None and code == 0:
            _notify(pending.finish())
    except Exception:  # an update problem never changes the user's command
        pass


# --- install kinds -------------------------------------------------------------

def _default_homes() -> list:
    homes = [Path(os.environ["CHAMPOLLION_HOME"]).expanduser()] if os.environ.get("CHAMPOLLION_HOME") else []
    if os.name == "nt":
        homes.append(Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Champollion")
    else:
        homes.append(Path.home() / ".champollion")
    return [home.resolve() for home in homes]


def installer_home() -> Optional[Path]:
    """The install.sh/install.ps1 folder this copy runs from (``<home>/venv``), or None."""
    prefix = Path(sys.prefix).resolve()
    return prefix.parent if prefix.name == "venv" and prefix.parent in _default_homes() else None


def _install_home() -> Optional[Path]:
    """The installer home used by the retention pass; None for a managed-less copy."""
    return installer_home()


def detect_install_kind() -> str:
    """installer, pip, uv, pipx, or source (a checkout or vendored snapshot, updated by git or re-vendoring)."""
    if installer_home() is not None:
        return "installer"
    parts = [part.lower() for part in Path(__file__).resolve().parts]
    if "site-packages" not in parts and "dist-packages" not in parts:
        return "source"
    if "pipx" in parts:
        return "pipx"
    if "uv" in parts and "tools" in parts:
        return "uv"
    return "pip"


def can_self_update(kind: str) -> bool:
    # A running Windows venv cannot be renamed, so the PowerShell installer does that job there.
    return kind in MANAGERS or (kind == "installer" and os.name != "nt")


def upgrade_hint(kind: str) -> str:
    if kind == "installer" and os.name == "nt":
        return f"irm {repository_url()}/releases/latest/download/install.ps1 | iex"
    return "champollion update"


def manager_command(kind: str, tag: str) -> list:
    """The package manager's own command, pinned to the release tag of the declared repository."""
    source = f"git+{repository_url()}.git@{tag}"
    if kind == "uv":
        return ["uv", "tool", "install", "--force", f"{PACKAGE} @ {source}"]
    if kind == "pipx":
        return ["pipx", "install", "--force", source]
    return [sys.executable, "-m", "pip", "install", "--upgrade", "--disable-pip-version-check", f"{PACKAGE} @ {source}"]


def _child_env() -> dict:
    return dict(os.environ, CHAMPOLLION_NO_UPDATE_CHECK="1")


def _run(run: Callable, command: list, temporary: Optional[Path] = None, **options: Any) -> Any:
    environment = _child_env()
    if temporary is not None:  # ensurepip on Python 3.9 leaves a cacert.pem in TMPDIR; keep it in ours
        environment.update(TMPDIR=str(temporary), TEMP=str(temporary), TMP=str(temporary))
    try:
        completed = run(command, env=environment, **options)
    except OSError as exc:
        raise ChampollionError(f"cannot run {command[0]}: {exc}", cause="update") from exc
    if completed.returncode:
        raise ChampollionError(f"{shlex.join(str(part) for part in command)} exited {completed.returncode}",
                               cause="update")
    return completed


def refuse_install(kind: str) -> None:
    """Name the way to update a copy that cannot update itself."""
    if can_self_update(kind):
        return
    if kind == "installer":
        raise ChampollionError(f"on Windows, update with the installer: {upgrade_hint(kind)}", cause="update")
    raise ChampollionError("this copy runs from a source checkout or a vendored snapshot; "
                           "update it with git pull or by vendoring a newer tag", cause="update")


def install(kind: str, version: str, tag: str, get: Callable = fetch, run: Optional[Callable] = None) -> dict:
    """Install a release the way this copy was installed."""
    import subprocess

    refuse_install(kind)
    if not is_newer(version) or parse_version(tag) != parse_version(version):
        raise ChampollionError(f"{tag!r} is not a newer stable release", cause="update")
    run = run or subprocess.run
    if kind in MANAGERS:
        command = manager_command(kind, tag)
        _run(run, command)
        return {"version": version, "command": shlex.join(command)}
    return install_release(installer_home(), version, tag, get, run)


# --- installer copies: verify, stage, swap, roll back ---------------------------

def base_python() -> str:
    """The interpreter the running venv was made from.

    A venv made by the venv's own ``bin/python`` would link back into ``<home>/venv`` and so point at itself
    after the swap; Python 3.9 reports that inner path as ``sys._base_executable``.
    """
    base = getattr(sys, "_base_executable", "") or ""
    inside = os.path.abspath(base).startswith(os.path.abspath(sys.prefix) + os.sep)
    return os.path.realpath(sys.executable) if not base or inside else base


def _wheel_and_digest(sums: str) -> tuple:
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) == 2 and _DIGEST.fullmatch(parts[0]) and _WHEEL.fullmatch(parts[1].lstrip("*")):
            return parts[1].lstrip("*"), parts[0].lower()
    raise ChampollionError("SHA256SUMS lists no champollion_protocol wheel; the release is incomplete",
                           cause="checksum")


def install_release(home: Optional[Path], version: str, tag: str, get: Callable = fetch,
                    run: Optional[Callable] = None) -> dict:
    """Verify the wheel against SHA256SUMS, stage a fresh venv, and only then swap it in, keeping one rollback."""
    import hashlib
    import subprocess

    if home is None:
        raise ChampollionError("this copy was not installed by install.sh", cause="update")
    run = run or subprocess.run
    base = release_base(tag)
    wheel_name, want = _wheel_and_digest(get(f"{base}/SHA256SUMS").decode("utf-8", "replace"))
    wheel = get(f"{base}/{wheel_name}")
    if hashlib.sha256(wheel).hexdigest() != want:
        raise ChampollionError(f"checksum mismatch for {wheel_name}; nothing was installed", cause="checksum")
    venv, previous, stage = home / "venv", home / "venv.previous", home / f"venv.tmp.{os.getpid()}"
    download = Path(tempfile.mkdtemp(prefix="champollion-update."))
    try:
        (download / wheel_name).write_bytes(wheel)
        shutil.rmtree(stage, ignore_errors=True)
        python = stage / "bin" / "python"
        _run(run, [base_python(), "-m", "venv", str(stage)], download)
        _run(run, [str(python), "-m", "pip", "install", "--no-index", "--disable-pip-version-check", "--quiet",
                   str(download / wheel_name)], download)
        probe = _run(run, [str(python), "-c", f'from importlib.metadata import version; print(version("{PACKAGE}"))'],
                     download, capture_output=True, text=True)
        staged = (probe.stdout or "").strip()
        if staged != version:
            raise ChampollionError(f"the downloaded wheel is version {staged or '?'}, not {version}", cause="update")
        _run(run, [str(python), "-m", "champollion", "--help"], download, stdout=subprocess.DEVNULL,
             stderr=subprocess.DEVNULL)
        # Swap last; one rollback copy is kept and the one before it goes.
        shutil.rmtree(previous, ignore_errors=True)
        venv.rename(previous)
        try:
            stage.rename(venv)
        except OSError as exc:
            previous.rename(venv)
            raise ChampollionError(f"cannot move the new version into place: {exc}", cause="update") from exc
        os.utime(previous)  # a missing marker falls back to this swap time
        try:  # retention observes the first successful run from the new environment
            from .retention import mark_pending_first_run
            mark_pending_first_run(home, version)
        except Exception:
            pass
    finally:
        shutil.rmtree(download, ignore_errors=True)
        shutil.rmtree(stage, ignore_errors=True)
    return {"version": version, "home": str(home), "rollback": str(previous)}


def rollback_install() -> dict:
    home = installer_home()
    if home is None or os.name == "nt":
        raise ChampollionError("only install.sh copies keep a previous version; reinstall an older release "
                               "with CHAMPOLLION_VERSION=x.y.z and the installer", cause="update")
    venv, previous, spare = home / "venv", home / "venv.previous", home / f"venv.rollback.{os.getpid()}"
    if not previous.is_dir():
        raise ChampollionError("no previous version is kept", cause="update")
    venv.rename(spare)
    try:
        previous.rename(venv)
    except OSError:
        spare.rename(venv)
        raise
    shutil.rmtree(spare, ignore_errors=True)
    try:  # a restored copy is current again, so no first run is pending
        from .retention import clear_pending_first_run
        clear_pending_first_run(home)
    except Exception:
        pass
    return {"restored": str(venv)}


def cleanup_staging(home: Path, min_age: float = STAGING_MAX_AGE) -> int:
    """Remove stale install staging and swap remnants without following symlinks."""
    base = Path(home)
    if base.is_symlink() or not base.is_dir():
        return 0
    now = time.time()
    removed = 0
    try:
        candidates = list(base.iterdir())
    except OSError:
        return 0
    for path in candidates:
        if not any(path.name.startswith(prefix) for prefix in STAGE_PREFIXES):
            continue
        try:
            if now - path.lstat().st_mtime < min_age:
                continue
            if path.is_symlink() or path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                continue
        except OSError:
            continue
        removed += 1
    return removed


def drop_rollback(ran_ok: bool) -> None:
    """Remove ``venv.previous`` once the new version has completed a command, or after 7 days at most.

    A swap that wrote ``venv.first-run.json`` is left to ``retention``, which takes the seven-day clock from
    the marker and counts only a successful run of the version the marker names.
    """
    home = installer_home()
    if home is None:
        return
    marker = home / FIRST_RUN_MARKER
    if marker.exists() or marker.is_symlink():
        return
    previous = home / "venv.previous"
    try:
        age = time.time() - previous.stat().st_mtime
    except OSError:
        return
    if ran_ok or age > ROLLBACK_MAX_AGE:
        shutil.rmtree(previous, ignore_errors=True)


# --- automatic installs ----------------------------------------------------------

def trim_log(path: Path, limit: int = LOG_LIMIT) -> None:
    """Keep the one log file within the limit by dropping its oldest half."""
    try:
        if path.stat().st_size <= limit // 2:
            return
        with open(path, "rb") as handle:
            handle.seek(-(limit // 2), os.SEEK_END)
            tail = handle.read()
        path.write_bytes(tail)
    except OSError:
        pass


def launch_auto_install(version: str) -> None:
    """Start one detached, low-priority install; its output goes to the bounded log."""
    import subprocess

    log = log_path()
    log.parent.mkdir(parents=True, exist_ok=True)
    trim_log(log)
    options: dict = {"stdin": subprocess.DEVNULL, "stderr": subprocess.STDOUT, "env": _child_env(),
                     "close_fds": True}
    if os.name == "nt":
        options["creationflags"] = (subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.DETACHED_PROCESS
                                    | subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        options["start_new_session"] = True
    save_state(auto_tried=version, auto_error="")
    descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        subprocess.Popen([sys.executable, "-m", "champollion", "update", "--auto-install"], stdout=descriptor,
                         **options)
    except OSError as exc:
        save_state(auto_error=_cause(exc))
    finally:
        os.close(descriptor)


def auto_install() -> int:
    """The detached worker: install the cached newer release without questions and record the outcome."""
    if hasattr(os, "nice"):
        try:
            os.nice(10)
        except OSError:
            pass
    state = load_state()
    version, tag = str(state.get("latest") or ""), str(state.get("tag") or "")
    if not state.get("auto") or not is_newer(version):
        return 0
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        install(detect_install_kind(), version, tag)
    except (ChampollionError, OSError) as exc:
        save_state(auto_error=_cause(exc))
        print(f"{stamp} automatic update to {version} failed: {exc}", flush=True)
        return 1
    finally:
        trim_log(log_path())
    save_state(auto_error="")
    print(f"{stamp} installed champollion {version}; it applies next run", flush=True)
    return 0


def skip_current() -> str:
    """Hide the notice for the release now available (the cached one, else a fresh check)."""
    state = load_state()
    if state.get("status") != "available":
        state = check_now()
    if state.get("status") == "failed":
        raise ChampollionError(f"update check failed: {state.get('cause')}", cause="update")
    latest = str(state.get("latest") or "") if state.get("status") == "available" else ""
    if latest:
        save_state(skip=latest)
    return latest


def ask(prompt: str) -> str:
    """Ask on stderr so stdout stays usable."""
    print(prompt, end="", file=sys.stderr, flush=True)
    return sys.stdin.readline().strip().lower()
