"""Retention tests: every local write has a lifetime and no debris is left.

Each case uses a temporary install home, cache, config and temporary folder, so
no real user directory is touched. No test opens a socket or runs an installer.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from champollion import cli, retention, updates

ROOT = Path(__file__).resolve().parent.parent
DAY = 24 * 60 * 60


class RetentionCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".test-retention-", dir=ROOT / "tests/fixtures")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / "install-home"
        self.venv = self.home / "venv"
        self.venv.mkdir(parents=True)
        self.tmp_root = self.base / "tmp"
        self.tmp_root.mkdir()
        patch = mock.patch.dict(os.environ, {
            "CHAMPOLLION_CONFIG_DIR": str(self.base / "config"),
            "CHAMPOLLION_CACHE_DIR": str(self.base / "cache"),
            "CHAMPOLLION_HOME": str(self.home),
            "CHAMPOLLION_NO_UPDATE_CHECK": "1",
            "CHAMPOLLION_AGENT": "", "AGENT_MODE": "", "CLAUDECODE": "",
            "CODEX_CLI": "", "PI_AGENT": "", "ANTIGRAVITY_AGENT": "", "DSH_AGENT": "",
            "CI": "", "NO_COLOR": "1",
        })
        patch.start()
        self.addCleanup(patch.stop)

    def age(self, path, days):
        stamp = time.time() - days * DAY
        os.utime(path, (stamp, stamp))
        return path

    def rollback_copy(self):
        previous = self.home / "venv.previous"
        previous.mkdir()
        (previous / "old.txt").write_text("old environment", encoding="utf-8")
        return previous


class RollbackRetentionTests(RetentionCase):
    def test_first_successful_run_removes_the_rollback_copy(self):
        previous = self.rollback_copy()
        marker = self.home / retention.FIRST_RUN_MARKER
        self.assertTrue(retention.mark_pending_first_run(self.home, updates.__version__))
        self.assertTrue(marker.is_file())
        report = retention.prune(self.home, successful=True, running_prefix=self.venv)
        self.assertTrue(report["previous_removed"])
        self.assertTrue(report["marker_cleared"])
        self.assertFalse(previous.exists())
        self.assertFalse(marker.exists())

    def test_rollback_copy_survives_until_the_new_version_has_run(self):
        previous = self.rollback_copy()
        marker = self.home / retention.FIRST_RUN_MARKER
        retention.mark_pending_first_run(self.home, updates.__version__)
        # A checkout, a pip install or a test run is not the first run of the swap.
        report = retention.prune(self.home, successful=True, running_prefix=self.base / "checkout")
        self.assertFalse(report["previous_removed"])
        self.assertTrue(previous.exists())
        self.assertTrue(marker.exists())
        # A failed command is not a successful first run either.
        report = retention.prune(self.home, successful=False, running_prefix=self.venv)
        self.assertFalse(report["previous_removed"])
        self.assertTrue(previous.exists())

    def test_unprepared_install_home_is_left_alone(self):
        previous = self.rollback_copy()
        report = retention.prune(self.base / "absent-home", successful=True, running_prefix=self.venv)
        self.assertFalse(report["previous_removed"])
        self.assertEqual(report["staging_removed"], 0)
        self.assertTrue(previous.exists())

    def test_seven_day_expiry_applies_without_a_successful_run(self):
        previous = self.age(self.rollback_copy(), 8)
        report = retention.prune(self.home, successful=False, running_prefix=self.venv)
        self.assertTrue(report["previous_removed"])
        self.assertFalse(previous.exists())
        fresh = self.rollback_copy()
        report = retention.prune(self.home, successful=False, running_prefix=self.venv)
        self.assertFalse(report["previous_removed"])
        self.assertTrue(fresh.exists())

    def test_fresh_marker_keeps_an_old_copy_until_the_first_success(self):
        now = time.time()
        # The replaced venv inherited an old mtime; the swap just happened.
        previous = self.age(self.rollback_copy(), 8)
        marker = self.home / retention.FIRST_RUN_MARKER
        retention.mark_pending_first_run(self.home, updates.__version__, now=now)
        report = retention.prune(self.home, now=now, successful=False, running_prefix=self.venv)
        self.assertFalse(report["previous_removed"])
        self.assertTrue(previous.is_dir())
        self.assertTrue(marker.is_file())
        report = retention.prune(self.home, now=now, successful=True, running_prefix=self.venv)
        self.assertTrue(report["previous_removed"])
        self.assertTrue(report["marker_cleared"])
        self.assertFalse(previous.exists())
        self.assertFalse(marker.exists())

    def test_rollback_restores_the_copy_and_clears_the_marker(self):
        previous = self.rollback_copy()
        retention.mark_pending_first_run(self.home, updates.__version__)
        outcome = updates.rollback(self.home)
        self.assertTrue(outcome["ok"], outcome)
        self.assertFalse((self.home / retention.FIRST_RUN_MARKER).exists())
        self.assertEqual((self.venv / "old.txt").read_text(encoding="utf-8"), "old environment")
        self.assertTrue(previous.is_dir())


class DebrisTests(RetentionCase):
    def test_stale_staging_and_swap_remnants_are_pruned_fresh_work_is_kept(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep", encoding="utf-8")
        stale_stage = self.home / ".champollion-stage-stale"
        stale_stage.mkdir()
        self.age(stale_stage, 0.3)
        fresh_stage = self.home / ".champollion-stage-fresh"
        fresh_stage.mkdir()
        stale_next = self.home / "venv.next.999"
        stale_next.mkdir()
        self.age(stale_next, 0.3)
        link = self.home / ".champollion-stage-link"
        link.symlink_to(outside, target_is_directory=True)
        stamp = time.time() - 0.3 * DAY
        os.utime(link, (stamp, stamp), follow_symlinks=False)
        keep = self.home / "bin"
        keep.mkdir()
        report = retention.prune(self.home, successful=True, running_prefix=self.venv)
        self.assertGreaterEqual(report["staging_removed"], 3)
        self.assertFalse(stale_stage.exists())
        self.assertFalse(stale_next.exists())
        self.assertFalse(link.is_symlink())
        self.assertTrue(fresh_stage.is_dir())
        self.assertTrue(keep.is_dir())
        self.assertEqual((outside / "keep.txt").read_text(encoding="utf-8"), "keep")

    def test_abandoned_export_temp_folders_expire(self):
        stale = self.tmp_root / "champollion-abandoned"
        stale.mkdir()
        self.age(stale, 2)
        fresh = self.tmp_root / "champollion-running"
        fresh.mkdir()
        other = self.tmp_root / "unrelated-tool"
        other.mkdir()
        self.age(other, 3)
        removed = retention.prune_export_temp(root=self.tmp_root)
        self.assertEqual(removed, 1)
        self.assertFalse(stale.exists())
        self.assertTrue(fresh.is_dir())
        self.assertTrue(other.is_dir())

    def test_no_export_debris_outside_the_temporary_folder(self):
        self.assertEqual(retention.prune_export_temp(root=self.base / "missing"), 0)


class InstallMarkerTests(RetentionCase):
    def test_successful_install_records_the_pending_first_run(self):
        name = "champollion_protocol-1.11.0-py3-none-any.whl"
        wheel = b"wheel bytes"
        sums = hashlib.sha256(wheel).hexdigest() + "  " + name + "\n"
        result = {"latest": "1.11.0", "assets": [
            {"name": "SHA256SUMS", "url": "https://invalid.test/sums"},
            {"name": name, "url": "https://invalid.test/wheel"}]}

        def asset(url, opener=None, timeout=10.0, deadline=None):
            return sums.encode() if url.endswith("sums") else wheel

        def run(argv, **kwargs):
            if list(argv[1:3]) == ["-m", "venv"]:
                Path(argv[-1]).mkdir(parents=True)
            return subprocess.CompletedProcess(argv, 0, b"", b"")

        with mock.patch.object(updates, "_installer_managed", return_value=True), \
             mock.patch.object(updates, "_get_asset", side_effect=asset), \
             mock.patch.object(updates.subprocess, "run", side_effect=run):
            outcome = updates.install_release(result, deadline=time.monotonic() + 10.0)
        self.assertTrue(outcome["ok"], outcome)
        marker = self.home / retention.FIRST_RUN_MARKER
        self.assertTrue(marker.is_file())
        self.assertEqual(json.loads(marker.read_text(encoding="utf-8"))["version"], "1.11.0")
        self.assertTrue((self.home / "venv").is_dir())
        # The swap kept the environment it replaced as the one rollback copy.
        self.assertTrue((self.home / "venv.previous").is_dir())


class CliRetentionTests(RetentionCase):
    def call(self, argv):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return cli.main(argv)

    def test_unmanaged_command_leaves_install_home_and_system_temp_alone(self):
        sentinel_home = self.base / "unmanaged-home"
        sentinel_home.mkdir()
        stale_stage = sentinel_home / ".champollion-stage-stale"
        stale_stage.mkdir()
        self.age(stale_stage, 0.3)
        previous = sentinel_home / "venv.previous"
        previous.mkdir()
        self.age(previous, 8)
        retention.mark_pending_first_run(
            sentinel_home, updates.__version__, now=time.time() - 9 * DAY)
        marker = sentinel_home / retention.FIRST_RUN_MARKER
        original_marker = marker.read_bytes()
        stale_export = self.tmp_root / "champollion-unmanaged"
        stale_export.mkdir()
        self.age(stale_export, 2)
        with mock.patch.object(updates, "_install_home", return_value=sentinel_home), \
             mock.patch.object(retention.tempfile, "gettempdir", return_value=str(self.tmp_root)):
            self.assertEqual(self.call(["rules"]), 0)
        self.assertTrue(stale_stage.is_dir())
        self.assertTrue(previous.is_dir())
        self.assertEqual(marker.read_bytes(), original_marker)
        self.assertTrue(stale_export.is_dir())

    def test_every_command_applies_retention_after_it_finishes(self):
        with mock.patch.object(retention, "prune", return_value={"ok": True}) as prune:
            self.assertEqual(self.call(["rules"]), 0)
            self.assertEqual(prune.call_args.kwargs, {"successful": True})
            prune.reset_mock()
            self.assertEqual(self.call(["not-a-command"]), 2)
            self.assertEqual(prune.call_args.kwargs, {"successful": False})

    def test_retention_failure_never_changes_the_exit_status(self):
        with mock.patch.object(retention, "prune", side_effect=OSError("denied")):
            self.assertEqual(self.call(["rules"]), 0)


if __name__ == "__main__":
    unittest.main()
