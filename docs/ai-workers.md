# Working with collaborators

Give one source unit and one register to each contributor. The coordinator validates
returned structure and references before integrating them. People or external
systems translate; Champollion does not call a model or certify meaning.

## Prepare a source-only packet

Set the intended target language and register definitions before dispatch. Packets
include the original unit, source/target language, one register definition,
constraints, exact response shape, ordered markers and any declared line count.
They never include another register's output.

```sh
champollion packets --register musean --units 1-1 --out packets/musean --json
champollion packets --register plain --units 1-1 --out packets/plain --json
```

These commands assume a Mouseia-style profile. Without `--out`, packets print to
stdout. With `--out`, files are deterministic; an existing different packet is not
overwritten. Retain the command's JSON report separately from the task packet.

A packet for the Emerald Tablet's first clause contains this source:

```markdown
## Source

### Clause 1

1. Verum, sine mendacio, certum et verissimum.
```

Its response contract requires only `### Clause 1`, a blank line, and the complete
translated text with marker `1.`. The packet's source span is one clause for a
collaborator task, not permission to publish an excerpt as the whole work. For a
declared line-for-line work, the emitted contract also gives the exact nonempty
line count from that unit.

**WRK-1:** retain the source's form and lacunae. Supply enough context to understand
the unit and record consulted comprehension aids. **WRK-2:** dispatch registers
separately; do not show one task the other's translation. Editing Musean into Plain
violates independence even if a later overlap screen passes.

## Validate and assemble

**WRK-3:** compare ordered markers and declared line counts, not just totals. Keep
contributor identity, direct-source/source-form attestation, and aid disclosure
outside the translated passage. A missing attestation is not a default declaration.

Stage one register's returned units in a response directory, ordered by filename.
Each response must contain exactly its `###` heading and translated body. The
complete register must contain every expected unit:

```sh
champollion assemble --register musean --from responses/musean \
  --work works/emerald-tablet.md --json
champollion check works/assembled/emerald-tablet.md --strict --json
```

Assembly writes `works/assembled/emerald-tablet.md`, leaving the input unchanged.
The preserved filename/slug lets you check the copy directly. It refuses missing,
duplicate, unknown, reordered, empty, or marker-mismatched units and violated
line/blank contracts. Keep the output, check report and contributor records
separate until editorial review approves integration.

**WRK-4:** do not invent text, borrow a neighboring paraphrase, or add explanation.
Read uncertain passages against the source; use a recorded witness repair or the
appropriate lacuna marker. Confidence is not evidence. Meaning, endpoint
correspondence and technical terms still require [judgement review](verification.md).

## Resolve failures

**WRK-5:** re-dispatch a failed unit with the same pinned source and the failed
requirement named. Do not merge an incomplete response, borrow the other register,
or insert a summary to make headings match. If the clean original changes,
regenerate affected packets and retranslate against that revised source.

**WRK-6:** retain each contributor's identified contribution, attestation and aid
use. Name machine assistance honestly. These are accountable project records;
software cannot reconstruct production history or establish their truthfulness.
Keep them outside reader-facing text under PRV-4. Publication requires current
review evidence, not just validated assembly.
