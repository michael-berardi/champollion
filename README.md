# Champollion

Champollion is a translation protocol and offline Python toolkit for editors and translators working on complete texts. Keep the original, independent translations, source evidence, and review records together. Check structure and provenance before publication without uploading your texts or calling a model.

Profiles choose the languages, edition styles, and applicable checks. The included Latin-to-Spanish example shows two independent translations from one original. Passing mechanical checks does not establish translation quality or approve publication: that requires recorded editorial review.

The method grew out of [Mouseia](https://mouseia.org), an open library that places original texts beside new translations.

## Install and try it

Requires Python 3.9 or later. On macOS or Linux:

```sh
curl -fsSL https://github.com/michael-berardi/champollion/releases/latest/download/install.sh | sh
```

On Windows (PowerShell):

```powershell
irm https://github.com/michael-berardi/champollion/releases/latest/download/install.ps1 | iex
```

The installer verifies the release wheel's SHA-256 and installs it in a private environment. It prints PATH instructions if needed; run it again to upgrade. The core toolkit has no runtime dependencies outside Python's standard library.

### With pip

In an activated virtual environment, with Git installed:

```sh
python3 -m pip install "champollion-protocol @ git+https://github.com/michael-berardi/champollion.git@v1.10.4"
```

On Windows use `python` instead of `python3`. Pip may download build tooling.

### From source

```sh
git clone https://github.com/michael-berardi/champollion.git
cd champollion
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install .
champollion check --root examples/latin-to-spanish
champollion report --root examples/latin-to-spanish --json
```

On Windows, create the environment with `py -3 -m venv .venv`, activate it with `.\.venv\Scripts\Activate.ps1`, and use `python` instead of `python3`.

The example has no mechanical errors, but its publication gate stays blocked because editorial review has not been recorded.

## Privacy

- Checks, reports, review and export run on your machine; your texts are never uploaded.
- The only automatic network request is the daily update check: one anonymous GET of GitHub's public release record, with no version, id, usage or project data. It is off outside a terminal, in CI and under agents, and `CHAMPOLLION_NO_UPDATE_CHECK=1` turns it off.
- No telemetry, analytics or accounts.
- Details, including every file Champollion writes: [PRIVACY.md](PRIVACY.md).

## Updates

When you run Champollion in a terminal, it checks for a newer release at most once a day and prints a short notice after your command. `champollion update` installs it after checking its SHA-256; `update --check`, `--skip` and `--auto on|off|status` cover the rest. Automatic installs are off unless you turn them on, and `CHAMPOLLION_NO_UPDATE_CHECK=1` turns the check off. See [docs/updates.md](docs/updates.md).

## Start a translation

```sh
champollion init my-translation
champollion profile validate my-translation/profiles/generic.json
```

This creates `works/`, a source manifest, and `champollion.json` pointing to a local profile. Edit that profile to select languages and editions. Follow the [first-work guide](docs/authoring.md) to add a source snapshot, its rights and revision, and complete translations made independently from the original.

```sh
champollion check --root my-translation
champollion report --root my-translation --json
```

Keep meaningful source divisions, lines, and reference numbers. Review each edition against the source, resolve findings, and retain reviewer records with the work. The [method guide](docs/method.md) explains the workflow; [SPEC.md](SPEC.md) defines the protocol.

## What the tools check

- Missing editions, mismatched section headings, and changed reference numbers.
- Missing source files, incorrect hashes, and incomplete source records.
- Unusually short sections and identical sentences across editions.
- Scan debris, quotation problems, and profile-selected spelling or name inconsistencies.

Reports distinguish disabled, unsupported, and insufficient-evidence checks. `check` does not change work documents. Exit codes are `0` for no errors, `1` for reported errors, and `2` for usage, configuration, or file problems. Warnings remain visible; `--strict` makes warnings fail too. A blocked publication gate is separate from these exit codes.

The toolkit also prepares source-only collaborator tasks, assembles returned sections into a separate work copy, and makes hash-verified tool snapshots for offline builds. Run `champollion --help` for the command list.

## Review, summaries, and books

- [Collaborator tasks](docs/ai-workers.md): keep independent editions separate.
- [Source-language review](docs/review.md): reviewer packets, second readings, and guarded application of confirmed corrections. Files only; no model API calls.
- [Study guides](docs/summaries.md): check a summary and machine index against the edition.
- [Book export](docs/export.md): PDF and EPUB editions, with optional `--inline-emphasis` for source italics and bold.

Checks, review, and summary tools support macOS, Linux, and Windows. The export CLI requires Chrome or Chromium for both formats, including EPUB covers; PDF additionally needs Poppler. Both export paths use POSIX process-group handling, so use macOS or Linux for export.

## Reference and contributing

See [verification](docs/verification.md), [provenance](docs/provenance.md), [adoption and vendoring](docs/adopting.md), and the [migration policy](docs/migration-policy.md).

Report bugs through this repository's Issues tab with the command, profile, and a small example you can share. Changes to a check need a reproducing test and a passing counterpart. From a checkout:

```sh
make test
make lint
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for code and protocol changes.

## License

Code is [MIT-licensed](LICENSE). The specification and documentation are [CC BY 4.0](LICENSE-docs). Source texts retain their own rights. See [THIRD-PARTY.md](THIRD-PARTY.md) and [SECURITY.md](SECURITY.md).

---

Part of [Pareto Cybernetics](https://paretocybernetics.com/projects/champollion/): free, private, open-source tools for working with AI agents.
