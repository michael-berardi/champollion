# From source to edition

Champollion keeps the source recoverable, the translations independent, and the
review evidence inspectable. The following seven stages apply to people and
external translation systems. The checker never produces a translation.

## 1. Choose and name the work

Establish the complete named work or complete surviving text. State lost material,
authorship uncertainty, source and target languages, and the intended registers.
Do not name an excerpt as though it were the complete work.

**Produce:** work identity, declared scope, and profile. **Rules:** SRC-3, SEG-1,
REG-1/4, PRV-1. Start with `champollion init .`; keep the project configuration
separate from its profile. See [adoption](adopting.md).

## 2. Preserve a canonical source

Choose the original-language witness. Verify the underlying work's rights and the
transcription's rights separately. Save the unchanged export, pin the revision,
and record the SHA-256. Document how it becomes the clean reading text; keep
consulted aids and repair witnesses attributed.

**Produce:** raw snapshot, provider/source records, rights and cleaning evidence.
**Rules:** SRC-1–SRC-8, PRV-3/5. Use `champollion source add --file` after acquiring
the source. Acquisition is separate from checking. A moving URL or another
translation is not the original. See [sourcing](sourcing.md).

## 3. Preserve the source's divisions

Place Original under explicit `###` unit headings in one work document. Preserve
numbering, lines, stanzas, parallelism, and deliberate blanks. Both house editions
carry the same units in order. Historical editions follow their own divisions.

**Produce:** the clean Original and stable unit inventory. **Rules:** SEG-1–SEG-10.
The checker compares structure and declared markers, not the meaning of unnumbered
passages. See [SPEC §2](../SPEC.md) and [verification](verification.md).

## 4. Translate each register independently

Translate every source unit directly into each declared register. Dispatch them
separately without showing one register's output to the other. Preserve difficult
passages; use a recorded witness repair or the appropriate lacuna marker rather
than inventing text.

For a single-work project, packets can be printed or explicitly written:

```sh
champollion packets --register literal --units 1-1 --out packets/literal
```

**Produce:** complete register drafts and contributor attestations. **Rules:**
REG-2–REG-11, WRK-1–WRK-6. Validate returned units before integrating them. Assembly
writes a separate copy and refuses gaps or marker mismatches. See
[registers](registers.md) and [collaborator guidance](ai-workers.md).

## 5. Check the observable requirements

```sh
champollion check --json
```

**Produce:** mechanical findings, gate states, source hashes, and exception debt.
**Rules:** VER-2–VER-9, VER-12. Fix errors and inspect warnings. A disabled,
inapplicable, or unsupported gate is not a pass. A plausible length or matched
heading cannot prove completeness of sense. Checking makes no network calls and
never changes the work. See [verification](verification.md).

## 6. Review meaning and record the judgement

Compare each unit's first and last source passage with its translation. Read a
sample aloud in every register. Check terms, names, figures, sense, poetic form,
and honest disclosure. Retain the reviewer's identity, date, scope, findings and
resolutions, bound to the reviewed work, source and profile fingerprints.

**Produce:** current judgement records and resolved findings. **Rules:** VER-10/11,
PRV-2–PRV-5. `champollion report --json` presents recorded evidence; it does not
create a review or perform these readings.

## 7. Publish the work with its evidence

Rerun affected checks after edits. Keep source evidence, credits, production notes,
attestations, reports and reviews outside the reader-facing translation. Publish
only after blockers are resolved and required judgement is complete.

**Produce:** the complete work and retained provenance. **Rules:** PRV-1–PRV-5,
VER-13. Champollion has no publication command. A clean mechanical report is not
translation, legal, or editorial certification. See the
[acceptance matrix](acceptance-matrix.md).
