"""Retention tests: every local write has a lifetime and no debris is left.

Each case uses a temporary install home, update cache and temporary folder, so
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

DAY = 24 * 60 * 60


class RetentionCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="test-retention-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "install-home"
        self.venv = self.home / "venv"
        self.venv.mkdir(parents=True)
        self.tmp_root = self.base / "tmp"
        self.tmp_root.mkdir()
        environment = {name: "" for name in updates.AGENT_FLAGS}
        environment.update(CHAMPOLLION_HOME=str(self.home), CHAMPOLLION_NO_UPDATE_CHECK="1",
                           CHAMPOLLION_UPDATE_API="", CHAMPOLLION_RELEASE_BASE="", CI="", NO_COLOR="1")
        # A managed-path test must never prune the real system temporary folder.
        for patcher in (mock.patch.dict(os.environ, environment),
                        mock.patch.object(updates, "cache_dir", return_value=self.base / "cache"),
                        mock.patch.object(tempfile, "tempdir", str(self.tmp_root))):
            patcher.start()
            self.addCleanup(patcher.stop)

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

    def test_dated_marker_older_than_seven_days_expires_without_a_successful_run(self):
        now = time.time()
        # The copy itself was just made current; only the recorded install time is old.
        previous = self.rollback_copy()
        marker = self.home / retention.FIRST_RUN_MARKER
        retention.mark_pending_first_run(self.home, updates.__version__, now=now - 7 * DAY - 60)
        report = retention.prune(self.home, now=now, successful=False, running_prefix=self.venv)
        self.assertTrue(report["previous_removed"])
        self.assertTrue(report["marker_cleared"])
        self.assertFalse(previous.exists())
        self.assertFalse(marker.exists())

    def test_unreadable_or_undated_marker_falls_back_to_its_own_age(self):
        contents = {
            "empty": "",
            "malformed": "{not json",
            "undated": json.dumps({"schema": retention.MARKER_SCHEMA,
                                   "version": updates.__version__}),
        }
        for label, content in contents.items():
            with self.subTest(label=label):
                previous = self.rollback_copy()
                marker = self.home / retention.FIRST_RUN_MARKER
                marker.write_text(content, encoding="utf-8")
                self.age(marker, 8)
                report = retention.prune(self.home, successful=False, running_prefix=self.venv)
                self.assertTrue(report["previous_removed"], label)
                self.assertTrue(report["marker_cleared"], label)
                self.assertFalse(previous.exists(), label)
                self.assertFalse(marker.exists(), label)

    def test_undated_marker_with_a_fresh_mtime_is_not_expired_early(self):
        previous = self.rollback_copy()
        marker = self.home / retention.FIRST_RUN_MARKER
        marker.write_text("{not json", encoding="utf-8")
        report = retention.prune(self.home, successful=False, running_prefix=self.venv)
        self.assertFalse(report["previous_removed"])
        self.assertTrue(previous.is_dir())
        self.assertTrue(marker.is_file())

    def test_undated_marker_expires_when_its_own_mtime_is_unavailable(self):
        previous = self.rollback_copy()
        marker = self.home / retention.FIRST_RUN_MARKER
        marker.write_text("{not json", encoding="utf-8")
        with mock.patch.object(retention, "_age", return_value=None):
            report = retention.prune(self.home, successful=False, running_prefix=self.venv)
        self.assertTrue(report["previous_removed"])
        self.assertFalse(previous.exists())
        self.assertFalse(marker.exists())

    def test_rollback_restores_the_copy_and_clears_the_marker(self):
        previous = self.rollback_copy()
        retention.mark_pending_first_run(self.home, updates.__version__)
        with mock.patch.object(updates, "installer_home", return_value=self.home):
            outcome = updates.rollback_install()
        self.assertTrue(outcome["restored"], outcome)
        self.assertFalse((self.home / retention.FIRST_RUN_MARKER).exists())
        self.assertEqual((self.venv / "old.txt").read_text(encoding="utf-8"), "old environment")
        # The restored copy is now the current environment; no second copy remains.
        self.assertFalse(previous.exists())


class DebrisTests(RetentionCase):
    def test_stale_staging_and_swap_remnants_are_pruned_fresh_work_is_kept(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep", encoding="utf-8")
        stale_stage = self.home / "venv.tmp.999"
        stale_stage.mkdir()
        self.age(stale_stage, 0.3)
        fresh_stage = self.home / "venv.tmp.1000"
        fresh_stage.mkdir()
        stale_spare = self.home / "venv.rollback.999"
        stale_spare.mkdir()
        self.age(stale_spare, 0.3)
        link = self.home / "venv.tmp.link"
        link.symlink_to(outside, target_is_directory=True)
        stamp = time.time() - 0.3 * DAY
        os.utime(link, (stamp, stamp), follow_symlinks=False)
        keep = self.home / "bin"
        keep.mkdir()
        # Not staging: the installers clear venv.old themselves; nothing else is touched.
        other = self.home / "venv.old"
        other.mkdir()
        self.age(other, 0.3)
        report = retention.prune(self.home, successful=True, running_prefix=self.venv)
        self.assertEqual(report["staging_removed"], 3)
        self.assertFalse(stale_stage.exists())
        self.assertFalse(stale_spare.exists())
        self.assertFalse(link.is_symlink())
        self.assertTrue(fresh_stage.is_dir())
        self.assertTrue(keep.is_dir())
        self.assertTrue(other.is_dir())
        self.assertTrue(self.venv.is_dir())
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

        def asset(url, timeout=10.0):
            return sums.encode() if url.endswith("SHA256SUMS") else wheel

        def run(argv, **kwargs):
            if list(argv[1:3]) == ["-m", "venv"]:
                Path(argv[-1]).mkdir(parents=True)
            output = "1.11.0\n" if "-c" in argv else ""
            return subprocess.CompletedProcess(argv, 0, output, "")

        with mock.patch.dict(os.environ, {"CHAMPOLLION_RELEASE_BASE": "https://invalid.test/v1.11.0"}):
            outcome = updates.install_release(self.home, "1.11.0", "v1.11.0", get=asset, run=run)
        self.assertEqual(outcome["version"], "1.11.0")
        marker = self.home / retention.FIRST_RUN_MARKER
        self.assertTrue(marker.is_file())
        record = json.loads(marker.read_text(encoding="utf-8"))
        self.assertEqual(record["version"], "1.11.0")
        self.assertLess(abs(record["at"] - time.time()), 60)
        if os.name != "nt":
            self.assertEqual(marker.stat().st_mode & 0o777, 0o600)
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
        stale_stage = sentinel_home / "venv.tmp.999"
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

    def test_copy_with_no_install_home_is_a_no_op(self):
        with mock.patch.object(updates, "_install_home", return_value=None):
            report = retention.prune()
        self.assertEqual((report["home"], report["managed"]), ("", False))

    def test_managed_command_keeps_a_fresh_swap_until_its_first_successful_run(self):
        # The full CLI path: updates.drop_rollback must defer to the marker, so an
        # old replaced venv is not expired early by its own mtime.
        previous = self.age(self.rollback_copy(), 8)
        marker = self.home / retention.FIRST_RUN_MARKER
        retention.mark_pending_first_run(self.home, updates.__version__)
        with mock.patch("sys.prefix", str(self.venv)):
            self.assertEqual(updates.installer_home(), self.home)
            with mock.patch.object(cli, "_dispatch", return_value=1):
                self.assertEqual(self.call(["rules"]), 1)
            self.assertTrue(previous.is_dir())
            self.assertTrue(marker.is_file())
            self.assertEqual(self.call(["rules"]), 0)
        self.assertFalse(previous.exists())
        self.assertFalse(marker.exists())

    def test_managed_run_of_another_version_keeps_the_copy(self):
        # The process that performed the swap still runs the old version.
        previous = self.rollback_copy()
        marker = self.home / retention.FIRST_RUN_MARKER
        retention.mark_pending_first_run(self.home, "99.0.0")
        with mock.patch("sys.prefix", str(self.venv)):
            self.assertEqual(self.call(["rules"]), 0)
        self.assertTrue(previous.is_dir())
        self.assertTrue(marker.is_file())

    def test_managed_command_without_a_marker_keeps_the_legacy_rule(self):
        previous = self.rollback_copy()
        with mock.patch("sys.prefix", str(self.venv)):
            with mock.patch.object(cli, "_dispatch", return_value=1):
                self.call(["rules"])
            self.assertTrue(previous.is_dir())
            self.assertEqual(self.call(["rules"]), 0)
        self.assertFalse(previous.exists())


if __name__ == "__main__":
    unittest.main()
