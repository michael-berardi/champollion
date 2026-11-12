#!/bin/sh
# Champollion installer for macOS and Linux:
#   curl -fsSL https://github.com/your-github-username/champollion/releases/latest/download/install.sh | sh
# (replace your-github-username with the repository owner; release copies built by scripts/build-release.sh
#  already name the owner recorded in the git remote.)
# Downloads the release wheel named in SHA256SUMS, checks its SHA-256, and installs it into a private venv
# under ~/.champollion. The package is pure Python standard library with no dependencies, so nothing else
# is fetched. Uses the Python 3.9+ already on this machine; if none exists it says how to install one.
# Environment: CHAMPOLLION_HOME (default ~/.champollion), CHAMPOLLION_BIN_DIR (default ~/.local/bin),
# CHAMPOLLION_VERSION (default: latest, e.g. 1.6.1), CHAMPOLLION_RELEASE_BASE (override the download base URL, used by tests).
set -eu

REPO="your-github-username/champollion"
HOME_DIR="${CHAMPOLLION_HOME:-$HOME/.champollion}"
case "$HOME_DIR" in /*) ;; *) HOME_DIR="$(pwd)/$HOME_DIR" ;; esac
BIN_DIR="${CHAMPOLLION_BIN_DIR:-$HOME/.local/bin}"
case "$BIN_DIR" in /*) ;; *) BIN_DIR="$(pwd)/$BIN_DIR" ;; esac
if [ -n "${CHAMPOLLION_RELEASE_BASE:-}" ]; then BASE="$CHAMPOLLION_RELEASE_BASE"
elif [ -n "${CHAMPOLLION_VERSION:-}" ]; then BASE="https://github.com/$REPO/releases/download/v${CHAMPOLLION_VERSION#v}"
else BASE="https://github.com/$REPO/releases/latest/download"; fi

say() { printf '%s\n' "$*"; }
die() { printf 'champollion install: %s\n' "$*" >&2; exit 1; }

if command -v curl >/dev/null 2>&1; then fetch() { curl -fsSL --retry 3 -o "$2" "$1" || die "download failed: $1"; }
elif command -v wget >/dev/null 2>&1; then fetch() { wget -q -O "$2" "$1" || die "download failed: $1"; }
else die "needs curl or wget; install one with your package manager, then run this again"; fi

if command -v sha256sum >/dev/null 2>&1; then sha256() { sha256sum "$1" | cut -d' ' -f1; }
elif command -v shasum >/dev/null 2>&1; then sha256() { shasum -a 256 "$1" | cut -d' ' -f1; }
else die "needs sha256sum or shasum"; fi

main() {
TMP=$(mktemp -d "${TMPDIR:-/tmp}/champollion-install.XXXXXX") || die "cannot create a temporary folder"
STAGE=""
trap 'rm -rf "$TMP"; [ -z "$STAGE" ] || rm -rf "$STAGE"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

case "$BASE" in *your-github-username*) die "this install.sh has no release repository configured; use the install.sh attached to a GitHub release (built by scripts/build-release.sh), or set CHAMPOLLION_RELEASE_BASE" ;; esac

# expect <file> <name> <sums-file>: the file's SHA-256 must equal the line for <name> in the sums file.
expect() {
  want=$(awk -v n="$2" '{ f=$2; sub(/^\*/, "", f); if (f == n) print $1 }' "$3")
  [ -n "$want" ] || die "no checksum for $2 in $(basename "$3")"
  [ "$(sha256 "$1")" = "$want" ] || die "checksum mismatch for $2; nothing was installed"
}

# Python 3.9 or newer, from this machine only (a system Python is never installed by this script).
PYTHON=""
for c in python3 python python3.14 python3.13 python3.12 python3.11 python3.10 python3.9; do
  command -v "$c" >/dev/null 2>&1 || continue
  if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
    PYTHON=$(command -v "$c"); break
  fi
