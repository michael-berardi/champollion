# Changelog

Changes are recorded in [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. Versions follow [Semantic Versioning](https://semver.org/).

Champollion enforces mechanical requirements and records judgement (VER-1). It does not translate or certify sense. The dated 1.0.0 entry records release contents, not approval to publish; SPEC.md remains a working specification until publication is approved.

## [Unreleased]

## [1.0.0] - 2026-10-13

### Added

- Protocol version 1.0.0 with work format `champollion/1`, scalar front matter, and profile schema `champollion-profile/1`.
- Stable rule families SRC (sourcing and rights), SEG (segmentation and alignment), REG (registers), VER (verification), PRV (provenance), and WRK (collaboration), with mechanical checks distinguished from recorded judgement.
- Python 3.9+ standard-library reference implementation, distributed as `champollion-protocol` with import package and console command `champollion`; checks use local evidence without network calls.
- CLI contract: `init`, `source add`, `check`, `lint` (alias of `check`), `packets`, `assemble`, `report`, `rules`, `profile validate`, `vendor`, and `verify-vendor`.
- Three shipped profiles: `generic`, `mouseia`, and `latin-to-spanish`. Language-specific policies belong in profiles.
- A complete Latin-to-Spanish example with independent `literaria` and `clara` registers, and a read-only Mouseia adoption example.
- Specification, method, adoption, authoring, verification, provenance, collaborator, acceptance-matrix, and migration documentation.
- Standard-library `unittest` fixture discipline: a failing fixture, rule ID, profile setting, finding code, migration note, and changelog entry for each new gate or changed rule; an independently frozen oracle when asserting compatibility with Mouseia's legacy linter (SPEC.md §11). Recorded judgement remains required under VER-10 and VER-11.
- Separate MIT code and CC BY 4.0 specification/documentation licenses, offline Make targets, and tracked-file SHA-256 release manifest generation.
