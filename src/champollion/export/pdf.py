"""PDF through headless Chrome/Chromium (the only external engine; located explicitly, never downloaded)."""
from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from ..findings import ChampollionError

CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome",
)


def find_chrome(explicit: Optional[str] = None) -> str:
    """Resolve the Chrome binary: --chrome, $CHAMPOLLION_CHROME, then well-known locations."""
    for candidate in (explicit, os.environ.get("CHAMPOLLION_CHROME"), *CANDIDATES):
        if not candidate:
            continue
        found = candidate if os.path.isabs(candidate) and os.access(candidate, os.X_OK) else shutil.which(candidate)
        if found:
            return found
    raise ChampollionError("no Chrome/Chromium found; pass --chrome or set CHAMPOLLION_CHROME", cause="ENGINE-MISSING")


def _run(args: List[str], timeout: int) -> None:
    """Run Chrome in its own process group so a hang takes its helper processes down with it."""
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        _, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate()
        raise ChampollionError(f"chrome did not finish within {timeout}s", cause="ENGINE-TIMEOUT")
    finally:
        try:  # helpers that outlive a clean exit
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    if proc.returncode != 0:
        raise ChampollionError(f"chrome exited {proc.returncode}: {stderr.decode('utf-8', 'replace')[-400:]}", cause="ENGINE-FAILED")


def html_to_pdf(html_text: str, out_pdf: str, chrome: str, timeout: int = 600, attempts: int = 3) -> None:
    """Print to PDF; Chrome occasionally stalls on a layout pass, so a timeout is retried."""
    for attempt in range(1, attempts + 1):
        try:
            return _print(html_text, out_pdf, chrome, timeout)
        except ChampollionError as exc:
            if exc.cause != "ENGINE-TIMEOUT" or attempt == attempts:
                raise


def _print(html_text: str, out_pdf: str, chrome: str, timeout: int) -> None:
    with tempfile.TemporaryDirectory(prefix="champollion-") as tmp:
        page = Path(tmp) / "book.html"
        page.write_text(html_text, "utf-8")
        profile = Path(tmp) / "profile"
        tmp_pdf = Path(tmp) / "book.pdf"
        _run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run", "--hide-scrollbars",
              f"--user-data-dir={profile}", "--no-pdf-header-footer", "--allow-file-access-from-files",
              "--virtual-time-budget=120000", "--run-all-compositor-stages-before-draw",
              f"--print-to-pdf={tmp_pdf}", page.as_uri()], timeout)
        if not tmp_pdf.is_file() or tmp_pdf.stat().st_size < 1000:
            raise ChampollionError("chrome produced no PDF", cause="ENGINE-FAILED")
        Path(out_pdf).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp_pdf), out_pdf)


def html_to_png(html_text: str, chrome: str, width: int, height: int, scale: float = 2.5, timeout: int = 120) -> bytes:
    with tempfile.TemporaryDirectory(prefix="champollion-") as tmp:
        page = Path(tmp) / "cover.html"
        page.write_text(html_text, "utf-8")
        tmp_png = Path(tmp) / "cover.png"
        _run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run", "--hide-scrollbars",
              f"--user-data-dir={Path(tmp) / 'profile'}", "--allow-file-access-from-files", f"--window-size={width},{height}",
              f"--force-device-scale-factor={scale}", "--virtual-time-budget=20000", f"--screenshot={tmp_png}", page.as_uri()], timeout)
        if not tmp_png.is_file():
            raise ChampollionError("chrome produced no screenshot", cause="ENGINE-FAILED")
        return tmp_png.read_bytes()


def pdf_pages(pdf: str) -> int:
    exe = shutil.which("pdfinfo")
    if not exe:
        raise ChampollionError("pdfinfo (poppler) not found", cause="ENGINE-MISSING")
    out = subprocess.run([exe, pdf], stdout=subprocess.PIPE, check=True).stdout.decode("utf-8", "replace")
    return int(re.search(r"^Pages:\s+(\d+)", out, re.M).group(1))


def locate_markers(pdf: str, count: int) -> Dict[int, int]:
    """Page number of each ``§§U<i>§§`` marker, via poppler's pdftotext (optional)."""
    exe = shutil.which("pdftotext")
    if not exe:
        return {}
    text = subprocess.run([exe, "-layout", pdf, "-"], stdout=subprocess.PIPE, check=True).stdout.decode("utf-8", "replace")
    found: Dict[int, int] = {}
    for page, chunk in enumerate(text.split("\f"), 1):
        for m in re.finditer(r"§§U(\d+)§§", chunk):
            found.setdefault(int(m.group(1)), page)
    return found
