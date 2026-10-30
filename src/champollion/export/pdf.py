"""PDF through headless Chrome/Chromium (the only external engine; located explicitly, never downloaded)."""
from __future__ import annotations

import datetime
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


def _run(args: List[str], timeout: int, output: Optional[Path] = None) -> None:
    """Run Chrome in its own process group so a hang takes its helper processes down with it."""
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        _, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        try:
            proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            pass
        raise ChampollionError(f"chrome did not finish within {timeout}s", cause="ENGINE-TIMEOUT")
    if proc.returncode != 0:
        # Under heavy load macOS Chrome can exit 2 while tearing down (a CVDisplayLink error) after it has written its
        # output and said so. That output is complete; anything else is a real failure.
        text = stderr.decode("utf-8", "replace")
        if output is not None and output.is_file() and output.stat().st_size > 1000 \
                and re.search(r"bytes written to file \S*" + re.escape(output.name), text):
            return
        raise ChampollionError(f"chrome exited {proc.returncode}: {stderr.decode('utf-8', 'replace')[-400:]}", cause="ENGINE-FAILED")


RETRIED = ("ENGINE-TIMEOUT", "ENGINE-FAILED")


def html_to_pdf(html_text: str, out_pdf: str, chrome: str, timeout: int = 600, attempts: int = 2) -> None:
    """Print to PDF. Chrome occasionally stalls on a layout pass or exits abnormally under load (exit 2 with a
    CVDisplayLink error on macOS), so one more attempt is made before the named error is raised."""
    for attempt in range(1, attempts + 1):
        try:
            return _print(html_text, out_pdf, chrome, timeout)
        except ChampollionError as exc:
            if exc.cause not in RETRIED or attempt == attempts:
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
              f"--print-to-pdf={tmp_pdf}", page.as_uri()], timeout, tmp_pdf)
        if not tmp_pdf.is_file() or tmp_pdf.stat().st_size < 1000:
            raise ChampollionError("chrome produced no PDF", cause="ENGINE-FAILED")
        _normalize_chrome_dates(tmp_pdf)
        Path(out_pdf).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp_pdf), out_pdf)


def _normalize_chrome_dates(pdf: Path) -> None:
    """Replace Chrome's Info dates with the Unix epoch, preserving all byte offsets.

    Only Chrome's classic, single-revision PDF and simple Info dictionary are
    accepted. An unfamiliar representation is an error, not a guessed replacement.
    """
    data = pdf.read_bytes()

    def bad() -> None:
        raise ChampollionError(f"{pdf}: unsupported or malformed Chrome PDF metadata", cause="ENGINE-PDF-METADATA")

    end = re.search(rb"startxref\s+(\d+)\s+%%EOF\s*$", data)
    if not data.startswith(b"%PDF-") or not end:
        raise ChampollionError(f"{pdf}: incomplete Chrome PDF", cause="ENGINE-FAILED")
    xref_at = int(end.group(1))
    if xref_at >= end.start() or not data.startswith(b"xref\n", xref_at):
        raise ChampollionError(f"{pdf}: missing Chrome PDF xref", cause="ENGINE-FAILED")
    trailer = re.compile(rb"trailer\s*<<(.*?)>>\s*startxref\s+\d+\s+%%EOF\s*$", re.S).search(data, xref_at)
    if not trailer or re.search(rb"/(?:Prev|XRefStm)\b", trailer.group(1)):
        bad()
    info = re.findall(rb"/Info\s+(\d+)\s+(\d+)\s+R\b", trailer.group(1))
    if len(info) != 1:
        bad()
    number, generation = map(int, info[0])
    table = data[xref_at + 5:trailer.start()]
    lines = table.splitlines()
    entries = []
    i = 0
    while i < len(lines):
        header = re.fullmatch(rb"(\d+)\s+(\d+)\s*", lines[i])
        if not header:
            bad()
        first, count = map(int, header.groups())
        i += 1
        if count > len(lines) - i:
            bad()
        for n in range(first, first + count):
            entry = re.fullmatch(rb"(\d{10})\s+(\d{5})\s+([nf])\s*", lines[i])
            if not entry:
                bad()
            if n == number:
                entries.append(entry.groups())
            i += 1
    if len(entries) != 1 or int(entries[0][1]) != generation or entries[0][2] != b"n":
        bad()
    obj_at = int(entries[0][0])
    if obj_at >= xref_at:
        bad()
    obj = re.compile(rb"%d\s+%d\s+obj\s*<<((?:(?!\bendobj\b).)*?)>>\s*endobj\b"
                     % (number, generation), re.S).match(data, obj_at, xref_at)
    if not obj:
        bad()
    dictionary = obj.group(1)
    base = obj.start(1)
    # Scan strings so a title containing '/CreationDate' is not treated as a key.
    pos = 0
    dates = {}
    while pos < len(dictionary):
        ws = re.match(rb"\s*", dictionary[pos:])
        pos += ws.end()
        if pos == len(dictionary):
            break
        key = re.match(rb"/([A-Za-z]+)\s*", dictionary[pos:])
        if not key:
            bad()
        name = key.group(1)
        pos += key.end()
        start = pos
        if pos < len(dictionary) and dictionary[pos] == 40:
            pos += 1
            depth = 1
            while pos < len(dictionary) and depth:
                char = dictionary[pos]
                if char == 92:
                    pos += 2
                    continue
                depth += (char == 40) - (char == 41)
                pos += 1
            if depth:
                bad()
        elif pos < len(dictionary) and dictionary[pos] == 60:
            close = dictionary.find(b">", pos + 1)
            if close < 0 or not re.fullmatch(rb"[0-9A-Fa-f\s]*", dictionary[pos + 1:close]):
                bad()
            pos = close + 1
        else:
            bad()
        if name in (b"CreationDate", b"ModDate"):
            if name in dates:
                bad()
            dates[name] = (start, pos)
    if len(dates) != 2:
        bad()
    result = bytearray(data)
    for start, stop in dates.values():
        value = dictionary[start:stop]
        match = re.fullmatch(rb"\(D:(\d{14})(Z|[+-]\d{2}'\d{2}')?\)", value)
        if not match:
            bad()
        try:
            datetime.datetime.strptime(match.group(1).decode("ascii"), "%Y%m%d%H%M%S")
        except ValueError:
            bad()
        zone = match.group(2) or b""
        if len(zone) > 1 and (int(zone[1:3]) > 23 or int(zone[4:6]) > 59):
            bad()
        replacement = b"(D:19700101000000" + (b"+00'00'" if len(zone) > 1 else zone) + b")"
        if len(replacement) != stop - start:
            bad()
        result[base + start:base + stop] = replacement
    pdf.write_bytes(result)


