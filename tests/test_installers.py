"""Static guards for the one-step installers (scripts/install.ps1, scripts/install.sh).

Windows PowerShell 5.1 is not available in CI here, so Windows-only code is guarded by patterns that must not
come back; the platform-neutral behaviour is exercised by scripts/test-install.sh under PowerShell 7.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(name):
    with open(os.path.join(ROOT, "scripts", name), encoding="utf-8") as f:
        return f.read()


class InstallPs1Static(unittest.TestCase):
    def setUp(self):
        self.ps1 = read("install.ps1")
        self.code = "\n".join(l for l in self.ps1.splitlines() if not l.lstrip().startswith("#"))

    def test_cmd_shim_is_not_written_as_ascii(self):
        self.assertNotRegex(self.code, r"(?i)-Encoding\s+ascii")
        self.assertIn(r"%~dp0..\venv\Scripts\python.exe", self.code)
        self.assertIn("OEMCodePage", self.code)

    def test_native_output_is_captured_only_through_the_helper(self):
        outside = self.code.split("function Invoke-Native", 1)[1].split("\n}\n", 1)[1]
        self.assertNotRegex(outside, r"2>&1|\*>&1|\*>\s*\$null|2>\s*\$null")
        self.assertIn("$ErrorActionPreference = 'Continue'", self.code)

    def test_user_path_is_read_unexpanded(self):
        self.assertIn("DoNotExpandEnvironmentNames", self.code)
        self.assertNotIn("GetEnvironmentVariable('Path', 'User')", self.code)

    def test_paths_are_normalised_and_session_is_left_clean(self):
        self.assertEqual(self.code.count("GetUnresolvedProviderPathFromPSPath"), 2)
        self.assertRegex(self.code, r"(?m)^function Install-Champollion")
        self.assertNotRegex(self.code, r"(?m)^\s*exit\b")
        self.assertIn("Remove-Item Function:\\Install-Champollion", self.code)
        self.assertIn("$ProgressPreference = 'SilentlyContinue'", self.code)
        self.assertIn("Tls12", self.code)

    def test_old_venv_is_restored_when_the_swap_fails(self):
        self.assertRegex(self.code, r"Move-Item \$old \$venv")

    def test_shims_carry_a_marker_and_foreign_files_are_left_alone(self):
        self.assertEqual(self.code.count("$ShimMarker"), 6)
        self.assertIn("Left $shim alone", self.code)


class LegacyShim(unittest.TestCase):
    """The 1.6.0 shims carried no marker; an upgrade must still recognise and replace them."""

    def test_ps1_recognises_the_1_6_0_cmd_shape_only(self):
        code = read("install.ps1")
        pat = re.search(r"-match '(\^@echo off[^']*)'", code).group(1)
        # PowerShell regex and Python regex agree on this subset.
        rx = re.compile(pat)
        old = '@echo off\r\n"C:\\Users\\Jos?\\AppData\\Local\\Champollion\\venv\\Scripts\\python.exe" -m champollion %*\r\n'
        self.assertTrue(rx.search(old))
        self.assertFalse(rx.search('@echo off\r\necho mine\r\n'))
        self.assertFalse(rx.search('@echo off\r\n"C:\\x\\python.exe" -m champollion %*\r\n'))

    def test_ps1_health_check_runs_through_the_shim_when_ours(self):
        self.assertIn("if ($ours) { Invoke-Native $shim @('--help') }", read("install.ps1"))

    def test_sh_accepts_the_1_6_0_exec_line(self):
        self.assertIn('grep -qxF "exec \\"$VENV/bin/python\\" -m champollion', read("install.sh"))


class InstallShStatic(unittest.TestCase):
    def test_shim_has_marker_and_foreign_file_guard(self):
        sh = read("install.sh")
        self.assertIn("# champollion-installer-shim", sh)
        self.assertIn("Left $SHIM alone", sh)

    def test_health_check_result_is_not_silenced(self):
        sh = read("install.sh")
        self.assertNotRegex(sh, r'"\$SHIM" --help\s*>/dev/null')
        self.assertIn("Health check:", sh)


if __name__ == "__main__":
    unittest.main()
