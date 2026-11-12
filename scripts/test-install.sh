#!/bin/sh
# Installer tests: builds the release assets, serves them from a short-lived local http server, and runs
# scripts/install.sh here (macOS or Linux host), in an ubuntu:24.04 container, and scripts/install.ps1 under
# PowerShell 7 in the mcr.microsoft.com/powershell container. Needs docker, curl and python3.
# Usage: scripts/test-install.sh          (PYTHON=python3.14 to pick the release-build interpreter)
set -eu
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"
export PYTHON
PORT="${CHAMPOLLION_TEST_PORT:-18473}"
command -v docker >/dev/null 2>&1 || { echo "test-install: needs docker" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "test-install: needs curl" >&2; exit 1; }

sh scripts/build-release.sh

# Stage under the repo's gitignored dist/: Docker (colima) shares the home folder but not $TMPDIR,
# and the containers mount this folder read-only.
mkdir -p dist
T=$(mktemp -d "$(pwd)/dist/test.XXXXXX")
SERVER_PID=""
cleanup() {
  if [ -n "$SERVER_PID" ]; then kill "$SERVER_PID" 2>/dev/null || true; wait "$SERVER_PID" 2>/dev/null || true; fi
  rm -rf "$T"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

mkdir "$T/www"
cp -R dist/release "$T/www/good"
cp -R dist/release "$T/www/bad"
WHEEL=$(awk '$2 ~ /\.whl$/ { print $2 }' "$T/www/bad/SHA256SUMS")
printf 'corrupted' >> "$T/www/bad/$WHEEL"

"$PYTHON" -m http.server "$PORT" --directory "$T/www" >"$T/server.log" 2>&1 &
SERVER_PID=$!
i=0
until curl -fsS -o /dev/null "http://127.0.0.1:$PORT/good/SHA256SUMS"; do
  i=$((i + 1)); [ "$i" -lt 50 ] || { echo "test-install: local release server did not start on port $PORT" >&2; exit 1; }
  sleep 0.2
done
BASE="http://127.0.0.1:$PORT"

echo "== host: install, version, upgrade =="
mkdir -p "$T/h1"
HOME="$T/h1" CHAMPOLLION_RELEASE_BASE="$BASE/good" sh scripts/install.sh >"$T/h1.log" 2>&1 || { cat "$T/h1.log" >&2; exit 1; }
grep -E 'Champollion [0-9]+\.[0-9]+' "$T/h1.log" >/dev/null || { echo "test-install: no version printed" >&2; exit 1; }
"$T/h1/.local/bin/champollion" --help >/dev/null || { echo "test-install: installed command does not run" >&2; exit 1; }
HOME="$T/h1" CHAMPOLLION_RELEASE_BASE="$BASE/good" sh scripts/install.sh >"$T/h1-again.log" 2>&1 || { cat "$T/h1-again.log" >&2; exit 1; }
"$T/h1/.local/bin/champollion" --help >/dev/null
echo "host install and upgrade ok"

echo "== host: corrupted wheel refused =="
mkdir -p "$T/h3"
if HOME="$T/h3" CHAMPOLLION_RELEASE_BASE="$BASE/bad" sh scripts/install.sh >"$T/h3.log" 2>&1; then
  echo "test-install: corrupted wheel was accepted" >&2; exit 1
fi
grep -q 'checksum mismatch' "$T/h3.log" || { cat "$T/h3.log" >&2; echo "test-install: wrong error for corrupted wheel" >&2; exit 1; }
[ ! -e "$T/h3/.champollion" ] || { echo "test-install: corrupted run left an install behind" >&2; exit 1; }
echo "host corruption refusal ok"

echo "== host: foreign command left alone, own shim upgraded =="
mkdir -p "$T/h5/.local/bin"
printf '#!/bin/sh\necho foreign\n' > "$T/h5/.local/bin/champollion"; chmod 755 "$T/h5/.local/bin/champollion"
HOME="$T/h5" CHAMPOLLION_RELEASE_BASE="$BASE/good" sh scripts/install.sh >"$T/h5.log" 2>&1 || { cat "$T/h5.log" >&2; exit 1; }
grep -q 'Left .* alone' "$T/h5.log" || { cat "$T/h5.log" >&2; echo "test-install: foreign command not reported" >&2; exit 1; }
[ "$("$T/h5/.local/bin/champollion")" = foreign ] || { echo "test-install: foreign command was overwritten" >&2; exit 1; }
grep -q 'Health check: usage' "$T/h5.log" || { cat "$T/h5.log" >&2; echo "test-install: health result not printed" >&2; exit 1; }
grep -q 'Health check: usage' "$T/h1.log" || { echo "test-install: health result not printed" >&2; exit 1; }
grep -q champollion-installer-shim "$T/h1/.local/bin/champollion" || { echo "test-install: shim has no marker" >&2; exit 1; }
# A 1.6.0-shaped shim (no marker) is ours and is replaced.
mkdir -p "$T/h6/.local/bin"
printf '#!/bin/sh\nexec "%s/.champollion/venv/bin/python" -m champollion "$@"\n' "$T/h6" > "$T/h6/.local/bin/champollion"; chmod 755 "$T/h6/.local/bin/champollion"
HOME="$T/h6" CHAMPOLLION_RELEASE_BASE="$BASE/good" sh scripts/install.sh >"$T/h6.log" 2>&1 || { cat "$T/h6.log" >&2; exit 1; }
! grep -q 'Left .* alone' "$T/h6.log" || { cat "$T/h6.log" >&2; echo "test-install: 1.6.0 shim treated as foreign" >&2; exit 1; }
grep -q champollion-installer-shim "$T/h6/.local/bin/champollion" || { echo "test-install: 1.6.0 shim not upgraded" >&2; exit 1; }
echo "host shim marker ok"

echo "== host: missing Python named =="
mkdir -p "$T/nopy" "$T/h4"
for tool in curl wget sha256sum shasum mktemp uname rm awk head cut mkdir cat chmod mv dirname basename sed grep; do
  p=$(command -v "$tool" 2>/dev/null) && ln -s "$p" "$T/nopy/$tool"
done
if PATH="$T/nopy" HOME="$T/h4" CHAMPOLLION_RELEASE_BASE="$BASE/good" /bin/sh scripts/install.sh >"$T/h4.log" 2>&1; then
  echo "test-install: installer ran without Python" >&2; exit 1
fi
grep -q 'Python 3.9' "$T/h4.log" || { cat "$T/h4.log" >&2; echo "test-install: missing Python not named" >&2; exit 1; }
[ ! -e "$T/h4/.champollion" ] || { echo "test-install: no-Python run left an install behind" >&2; exit 1; }
echo "host missing-prerequisite ok"

cat > "$T/linux.sh" <<'LINUX'
set -eu
apt-get update -qq
apt-get install -y -qq --no-install-recommends curl ca-certificates >/dev/null
if CHAMPOLLION_RELEASE_BASE="$TEST_BASE/good" sh /test/www/good/install.sh >/tmp/nopy.log 2>&1; then
  echo "installer ran without Python" >&2; exit 1
fi
grep -q "Python 3.9" /tmp/nopy.log
apt-get install -y -qq --no-install-recommends python3 python3-venv >/dev/null
CHAMPOLLION_RELEASE_BASE="$TEST_BASE/good" sh /test/www/good/install.sh >/tmp/ok.log 2>&1 || { cat /tmp/ok.log; exit 1; }
cat /tmp/ok.log
grep -Eq "Champollion [0-9]+\.[0-9]+" /tmp/ok.log || { echo "no version printed" >&2; exit 1; }
"$HOME/.local/bin/champollion" --help >/dev/null
CHAMPOLLION_RELEASE_BASE="$TEST_BASE/good" sh /test/www/good/install.sh
"$HOME/.local/bin/champollion" --help >/dev/null
if CHAMPOLLION_RELEASE_BASE="$TEST_BASE/bad" CHAMPOLLION_HOME=/tmp/badhome sh /test/www/good/install.sh >/tmp/bad.log 2>&1; then
  echo "corrupted wheel was accepted" >&2; exit 1
fi
grep -q "checksum mismatch" /tmp/bad.log
[ ! -e /tmp/badhome ] || { echo "corrupted run left an install behind" >&2; exit 1; }
echo "linux container tests passed"
LINUX
echo "== linux: ubuntu:24.04 container =="
docker run --rm --name champollion-install-test \
  --add-host=host.docker.internal:host-gateway \
  -e TEST_BASE="http://host.docker.internal:$PORT" \
  -v "$T:/test:ro" ubuntu:24.04 sh /test/linux.sh

cat > "$T/win.ps1" <<'WIN'
$ErrorActionPreference = 'Stop'
apt-get update -qq
apt-get install -y -qq --no-install-recommends python3 python3-venv | Out-Null
$env:CHAMPOLLION_RELEASE_BASE = "$env:TEST_BASE/good"
$out = & /test/www/good/install.ps1 *>&1 | Out-String
Write-Host $out
if ($out -notmatch 'Champollion \d+\.\d+') { throw 'no version printed' }
& "$HOME/.local/bin/champollion" --help | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'installed shim failed' }
& /test/www/good/install.ps1
# Relative home and bin overrides (with a dot segment) are normalised; the fresh install must survive.
New-Item -ItemType Directory -Path /tmp/rel -Force | Out-Null
Push-Location /tmp/rel
$env:CHAMPOLLION_RELEASE_BASE = "$env:TEST_BASE/good"
$env:CHAMPOLLION_HOME = './x/../home'
$env:CHAMPOLLION_BIN_DIR = './bin'
& /test/www/good/install.ps1
if (-not (Test-Path /tmp/rel/home/venv/bin/python)) { throw 'relative CHAMPOLLION_HOME: install was deleted or misplaced' }
if (-not (Test-Path /tmp/rel/bin/champollion)) { throw 'relative CHAMPOLLION_BIN_DIR: shim missing' }
& /test/www/good/install.ps1
if (-not (Test-Path /tmp/rel/home/venv/bin/python)) { throw 'relative home: upgrade deleted the install' }
# A command the installer did not write is left alone; its own shim is upgraded.
Set-Content /tmp/rel/bin/champollion "#!/bin/sh`necho foreign`n"
$out = & /test/www/good/install.ps1 *>&1 | Out-String
if ($out -notmatch 'Left .* alone') { throw 'foreign command not reported' }
if ((Get-Content /tmp/rel/bin/champollion -Raw) -notmatch 'foreign') { throw 'foreign command was overwritten' }
if ($out -notmatch 'Health check: usage') { throw 'health result not printed' }
# A 1.6.0-shaped shim (no marker) is ours and is replaced.
Set-Content /tmp/rel/bin/champollion "#!/bin/sh`nexec `"/tmp/rel/home/venv/bin/python`" -m champollion `"`$@`"`n"
$out = & /test/www/good/install.ps1 *>&1 | Out-String
if ($out -match 'Left .* alone') { throw '1.6.0 shim treated as foreign' }
if (-not (Select-String -Path /tmp/rel/bin/champollion -Pattern champollion-installer-shim -SimpleMatch -Quiet)) { throw '1.6.0 shim not upgraded' }
Pop-Location
Remove-Item Env:CHAMPOLLION_HOME, Env:CHAMPOLLION_BIN_DIR
if (Get-Command Install-Champollion -ErrorAction SilentlyContinue) { throw 'installer function leaked into the session' }
if (Select-String -Path "$HOME/.local/bin/champollion" -Pattern champollion-installer-shim -SimpleMatch -Quiet) {} else { throw 'shim has no marker' }
$env:CHAMPOLLION_RELEASE_BASE = "$env:TEST_BASE/bad"
$env:CHAMPOLLION_HOME = '/tmp/badhome'
$refused = $false
try { & /test/www/good/install.ps1 } catch {
  if ($_.Exception.Message -match 'checksum mismatch') { $refused = $true } else { throw }
}
if (-not $refused) { throw 'corrupted wheel was accepted' }
if (Test-Path '/tmp/badhome') { throw 'corrupted run left an install behind' }
Write-Host 'pwsh container tests passed'
try {
  Install-Module PSScriptAnalyzer -Force -Scope CurrentUser -ErrorAction Stop
  $r = Invoke-ScriptAnalyzer -Path /test/www/good/install.ps1
  if ($r) { $r | Format-Table -AutoSize | Out-String | Write-Host } else { Write-Host 'PSScriptAnalyzer: clean' }
} catch { Write-Host "PSScriptAnalyzer skipped: $($_.Exception.Message)" }
WIN
# mcr.microsoft.com/powershell publishes no arm64 Linux image (amd64 and 32-bit arm only), so the
# PowerShell 7 tests run in a small local image: ubuntu:24.04 plus Microsoft's official arm64/x64 tarball.
PS_VERSION=7.4.6
PWSH_IMAGE="pwsh-install-test:$PS_VERSION"
if ! docker image inspect "$PWSH_IMAGE" >/dev/null 2>&1; then
  echo "building $PWSH_IMAGE (ubuntu:24.04 plus the official PowerShell $PS_VERSION tarball)"
  docker build -q -t "$PWSH_IMAGE" - >/dev/null <<DOCKERFILE || { echo "test-install: cannot build the PowerShell $PS_VERSION test image" >&2; exit 1; }
FROM ubuntu:24.04
RUN apt-get update -qq && apt-get install -y -qq ca-certificates curl libicu74 >/dev/null \\
 && case "\$(uname -m)" in aarch64) a=arm64 ;; x86_64) a=x64 ;; *) echo "unsupported CPU \$(uname -m)" >&2; exit 1 ;; esac \\
 && curl -fsSL --retry 3 -o /tmp/ps.tgz "https://github.com/PowerShell/PowerShell/releases/download/v$PS_VERSION/powershell-$PS_VERSION-linux-\$a.tar.gz" \\
 && mkdir -p /opt/powershell && tar -xzf /tmp/ps.tgz -C /opt/powershell && chmod +x /opt/powershell/pwsh \\
 && ln -s /opt/powershell/pwsh /usr/bin/pwsh && rm /tmp/ps.tgz
DOCKERFILE
fi
echo "== windows script: PowerShell 7 container ($PWSH_IMAGE, Linux) =="
docker run --rm --name champollion-pwsh-test \
  --add-host=host.docker.internal:host-gateway \
  -e TEST_BASE="http://host.docker.internal:$PORT" \
  -v "$T:/test:ro" "$PWSH_IMAGE" pwsh -NoProfile -File /test/win.ps1

kill "$SERVER_PID" 2>/dev/null || true
wait "$SERVER_PID" 2>/dev/null || true
SERVER_PID=""
"$PYTHON" - "$PORT" <<'PY'
import socket, sys
port = int(sys.argv[1])
with socket.socket() as s:
    s.settimeout(2)
    if s.connect_ex(("127.0.0.1", port)) == 0:
        sys.exit(f"test-install: port {port} is still in use after stopping the server")
print(f"release server stopped; port {port} released")
PY
echo "all installer tests passed"