# Contributing

Start with a reproducible defect and the smallest fixture that exposes it. Champollion enforces mechanical requirements and records judgment; it does not translate or certify sense. Read [SPEC.md](SPEC.md), the [acceptance matrix](docs/acceptance-matrix.md), and the [migration policy](docs/migration-policy.md) before changing behavior.

## Propose a rule

A new rule arrives with a **failing fixture reproducing a real defect, a rule ID, and an entry in `docs/CHANGELOG.md`**. Explain the defect, the intended requirement, the profile setting, the stable finding code, and which part is mechanical versus judgment. Cite the evidence for a historical defect; do not invent an audit case.

Use the fixed SRC, SEG, REG, VER, PRV, and WRK families. Clarify an existing meaning under its existing ID; a changed meaning needs a new ID and retirement of the old one. Do not reuse IDs or silently enable a new gate in an adopted profile. Include migration and rollback consequences; incompatible accepted-input or publication changes require a major version.

If a checker cannot test the proposed behavior, put it in the judgment half with a reviewer and a retained record—not a heuristic presented as proof (VER-1, VER-10–VER-11; judgment and mechanical record completeness). Sense, honest independence, and rights interpretation remain review responsibilities.

## Add a check

1. Add the reproducing failing case before the implementation.
2. Add a passing case that differs only in the relevant correction. **A check never ships without both cases.** Include boundary cases for thresholds, disabled and inapplicable states, malformed input, and exceptions where relevant.
3. Keep the check deterministic and offline. Read local evidence; never edit a work or repair a missing snapshot during checking (SRC-8, VER-9; mechanical integrity and evidence checks).
4. Return a stable finding code with its rule ID, severity, work, unit or work-level location, and actionable evidence. Measure heuristics honestly; record denominators and thresholds rather than claiming sense is verified.
5. Declare language-specific policy in a profile. Validate profile fields against SPEC §3; do not add arbitrary keys or implicit aliases. Add the acceptance-matrix row, migration note, and changelog entry.

For Mouseia compatibility, compare against an independently frozen old `scripts/lint_corpus.py`, including stdout, stderr, and exit status. Preserve its work-scoped speech checks and warning behavior until an explicit migration changes them. A replacement compared with itself is not an oracle.

## Add a fixture

Put the smallest reproducible case under `tests/fixtures/` and exercise it from a `unittest` test. Name the rule and expected finding, supply every record needed to reach the intended check, and retain a corrected passing counterpart. If the defect is a hash mismatch, make that mismatch intentional; do not let unrelated missing provenance hide the result.

Use original or public-domain material. Record authorship or the public-domain basis with the fixture; underlying-work and transcription rights are separate (SRC-4; mechanical evidence, judgment of rights). Do not copy a Mouseia corpus work or a licensed provider export into this repository. Synthetic wording may reproduce a documented defect class, but must not be labeled as the historical passage.

## Run tests

From the repository root, use Python's standard-library test runner:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests
```

For a focused check, supply the relevant test filename pattern to `unittest discover` with `-p`. Tests need no third-party test runner or translation model. Passing tests show implementation behavior, not translation quality. Validate a changed profile separately:

```sh
champollion profile validate profiles/generic.json
```

Use the corresponding profile path when changing a different profile. Keep schemas, examples, fixtures, and documentation consistent; do not claim tests ran when only text was inspected.

## Update a host project's vendored snapshot

Update in a development checkout with the selected tagged release available locally. Keep the previous snapshot and reports so rollback is possible. The pinned update and integrity check are:

```sh
champollion vendor --into vendor --tag v1.0.1
champollion verify-vendor vendor/champollion
```

`VENDOR.json` retains the selected upstream label and per-file SHA-256 evidence. Record the verified commit in the label when applicable; a label alone does not prove origin. Confirm the tag and file inventory before accepting the change. Run the host's focused fixtures and, for Mouseia, the frozen-oracle comparisons on the corpus and pass/fail/baselined cases. Review any profile change separately; do not introduce new gates as a side effect of re-vendoring. Commit the snapshot, integrity evidence, profile revision, and migration record together after the host's release review. Production checks use the stored snapshot, not an update command or network fetch.

## Report a false positive

Open a repository issue with:

- Checker and protocol versions, effective profile and revision, and the command used.
- The **work**, exact **unit**, stable finding **code**, and the **text** that triggered it, including enough original and target context to assess the comparison.
- The complete finding, why it is wrong, and the expected mechanical result.
- Source and fixture rights; remove unrelated private material rather than posting an entire corpus.

The report should become a minimal fixture with a passing counterpart. A genuinely tolerated finding is different from a checker bug: record its owner, reason, recorded date, and expiry in an exact-match exception (VER-12; mechanical matching/expiry, judgment of tolerance). Exceptions remain visible debt and cannot supply missing rights or source evidence.
