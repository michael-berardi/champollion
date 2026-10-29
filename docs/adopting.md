# Adopt Champollion

Your project keeps its texts, editorial choices, source evidence, and publication
authority. Champollion supplies the protocol, parsers, checks, and reports.
Mechanical compatibility and full protocol conformance are different milestones.

## Project configuration and profile

`champollion init .` creates a project configuration at `champollion.json`, a local
profile at `profiles/generic.json`, an empty source manifest, and `works/`.
The configuration points to the profile:

```json
{"profile_path": "profiles/generic.json"}
```

The profile is a separate `champollion-profile/1` JSON document. Start from a shipped
profile, declare source/target languages and at least two independent house
registers, map your section labels, and select applicable checks. Keep English
spelling and archaism policies off for other languages. Name tables are local paths.

```sh
champollion profile validate profiles/generic.json
champollion check
champollion report --json
```

An explicit `--profile profiles/project.json` overrides the configured profile.
Never pass the project configuration as though it were a profile. Record the
profile revision or fingerprint with your review evidence; the strict profile
schema does not accept arbitrary extra fields.

## Existing texts

Use explicit work paths, excluding registry documents:

```sh
champollion check works/example.md --json
```

Map existing section aliases in the profile. The Mouseia adapter maps
`curated_translator` and `curated_note` to the Musean keys and diagnoses conflicting
values. Historical/reference sections retain their own divisions; do not include
unchecked sections in a house-register conformance claim.

Prepare local source records with snapshots, revisions, hashes, rights layers,
cleaning decisions, and disclosed aids. The [sourcing guide](sourcing.md) explains
the evidence. Do not invent missing records for old work to get a green report.
`check` never writes a work or fetches a missing source.

## A safe migration from an existing gate

Freeze the old implementation and its data before replacement. Compare exact
stdout, stderr, and exit status over the real corpus, selected works, and synthetic
passing, failing, and baselined cases. Retain that oracle for later upgrades.

Mouseia's offline build loads `champollion.compat.mouseia`, the explicit
compatibility implementation of its established gate. Its wrapper verifies the
vendor manifest before checking the corpus. Retex doctor and the seed builder
remain separate gates. The compatibility module keeps the old baseline semantics
and output; **it does not claim strict Champollion conformance**.

Activate new strict requirements deliberately, with a migration record. A legacy
baseline is not a dated Champollion exception. Review each finding: fix it, report a
checker bug with a fixture, or record an accountable exception with an owner,
reason, date, and expiry. Do not invent owners or silently renew dates. Unknown
rights and missing source evidence cannot be waived.

## Offline vendoring

From an installed, verified release or a reviewed tagged checkout:

```sh
champollion vendor --into vendor --tag v1.2.2
champollion verify-vendor vendor/champollion
python3 vendor/champollion/__main__.py rules
```

`--into vendor` creates `vendor/champollion`; do not repeat `champollion` in the
argument. Retain `VENDOR.json`, including its upstream label and file hashes. The
label is a record of the selected release, not cryptographic proof of its origin.
Review and verify the upstream artifact before accepting a new manifest.
Production builds must not fetch packages. Updating a vendor is a development
change followed by integrity checks, host tests, and oracle comparisons.

## Review and publication

Retain a reviewer's identity, date, protocol version, works/units/registers,
findings, and resolutions. Bind the review to `work_sha256`, `source_sha256`, and
`profile_fingerprint`; changed bytes/settings require fresh evidence. Read aloud,
compare endpoints, and review sense and terminology—software cannot do that for you.

An error-free check is only a mechanical result. Publication requires the complete
protocol and current judgement records, with no unresolved blocking findings or
overdue exceptions. See the [authoring guide](authoring.md),
[acceptance matrix](acceptance-matrix.md), and [migration policy](migration-policy.md).
