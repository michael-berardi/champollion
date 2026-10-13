# Acceptance matrix

This matrix names shipped checks and executable evidence, not planned fixtures.
A mechanical check cannot establish meaning, legal rights, canonical selection,
production history or honest disclosure. Those remain recorded editorial judgement.

Run `make test` to execute the referenced unittest classes. `tests/fixtures/` holds
original synthetic defects and controls, never copies presented as historical texts.

## SRC

| Rule | Enforcement and limits | Executable evidence | Setting/record |
|---|---|---|---|
| **SRC-1 Canonical original, stored not linked** | Local snapshot presence; canonical witness selection is judgement | [`tests/test_checks.py`](../tests/test_checks.py) (`ProvenanceRightsTests`) | `Source record` |
| **SRC-2 Immutable revision evidence** | SRC-NO-PIN and digest checks; edition identity is judgement | [`tests/test_checks.py`](../tests/test_checks.py) (`ProvenanceRightsTests`) | `revision, sha256` |
| **SRC-3 Complete works only** | Completeness/scope declarations; actual boundaries are judgement | [`tests/test_checks.py`](../tests/test_checks.py) (`ProvenanceRightsTests`) | `Work front matter` |
| **SRC-4 Rights gate** | SRC-RIGHTS and separate rights status; legal basis is judgement | [`tests/test_checks.py`](../tests/test_checks.py) (`ProvenanceRightsTests`) | `rights.allowed` |
| **SRC-5 Primary source only** | Direct-source account and disclosed aid use: judgement | No automated semantic test | `Source and review records` |
| **SRC-6 Reproducible cleaning** | Record cleaning decisions and regenerate/compare: project review | No automatic transformation execution | `Source cleaning record` |
| **SRC-7 Source registry** | SRC-7 checks provider reference; full registry suitability is project review | [`tests/test_checks.py`](../tests/test_checks.py) (`ProvenanceRightsTests`) | `Source provider record` |
| **SRC-8 Snapshot integrity** | SRC-8 and SRC-HASH-MISMATCH check local bytes | [`tests/test_checks.py`](../tests/test_checks.py) (`ProvenanceRightsTests`) | `Snapshot and sha256` |
## SEG

| Rule | Enforcement and limits | Executable evidence | Setting/record |
|---|---|---|---|
| **SEG-1 One work per document; units** | Strict parser; title accuracy is judgement | [`tests/test_core.py`](../tests/test_core.py) (`FrontMatterTests`) | `Work format` |
| **SEG-2 House editions carry the original's units, in order, exactly** | SEG-PARITY compares ordered titles | [`tests/test_checks.py`](../tests/test_checks.py) (`StructureCoverageTests`) | `registers[].alignment` |
| **SEG-3 Every unit translates exactly the source under the same heading** | SEG-COVERAGE/VER-SHORT-UNIT; semantic completeness is judgement | [`tests/test_checks.py`](../tests/test_checks.py) (`StructureCoverageTests`) | `coverage and ratio settings` |
| **SEG-4 Source form is part of the text** | Declared line counts; stanza/cadence review remains manual. Unsupported source_form is reported | [`tests/test_checks.py`](../tests/test_checks.py) (`StructureCoverageTests`) | `Source numbering policy` |
| **SEG-5 The source keeps its own numbering** | SEG-NUMBERING compares ordered markers | [`tests/test_checks.py`](../tests/test_checks.py) (`NumberingTests`) | `checks.numbering` |
| **SEG-6 Line-for-line works stay line-for-line** | Declared line-for-line counts; correspondence in sense is judgement | [`tests/test_checks.py`](../tests/test_checks.py) (`NumberingTests`) | `numbering.line_for_line` |
| **SEG-7 Historical and reference editions keep their own divisions** | Positional count parity; edition-specific mapping is judgement | [`tests/test_checks.py`](../tests/test_checks.py) (`StructureCoverageTests`) | `registers[].alignment` |
| **SEG-8 Damage and lacunae** | VER-OCR-MARKER; witness repair and lacuna reading are judgement | [`tests/test_checks.py`](../tests/test_checks.py) (`CopySpeechHygieneLanguageTests`) | `checks.debris` |
| **SEG-9 Deliberate blanks stay visible** | SEG-COVERAGE compares visible blank counts; source blank identification is judgement | [`tests/test_checks.py`](../tests/test_checks.py) (`StructureCoverageTests`) | `checks.coverage` |
| **SEG-10 No summaries and no silent omissions** | Coverage heuristics provide evidence; omissions of sense require review | [`tests/test_checks.py`](../tests/test_checks.py) (`StructureCoverageTests`) | `coverage and review` |
## REG