def html_to_png(html_text: str, chrome: str, width: int, height: int, scale: float = 2.5, timeout: int = 120,
                attempts: int = 2) -> bytes:
    for attempt in range(1, attempts + 1):
        try:
            return _screenshot(html_text, chrome, width, height, scale, timeout)
        except ChampollionError as exc:
            if exc.cause not in RETRIED or attempt == attempts:
                raise
    raise AssertionError("unreachable")


def _screenshot(html_text: str, chrome: str, width: int, height: int, scale: float, timeout: int) -> bytes:
    with tempfile.TemporaryDirectory(prefix="champollion-") as tmp:
        page = Path(tmp) / "cover.html"
        page.write_text(html_text, "utf-8")
        tmp_png = Path(tmp) / "cover.png"
        _run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run", "--hide-scrollbars",
              f"--user-data-dir={Path(tmp) / 'profile'}", "--allow-file-access-from-files", f"--window-size={width},{height}",
              f"--force-device-scale-factor={scale}", "--virtual-time-budget=20000", f"--screenshot={tmp_png}", page.as_uri()], timeout, tmp_png)
        if not tmp_png.is_file():
            raise ChampollionError("chrome produced no screenshot", cause="ENGINE-FAILED")
        return tmp_png.read_bytes()


def require_poppler() -> None:
    """Name a missing poppler tool before any Chrome time is spent."""
    for tool in ("pdfinfo", "pdftotext"):
        if not shutil.which(tool):
            raise ChampollionError(f"{tool} (poppler) not found; it numbers the contents and counts pages", cause="ENGINE-MISSING")


