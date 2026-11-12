# Champollion installer for Windows (PowerShell 5.1 and 7):
#   irm https://github.com/your-github-username/champollion/releases/latest/download/install.ps1 | iex
# (replace your-github-username with the repository owner; release copies built by scripts/build-release.sh
#  already name the owner recorded in the git remote.)
# Downloads the release wheel named in SHA256SUMS, checks its SHA-256, and installs it into a private venv
# under %LOCALAPPDATA%\Champollion. The package is pure Python standard library with no dependencies, so
# nothing else is fetched. Uses the Python 3.9+ already on this machine; if none exists it says how to get one.
# Also runs under PowerShell 7 on Linux for testing (CHAMPOLLION_HOME / CHAMPOLLION_BIN_DIR overrides).
# The whole installer is one function that is called last and removed afterwards, so running it through
# `irm | iex` leaves no variables, preferences or functions behind in the user's session. It never calls
# `exit` (that would close the user's shell); failures are thrown.
function Install-Champollion {
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # the progress bar makes downloads very slow on Windows PowerShell 5.1
$Repo = 'your-github-username/champollion'
$ShimMarker = 'champollion-installer-shim'
$base = if ($env:CHAMPOLLION_RELEASE_BASE) { $env:CHAMPOLLION_RELEASE_BASE }
        elseif ($env:CHAMPOLLION_VERSION) { "https://github.com/$Repo/releases/download/v$($env:CHAMPOLLION_VERSION.TrimStart('v'))" }
        else { "https://github.com/$Repo/releases/latest/download" }
if ($base -like '*your-github-username*') {
  throw 'This install.ps1 has no release repository configured; use the install.ps1 attached to a GitHub release (built by scripts/build-release.sh), or set CHAMPOLLION_RELEASE_BASE.'
}

# Runs a native command with its output captured. Windows PowerShell 5.1 turns the first stderr line of a
# captured native command into a terminating error under 'Stop', so this runs under 'Continue' and the
# caller tests the exit code instead.
function Invoke-Native([string]$File, [string[]]$Arguments) {
  $ErrorActionPreference = 'Continue'
  $lines = @(& $File @Arguments 2>&1 | ForEach-Object { "$_" })
  [pscustomobject]@{ Code = $LASTEXITCODE; Output = ($lines -join "`n") }
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
$defaultBin = Join-Path $homeDir 'bin'
$binDir = if ($env:CHAMPOLLION_BIN_DIR) { $env:CHAMPOLLION_BIN_DIR }
          elseif ($onWindows) { $defaultBin }
          else { Join-Path $HOME '.local/bin' }
# Normalise now: a relative or forward-slash override must name the same folder for every later comparison.
$homeDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($homeDir)
$binDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($binDir)
$defaultBin = Join-Path $homeDir 'bin'

# Python 3.9 or newer, from this machine only (a system Python is never installed by this script).
$python = $null
$candidates = if ($onWindows) { @(@('py', '-3'), @('python'), @('python3')) } else { @(@('python3'), @('python')) }
foreach ($c in $candidates) {
  if (-not (Get-Command $c[0] -ErrorAction SilentlyContinue)) { continue }
  $prefix = @(); if ($c.Count -gt 1) { $prefix = $c[1..($c.Count - 1)] }
  $probe = Invoke-Native $c[0] ($prefix + @('-c', 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'))
  if ($probe.Code -eq 0) { $python = $c; break }
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
  $r = Invoke-Native $python[0] ($prefix + @('-m', 'venv', $stage))
  if ($r.Code -ne 0) { throw 'python -m venv failed; on Debian/Ubuntu install the venv module with: sudo apt-get install -y python3-venv, then run this again.' }
  $venvPython = if ($onWindows) { Join-Path $stage 'Scripts\python.exe' } else { Join-Path $stage 'bin/python' }
  # The package has no dependencies (pyproject: dependencies = []), so --no-index: nothing is fetched from PyPI.
  $r = Invoke-Native $venvPython @('-m', 'pip', 'install', '--no-index', '--disable-pip-version-check', '--quiet', $wheelPath)
  if ($r.Code -ne 0) { throw "pip could not install $wheelName into the new venv; nothing was changed" }
  $r = Invoke-Native $venvPython @('-c', 'from importlib.metadata import version; print(version("champollion-protocol"))')
  if ($r.Code -ne 0) { throw 'the new copy does not report its version; nothing was changed' }
  $version = $r.Output.Trim()
  $r = Invoke-Native $venvPython @('-m', 'champollion', '--help')
  if ($r.Code -ne 0) { throw "the new copy does not run 'champollion --help'; nothing was changed" }

  # Move into place last: swap the staged venv over the old one, then drop the old one.
  # If the swap fails after the old venv was moved aside, put it back.
  $old = "$venv.old"
  if (Test-Path $old) { Remove-Item -Recurse -Force $old }
  $movedOld = $false
  if (Test-Path $venv) { Move-Item $venv $old; $movedOld = $true }
  try { Move-Item $stage $venv }
  catch {
    if ($movedOld -and -not (Test-Path $venv)) { Move-Item $old $venv }
    throw "cannot move the new venv into place ($($_.Exception.Message)); the previous install was left as it was"
  }
  if (Test-Path $old) { Remove-Item -Recurse -Force $old }

  # The venv was staged under a temporary name, so its console scripts are stale; the shim runs the module
  # through the venv interpreter instead, which is location-independent.
  if ($onWindows) {
    $shim = Join-Path $binDir 'champollion.cmd'
    $finalPython = Join-Path $venv 'Scripts\python.exe'
    # Never overwrite a file this installer did not write.
    $ours = $true
    if (Test-Path -LiteralPath $shim) {
      # The 1.6.0 shim had no marker; its exact shape is also ours and is upgraded.
      $raw = [string](Get-Content -LiteralPath $shim -Raw)
      $ours = $raw.Contains($ShimMarker) -or ($raw -match '^@echo off\r?\n"[^"]*\\venv\\Scripts\\python\.exe" -m champollion %\*\s*$')
    }
    if ($ours) {
      if ($binDir.TrimEnd('\', '/') -ieq $defaultBin.TrimEnd('\', '/')) {
        # Inside the tool's own folder the shim is relative, so a non-ASCII profile name cannot break it.
        $shimText = "@echo off`r`nREM $ShimMarker`r`n`"%~dp0..\venv\Scripts\python.exe`" -m champollion %*`r`n"
        [IO.File]::WriteAllText($shim, $shimText, (New-Object Text.UTF8Encoding($false)))
      } else {
        # Elsewhere the absolute path is written in the console's OEM code page, which is what cmd.exe reads.
        $shimText = "@echo off`r`nREM $ShimMarker`r`n`"$finalPython`" -m champollion %*`r`n"
        $oem = [Text.Encoding]::GetEncoding([Globalization.CultureInfo]::CurrentCulture.TextInfo.OEMCodePage)
        [IO.File]::WriteAllText($shim, $shimText, $oem)
      }
    } else {
      Write-Host "Left $shim alone: it exists and was not written by this installer. Run Champollion with: `"$finalPython`" -m champollion"
    }
    # Add the bin folder to the USER Path only when it is absent (Windows only; never the machine Path).
    # The raw value is read without expanding %VAR% entries, and written back with the same registry type.
    $envKey = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment', $true)
    try {
      $userPath = [string]$envKey.GetValue('Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
      $already = @($userPath -split ';' | Where-Object {
        $_ -and (($_.TrimEnd('\') -ieq $binDir.TrimEnd('\')) -or ([Environment]::ExpandEnvironmentVariables($_).TrimEnd('\') -ieq $binDir.TrimEnd('\')))
      })
      if ($already.Count -eq 0) {
        $newPath = if ($userPath) { $userPath.TrimEnd(';') + ';' + $binDir } else { $binDir }
        $kind = if ($userPath -match '%') { [Microsoft.Win32.RegistryValueKind]::ExpandString } else { [Microsoft.Win32.RegistryValueKind]::String }
        $envKey.SetValue('Path', $newPath, $kind)
        # Setting any user variable broadcasts the environment change so new terminals pick the Path up.
        [Environment]::SetEnvironmentVariable('CHAMPOLLION_PATH_REFRESH', '1', 'User')
        [Environment]::SetEnvironmentVariable('CHAMPOLLION_PATH_REFRESH', $null, 'User')
        Write-Host "Added $binDir to your user PATH; open a new terminal to use it."
      }
    } finally { if ($envKey) { $envKey.Close() } }
    $health = if ($ours) { Invoke-Native $shim @('--help') } else { Invoke-Native $finalPython @('-m', 'champollion', '--help') }
  } else {
    $shim = Join-Path $binDir 'champollion'
    $finalPython = Join-Path $venv 'bin/python'
    $ours = $true
    if (Test-Path -LiteralPath $shim) {
      # The 1.6.0 shim had no marker; its exact shape is also ours and is upgraded.
      $raw = [string](Get-Content -LiteralPath $shim -Raw)
      $ours = $raw.Contains($ShimMarker) -or ($raw -match '(?m)^exec "[^"]*/venv/bin/python" -m champollion "\$@"\s*$')
    }
    if ($ours) {
      Set-Content -Path $shim -Value "#!/bin/sh`n# $ShimMarker`nexec `"$finalPython`" -m champollion `"`$@`"`n"
      & chmod 755 $shim
      $health = Invoke-Native $shim @('--help')
    } else {
      Write-Host "Left $shim alone: it exists and was not written by this installer. Run Champollion with: $finalPython -m champollion"
      $health = Invoke-Native $finalPython @('-m', 'champollion', '--help')
    }
  }
  if ($health.Code -ne 0) { throw "the installed command does not run: $shim --help" }
  Write-Host ("Health check: " + (($health.Output -split "`n")[0]))
  Write-Host "Champollion $version installed ($shim)."
  Write-Host 'Next: champollion init my-translation'
} finally {
  Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
  if (Test-Path $stage) { Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue }
}
}

try { Install-Champollion } finally { Remove-Item Function:\Install-Champollion -ErrorAction SilentlyContinue }
