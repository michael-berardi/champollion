"""Offline tests for the anonymous release check, notice and opt-in install.

No test opens a socket or runs a real installer: release records, downloads and
prompts are fixtures. The daily cache, preferences and install log are redirected
into a temporary directory inside the repository.
"""
from __future__ import annotations

import builtins
import contextlib
import hashlib
import io
import json
import os
import stat
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import URLError

from champollion import cli, updates

ROOT = Path(__file__).resolve().parent.parent
REPOSITORY = "https://github.com/example-owner/example-tool"


class FakeTTY:
    def isatty(self):
        return True


class FakeTTYOut(io.StringIO):
    def isatty(self):
        return True


def release(tag="v1.11.0", *, draft=False, prerelease=False, body="First note.\nSecond note."):
    return {"tag_name": tag, "draft": draft, "prerelease": prerelease, "body": body,
            "html_url": "https://github.com/example-owner/example-tool/releases/tag/" + tag,
            "assets": [
                {"name": "SHA256SUMS", "browser_download_url": "https://invalid.test/SHA256SUMS"},
                {"name": "champollion_protocol-1.11.0-py3-none-any.whl",
                 "browser_download_url": "https://invalid.test/wheel.whl"},
            ]}


class UpdateCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".test-updates-", dir=ROOT / "tests/fixtures")
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        env = {
            "CHAMPOLLION_CONFIG_DIR": str(base / "config"),
            "CHAMPOLLION_CACHE_DIR": str(base / "cache"),
            "CHAMPOLLION_NO_UPDATE_CHECK": "",
            "CHAMPOLLION_AGENT": "", "AGENT_MODE": "", "CLAUDECODE": "",
            "CODEX_CLI": "", "PI_AGENT": "", "ANTIGRAVITY_AGENT": "", "DSH_AGENT": "",
            "CI": "", "NO_COLOR": "1",
        }
        patch = mock.patch.dict(os.environ, env)
        patch.start()
        self.addCleanup(patch.stop)


class VersionTests(UpdateCase):
    def test_only_stable_semver_is_newer(self):
        self.assertEqual(updates.parse_version("v1.2.3"), (1, 2, 3))
        self.assertIsNone(updates.parse_version("1.2"))
        self.assertIsNone(updates.parse_version("v1.2.3-rc.1"))
        self.assertIsNone(updates.parse_version("nightly"))
        self.assertEqual(updates.compare_versions("v1.10.0", "1.9.1"), 1)
        self.assertEqual(updates.compare_versions("1.9.1", "v1.9.1"), 0)
        self.assertEqual(updates.compare_versions("1.9.0", "1.9.1"), -1)
        self.assertIsNone(updates.compare_versions("1.9.1-beta", "1.9.1"))
        self.assertIsNone(updates.compare_versions("not-a-version", "1.9.1"))


