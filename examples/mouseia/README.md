# Checking a user-supplied Mouseia checkout

Mouseia is an existing corpus with Musean and Plain English editions.
Champollion supplies a read-only vocabulary adapter and a Mouseia profile;
it does not ship Mouseia's corpus or certify its editions. Bring your own
checkout. No private machine path, network service, or browser is required.

## Read-only diagnostic run

Start in the Champollion repository. Set `MOUSEIA_ROOT` to **your** checkout
and choose one work; the example below selects the Emerald Tablet, not the
whole corpus. A small local profile copy explicitly resolves Mouseia's name
table without changing the checkout or disabling any core check:

```sh
export CHAMPOLLION_ROOT="$PWD"
export MOUSEIA_ROOT="$(cd ../your-mouseia-checkout && pwd)"
export DIAGNOSTIC_DIR="$PWD/mouseia-diagnostics"
export WORK="corpus/emerald-tablet.md"
mkdir -p "$DIAGNOSTIC_DIR"
python3 - <<'PY'
import json, os
from pathlib import Path
repo = Path(os.environ['CHAMPOLLION_ROOT'])
profile = json.loads((repo / 'profiles/mouseia.json').read_text(encoding='utf-8'))
profile['checks']['name_table'] = 'scripts/names.json'
# Keep name='mouseia': it selects the explicit legacy adapter.
(Path(os.environ['DIAGNOSTIC_DIR']) / 'profile.json').write_text(
    json.dumps(profile, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
PY
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$CHAMPOLLION_ROOT/src" \
  python3 -m champollion check --root "$MOUSEIA_ROOT" \
  --profile "$DIAGNOSTIC_DIR/profile.json" "$WORK"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$CHAMPOLLION_ROOT/src" \
  python3 -m champollion check --root "$MOUSEIA_ROOT" \
  --profile "$DIAGNOSTIC_DIR/profile.json" "$WORK" --json
```

Replace the placeholder checkout path before running. If Champollion is
installed, its console command can replace `python3 -m champollion` and
`PYTHONPATH` is unnecessary. `check` does not modify the work or fetch missing
sources. The generated profile is a diagnostic project record, not an
immutable vendor pin or an approved adoption.

Expect diagnostics on legacy data. A legacy `source: corpus/SOURCES.md
registry` is a human-readable citation, **not** a local JSON source record;
Champollion does not manufacture a hash pin or rights record from it.
Missing records, numbering differences, and missing provenance remain
findings. Exit 0 means no blocking mechanical finding, 1 means error
findings, and 2 means an operational/configuration failure. Review the JSON
`publication_gate`, `review_records`, adapter mappings, and individual gate
states even when the command exits 0.

## What the adapter does—and does not do

- Maps `curated_translator`/`curated_note` to
  `musean_translator`/`musean_note`; conflicting values are refused.
- Recognizes the profile's Musean and Plain section aliases; conflicting
  Musean sections are refused rather than overwritten.
- Preserves optional historical divisions. Positional alignment needs equal
  counts and an edition-specific mapping; it is not a house translation.
- Retains Mouseia's legacy speech-check scope (`iliad`, `odyssey`) and reports
  that scope explicitly. Other works do not receive that legacy speech gate.
- Leaves unknown sections preserved but unchecked. In particular,
  `Reference translation` is not an implicitly certified register.

The adapter does not copy sources, translate text, repair omissions, infer
rights, import a timeless lint baseline, create reviews, or approve a
legacy `Published` value. Legacy lint parity and Champollion conformance
are different claims.

## Prepare an adoption without editing the checkout

Use a separate project directory. Copy the selected complete work into
`works/<slug>.md`, its actual raw snapshot into a project-relative path,
and `scripts/names.json` into `names.json`. Reference the shipped Mouseia
profile from `champollion.json` with a relative `profile_path` appropriate
to that directory; keep the shipped name-table setting when supplying
`names.json`. Do not bake a private absolute path into a shared project.

Replace legacy prose source references in the **copied** work with a local
manifest selector such as `sources/manifest.json#<source-id>`. Register the
real provider, edition and immutable revision; hash the stored raw bytes;
record underlying-work and transcription rights separately with genuine
evidence, cleaning rules, whole-work boundaries, aids and uncertainty.
Do not guess a provider acquisition date. Change copied publication state
to a draft until the required records and gates exist. Preserve historical
credits and record adapter changes explicitly.

Then select the copied work with `champollion check --root <project>
works/<slug>.md --json`. A mechanical report cannot establish sense,
register independence, source rights interpretation, or that someone read
the text aloud. VER-10/VER-11 judgement and resolution of blockers remain
necessary before publication; no such review is supplied by this README.
