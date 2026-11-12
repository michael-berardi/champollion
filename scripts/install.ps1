# Champollion installer for Windows (PowerShell 5.1 and 7):
#   irm https://github.com/your-github-username/champollion/releases/latest/download/install.ps1 | iex
# (replace your-github-username with the repository owner; release copies built by scripts/build-release.sh
#  already name the owner recorded in the git remote.)
# Downloads the release wheel named in SHA256SUMS, checks its SHA-256, and installs it into a private venv
# under %LOCALAPPDATA%\Champollion. The package is pure Python standard library with no dependencies, so
# nothing else is fetched. Uses the Python 3.9+ already on this machine; if none exists it says how to get one.
# Also runs under PowerShell 7 on Linux for testing (CHAMPOLLION_HOME / CHAMPOLLION_BIN_DIR overrides).
$ErrorActionPreference = 'Stop'
$Repo = 'your-github-username/champollion'
$base = if ($env:CHAMPOLLION_RELEASE_BASE) { $env:CHAMPOLLION_RELEASE_BASE }
        elseif ($env:CHAMPOLLION_VERSION) { "https://github.com/$Repo/releases/download/v$($env:CHAMPOLLION_VERSION.TrimStart('v'))" }
        else { "https://github.com/$Repo/releases/latest/download" }
if ($base -like '*your-github-username*') {
  throw 'This install.ps1 has no release repository configured; use the install.ps1 attached to a GitHub release (built by scripts/build-release.sh), or set CHAMPOLLION_RELEASE_BASE.'
}

