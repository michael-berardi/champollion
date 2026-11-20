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

## Packets of a long text

For a long prose work whose units are too large for one task, split the clean
Original into packets of at most N words. Packets break only between blocks
(blank-line-separated paragraphs); a heading or a bare marker line such as a page
milestone stays with the block after it, and a `[Note L]` line (SPEC §2.4) stays
with the paragraph before it. A single block longer than N becomes its own packet
and is reported as oversize rather than cut.

```sh
champollion packets split original.md --max-words 2000 --out packets/source --json
champollion packets verify packets/source drafts/musean
champollion packets join drafts/musean --source packets/source --out musean.md
```

`split` writes `001.md`, `002.md`, … and `packets.json` (source SHA-256, limit and
word counts); rerunning with identical bytes is a no-op and different bytes are
refused. Save each draft under the same filename. `verify` is read-only and exits
1 when any packet fails. For every packet it compares, in order:

- paragraph anchors: line-initial `[ID nnnn]` by default, `--anchor REGEX` to change;
- page markers: `[YYYY page]` by default (for example `[1845 35]`), `--page REGEX`;
- the number of Markdown headings;
- `[Note L]` labels, and that each label anchored inline in the source is still
  anchored inline in the draft.

It names each missing, extra, duplicate and out-of-order item per packet, and any
missing or unexpected draft file. Page markers are the item most often dropped:
Haiku drafts of Mouseia's 1845 Stirner edition lost 19 of them across 128
packets, which only this per-packet comparison caught. `join` concatenates
packets in filename order; with `--source` it verifies first and refuses
(`WRK-5`) to write anything if a packet fails. `join` of the source packets
reproduces the Original with blocks separated by one blank line.

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

## Review against the source

After assembly, `champollion review` prepares a passage-by-passage review of every
register against the Original: reviewer packets, an independent second reading of
each finding, and guarded application of only the confirmed corrections. It writes
packets and reads reply files; it never calls a model. Source findings are recorded
for the editor, never auto-applied, and a model-run review must be recorded as
machine review, not human editorial approval. See [review](review.md) and
[VER-10/VER-11](verification.md).