class CheckTests(UpdateCase):
    def test_one_anonymous_get_with_fixed_user_agent_and_short_timeout(self):
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["agent"] = request.get_header("User-agent")
            seen["timeout"] = timeout
            seen["data"] = request.data
            return io.BytesIO(json.dumps(release()).encode("utf-8"))

        result = updates.check_now(repository=REPOSITORY, opener=opener, timeout=3.0, current="1.9.1")
        self.assertEqual(result["status"], "update")
        self.assertEqual(result["latest"], "1.11.0")
        self.assertEqual(seen["url"], "https://api.github.com/repos/example-owner/example-tool/releases/latest")
        self.assertEqual(seen["agent"], "champollion-update-check")
        self.assertEqual(seen["data"], None)
        self.assertLessEqual(seen["timeout"], 4.0)
        self.assertEqual(seen["url"].count("?"), 0)

    def test_drafts_prereleases_garbage_and_equal_versions_are_not_newer(self):
        for tag, flags in (("v2.0.0", {"draft": True}), ("v2.0.0", {"prerelease": True}),
                           ("nightly", {}), ("1.9.1", {}), ("1.8.0", {})):
            payload = release(tag, **flags)
            result = updates.check_now(repository=REPOSITORY,
                                        opener=lambda request, timeout, p=payload: io.BytesIO(json.dumps(p).encode()),
                                        current="1.9.1")
            self.assertEqual(result["status"], "current", (tag, flags))

    def test_failure_is_cached_owner_only_and_shown_by_check(self):
        def failed(request, timeout):
            raise URLError("offline")

        result = updates.check_now(repository=REPOSITORY, opener=failed)
        self.assertEqual(result["status"], "failed")
        self.assertIn("offline", result["cause"])
        updates.record_check(result)
        cache = updates.load_cache()
        self.assertEqual(cache["last_error_stage"], "check")
        self.assertIn("offline", updates.report_text(result))
        self.assertFalse(updates.automatic_check_due(cache))
        path = updates.cache_path()
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)

    def test_interactive_default_and_all_off_switches(self):
        config = updates.load_config()
        self.assertTrue(config["check"])
        self.assertFalse(config["auto"])
        self.assertTrue(updates.check_allowed(["rules"], config, FakeTTY(), FakeTTY()))
        for argv, env, out, err, cfg in (
            (["rules", "--json"], {}, FakeTTY(), FakeTTY(), config),
            (["rules"], {"CI": "1"}, FakeTTY(), FakeTTY(), config),
            (["rules"], {"CHAMPOLLION_AGENT": "1"}, FakeTTY(), FakeTTY(), config),
            (["rules"], {"CHAMPOLLION_NO_UPDATE_CHECK": "1"}, FakeTTY(), FakeTTY(), config),
            (["rules"], {}, io.StringIO(), FakeTTY(), config),
            (["rules"], {}, FakeTTY(), io.StringIO(), config),
            (["rules"], {}, FakeTTY(), FakeTTY(), dict(config, check=False)),
            (["update"], {}, FakeTTY(), FakeTTY(), config),
        ):
            with self.subTest(argv=argv, env=env):
                with mock.patch.dict(os.environ, env):
                    self.assertFalse(updates.check_allowed(argv, cfg, out, err))

    def test_notice_frequency_skip_and_newer_version(self):
        result = updates.check_now(repository=REPOSITORY,
                                   opener=lambda request, timeout: io.BytesIO(json.dumps(release()).encode()),
                                   current="1.9.1")
        first, second = updates.notice_lines(result["latest"], result["current"])
        self.assertEqual(first, "champollion 1.11.0 available (you have 1.9.1) · run: champollion update")
        self.assertIn("update --auto on", second)
        self.assertIn("update --skip", second)
        self.assertTrue(updates.should_show_notice(result, now=1000.0))
        updates.record_shown("1.11.0", at=1000.0)
        self.assertFalse(updates.should_show_notice(result, now=1000.0 + updates.DAY_SECONDS - 1))
        self.assertTrue(updates.should_show_notice(result, now=1000.0 + updates.DAY_SECONDS))
        updates.skip_version("1.11.0")
        self.assertFalse(updates.should_show_notice(result, now=1000.0 + updates.DAY_SECONDS))
        newer = dict(result, latest="1.12.0")
        self.assertTrue(updates.should_show_notice(newer, now=1000.0 + updates.DAY_SECONDS))

    def test_auto_and_check_preferences_persist(self):
        self.assertEqual(updates.set_auto("on")["auto"], True)
        self.assertTrue(updates.load_config()["auto"])
        self.assertTrue(updates.load_config()["auto_prompted"])
        self.assertEqual(updates.set_auto("off")["auto"], False)
        self.assertFalse(updates.load_config()["auto"])
        updates.set_check(False)
        self.assertFalse(updates.load_config()["check"])

    def test_background_check_does_not_run_for_json_or_twice_daily(self):
        result = updates.check_now(repository=REPOSITORY,
                                   opener=lambda request, timeout: io.BytesIO(json.dumps(release()).encode()),
                                   current="1.9.1")
        result["checked_at"] = time.time()
        updates.record_check(result)
        with mock.patch.object(updates, "check_now") as fetch:
            updates.finish_background_check(["rules", "--json"], 0)
            updates.finish_background_check(["rules"], 0)
            fetch.assert_not_called()

    def test_auto_install_success_suppresses_notice(self):
        result = {"status": "update", "current": "1.9.1", "latest": "1.11.0", "notes": "",
                  "checked_at": 1000.0, "cause": "", "assets": []}
        stderr = io.StringIO()
        with mock.patch.object(updates, "check_allowed", return_value=True), \
             mock.patch.object(updates, "load_config", return_value={"check": True, "auto": True}), \
             mock.patch.object(updates, "automatic_check_due", return_value=True), \
             mock.patch.object(updates, "check_now", return_value=result), \
             mock.patch.object(updates, "record_check"), \
             mock.patch.object(updates, "auto_install") as install, \
             mock.patch.object(updates, "load_cache", return_value={"last_install": {"ok": True}}), \
             contextlib.redirect_stderr(stderr):
            updates.finish_background_check(["rules"], 0)
        install.assert_called_once_with(result)
        self.assertEqual(stderr.getvalue(), "")


