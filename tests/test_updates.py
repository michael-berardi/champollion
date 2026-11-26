"""Offline tests for the anonymous release check and the opt-in updater (update contract v1)."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch
from urllib.error import URLError

from champollion import updates
from champollion.cli import main
from champollion.findings import ChampollionError

CURRENT = updates.__version__
MAJOR, MINOR, _ = updates.parse_version(CURRENT)
NEWER = f"{MAJOR}.{MINOR + 1}.0"
NEWEST = f"{MAJOR}.{MINOR + 2}.0"
DIM_START, DIM_END = "\x1b[2m", "\x1b[0m"


def release(version=NEWER, **fields):
    record = {"tag_name": "v" + version, "draft": False, "prerelease": False, "body": "Fixes.\n\n- one\n- two\n"}
    record.update(fields)
    return record


def available(version=NEWER):
    return updates.parse_release(release(version))


class TtyStream(io.StringIO):
    def isatty(self):
        return True


class UpdateCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.tmp = self.root / "tmp"
        self.tmp.mkdir()
        cleared = {name: "" for name in ("CI", "CHAMPOLLION_NO_UPDATE_CHECK", "CHAMPOLLION_UPDATE_API",
                                         "CHAMPOLLION_RELEASE_BASE", "CHAMPOLLION_HOME", "NO_COLOR")
                   + updates.AGENT_FLAGS}
        for patcher in (patch.dict(os.environ, cleared),
                        patch.object(updates, "cache_dir", return_value=self.root / "cache"),
                        patch.object(tempfile, "tempdir", str(self.tmp))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_cli(self, *arguments, tty=False, stdin=None):
        output, errors = (TtyStream(), TtyStream()) if tty else (io.StringIO(), io.StringIO())
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors), \
                patch("sys.stdin", stdin if stdin is not None else io.StringIO()):
            code = main(list(arguments))
        return code, output.getvalue(), errors.getvalue()

    def cache_files(self):
        return sorted(path.name for path in (self.root / "cache").iterdir())


class VersionTests(UpdateCase):
    def test_only_stable_strictly_newer_versions_count(self):
        for candidate, expected in (("1.10.1", True), ("v1.11.0", True), ("2.0.0", True), ("1.10.0", False),
                                    ("1.9.9", False), ("nonsense", False), ("1.11", False),
                                    ("2.0.0-rc1", False), ("v2.0.0b1", False), (None, False), (11, False)):
            with self.subTest(candidate=candidate):
                self.assertEqual(updates.is_newer(candidate, "1.10.0"), expected)
        self.assertFalse(updates.is_newer("9.0.0", "garbage"))
        for record in (release(draft=True), release(prerelease=True), release(tag_name="v9.0.0-rc1"),
                       release(CURRENT), release("0.1.0"), release(tag_name="latest")):
            self.assertEqual(updates.parse_release(record)["status"], "current")
        self.assertEqual(available()["latest"], NEWER)

    def test_api_url_comes_from_package_metadata(self):
        owner, name = updates.repository_url().split("/")[-2:]
        self.assertEqual(updates.api_url(), f"https://api.github.com/repos/{owner}/{name}/releases/latest")
        self.assertEqual(updates.release_base("v" + NEWER),
                         f"{updates.repository_url()}/releases/download/v{NEWER}")


class CheckTests(UpdateCase):
    def test_daily_check_writes_one_private_file_and_records_failure_cause(self):
        body = json.dumps(release()).encode()
        with patch.object(updates, "fetch", return_value=body) as fetch:
            first = updates.BackgroundCheck(updates.load_state()).finish()
            again = updates.BackgroundCheck(updates.load_state())
            self.assertIsNone(again.thread)
            self.assertEqual(again.finish()["latest"], NEWER)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual((first["status"], first["latest"]), ("available", NEWER))
        self.assertEqual(self.cache_files(), ["update.json"])
        self.assertEqual(stat.S_IMODE(updates.state_path().stat().st_mode), 0o600)
        self.assertNotIn("notes", updates.load_state())
        updates.save_state(checked_at=time.time() - updates.DAY - 1)
        with patch.object(updates, "fetch", side_effect=URLError("offline")):
            failed = updates.BackgroundCheck(updates.load_state()).finish()
        self.assertEqual(failed["status"], "failed")
        self.assertIn("offline", updates.load_state()["cause"])
        with patch.object(updates, "fetch") as fetch:
            updates.BackgroundCheck(updates.load_state()).finish()
        fetch.assert_not_called()  # a failure counts as the day's check: no retry loop

    def test_slow_answer_is_recorded_without_holding_the_command(self):
        release_gate = threading.Event()
        self.addCleanup(release_gate.set)
        with patch.object(updates, "TIMEOUT", 0.05), \
                patch.object(updates, "fetch", side_effect=lambda *_: release_gate.wait(5) and b"{}"):
            started = time.monotonic()
            result = updates.BackgroundCheck({}).finish()
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertEqual(result["status"], "failed")
        self.assertIn("no answer within", result["cause"])

    def test_check_is_one_anonymous_get_with_the_fixed_user_agent(self):
        seen = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append((self.command, self.path, dict(self.headers)))
                payload = json.dumps(release()).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = f"http://127.0.0.1:{server.server_port}/repos/owner/name/releases/latest"
        with patch.dict(os.environ, {"CHAMPOLLION_UPDATE_API": url, "no_proxy": "*", "NO_PROXY": "*"}):
            result = updates.check_now()
        self.assertEqual(result["latest"], NEWER)
        self.assertEqual(len(seen), 1)
        method, path, headers = seen[0]
        self.assertEqual((method, path), ("GET", "/repos/owner/name/releases/latest"))
        self.assertEqual(headers["User-Agent"], "champollion-update-check")
        self.assertFalse({"Cookie", "Authorization"} & set(headers))

    def test_update_check_exit_codes_and_cause(self):
        with patch.object(updates, "_ask_release", return_value=updates.parse_release(release(CURRENT))):
            self.assertEqual(self.run_cli("update", "--check"), (0, f"champollion {CURRENT} is current\n", ""))
        with patch.object(updates, "_ask_release", return_value=available()):
            self.assertEqual(self.run_cli("update", "--check"),
                             (10, f"champollion {NEWER} available (you have {CURRENT})\n", ""))
            code, output, _ = self.run_cli("update", "--check", "--json")
        self.assertEqual((code, json.loads(output)["latest"]), (10, NEWER))
        with patch.object(updates, "_ask_release", return_value=updates._failed("HTTP Error 403: rate limited")):
            code, output, errors = self.run_cli("update", "--check")
        self.assertEqual((code, output), (1, ""))
        self.assertIn("update check failed: HTTP Error 403: rate limited", errors)


class NoticeTests(UpdateCase):
    def setUp(self):
        super().setUp()
        kind = patch.object(updates, "detect_install_kind", return_value="installer")
        kind.start()
        self.addCleanup(kind.stop)

    def notice(self, version=NEWER):
        return (f"champollion {version} available (you have {CURRENT}) · run: champollion update\n"
                f"{DIM_START}turn on automatic updates: champollion update --auto on · "
                f"skip: champollion update --skip{DIM_END}\n")

    def test_check_is_off_for_non_tty_ci_agent_json_update_source_and_opt_outs(self):
        with patch.object(updates, "_ask_release", return_value=available()):
            with patch("sys.stdout.isatty", return_value=True), patch("sys.stderr.isatty", return_value=True):
                self.assertIsNotNone(updates.start_check(["rules"]))
                for argv in (["rules", "--json"], ["update"], ["update", "--check"], []):
                    self.assertIsNone(updates.start_check(argv), argv)
                for name in ("CI", "CHAMPOLLION_NO_UPDATE_CHECK", "CLAUDECODE", "CHAMPOLLION_AGENT"):
                    with patch.dict(os.environ, {name: "1"}):
                        self.assertIsNone(updates.start_check(["rules"]), name)
                with patch.object(updates, "detect_install_kind", return_value="source"):
                    self.assertIsNone(updates.start_check(["rules"]))
                updates.save_state(check=False)
                self.assertIsNone(updates.start_check(["rules"]))
                self.assertFalse(updates.auto_status()["check_automatically"])
            updates.save_state(check=True)
            for out, err in ((False, True), (True, False)):
                with patch("sys.stdout.isatty", return_value=out), patch("sys.stderr.isatty", return_value=err):
                    self.assertIsNone(updates.start_check(["rules"]))

    def test_notice_follows_the_command_on_stderr_and_never_enters_json(self):
        with patch.object(updates, "_ask_release", return_value=available()) as ask:
            code, output, errors = self.run_cli("rules", tty=True)
            self.assertEqual((code, ask.call_count), (0, 1))
            self.assertTrue(output.startswith("SRC-1 "))
            self.assertNotIn("available", output)
            self.assertEqual(errors, self.notice())
            code, output, errors = self.run_cli("rules", "--json", tty=True)
            self.assertEqual((code, errors, ask.call_count), (0, "", 1))
            json.loads(output)
            code, output, errors = self.run_cli("rules")
            self.assertEqual((code, errors, ask.call_count), (0, "", 1))
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            lines = updates.notice_lines(NEWER, "installer")
        self.assertEqual("\n".join(lines) + "\n", self.notice().replace(DIM_START, "").replace(DIM_END, ""))

    def test_notice_once_a_day_per_version_skip_and_newer_release(self):
        with patch.object(updates, "_ask_release", return_value=available()):
            self.assertEqual(self.run_cli("rules", tty=True)[2], self.notice())
            self.assertEqual(self.run_cli("rules", tty=True)[2], "")
            updates.save_state(notified_at=time.time() - updates.DAY - 1)
            self.assertEqual(self.run_cli("rules", tty=True)[2], self.notice())
            self.assertEqual(self.run_cli("update", "--skip"), (0, f"skipped {NEWER}; a newer release will notify again\n", ""))
            updates.save_state(notified_at=0)
            self.assertEqual(self.run_cli("rules", tty=True)[2], "")
        updates.save_state(checked_at=0)
        with patch.object(updates, "_ask_release", return_value=available(NEWEST)):
            self.assertEqual(self.run_cli("rules", tty=True)[2], self.notice(NEWEST))
        self.assertEqual(self.cache_files(), ["update.json"])

    def test_no_notice_after_a_failed_command(self):
        with patch.object(updates, "_ask_release", return_value=available()):
            code, _, errors = self.run_cli("profile", "validate", str(self.root / "missing.json"), tty=True)
        self.assertEqual(code, 2)
        self.assertNotIn("available", errors)


class AutoTests(UpdateCase):
    def test_auto_on_off_status_persist_and_default_off(self):
        code, output, _ = self.run_cli("update", "--auto", "status")
        self.assertEqual((code, output), (0, f"check for updates automatically: on\n"
                                              f"install updates automatically: off\nversion {CURRENT}\n"))
        self.assertFalse(updates.state_path().exists())  # reading the status writes nothing
        self.assertEqual(self.run_cli("update", "--auto", "on")[0], 0)
        self.assertTrue(updates.load_state()["auto"])
        self.assertTrue(json.loads(self.run_cli("update", "--auto", "status", "--json")[1])["install_automatically"])
        self.assertIn("install updates automatically: off", self.run_cli("update", "--auto", "off")[1])
        self.assertFalse(updates.auto_status()["install_automatically"])
        self.assertEqual(stat.S_IMODE(updates.state_path().stat().st_mode), 0o600)

    def test_auto_installs_once_in_the_background_then_falls_back_to_the_notice(self):
        updates.save_state(auto=True, checked_at=time.time(), **{k: v for k, v in available().items() if k != "notes"})
        with patch.object(updates, "detect_install_kind", return_value="installer"), \
                patch("subprocess.Popen") as popen:
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                updates.after_command(updates.BackgroundCheck(updates.load_state()), "rules", 0)
            self.assertEqual(errors.getvalue(), "")
            self.assertEqual(popen.call_count, 1)
            command, options = popen.call_args.args[0], popen.call_args.kwargs
            self.assertEqual(command[-3:], ["champollion", "update", "--auto-install"])
            self.assertEqual(options["env"]["CHAMPOLLION_NO_UPDATE_CHECK"], "1")
            self.assertTrue(options.get("start_new_session") or options.get("creationflags"))
            with contextlib.redirect_stderr(errors):
                updates.after_command(updates.BackgroundCheck(updates.load_state()), "rules", 0)
            self.assertEqual(popen.call_count, 1)
        self.assertIn(f"champollion {NEWER} available", errors.getvalue())
        self.assertIn("skip: champollion update --skip", errors.getvalue())
        self.assertNotIn("turn on automatic updates", errors.getvalue())
        self.assertEqual(self.cache_files(), ["update.json", "update.log"])

    def test_failed_automatic_install_records_its_cause(self):
        updates.save_state(auto=True, latest=NEWER, tag="v" + NEWER, status="available")
        nice = patch("os.nice", create=True)
        nice.start()
        self.addCleanup(nice.stop)
        with patch.object(updates, "detect_install_kind", return_value="source"), \
                contextlib.redirect_stdout(io.StringIO()) as log:
            self.assertEqual(updates.auto_install(), 1)
        self.assertIn("source checkout", updates.load_state()["auto_error"])
        self.assertIn(f"automatic update to {NEWER} failed", log.getvalue())
        self.assertIn("last automatic install failed", self.run_cli("update", "--auto", "status")[1])
        updates.save_state(auto=False)
        with patch.object(updates, "install") as install:
            self.assertEqual(updates.auto_install(), 0)
        install.assert_not_called()

    def test_log_stays_one_bounded_file(self):
        log = updates.log_path()
        log.parent.mkdir(parents=True)
        log.write_bytes(b"x" * (3 * updates.LOG_LIMIT) + b"newest line\n")
        with patch("subprocess.Popen"):
            updates.launch_auto_install(NEWER)
        self.assertLessEqual(log.stat().st_size, updates.LOG_LIMIT)
        self.assertTrue(log.read_bytes().endswith(b"newest line\n"))
        self.assertEqual(self.cache_files(), ["update.json", "update.log"])


class UpdateCommandTests(UpdateCase):
    def setUp(self):
        super().setUp()
        for patcher in (patch.object(updates, "_ask_release", return_value=available()),
                        patch.object(updates, "detect_install_kind", return_value="installer")):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_interactive_update_confirms_then_asks_about_automatic_installs_once(self):
        with patch.object(updates, "install", return_value={"version": NEWER}) as install:
            code, output, errors = self.run_cli("update", tty=True, stdin=TtyStream("\nn\n"))
            self.assertEqual(code, 0)
            self.assertEqual(output, f"champollion {NEWER} available (you have {CURRENT})\nFixes.\n- one\n- two\n"
                                     f"installed champollion {NEWER}; it applies next run\n")
            self.assertEqual(errors, f"Install {NEWER} now? [Y/n] Install future updates automatically? [y/N] ")
            self.assertEqual((updates.load_state()["auto"], updates.load_state()["asked_auto"]), (False, True))
            code, _, errors = self.run_cli("update", tty=True, stdin=TtyStream("y\n"))
            self.assertEqual(errors, f"Install {NEWER} now? [Y/n] ")
            self.assertEqual(install.call_count, 2)
            self.run_cli("update", tty=True, stdin=TtyStream("n\n"))
            self.assertEqual(install.call_count, 2)

    def test_yes_to_automatic_installs_turns_them_on(self):
        with patch.object(updates, "install", return_value={"version": NEWER}):
            self.run_cli("update", tty=True, stdin=TtyStream("y\ny\n"))
        self.assertTrue(updates.load_state()["auto"])

    def test_explicit_non_tty_update_installs_without_questions(self):
        with patch.object(updates, "install", return_value={"version": NEWER}) as install:
            code, output, errors = self.run_cli("update", "--json")
        self.assertEqual((code, errors), (0, ""))
        self.assertEqual(json.loads(output)["new"], NEWER)
        install.assert_called_once_with("installer", NEWER, "v" + NEWER)
        self.assertNotIn("asked_auto", updates.load_state())

    def test_update_names_the_package_manager_command_before_running_it(self):
        with patch.object(updates, "detect_install_kind", return_value="uv"), \
                patch.object(updates, "install", return_value={"version": NEWER}) as install:
            code, output, _ = self.run_cli("update")
        self.assertEqual(code, 0)
        self.assertIn(f"runs: uv tool install --force 'champollion-protocol @ git+{updates.repository_url()}.git@v{NEWER}'",
                      output)
        install.assert_called_once_with("uv", NEWER, "v" + NEWER)

    def test_package_manager_installs_run_the_managers_command_pinned_to_the_tag(self):
        source = f"git+{updates.repository_url()}.git@v{NEWER}"
        expected = {"uv": ["uv", "tool", "install", "--force", f"champollion-protocol @ {source}"],
                    "pipx": ["pipx", "install", "--force", source]}
        for kind in ("uv", "pipx", "pip"):
            calls = []
            run = lambda command, **_: calls.append(command) or subprocess.CompletedProcess(command, 0)
            result = updates.install(kind, NEWER, "v" + NEWER, run=run)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0], expected.get(kind, calls[0]))
            self.assertTrue(calls[0][-1].endswith(source), calls[0])
            self.assertIn(f"@v{NEWER}", result["command"])
        with self.assertRaises(ChampollionError) as caught:
            updates.install("uv", NEWER, "v" + NEWER, run=lambda command, **_: subprocess.CompletedProcess(command, 3))
        self.assertIn("exited 3", str(caught.exception))
        with self.assertRaises(ChampollionError) as caught:
            updates.install("source", NEWER, "v" + NEWER)
        self.assertIn("git pull", str(caught.exception))
        with self.assertRaises(ChampollionError):
            updates.install("pip", CURRENT, "v" + CURRENT, run=run)


class InstallTests(UpdateCase):
    def setUp(self):
        super().setUp()
        self.home = self.root / "home"
        self.venv = self.home / "venv"
        self.venv.mkdir(parents=True)
        (self.venv / "marker").write_text("old", encoding="utf-8")
        self.temporaries = []
        located = patch.object(updates, "installer_home", return_value=self.home)
        located.start()
        self.addCleanup(located.stop)

    def fetcher(self, version=NEWER, wheel=b"wheel", listed=None):
        name = f"champollion_protocol-{version}-py3-none-any.whl"
        digest = hashlib.sha256(listed if listed is not None else wheel).hexdigest()
        sums = f"{digest}  champollion_protocol-{version}.tar.gz\n{digest}  {name}\n".encode()
        requested = []

        def get(url, *_):
            requested.append(url)
            return sums if url.endswith("/SHA256SUMS") else wheel
        get.requested = requested
        return get

    def runner(self, version=NEWER, fail=None):
        def run(command, **options):
            self.temporaries.append(options["env"]["TMPDIR"])
            if fail and fail in command:
                return subprocess.CompletedProcess(command, 1)
            if command[1:3] == ["-m", "venv"]:
                Path(command[3]).mkdir(parents=True)
                (Path(command[3]) / "marker").write_text(version, encoding="utf-8")
            stdout = version + "\n" if "-c" in command else ""
            return subprocess.CompletedProcess(command, 0, stdout=stdout)
        return run

    def leftovers(self):
        return sorted(path.name for path in self.home.iterdir()), list(self.tmp.iterdir())

    def test_checksum_mismatch_refuses_before_touching_the_install(self):
        get = self.fetcher(wheel=b"tampered", listed=b"wheel")
        with self.assertRaises(ChampollionError) as caught:
            updates.install("installer", NEWER, "v" + NEWER, get=get, run=self.runner())
        self.assertEqual(caught.exception.cause, "checksum")
        self.assertEqual((self.venv / "marker").read_text(encoding="utf-8"), "old")
        self.assertEqual(self.leftovers(), (["venv"], []))
        self.assertEqual(get.requested[0], f"{updates.repository_url()}/releases/download/v{NEWER}/SHA256SUMS")

    def test_swap_keeps_exactly_one_rollback_that_restores(self):
        result = updates.install("installer", NEWER, "v" + NEWER, get=self.fetcher(), run=self.runner())
        self.assertEqual(result["version"], NEWER)
        self.assertEqual((self.venv / "marker").read_text(encoding="utf-8"), NEWER)
        self.assertEqual((self.home / "venv.previous" / "marker").read_text(encoding="utf-8"), "old")
        self.assertEqual(self.leftovers(), (["venv", "venv.previous"], []))
        self.assertEqual(len(set(self.temporaries)), 1)  # every step's TMPDIR is the update's own folder
        self.assertEqual(Path(self.temporaries[0]).parent, self.tmp)
        updates.install("installer", NEWEST, "v" + NEWEST, get=self.fetcher(NEWEST), run=self.runner(NEWEST))
        self.assertEqual((self.home / "venv.previous" / "marker").read_text(encoding="utf-8"), NEWER)
        self.assertEqual(self.leftovers(), (["venv", "venv.previous"], []))
        code, output, _ = self.run_cli("update", "--rollback")
        self.assertEqual((code, output), (0, "restored the previous version; it applies next run\n"))
        self.assertEqual((self.venv / "marker").read_text(encoding="utf-8"), NEWER)
        self.assertEqual(self.leftovers(), (["venv"], []))
        self.assertEqual(self.run_cli("update", "--rollback")[0], 2)

    def test_failed_or_wrong_stage_cleans_up_and_keeps_the_install(self):
        for run in (self.runner(fail="pip"), self.runner(version=NEWEST)):
            with self.assertRaises(ChampollionError):
                updates.install("installer", NEWER, "v" + NEWER, get=self.fetcher(), run=run)
            self.assertEqual((self.venv / "marker").read_text(encoding="utf-8"), "old")
            self.assertEqual(self.leftovers(), (["venv"], []))

    def test_rollback_copy_goes_after_the_new_version_runs_or_after_seven_days(self):
        previous = self.home / "venv.previous"
        previous.mkdir()
        updates.after_command(None, "update", 0)  # the updating process itself does not count
        updates.after_command(None, "check", 1)
        self.assertTrue(previous.exists())
        updates.after_command(None, "rules", 0)
        self.assertFalse(previous.exists())
        previous.mkdir()
        old = time.time() - updates.ROLLBACK_MAX_AGE - 60
        os.utime(previous, (old, old))
        updates.after_command(None, "check", 1)
        self.assertFalse(previous.exists())

    def test_stage_is_made_from_the_base_interpreter(self):
        with patch("sys.prefix", str(self.venv)), patch("sys.executable", str(self.venv / "bin" / "python")), \
                patch("sys._base_executable", str(self.venv / "bin" / "python"), create=True), \
                patch("os.path.realpath", return_value="/base/bin/python3"):
            self.assertEqual(updates.base_python(), "/base/bin/python3")
        with patch("sys._base_executable", "/usr/bin/python3", create=True):
            self.assertEqual(updates.base_python(), "/usr/bin/python3")


if __name__ == "__main__":
    unittest.main()
