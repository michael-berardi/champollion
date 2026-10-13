# Migration policy

Pin the protocol, checker, and project profile independently. Upgrade them as a reviewed change, retain the old evidence, and compare new findings before publication. Champollion does not translate for a project; neither a version number nor a mechanical pass certifies sense. Required judgement records remain part of every publication decision.

This policy implements SPEC §11 and VER-11–VER-13. The current specification is 1.0.0 and is a working specification, not an approved release. See [adopting](adopting.md) for project setup and the [acceptance matrix](acceptance-matrix.md) for rule-specific migration evidence.

## Three release versions

Use semantic versions, `major.minor.patch`, for these three independently identified artifacts:

| Version | What it identifies | Patch | Minor | Major |
|---|---|---|---|---|
| **Specification** | Normative rule meanings, obligations, and conformance requirements. | Clarification or correction that changes no obligation or accepted behavior. | An additive rule or capability that leaves existing conformance intact and is not silently activated. | Incompatible accepted inputs, gate behavior, thresholds, or publication requirements. |
| **Package** | Reference checker and CLI implementation. | Corrections preserving accepted inputs, gate decisions, finding-code meanings, and public output contracts. | Additive commands/capabilities or opt-in gates preserving existing behavior. | Incompatible CLI, accepted-input, gate-decision, or report-contract changes. A change called a bug fix still needs a major bump if it changes blocking behavior incompatibly. |
| **Profile** | A project's exact register declarations, policies, thresholds, rights allow-list, and exceptions. | Record corrections or debt updates that preserve gate policy; disclose finding disposition changes from exceptions. | Additive optional register or policy capability that preserves current required gates and accepted inputs. | Tightened thresholds, newly enabled gates, required-register changes, incompatible rights-policy changes, or other changed acceptance behavior. |

The numbers need not match. A package can implement an unchanged specification while gaining an optional capability. A project can keep its previous profile revision while evaluating a newer implementation, provided that implementation explicitly supports the old schema and gate behavior. An older profile cannot establish conformance to newer incompatible requirements merely because it parses.

Track **schema identifiers separately**: `champollion/1` describes work syntax and `champollion-profile/1` describes profile JSON. They are not specification or profile release numbers. An incompatible schema change needs a new schema identifier and the corresponding major artifact release. SPEC §3 rejects unknown profile fields; do not add a `version` or `spec_version` key to the current JSON schema. Record the profile release version in the adoption record, tagged profile snapshot, and verification evidence, with exact effective settings or a local fingerprint.

The package report must identify the protocol and checker versions and the exact profile identity/settings used. Record the profile revision alongside it. A label such as “Mouseia profile” without its revision and effective configuration is insufficient.

## Add a rule with evidence first

1. Write a failing fixture and a repaired control before implementing the gate. State the finding code, severity, applicable profile setting, and expected report evidence. For judgement rules, specify the review record and its completeness fixture; do not invent a semantic oracle.
2. Assign a new rule ID in the appropriate family. Never change an existing ID's meaning to fit the addition. Link its requirement, rationale, mechanical/judgement boundary, and profile setting in the specification.
3. Add its row to the acceptance matrix and a migration note for projects. Document any new field's type, allowed values, missing-value behavior, validation errors, and rule relationship before accepting it.
4. Add a `CHANGELOG.md` entry naming the rule, code, fixture, configuration effect, migration action, and affected versions.
5. Bump the specification's minor version for a compatible additive rule. Ship its implementation without silently enabling it in deployed profiles. A project already conforming keeps that versioned claim; it evaluates and adopts the addition explicitly.

The minor-bump path is not permission to add a mandatory failure condition to an existing conformance claim. If the new rule changes what an existing project must do to conform, or introduces incompatible blocking behavior, it requires a **major specification bump**, plus major package/profile bumps where their acceptance behavior changes. Existing reports keep their original version; do not relabel them as checked under the new rules. A judgement requirement is a publication requirement even if no text-pattern gate can enforce its substance.

## Tighten a threshold or activate a gate

A stricter threshold is a major change to the profile's acceptance policy. Tightening a normative threshold also requires a major specification bump; an incompatible checker decision change requires a major package bump. Enabling a previously inactive gate follows the same discipline. Supply boundary fixtures, including equality and inapplicability, and show before/after findings in the changelog or release evidence.

A project may pin the previous profile version and retain its previous compatible checker/specification snapshot while reviewing the upgrade. That is an explicit older-version adoption, not conformance to the stricter version. Record disabled optional heuristics visibly. A profile with core structure, coverage, or numbering disabled cannot support conformance under SPEC §10.

For Mouseia, its existing `scripts/lint_corpus.py` supplies the 0.35 copy threshold and the 0.5 short-unit threshold, with eligibility conditions; SPEC §7.2 and [verification](verification.md) give the exact algorithms. A changed sentence splitter, denominator, eligible-unit set, or median calculation can change acceptance just as a changed numeric threshold can. Evaluate the whole algorithm, not only the number.

Do not describe new snapshot hashes, ordered markers, or semantic endpoint review as behavior already performed by that linter. Mouseia's `seed/build.mjs` checks raw-path existence and house headings; its `docs/translation-guidelines.md` §7 requires endpoint reading by judgement. Adapter parity and activation of additional Champollion gates are separate changes.

## Retire an ID without losing its history

Keep rule IDs and meanings stable. A clarification retains the ID. A changed meaning gets a new ID, with the old ID retired. Never reuse a retired ID.

Keep a tombstone in the rule catalogue/specification history naming the retired ID, its former title and meaning, retirement version, reason, successor if any, and migration action. Retain its acceptance evidence and changelog history. Old reports and exceptions must remain interpretable. Do not silently retarget an exception to a successor rule or a different finding-code meaning; have its owner review the new selector and reason.