class InstallTests(UpdateCase):
    def test_checksum_mismatch_refuses_before_any_swap(self):
        sums = "abc " + "0" * 64 + "  SHA256SUMS\n"
        wheel = "b" * 32
        name = "champollion_protocol-1.11.0-py3-none-any.whl"
        with self.assertRaises(updates.ChampollionError) as caught:
            updates.verify_wheel(wheel.encode(), name, sums)
        self.assertEqual(caught.exception.cause, "checksum")
        self.assertIn("no checksum", str(caught.exception))
        bad = "0" * 64 + "  " + name + "\n"
        with self.assertRaises(updates.ChampollionError) as caught:
            updates.verify_wheel(wheel.encode(), name, bad)
        self.assertEqual(caught.exception.cause, "checksum")
        self.assertIn("nothing was installed", str(caught.exception))
        good = hashlib.sha256(wheel.encode()).hexdigest() + "  " + name + "\n"
        self.assertIsNone(updates.verify_wheel(wheel.encode(), name, good))

    def test_package_managers_are_named_not_overwritten(self):
        result = {"latest": "1.11.0"}
        with mock.patch.object(updates, "_installer_managed", return_value=False), \
             mock.patch.object(updates, "_package_manager", return_value="uv"):
            self.assertEqual(updates.install_plan(result)["command"], "uv tool upgrade champollion-protocol")
        with mock.patch.object(updates, "_installer_managed", return_value=False), \
             mock.patch.object(updates, "_package_manager", return_value="pip"):
            plan = updates.install_plan(result)
        self.assertIn("champollion-protocol @ git+", plan["command"])
        self.assertIn("@v1.11.0", plan["command"])

    def test_atomic_swap_keeps_one_rollback_and_restores_it(self):
        home = Path(self.temp.name) / "install-home"
        current, staged, previous = home / "venv", home / "venv.next", home / "venv.previous"
        current.mkdir(parents=True)
        (current / "old.txt").write_text("new", encoding="utf-8")
        staged.mkdir()
        (staged / "new.txt").write_text("newer", encoding="utf-8")
        updates.swap_directories(current, staged, previous)
        self.assertEqual((current / "new.txt").read_text(), "newer")
        self.assertEqual((previous / "old.txt").read_text(), "new")
        restored = updates.rollback(home)
        self.assertTrue(restored["ok"])
        self.assertEqual((current / "old.txt").read_text(), "new")
        self.assertEqual((previous / "new.txt").read_text(), "newer")
        self.assertFalse(updates.load_cache()["last_error"])


class CliTests(UpdateCase):
    def test_update_check_exit_codes_json_and_report_only(self):
        result = {"status": "update", "current": "1.9.1", "latest": "1.11.0", "tag": "v1.11.0",
                  "notes": "First note.", "url": "https://invalid.test/release", "assets": [],
                  "cause": "", "checked_at": 1000.0}
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(updates, "check_now", return_value=result), \
             contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = cli.main(["update", "--check", "--json"])
        self.assertEqual(status, updates.UPDATE_EXIT)
        self.assertEqual(json.loads(stdout.getvalue())["latest"], "1.11.0")
        self.assertEqual(stderr.getvalue(), "")
        with mock.patch.object(updates, "check_now", return_value=dict(result, status="current")):
            self.assertEqual(cli.main(["update", "--check"]), 0)
        with mock.patch.object(updates, "check_now", return_value=dict(result, status="failed", latest="",
                                                                        cause="offline")):
            self.assertEqual(cli.main(["update", "--check"]), 1)

    def test_update_prompt_installs_and_never_asks_auto_twice(self):
        result = {"status": "update", "current": "1.9.1", "latest": "1.11.0", "tag": "v1.11.0",
                  "notes": "First note.", "url": "https://invalid.test/release", "assets": [],
                  "cause": "", "checked_at": 1000.0}
        outcome = {"ok": True, "kind": "installer", "version": "1.11.0", "cause": "", "at": 1000.0}
        stdout, stderr = FakeTTYOut(), io.StringIO()
        answers = iter(["", "n"])

        def answer(prompt):
            print(prompt, end="", file=stdout)
            return next(answers)

        with mock.patch.object(updates, "check_now", return_value=result), \
             mock.patch.object(updates, "install_plan", return_value={"kind": "installer", "command": "", "argv": []}), \
             mock.patch.object(updates, "install_release", return_value=outcome) as install, \
             mock.patch.object(updates, "log_install"), \
             mock.patch.object(builtins, "input", side_effect=answer), \
             mock.patch("sys.stdin", FakeTTY()), \
             contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = cli.main(["update"])
        self.assertEqual(status, 0)
        install.assert_called_once()
        self.assertIn("Install 1.11.0 now? [Y/n]", stdout.getvalue())
        self.assertIn("Install future updates automatically? [y/N]", stdout.getvalue())
        self.assertFalse(updates.load_config()["auto"])
        self.assertTrue(updates.load_config()["auto_prompted"])

    def test_docs_marker_and_cli_only_update_ui(self):
        self.assertIn("<!-- update-contract: v1 -->", (ROOT / "docs/updates.md").read_text(encoding="utf-8"))
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Updates", readme)
        self.assertIn("docs/updates.md", readme)
        self.assertIn("## Privacy", readme)
        entry = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('champollion = "champollion.cli:main"', entry)
        for dependency in (" PyQt", "tkinter", "wxPython", "pywebview"):
            self.assertNotIn(dependency, entry)
        sources = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "src").rglob("*.py"))
        for gui in ("import tkinter", "import PyQt", "import wx", "import pywebview"):
            self.assertNotIn(gui, sources)


if __name__ == "__main__":
    unittest.main()
