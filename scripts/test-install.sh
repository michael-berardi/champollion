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
echo "== windows script: PowerShell 7 container (Linux) =="
docker run --rm --name champollion-pwsh-test \
  --add-host=host.docker.internal:host-gateway \
  -e TEST_BASE="http://host.docker.internal:$PORT" \
  -v "$T:/test:ro" mcr.microsoft.com/powershell pwsh -NoProfile -File /test/win.ps1

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