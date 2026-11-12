#!/bin/sh
# Builds the release assets into <out> (default dist/release):
#   champollion_protocol-<version>-py3-none-any.whl   the installable wheel (built by scripts/build-release.py)
#   champollion_protocol-<version>.tar.gz             the source archive
#   install.sh, install.ps1                           the installers, with the release repository taken from the git remote
#   SHA256SUMS                                        checksums of the four files above
# The installers read the wheel name from SHA256SUMS, so releases/latest/download works without knowing the version.
# Usage: scripts/build-release.sh [out-dir]   (run from a clean checkout; PYTHON must have pip and setuptools>=77)
set -eu
cd "$(dirname "$0")/.."
OUT="${1:-dist/release}"
PYTHON="${PYTHON:-python3}"

[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "build-release: the working tree has changes; build from a clean checkout" >&2; exit 1; }
"$PYTHON" -c 'import pip, setuptools' >/dev/null 2>&1 || { echo "build-release: $PYTHON lacks pip or setuptools>=77; run with an interpreter that has them, e.g. PYTHON=python3.14 scripts/build-release.sh" >&2; exit 1; }

# The release repository comes from the git remote, so the checked-in installers stay owner-neutral.
url=$(git config --get remote.origin.url) || { echo "build-release: no git remote origin; cannot address the release downloads" >&2; exit 1; }
repo=$(printf '%s\n' "$url" | sed -e 's#^https://github.com/##' -e 's#^git@github.com:##' -e 's#\.git$##')
case "$repo" in
  */*) ;;
  *) echo "build-release: remote origin is not a GitHub repository URL: $url" >&2; exit 1 ;;
esac
case "$repo" in *[!A-Za-z0-9._/-]*) echo "build-release: unexpected characters in repository name: $repo" >&2; exit 1 ;; esac

# Reproducible wheel and source archive (scripts/build-release.py writes dist/ and dist/SHA256SUMS).
"$PYTHON" scripts/build-release.py
wheel=$(awk '$2 ~ /\.whl$/ { print $2 }' dist/SHA256SUMS)
sdist=$(awk '$2 ~ /\.tar\.gz$/ { print $2 }' dist/SHA256SUMS)
[ -n "$wheel" ] && [ -n "$sdist" ] || { echo "build-release: dist/SHA256SUMS lists no wheel or source archive" >&2; exit 1; }

rm -rf "$OUT"; mkdir -p "$OUT"
cp "dist/$wheel" "dist/$sdist" "$OUT/"
sed "s#your-github-username/champollion#$repo#g" scripts/install.sh > "$OUT/install.sh"
sed "s#your-github-username/champollion#$repo#g" scripts/install.ps1 > "$OUT/install.ps1"
chmod 755 "$OUT/install.sh" "$OUT/install.ps1"
( cd "$OUT" && if command -v sha256sum >/dev/null 2>&1; then sha256sum "$wheel" "$sdist" install.sh install.ps1; else shasum -a 256 "$wheel" "$sdist" install.sh install.ps1; fi > SHA256SUMS )
echo "built $OUT for $repo"
ls -l "$OUT"