Retirement needs a major release when removing the rule changes conformance or gate behavior incompatibly. Finding codes remain stable references to their original check meanings even when their checks are retired.

## Deprecate a profile field explicitly

State the deprecated field, its unchanged old meaning, replacement, first deprecation release, migration period, and scheduled removal release. Continue validating the old field during that period. Document the valid old/new shapes and how to handle both fields if present; conflicting values must be a named configuration error, not a silently chosen value.

Do not let permissive parsing substitute for a migration policy. Current `champollion-profile/1` rejects unknown fields and has no implicit check defaults. An implementation accepting a replacement must have a specified, versioned schema for it. Supply fixtures for old, new, conflicting, malformed, and removed forms. Removing a field, changing its meaning or a default, or incompatibly changing accepted inputs requires a major release and, where needed, a new schema identifier.

Projects validate the migrated JSON with `champollion profile validate champollion.json` before checking works. Do not reinterpret old profile files as if they had the new meaning.

## Exceptions expire

VER-12 exceptions are temporary, owned decisions, not permission to hide findings. Every entry records `code`, `work`, exact `unit`, `owner`, `reason`, `recorded`, and `expires`. Expiry must be later than the recorded date. Match the code/work/unit exactly; do not infer wildcards. For work-level findings, use the work-level location actually reported by the checker.

An unexpired matched exception leaves the finding visible as a warning with `[exception]` and its original code. It remains debt in the report. It becomes overdue after its `expires` date using the recorded UTC run date; an overdue exception is blocking under VER-12/VER-13. Reports also retain unmatched exception debt, so abandoned entries do not disappear from view.

The owner must resolve the cause or make and record a fresh tolerance decision before publication. Do not automatically extend expiry during an upgrade or copy exceptions to new codes without review. Retain the decision history and rerun affected gates. Exceptions cannot create missing source evidence or make unknown rights admissible. A legacy baseline without owner and expiry does not satisfy VER-12; Mouseia's baseline shape is documented in `scripts/lint_corpus.py`.

## Upgrade a project

1. **Read the changelog.** Identify rule changes, retired IDs, schema changes, new or newly enabled gates, threshold changes, and supported older-version behavior. Decide the target specification, package, and profile versions together.
2. **Retain the old state.** Keep the previous immutable vendored tag, commit and per-file hashes, profile revision/settings, mechanical report, corpus snapshot identity, and judgement records. This is the comparison and rollback evidence.
3. **Update the pinned implementation and bump the profile.** Use `champollion vendor` with `--into` naming the project's vendor directory and `--tag` naming the chosen immutable release tag. Activate additional checks explicitly. Resolve project-root-relative paths, including any name table, and record the new profile revision outside the JSON schema.
4. **Validate and check.** Run the commands below against the same corpus state used for comparison. Preserve operational failures as failures, not as an empty finding set.
5. **Compare findings.** Compare by stable code, rule, work, register, and location. Separate new findings from changed severity, eligibility, thresholds, gate state, exception matches, and source evidence. A smaller finding count is not automatically an improvement.
6. **Resolve or record exceptions.** Repair real defects; use owned, justified, expiring exceptions only where permitted. Renew affected judgement review for changed source, units, editions, or editorial requirements. Do not manufacture retroactive review records.
7. **Record the adoption decision.** Retain the new report and exact versions/settings, remaining debt, changed reviews, and publication-gate decision. Publish only after VER-13 is satisfied.

```text
champollion verify-vendor vendor/champollion --json
champollion profile validate champollion.json
champollion check --root . --json
champollion report --root . --json
```

These commands document the contract, not evidence that the current working package has passed it. `check` never edits the corpus and makes no network calls; it reads local evidence. It returns 0 with no errors (warnings allowed), 1 with error findings, and 2 for usage, configuration, schema, or IO failure. `report` presents evidence; it does not perform a sense review. There is no automatic profile-upgrade or findings-comparison command in this CLI contract.

A Mouseia adoption additionally preserves an independently frozen `scripts/lint_corpus.py` oracle and compares stdout, stderr, and exit codes on legacy valid inputs and pass/fail/baselined fixtures. Keep new normative refusals and additional checks separate from that parity claim. See [adopting](adopting.md).

## Roll back the checker, not the corpus

Revert the vendored snapshot to the previous immutable tag and restore its matching profile revision and adoption configuration. Use `champollion vendor` with the previous tag and `--into` directory, then verify local integrity with `champollion verify-vendor vendor/champollion --json`. Retain the superseded report and the rollback reason; check the current corpus under the restored configuration before renewing a publication decision.

The corpus itself is unaffected by reverting the vendor snapshot. Checker rollback does not undo translation edits, source repairs, assembly output, or invalidated reviews. Do not claim an older report covers a changed corpus. If source, units, or editions changed, rerun affected gates and judgement review under the restored version. Use [provenance](provenance.md) to retain both evidence histories.

## Stability promises

- Finding codes are stable. Wording may be clarified; the code's meaning must not be repurposed. New semantics need a new code and migration evidence. Keep the responsible rule ID separate from the specialized code.
- Report shape is stable within a package major version. Preserve existing field names, types, location conventions, severity meanings, and mechanical-versus-judgement separation. Document any compatible optional additions; do not make consumers reinterpret existing fields.
- Rule IDs are never reused. Old reports remain evidence of their stated version, not automatic attestations under later versions.
- Deployed profiles do not gain new active gates silently. Language-specific policies stay in profiles; unsupported policies are named errors, never hidden skips.
- Verification remains offline, uses Python 3.9+ and the standard library, and does not modify work documents. Acquisition, scaffolding, vendoring, and assembly are separate writing operations. No release changes the boundary between mechanical evidence and recorded judgement without an explicit normative migration.
