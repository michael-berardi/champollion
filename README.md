# Champollion

Champollion is a translation protocol, a Python reference checker, and a set of working documents. It specifies how to store an original-language source, preserve its divisions, produce at least two independent registers directly from it, run mechanical checks, record editorial judgment, and disclose provenance. It formalizes the method used by Mouseia and lets other projects declare their own languages and editorial profiles. It does not translate for you and cannot certify sense.

## Install

Install a tagged release in a virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install "champollion-protocol @ git+https://github.com/michael-berardi/champollion.git@v1.0.1"
```

On Windows, use `.venv\\Scripts\\Activate.ps1` to activate the environment.

Installation needs access to the repository; checking does not. Profiles are included in the installed package. Clone the tagged repository to use its examples and documentation locally. There are no runtime dependencies outside the Python standard library.

## Quickstart

Prepare `original.txt` as a complete original-language text whose rights you can document; [the authoring guide](docs/authoring.md) supplies an original teaching exercise. Run these four commands in your project directory:

```sh
champollion init .
champollion source add --id sunrise --file original.txt --provider local --edition "Sunrise teaching edition" --revision sunrise-v1 --rights public-domain --note "Original teaching text from docs/authoring.md; no cleaning changes."
champollion check
champollion report --json
```

**Between `source add` and `check`, author `works/sunrise.md`, complete the source records, and set the profile in `champollion.json`.** Neither initialization nor source acquisition generates a translation. Use [SPEC §2 and §8](SPEC.md) for the work and provenance schemas and [SPEC §3](SPEC.md) for the profile. The generic profile requires `## Literal` and `## Plain`; it does not recognize `## Musean` automatically.

`init` scaffolds `champollion.json`, `sources/manifest.json`, and `works/`. `source add` stores source evidence. `check` prints one finding per line and then a summary; an authored work is not guaranteed to pass. Finding lines have this shape:

```text
ERROR sunrise [Morning] SEG-NUMBERING: target marker sequence differs from Original
WARN sunrise [Morning] VER-ELLIPSIS: use a single ellipsis character
```

`report --json` emits a report of mechanical results, effective gates, source evidence, exceptions, and judgment records or their absence. It is not a translation or an approval. Exit codes are **0** for no error findings, warnings allowed; **1** for error findings; **2** for usage, configuration, schema, or IO errors. An unexpired recorded exception remains visible as `WARN` with `[exception]` (VER-12; mechanical matching and expiry, judgment of tolerance).

## The seven stages

1. **Choose and name:** establish the complete work, identity, and house-register definitions (SRC-3, SEG-1, REG-1, REG-4, PRV-1; mechanical declarations, judgment of scope).
2. **Source:** store a canonical original with revision, hash, rights, and cleaning evidence (SRC-1–SRC-8; mechanical evidence, judgment of suitability).
3. **Segment:** preserve units, source form, numbering, blanks, and damage (SEG-1–SEG-10; mechanical alignment, judgment of coverage).
4. **Translate independently:** make each register from the original, never from the other (REG-2–REG-3; judgment and attestation, with a mechanical copy heuristic).
5. **Check:** run the core and enabled profile gates (VER-2–VER-9; mechanical).
6. **Review:** read endpoints, sample aloud, check sense and terms, and retain findings and resolutions (VER-10–VER-11; judgment).
7. **Disclose and publish:** retain provenance and attestations; publish only after the publication gate (PRV-1–PRV-5, WRK-6, VER-13; mechanical records and recorded judgment).

## What the CLI checks

The core checks document structure, required registers, alignment, coverage evidence, ordered source markers, local snapshots, hashes, rights records, and provenance. Profiles select copy and length heuristics, quotation balance, language and spelling policies, name variants, and text hygiene (VER-2–VER-9; mechanical). Reports distinguish disabled, inapplicable, unsupported, failed, and passed gates. `check` never edits a work or fetches missing evidence.

A plausible length or matching heading cannot prove that a passage was translated. Independence, completeness of sense, source selection, rights interpretation, and translation quality require recorded judgment (VER-1, VER-10–VER-11). See [verification](docs/verification.md) and the [acceptance matrix](docs/acceptance-matrix.md).