def _poppler(tool: str, *args: str) -> str:
    exe = shutil.which(tool)
    if not exe:
        raise ChampollionError(f"{tool} (poppler) not found", cause="ENGINE-MISSING")
    proc = subprocess.run([exe, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise ChampollionError(f"{tool} failed: {proc.stderr.decode('utf-8', 'replace')[-300:]}", cause="ENGINE-FAILED")
    return proc.stdout.decode("utf-8", "replace")


def pdf_pages(pdf: str) -> int:
    match = re.search(r"^Pages:\s+(\d+)", _poppler("pdfinfo", pdf), re.M)
    if not match:
        raise ChampollionError(f"pdfinfo reported no page count for {pdf}", cause="ENGINE-FAILED")
    return int(match.group(1))


def locate_markers(pdf: str, count: int) -> Dict[int, int]:
    """Page number of each ``§§U<i>§§`` marker, via poppler's pdftotext."""
    text = _poppler("pdftotext", "-layout", pdf, "-")
    found: Dict[int, int] = {}
    for page, chunk in enumerate(text.split("\f"), 1):
        for m in re.finditer(r"§§U(\d+)§§", chunk):
            # Chrome can also paint a positioned marker at the foot of the page before a forced break; the last sighting is the real one.
            found[int(m.group(1))] = page
    return found


def locate_body(pdf: str) -> int:
    """PDF page where the text begins. Only text pages print a folio, and a probe prints the PDF page number as
    that folio, so the first page ending on its own number is the first page of text."""
    for page, chunk in enumerate(_poppler("pdftotext", "-layout", pdf, "-").split("\f"), 1):
        lines = [ln for ln in re.sub("[\u202a-\u202e\u2066-\u2069]", "", chunk).split("\n") if ln.strip()]  # bidi controls wrap folios on right-to-left books
        if page > 2 and lines and lines[-1].strip() == str(page):
            return page
    raise ChampollionError(f"no printed folio found in {pdf}", cause="ENGINE-FAILED")


def check_folio(pdf: str, offset: int) -> None:
    """The first page of text must print the folio 1, whichever path produced the PDF."""
    if offset <= 0:
        return
    texts = _poppler("pdftotext", "-layout", pdf, "-").split("\f")
    lines = [ln for ln in re.sub("[\u202a-\u202e\u2066-\u2069]", "", texts[offset] if offset < len(texts) else "").split("\n") if ln.strip()]
    if not lines or lines[-1].strip() != "1":
        raise ChampollionError(f"{pdf}: page {offset + 1} should be the first page of text and print folio 1, found {lines[-1].strip() if lines else 'nothing'!r}", cause="ENGINE-FAILED")


def page_texts(pdf: str) -> List[str]:
    """Plain text of every page (index 0 = page 1)."""
    return _poppler("pdftotext", "-layout", pdf, "-").split("\f")


def _pdf_text(value: str) -> bytes:
    return b"<" + ("\ufeff" + value).encode("utf-16-be").hex().upper().encode() + b">"


def set_info(pdf: str, info: Dict[str, str]) -> None:
    """Write the document information (title, author, subject, keywords, creator) as an incremental update.
    Chrome records only a title. Only classic cross-reference tables are handled; anything else is named."""
    data = Path(pdf).read_bytes()
    tail = data[-2048:]
    start = re.search(rb"startxref\s+(\d+)\s+%%EOF\s*$", tail)
    trailer = re.search(rb"trailer\s*<<(.*?)>>\s*startxref", tail, re.S)
    if not start or not trailer:
        raise ChampollionError(f"{pdf}: no classic PDF trailer to add document information to", cause="ENGINE-FAILED")
    size = re.search(rb"/Size\s+(\d+)", trailer.group(1))
    root = re.search(rb"/Root\s+(\d+\s+\d+\s+R)", trailer.group(1))
    if not size or not root:
        raise ChampollionError(f"{pdf}: PDF trailer lacks /Size or /Root", cause="ENGINE-FAILED")
    num = int(size.group(1))
    body = b"".join(b"/" + key.encode() + b" " + _pdf_text(value) + b"\n" for key, value in info.items() if value)
    obj_at = len(data) + 1
    update = b"\n%d 0 obj\n<<\n%s>>\nendobj\n" % (num, body)
    xref_at = len(data) + len(update)
    update += (b"xref\n%d 1\n%010d 00000 n \ntrailer\n<</Size %d /Root %s /Info %d 0 R /Prev %s>>\nstartxref\n%d\n%%%%EOF\n"
               % (num, obj_at, num + 1, root.group(1), num, start.group(1), xref_at))
    Path(pdf).write_bytes(data + update)


def check_overflow(pdf: str) -> None:
    """The print page's overflow probe stamps a flag naming any line too wide for the page (typeset.OVERFLOW_PROBE)."""
    text = _poppler("pdftotext", "-l", "3", pdf, "-")
    m = re.search(r"§§OVERFLOW§§ ?(.*)", text)
    if m:
        raise ChampollionError(f"{pdf}: a line is wider than the page and would be clipped: {m.group(1)[:200]!r}", cause="PAGE-OVERFLOW")


def check_scale(pdf: str, page: int = 2, width_pt: float = 432.0) -> None:
    """Chrome silently shrinks the whole book when any line is wider than the page. The title page is centred, so its
    text must be centred on the page; a shrunken book is refused by name."""
    xs = [(float(a), float(b)) for a, b in re.findall(
        r'<word xMin="([\d.]+)" yMin="[\d.]+" xMax="([\d.]+)"', _poppler("pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf, "-"))]
    if not xs:
        return
    centre = (min(a for a, _ in xs) + max(b for _, b in xs)) / 2
    if abs(centre - width_pt / 2) > 8:
        raise ChampollionError(
            f"{pdf}: pages are scaled down (title page centred at {centre:.0f}pt, not {width_pt / 2:.0f}pt): "
            "some line is wider than the page", cause="PAGE-OVERFLOW")
