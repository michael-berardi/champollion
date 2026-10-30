# Champollion

Champollion is an open-source method for translating complete works directly from their original texts. It gives contributors a process to follow and tools to check their work before publication.

The method grew out of [Mouseia](https://mouseia.org), an open library that places original texts beside new translations. Champollion makes that method available to other projects, with contributor guides and an offline Python toolkit. You can use it with human translators, AI systems, or both, in any language pair.

## Two translations from the same original

Mouseia publishes two complete English editions:

- **Musean:** a literary translation in modern English, preserving the original's imagery, symbolism, rhythm, and structure.
- **Plain English:** an independent translation in everyday language, preserving the same complete content in familiar words and direct sentences.

Each is made from the original. Plain English is not produced by simplifying the Musean edition. Both preserve the source's divisions and references, so readers can compare the same passage across editions.

Other projects can define their own translation styles and target languages. Champollion keeps those choices in a **profile**, a settings file that names the required editions and selects the appropriate checks.

## How a work is made

1. **Choose the complete work.** Identify its boundaries and the edition you will use. If only part survives, include the complete surviving text and state what is lost.
2. **Preserve the original.** Save the provider's unchanged file and identify its revision. Record a content hash, a checksum that detects later changes, and the rights to both the work and its transcription. Document any cleanup, other copies used to repair damaged text, and aids you consult.
3. **Keep the source's structure.** Divide it into matching sections. Preserve meaningful lines, stanzas, paragraphs, and reference numbers.
4. **Translate independently.** Make each edition directly from the original. Give collaborators separate tasks for each edition, without showing them the other's translation.
5. **Run the checks.** Fix structural errors and investigate passages flagged for missing content, copied wording, or text corruption.
6. **Review against the source.** Compare each section's opening and ending. Check meaning, names, numbers, and technical terms. Read a sample aloud in each edition, then record the reviewer, findings, and corrections.
7. **Publish with the evidence.** Keep the source, translator credits, and review records with the work. Resolve blocking findings before publishing.

The [method guide](docs/method.md) explains each stage. The [protocol specification](SPEC.md) defines the full requirements.

## Install

Requires **Python 3.9 or later** and Git. The tools use Python's standard library and check local files without uploading your texts.

Use a new directory for the install and example below. On macOS or Linux:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install "champollion-protocol @ git+https://github.com/michael-berardi/champollion.git@v1.2.3"
```

On Windows, create the environment with `py -3 -m venv .venv`, activate it with `.\.venv\Scripts\Activate.ps1`, then run the same install command using `python -m pip`.

Tagged releases also include a wheel, a source archive, and `SHA256SUMS` on the [releases page](https://github.com/michael-berardi/champollion/releases).

## Try a complete example

After installing, download the example and run its checks:

```sh
git clone --branch v1.2.3 --depth 1 https://github.com/michael-berardi/champollion.git
champollion check --root champollion/examples/latin-to-spanish
champollion report --root champollion/examples/latin-to-spanish --json
```

The example contains a complete Latin micro-fable written for the project, its stored source, and two Spanish drafts. It demonstrates the file format and checks. The report keeps publication blocked because editorial review has not been recorded.

## Start your own translation

Create a project:

```sh
champollion init my-translation
```

This creates `works/`, a source manifest, and a local profile at `profiles/generic.json`. The project configuration, `champollion.json`, points to that profile.

Follow the [first-work guide](docs/authoring.md) to add your source evidence and complete translations. Edit the local profile to choose your languages and edition styles. The starting profile uses Literal and Plain; the supplied Mouseia profile uses Musean and Plain English.

Once the work and its records are ready:

```sh
champollion check --root my-translation
champollion report --root my-translation --json
```

The toolkit also prepares source-only tasks for collaborators, assembles returned sections into a separate work copy, and creates a hash-verified copy of the tools for offline project builds. Run `champollion --help` for the commands, or see [working with collaborators](docs/ai-workers.md) and [adopting Champollion](docs/adopting.md).

## Checks and review

The checker looks for:

- Missing editions, mismatched section headings, and changed reference numbers.
- Missing source files, incorrect hashes, and incomplete required source records.
- Sections that are unusually short compared with the rest of the work.
- Identical sentences across editions, using the profile's overlap threshold.
- Scan debris, quotation problems, and selected spelling or name inconsistencies.

Language-specific checks apply only where the profile selects them. Reports identify checks that are disabled, unsupported, or lack enough evidence to run. `check` leaves your work documents unchanged.

A reviewer still needs to assess meaning, completeness, and fidelity to the source. The report separates file checks from recorded editorial review; passing the checks alone does not approve a translation for publication. See [verification](docs/verification.md) for the procedure and [provenance](docs/provenance.md) for the records to keep.

Use `report --json` to get a structured report for scripts. Exit codes are `0` for no errors, `1` for reported errors, and `2` when the command cannot run because of a usage, configuration, or file problem. Warnings remain visible; `--strict` makes them fail the check too.

## Publish the editions as books

`champollion export` typesets every edition of a work as a PDF and a Kindle-ready EPUB, from the same files the checks read. Add `--inline-emphasis` to preserve source emphasis recorded as `*italics*` and `**bold**`; existing editions keep literal asterisks by default. See [docs/export.md](docs/export.md).

```sh
champollion export works/analects.md --out books/ --publisher "My Press"
```

## Contribute

Use the [issue tracker](https://github.com/michael-berardi/champollion/issues) to report a bug, a false positive, or a proposed improvement to the method. Include the command, profile, and a small example you have permission to share.

Changes to a check should include a test that reproduces the problem and a passing example. Run the test suite from a checkout:

```sh
make test
```

[CONTRIBUTING.md](CONTRIBUTING.md) covers code and protocol changes. The [migration policy](docs/migration-policy.md) explains how to update a project's pinned tools and rules.

## License

Code is [MIT-licensed](LICENSE). The specification and documentation are [CC BY 4.0](LICENSE-docs). Source texts retain their own rights; using Champollion does not change them. See [THIRD-PARTY.md](THIRD-PARTY.md) for notices and [SECURITY.md](SECURITY.md) for security reports.