| Rule | Enforcement and limits | Executable evidence | Setting/record |
|---|---|---|---|
| **REG-1 Every work carries the required registers** | Required register presence | [`tests/test_checks.py`](../tests/test_checks.py) (`StructureCoverageTests`) | `registers[].required` |
| **REG-2 Each register is made directly from the original** | Direct-source production and attestation: judgement | No automatic production-history test | `Contributor records` |
| **REG-3 Registers are independent** | Pairwise sentence overlap; production independence is judgement | [`tests/test_checks.py`](../tests/test_checks.py) (`CopySpeechHygieneLanguageTests`) | `copy_ratio and sentence settings` |
| **REG-4 Register definitions** | Definitions in packets; applying the register requires judgement | [`tests/test_tooling.py`](../tests/test_tooling.py) (`PacketAssemblyTests`) | `Register definitions` |
| **REG-5 Sense, not word order** | Sense, false friends and terminology: judgement | No semantic-certification test | `Target language/register` |
| **REG-6 Poetry is kept** | Declared line counts; imagery/formulae/epithets: judgement | [`tests/test_checks.py`](../tests/test_checks.py) (`NumberingTests`) | `Source form and review` |
| **REG-7 Modern English** | REG-ARCHAISM/REG-PLAIN-ARCHAISM for selected English policies | [`tests/test_checks.py`](../tests/test_checks.py) (`CopySpeechHygieneLanguageTests`) | `archaisms, plain_archaisms` |
| **REG-8 One spelling per name per work** | REG-NAME-VARIANT; source-attested alternatives require judgement | [`tests/test_checks.py`](../tests/test_checks.py) (`CopySpeechHygieneLanguageTests`) | `name_table` |
| **REG-9 Mechanics** | Ellipsis, repetition, speech balance and reference checks; remaining punctuation/figures: judgement | [`tests/test_checks.py`](../tests/test_checks.py) (`CopySpeechHygieneLanguageTests`) | `debris, ellipsis, speech_marks` |
| **REG-10 Spelling profile per edition** | REG-SPELLING for selected supported list; other languages need editorial spelling review | [`tests/test_checks.py`](../tests/test_checks.py) (`CopySpeechHygieneLanguageTests`) | `spelling_profile` |
| **REG-11 Adding a register** | Strict register declaration and credit fields; editorial definition/independence: judgement | [`tests/test_core.py`](../tests/test_core.py) (`ProfileTests`) | `registers` |
## VER

| Rule | Enforcement and limits | Executable evidence | Setting/record |
|---|---|---|---|
| **VER-1 Two halves** | Report separates mechanical results and judgement records | [`tests/test_checks.py`](../tests/test_checks.py) (`ExceptionReportTests`) | `Report contract` |
| **VER-2 Structure gate** | Structure/parity gate | [`tests/test_checks.py`](../tests/test_checks.py) (`StructureCoverageTests`) | `checks.structure` |
| **VER-3 Coverage gate** | Coverage and upper-middle ratio arithmetic | [`tests/test_checks.py`](../tests/test_checks.py) (`StructureCoverageTests`) | `coverage and ratio settings` |
| **VER-4 Numbering gate** | Ordered markers and declared line counts | [`tests/test_checks.py`](../tests/test_checks.py) (`NumberingTests`) | `checks.numbering` |
| **VER-5 Independence gate** | Pairwise overlap with exact denominators/boundaries | [`tests/test_checks.py`](../tests/test_checks.py) (`CopySpeechHygieneLanguageTests`) | `copy_ratio and sentence settings` |
| **VER-6 Hygiene gates** | Hygiene patterns; intentional/source-attested notation requires judgement | [`tests/test_checks.py`](../tests/test_checks.py) (`CopySpeechHygieneLanguageTests`) | `debris, ellipsis` |
| **VER-7 Language gates** | Selected language/name lists; unavailable policies are explicit | [`tests/test_checks.py`](../tests/test_checks.py) (`CopySpeechHygieneLanguageTests`) | `Language settings` |
| **VER-8 Speech-mark gate** | Straight-quote balance; identifying unmarked speech is judgement | [`tests/test_checks.py`](../tests/test_checks.py) (`CopySpeechHygieneLanguageTests`) | `speech_marks` |
| **VER-9 Rights, pin and provenance gate** | Rights, local source hash/pin and metadata checks | [`tests/test_checks.py`](../tests/test_checks.py) (`ProvenanceRightsTests`) | `Source/profile records` |
| **VER-10 Judgement** | Read aloud, endpoints, terms/names/figures and sense: judgement | No software substitutes for these readings | `Review scope` |
| **VER-11 Review record** | Review fields and current work/source/profile binding; substance is judgement | [`tests/test_checks.py`](../tests/test_checks.py) (`ExceptionReportTests`) | `Review records` |
| **VER-12 Exceptions** | Exact exception matching, dates, overdue/unmatched debt | [`tests/test_checks.py`](../tests/test_checks.py) (`ExceptionReportTests`) | `exceptions` |
| **VER-13 Publication gate** | Report blockers/current evidence; publication authority remains with project | [`tests/test_checks.py`](../tests/test_checks.py) (`ExceptionReportTests`) | `All required evidence` |
## PRV

