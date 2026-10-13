"""Owned-path scratch projects for real runtime tests (no mocked core APIs)."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

FIXTURES = Path(__file__).resolve().parent
REPO = FIXTURES.parent.parent
TODAY = "2026-01-02"


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def tree_state(root):
    """Observe file bytes and modification times, plus directory membership."""
    return {p.relative_to(root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
            if p.is_file() else None for p in Path(root).rglob("*")}


class ProjectCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".test-", dir=FIXTURES)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        shutil.copytree(FIXTURES / "clean", self.root)
        self.work_path = self.root / "works/synthetic.md"

    def settings(self):
        return json.loads((self.root / "profile.json").read_text())

    def profile(self, **checks):
        from champollion.profile import validate_profile
        settings = self.settings()
        settings["checks"].update(checks)
        return validate_profile(settings, str(self.root / "profile.json"))

    def work(self):
        from champollion.format import parse_work
        return parse_work(self.work_path)

    def sources(self):
        from champollion.sources import load_sources
        return load_sources(str(self.root), [self.work()])

    def context(self, profile=None, **kwargs):
        from champollion.checks import Context
        work = self.work()
        original = work.section("Original")
        locations = {u.title: u.line for u in original.units} if original else {}
        return Context(work, profile or self.profile(), str(self.root), TODAY,
                       self.sources(), locations, **kwargs)

    def change_text(self, old, new):
        text = self.work_path.read_text()
        if old not in text:
            raise AssertionError("test mutation did not match fixture")
        self.work_path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def record(self, **changes):
        path = self.root / "sources/manifest.json"
        obj = json.loads(path.read_text())
        obj["records"][0].update(changes)
        write_json(path, obj)
        return obj["records"][0]

    def replace_units(self, original, musean, plain):
        """Write actual Markdown and snapshot bytes for exact-ratio tests."""
        text = self.work_path.read_text().split("\n## ", 1)[0]
        source = "\n\n".join(f"### {title}\n\n{body}" for title, body in original) + "\n"
        for label, units in (("Original", original), ("Mouseia translation", musean),
                             ("Plain English translation", plain)):
            text += f"\n## {label}\n\n" + "\n\n".join(f"### {title}\n\n{body}" for title, body in units) + "\n"
        self.work_path.write_text(text, encoding="utf-8")
        raw = self.root / "sources/raw/synthetic.txt"
        raw.write_bytes(source.encode("utf-8"))
        self.record(sha256=hashlib.sha256(raw.read_bytes()).hexdigest())

    def report(self, profile=None, today=TODAY):
        from champollion.report import build_report
        return build_report([self.work_path], profile or self.profile(), str(self.root), today)


def codes(findings):
    return [f.code for f in findings]