done
if [ -z "$PYTHON" ]; then
  case "$(uname -s)" in
    Darwin) die "needs Python 3.9 or later and none was found; install it with: brew install python3 (or download it from https://www.python.org/downloads/), then run this again" ;;
    Linux)
      if command -v apt-get >/dev/null 2>&1; then hint="sudo apt-get install -y python3 python3-venv"
      elif command -v dnf >/dev/null 2>&1; then hint="sudo dnf install -y python3"
      elif command -v apk >/dev/null 2>&1; then hint="sudo apk add python3"
      else hint="install Python 3.9+ with your package manager (or from https://www.python.org/downloads/)"; fi
      die "needs Python 3.9 or later and none was found; install it with: $hint, then run this again" ;;
    *) die "needs Python 3.9 or later and none was found; on Windows use install.ps1" ;;
  esac
fi

say "Downloading Champollion..."
fetch "$BASE/SHA256SUMS" "$TMP/SHA256SUMS"
WHEEL=$(awk '{ f=$2; sub(/^\*/, "", f); if (f ~ /^champollion_protocol-.*-py3-none-any\.whl$/) print f }' "$TMP/SHA256SUMS" | head -n 1)
[ -n "$WHEEL" ] || die "SHA256SUMS lists no champollion_protocol wheel; the release is incomplete"
fetch "$BASE/$WHEEL" "$TMP/$WHEEL"
expect "$TMP/$WHEEL" "$WHEEL" "$TMP/SHA256SUMS"

# Stage a fresh venv inside the tool folder; the previous install stays untouched until the new one works.
mkdir -p "$HOME_DIR" "$BIN_DIR" || die "cannot create $HOME_DIR or $BIN_DIR"
VENV="$HOME_DIR/venv"
STAGE="$HOME_DIR/venv.tmp.$$"
rm -rf "$STAGE"
"$PYTHON" -m venv "$STAGE" || die "python3 -m venv failed; on Debian/Ubuntu install the venv module with: sudo apt-get install -y python3-venv, then run this again"
# The package has no dependencies (pyproject: dependencies = []), so --no-index: nothing is fetched from PyPI.
"$STAGE/bin/python" -m pip install --no-index --disable-pip-version-check --quiet "$TMP/$WHEEL" \
  || die "pip could not install $WHEEL into the new venv; nothing was changed"
VERSION=$("$STAGE/bin/python" -c 'from importlib.metadata import version; print(version("champollion-protocol"))') \
  || die "the new copy does not report its version; nothing was changed"
"$STAGE/bin/python" -m champollion --help >/dev/null 2>&1 \
  || die "the new copy does not run 'champollion --help'; nothing was changed"

# Move into place last: swap the staged venv over the old one, then drop the old one.
rm -rf "$VENV.old"
if [ -d "$VENV" ]; then mv "$VENV" "$VENV.old" || die "cannot move the old install aside"; fi
mv "$STAGE" "$VENV" || { [ ! -d "$VENV.old" ] || mv "$VENV.old" "$VENV"; die "cannot move the new venv into place"; }
STAGE=""
rm -rf "$VENV.old"

# The venv was staged under a temporary name, so its console-script shebangs are stale; the shim runs the
# module through the venv interpreter instead, which is location-independent.
# Never overwrite a file this installer did not write: only a file carrying the marker is ours.
SHIM="$BIN_DIR/champollion"
if [ -e "$SHIM" ] && ! grep -q 'champollion-installer-shim' "$SHIM" 2>/dev/null; then
  say "Left $SHIM alone: it exists and was not written by this installer. Run Champollion with: $VENV/bin/python -m champollion"
  SHIM="$VENV/bin/python -m champollion"
  HEALTH=$("$VENV/bin/python" -m champollion --help 2>&1) || die "the installed command does not run: $SHIM --help"
else
  cat > "$BIN_DIR/champollion.tmp.$$" <<SHIM
#!/bin/sh
# champollion-installer-shim
exec "$VENV/bin/python" -m champollion "\$@"
SHIM
  chmod 755 "$BIN_DIR/champollion.tmp.$$"
  mv -f "$BIN_DIR/champollion.tmp.$$" "$SHIM"
  HEALTH=$("$SHIM" --help 2>&1) || die "the installed command does not run: $SHIM --help (${HEALTH:-no output})"
fi
say "Health check: $(printf '%s\n' "$HEALTH" | head -n 1)"
say "Champollion $VERSION installed ($SHIM)."
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) say "Add $BIN_DIR to your PATH:  export PATH=\"$BIN_DIR:\$PATH\"" ;; esac
say "Next: champollion init my-translation"
}

main "$@"