| Rule | Enforcement and limits | Executable evidence | Setting/record |
|---|---|---|---|
| **PRV-1 Front-matter schema** | PRV-INCOMPLETE and strict scalar grammar | [`tests/test_core.py`](../tests/test_core.py) (`FrontMatterTests`); [`tests/test_checks.py`](../tests/test_checks.py) (`ProvenanceRightsTests`) | `Front matter/register IDs` |
| **PRV-2 Honest edition notes** | Edition note presence; truthful disclosure is judgement | [`tests/test_checks.py`](../tests/test_checks.py) (`ProvenanceRightsTests`) | `Edition credit/note keys` |
| **PRV-3 Comprehension aids disclosed** | Record aids and how they were used; completeness/truthfulness is judgement | No automatic aid-use test | `Source aids` |
| **PRV-4 Provenance is not in the text** | Known production artifacts via hygiene; contextual process notes require review | [`tests/test_checks.py`](../tests/test_checks.py) (`CopySpeechHygieneLanguageTests`) | `Edition notes and debris` |
| **PRV-5 Witnesses and aids are attributed** | Record every witness/aid and its rights; completeness is judgement | No automatic consultation-history test | `Source/review records` |
## WRK

| Rule | Enforcement and limits | Executable evidence | Setting/record |
|---|---|---|---|
| **WRK-1 Per-unit packets** | Deterministic source-only per-unit packets | [`tests/test_tooling.py`](../tests/test_tooling.py) (`PacketAssemblyTests`) | `Register/unit selection` |
| **WRK-2 Register separation** | Packet excludes other register text; actual dispatch separation is judgement | [`tests/test_tooling.py`](../tests/test_tooling.py) (`PacketAssemblyTests`) | `Dispatch records` |
| **WRK-3 Numbering contract** | Ordered returned marker validation | [`tests/test_tooling.py`](../tests/test_tooling.py) (`PacketAssemblyTests`) | `Source numbering policy` |
| **WRK-4 No invention** | Noninvention and probable readings: judgement | No automatic invention certification | `Source comparison` |
| **WRK-5 Assembly refuses gaps** | Assembly refuses missing/duplicate/unknown/reordered/empty units and marker/blank mismatches | [`tests/test_tooling.py`](../tests/test_tooling.py) (`PacketAssemblyTests`) | `Assembly contract` |
| **WRK-6 Attestation** | Retain contributor identity, originality, source and form attestations: project review | No automatic attestation-truth test | `Contributor records` |

## Adoption and changes

A project adopting a rule retains its source evidence, profile fingerprint, mechanical
report and judgement records. Recheck affected evidence after source/text/profile
changes. Rules without semantic tests still require a review; they are not waived.
New gates require fixtures, stable codes and a migration note. Incompatible changes
require an explicit profile upgrade, never silent activation. See
[migration policy](migration-policy.md).

The Mouseia compatibility lane is narrower than strict conformance. Its independently
frozen oracle comparisons live in Mouseia's `tests/champollion-parity.test.mjs`; the
package's `LegacyCompatibilityTests` exercises its own synthetic pass/fail/baseline
contract. Neither proves source-language accuracy.

## Retained review evidence

Store reviewer, date, protocol version, work/units/registers, findings and resolutions.
Current evidence binds `work_sha256`, `source_sha256`, and `profile_fingerprint`.
A draft without that review can pass mechanical checks while publication remains
blocked. No test fabricates a real read-aloud or scholarly review.
