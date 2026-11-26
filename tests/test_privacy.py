"""Privacy regressions: no beacons, no default network calls, no world-readable text.

The checks are deliberately local: they scan shipped files for known telemetry
identifiers and endpoints, run the default CLI commands with sockets and process
spawning disabled, and assert the renderer and local-file permissions.
"""
from __future__ import annotations

import contextlib
import inspect
import io
import re
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from champollion import cli
from champollion.export import pdf as pdfmod
from champollion.sources import write_bytes_atomic

ROOT = Path(__file__).resolve().parent.parent

# Specific package names and endpoints, not the word "telemetry": the README and
# changelog say plainly that the toolkit has none.
FORBIDDEN = (
    r"\bsentry[_-]?sdk\b", r"\bposthog\b", r"\bsegment\.com\b", r"\bmixpanel\.com\b",
    r"\bgoogle-analytics\.com\b", r"\banalytics\.google\.com\b", r"\bgoogletagmanager\.com\b",
    r"\bdatadoghq\.com\b", r"\bopentelemetry\b", r"\bhuggingface_hub\b",
    r"\bfonts\.googleapis\.com\b", r"\bcdnjs\.cloudflare\.com\b", r"\bcdn\.jsdelivr\.net\b",
    r"\bunpkg\.com\b", r"\bgravatar\.com\b",
)
SCANNED = (
    ROOT / "pyproject.toml", ROOT / "README.md", ROOT / "Makefile",
    ROOT / "scripts/install.sh", ROOT / "scripts/install.ps1",
    *sorted((ROOT / "src").rglob("*.py")),
)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _call(argv):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return cli.main(argv)


class PrivacyTests(unittest.TestCase):
    def test_no_telemetry_packages_or_endpoints(self):
        for path in SCANNED:
            text = path.read_text(encoding="utf-8")
            for pattern in FORBIDDEN:
                self.assertIsNone(re.search(pattern, text, re.IGNORECASE),
                                  f"{path.relative_to(ROOT)} contains {pattern}")
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("dependencies = []", pyproject)
        for extra in ("fonttools", "brotli", "Pillow"):
            self.assertIn(extra, pyproject)

    def test_default_commands_open_no_socket_or_subprocess(self):
        with tempfile.TemporaryDirectory(prefix=".test-privacy-", dir=ROOT / "tests/fixtures") as tmp:
            project = Path(tmp) / "project"
            source = Path(tmp) / "source.txt"
            source.write_text("Sol super colles oritur.\n", encoding="utf-8")
            commands = (
                ["rules"],
                ["summary", "schema"],
                ["init", str(project)],
                ["profile", "validate", str(ROOT / "profiles/generic.json")],
                ["check", "--root", str(ROOT / "examples/latin-to-spanish")],
                ["report", "--root", str(ROOT / "examples/latin-to-spanish")],
                ["source", "add", "--id", "local", "--file", str(source), "--provider", "local",
                 "--edition", "test", "--revision", "r1", "--rights", "public-domain", "--root", str(project)],
                ["source", "add", "--id", "remote", "--url", "https://example.invalid/source",
                 "--provider", "local", "--edition", "test", "--revision", "r1",
                 "--rights", "public-domain", "--root", str(project)],
            )
            with contextlib.ExitStack() as stack:
                for target in ("socket.socket", "socket.create_connection",
                               "subprocess.Popen", "subprocess.run"):
                    stack.enter_context(mock.patch(target, side_effect=AssertionError(target)))
                for argv in commands:
                    # The --url form deliberately refuses to fetch and returns a usage failure.
                    expected = 2 if "--url" in argv else 0
                    self.assertEqual(_call(argv), expected, argv)

    def test_renderer_disables_background_networking(self):
        flags = pdfmod._chrome_args(Path("profile"), ("--print-to-pdf=book.pdf",))
        for flag in ("--disable-background-networking", "--disable-component-update",
                     "--disable-breakpad", "--disable-metrics", "--no-first-run",
                     "--host-resolver-rules=MAP * ~NOTFOUND"):
            self.assertIn(flag, flags)
        self.assertEqual(pdfmod._chrome_env()["DO_NOT_TRACK"], "1")
        self.assertIn("_chrome_args(", inspect.getsource(pdfmod._print))
        self.assertIn("_chrome_args(", inspect.getsource(pdfmod._screenshot))

    def test_toolkit_written_text_is_owner_only(self):
        with tempfile.TemporaryDirectory(prefix=".test-privacy-", dir=ROOT / "tests/fixtures") as tmp:
            project = Path(tmp) / "project"
            self.assertEqual(_call(["init", str(project)]), 0)
            for directory in ("works", "profiles", "sources"):
                self.assertEqual(_mode(project / directory), 0o700, directory)
            for name in ("champollion.json", "profiles/generic.json", "sources/manifest.json"):
                self.assertEqual(_mode(project / name), 0o600, name)
            target = project / "sources/raw/deep/snapshot.source"
            write_bytes_atomic(target, b"text")
            self.assertEqual(_mode(target.parent), 0o700)
            self.assertEqual(_mode(target), 0o600)

    def test_readme_states_privacy_in_plain_language(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Privacy", readme)
        section = readme.split("## Privacy", 1)[1].split("\n## ", 1)[0]
        # Short and confident in the README (at most 6 lines); every detail lives in PRIVACY.md.
        self.assertLessEqual(len([line for line in section.splitlines() if line.strip()]), 6)
        for phrase in ("no telemetry", "update check", "privacy.md"):
            self.assertIn(phrase, section.lower())
        privacy = (ROOT / "PRIVACY.md").read_text(encoding="utf-8").lower()
        for phrase in ("no telemetry", "0600", "0700", "removing everything", "reviewers and model providers"):
            self.assertIn(phrase, privacy)


if __name__ == "__main__":
    unittest.main()