# PowerShell 5.1 has no $IsWindows and only runs on Windows; PowerShell 7 sets it on every platform.
$onWindows = if ($PSVersionTable.PSVersion.Major -ge 6) { $IsWindows } else { $true }
# PowerShell 5.1 on older Windows defaults to TLS 1.0; GitHub downloads need TLS 1.2.
if ($onWindows -and $PSVersionTable.PSVersion.Major -lt 6) {
  [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
}
$homeDir = if ($env:CHAMPOLLION_HOME) { $env:CHAMPOLLION_HOME }
           elseif ($onWindows) { Join-Path $env:LOCALAPPDATA 'Champollion' }
           else { Join-Path $HOME '.champollion' }
$binDir = if ($env:CHAMPOLLION_BIN_DIR) { $env:CHAMPOLLION_BIN_DIR }
          elseif ($onWindows) { Join-Path $homeDir 'bin' }
          else { Join-Path $HOME '.local/bin' }

# Python 3.9 or newer, from this machine only (a system Python is never installed by this script).
$python = $null
$candidates = if ($onWindows) { @(@('py', '-3'), @('python'), @('python3')) } else { @(@('python3'), @('python')) }
foreach ($c in $candidates) {
  if (-not (Get-Command $c[0] -ErrorAction SilentlyContinue)) { continue }
  $prefix = @(); if ($c.Count -gt 1) { $prefix = $c[1..($c.Count - 1)] }
  try { & $c[0] @prefix -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' *> $null } catch { continue }
  if ($LASTEXITCODE -eq 0) { $python = $c; break }
}
if (-not $python) {
  if ($onWindows) {
    throw 'Champollion needs Python 3.9 or later and none was found; install it with: winget install -e --id Python.Python.3.12 (or download it from https://www.python.org/downloads/), then run this installer again.'
  }
  throw 'Champollion needs Python 3.9 or later and none was found; install it with: sudo apt-get install -y python3 python3-venv (or your package manager equivalent), then run this installer again.'
}

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("champollion-install-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $tmp | Out-Null
$venv = Join-Path $homeDir 'venv'
$stage = Join-Path $homeDir ("venv.tmp." + $PID)
try {
  Write-Host 'Downloading Champollion...'
  $sumsPath = Join-Path $tmp 'SHA256SUMS'
  Invoke-WebRequest -UseBasicParsing -Uri "$base/SHA256SUMS" -OutFile $sumsPath
  $wheelLine = Get-Content $sumsPath | Where-Object { $_ -match '^\s*[0-9a-fA-F]{64}\s+\*?champollion_protocol-\S+-py3-none-any\.whl\s*$' } | Select-Object -First 1
  if (-not $wheelLine) { throw 'SHA256SUMS lists no champollion_protocol wheel; the release is incomplete.' }
  $null = $wheelLine -match '^\s*([0-9a-fA-F]{64})\s+\*?(champollion_protocol-\S+-py3-none-any\.whl)\s*$'
  $want = $Matches[1].ToLower()
  $wheelName = $Matches[2]
  $wheelPath = Join-Path $tmp $wheelName
  Invoke-WebRequest -UseBasicParsing -Uri "$base/$wheelName" -OutFile $wheelPath
  $got = (Get-FileHash $wheelPath -Algorithm SHA256).Hash.ToLower()
  if ($got -ne $want) { throw "checksum mismatch for $wheelName; nothing was installed" }

  # Stage a fresh venv inside the tool folder; the previous install stays untouched until the new one works.
  New-Item -ItemType Directory -Path $homeDir -Force | Out-Null
  New-Item -ItemType Directory -Path $binDir -Force | Out-Null
  if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
  $prefix = @(); if ($python.Count -gt 1) { $prefix = $python[1..($python.Count - 1)] }
  & $python[0] @prefix -m venv $stage
  if ($LASTEXITCODE -ne 0) { throw 'python -m venv failed; on Debian/Ubuntu install the venv module with: sudo apt-get install -y python3-venv, then run this again.' }
  $venvPython = if ($onWindows) { Join-Path $stage 'Scripts\python.exe' } else { Join-Path $stage 'bin/python' }
  # The package has no dependencies (pyproject: dependencies = []), so --no-index: nothing is fetched from PyPI.
  & $venvPython -m pip install --no-index --disable-pip-version-check --quiet $wheelPath
  if ($LASTEXITCODE -ne 0) { throw "pip could not install $wheelName into the new venv; nothing was changed" }
  $version = & $venvPython -c 'from importlib.metadata import version; print(version("champollion-protocol"))'
  if ($LASTEXITCODE -ne 0) { throw 'the new copy does not report its version; nothing was changed' }
  & $venvPython -m champollion --help *> $null
  if ($LASTEXITCODE -ne 0) { throw "the new copy does not run 'champollion --help'; nothing was changed" }

  # Move into place last: swap the staged venv over the old one, then drop the old one.
  $old = "$venv.old"
  if (Test-Path $old) { Remove-Item -Recurse -Force $old }
  if (Test-Path $venv) { Move-Item $venv $old }
  Move-Item $stage $venv
  if (Test-Path $old) { Remove-Item -Recurse -Force $old }

  # The venv was staged under a temporary name, so its console scripts are stale; the shim runs the module
  # through the venv interpreter instead, which is location-independent.
  if ($onWindows) {
    $shim = Join-Path $binDir 'champollion.cmd'
    $finalPython = Join-Path $venv 'Scripts\python.exe'
    Set-Content -Path $shim -Value "@echo off`r`n`"$finalPython`" -m champollion %*" -Encoding ASCII
    # Add the bin folder to the USER Path only when it is absent (Windows only; never the machine Path).
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $already = @($userPath -split ';' | Where-Object { $_.TrimEnd('\') -ieq $binDir.TrimEnd('\') -and $_ })
    if ($already.Count -eq 0) {
      $newPath = if ($userPath) { $userPath.TrimEnd(';') + ';' + $binDir } else { $binDir }
      [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
      Write-Host "Added $binDir to your user PATH; open a new terminal to use it."
    }
    & $shim --help *> $null
  } else {
    $shim = Join-Path $binDir 'champollion'
    $finalPython = Join-Path $venv 'bin/python'
    Set-Content -Path $shim -Value "#!/bin/sh`nexec `"$finalPython`" -m champollion `"`$@`"`n"
    & chmod 755 $shim
    & $shim --help *> $null
  }
  if ($LASTEXITCODE -ne 0) { throw "the installed command does not run: $shim --help" }
  Write-Host "Champollion $version installed ($shim)."
  Write-Host 'Next: champollion init my-translation'
} finally {
  Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
  if (Test-Path $stage) { Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue }
}