## Why two registers

Mouseia's **Musean** register joins fidelity with modern clarity, beauty, symbolism, and source structure. Its **Plain English** register conveys the same complete content in everyday contemporary English. Both start from the original independently; Plain is not an edited Musean text (REG-2–REG-4; judgment, supported by a mechanical copy heuristic). Two registers offer different ways to read without substituting a summary for a translation. Mouseia defines these in `docs/translation-guidelines.md` §2–§3.

These English definitions are not universal defaults. The generic profile uses Literal and Plain; the Latin-to-Spanish profile uses Literaria and Clara. Language-specific choices belong in profiles, not the core. See [registers](docs/registers.md).

## What a project may claim

A project may claim **Champollion 1.0 conformance** only for identified works and house registers, with protocol version 1.0.0, an exact profile revision, checker configuration, retained source evidence, a mechanical report, and current judgment records. Mandatory and enabled applicable gates must run; publication requires no unresolved blocking finding or overdue exception (VER-13; mechanical gate state and recorded judgment). Ignored historical or unknown sections are outside that claim.

A mechanical pass alone may be reported as a mechanical pass. Conformance is not certification of meaning, translation quality, legal status, or production history. [SPEC §10](SPEC.md) defines the claim.

## Repository layout

- `SPEC.md`: normative rules, work format, profile schema, and conformance.
- `docs/`: method, sourcing, registers, verification, provenance, collaborators, adoption, authoring, migration, and acceptance matrix.
- `profiles/`: Generic, Mouseia, and Latin-to-Spanish editorial profiles.
- `src/champollion/`: standard-library reference implementation and Mouseia adapter.
- `examples/latin-to-spanish/`: a small two-register example; `examples/mouseia/`: guidance for a separate checkout.
- `tests/`: `unittest` checks, pass/fail fixtures, and compatibility/CLI contracts.
- `CONTRIBUTING.md`, `CITATION.cff`, `THIRD-PARTY.md`, `CHANGELOG.md`: contribution, citation, licensing evidence, and changes.
- `pyproject.toml`, `Makefile`, `LICENSE`, `LICENSE-docs`: packaging, local checks, and licenses.
- `dist/`: generated wheel/source archives and `SHA256SUMS`, published as release assets.

## Mouseia and the reference implementation

Mouseia's existing method is documented in its `docs/translation-guidelines.md` and `corpus/SOURCES.md`. Its `scripts/lint_corpus.py` checks house-register text and ratio heuristics; `seed/build.mjs` separately checks required editions, matching headings, publication metadata, and raw-path existence. Those existing gates do not establish semantic fidelity or snapshot hashes.

Champollion separates that method from Mouseia's editorial choices. Adoption must retain the old linter as an independent oracle until output and exit-code parity is proven; new protocol gates are a separate explicit migration, not presumed existing Mouseia behavior. See [adopting](docs/adopting.md).

## Support and maintenance

Report reproducible defects and false positives in the [repository issue tracker](https://github.com/michael-berardi/champollion/issues), with the version, profile, work, unit, finding code, and relevant text. Michael Berardi maintains the protocol; contributions follow [CONTRIBUTING.md](CONTRIBUTING.md). There is no guaranteed response time, hosted checking service, or translation-review service.

The supported runtime is Python 3.9 and later. Maintenance uses fixtures, stable rule IDs, explicit profile migrations, and semantic versioning. Incompatible changes require a major version; deployed profiles never gain a gate silently. Projects own their pinned upgrades and expiring exceptions. See [migration policy](docs/migration-policy.md).

## License

Code is [MIT](LICENSE). The specification and documentation are [CC BY 4.0](LICENSE-docs). The split lets projects reuse the implementation with minimal conditions while preserving attribution for the protocol. Source-text rights are separate; see [THIRD-PARTY.md](THIRD-PARTY.md).

## Status

Implementation **1.0.1**, protocol **1.0.0**. Supports **Python 3.9+**, uses the **standard library only** at runtime, and makes **no network calls at check time**. Releases are tagged and include package archives and **SHA256SUMS**.
