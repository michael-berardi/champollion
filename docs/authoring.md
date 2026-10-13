# Author your first work

Choose a complete short public-domain text in a language you can read. Champollion will check its format and evidence; you are responsible for translating its meaning. A clean report does not make a translation faithful (VER-1; mechanical results and recorded judgment).

## 1. Get the original

Use an original-language edition from a national library, an identified scholarly repository, or a scan of a public-domain printing. Verify the work's boundaries and the selected transcription's rights separately; an old underlying work does not automatically make a modern transcription public domain (SRC-3–SRC-5; judgment, with mechanical scope and rights records). A dictionary or scholarly gloss is an aid, not a replacement source; record its author, license, and use (PRV-3, PRV-5; mechanical disclosure, judgment of actual use).

Save the provider's unmodified export, an immutable revision or edition identifier with a content hash, and a rule or script for deriving the clean Original text (SRC-1–SRC-2, SRC-6–SRC-8; mechanical records and integrity, judgment of edition selection). Acquisition happens before checking. Checking cannot fetch a missing original.

For a practice run, use this complete two-line teaching composition. It was written for this guide, is not ancient verse, and its original Latin is dedicated to the public domain. Save the following bytes as UTF-8 `original.txt`, with a final newline:

```text
Sol super colles oritur.
Avis in arbore cantat.
```

Record the provider as `local`, edition as `Sunrise teaching edition`, and revision as `sunrise-v1`. The local snapshot's SHA-256 supplies content evidence; the revision label alone is not a historical edition pin. Record that the whole composition is present and that cleaning makes no changes. Do not use this exercise's provenance for a different work.

## 2. Create the project and profile

In your project directory:

```sh
champollion init .
champollion source add --id sunrise --file original.txt --provider local --edition "Sunrise teaching edition" --revision sunrise-v1 --rights public-domain --note "Original teaching text from docs/authoring.md; no cleaning changes."
```

Use the complete `profiles/generic.json` from a tagged checkout as your `champollion.json`. For this English exercise, change the `literal` register's `id` to `musean`, `label` to `Musean`, and `sections` to `["Musean"]`. Set the `plain` register's `label` to `Plain English` and `sections` to `["Plain English"]`. Keep both required with `same-units` alignment. Set `target` to `{"tag":"en","name":"English"}`. Keep every required check field; do not add an undeclared register-definition field. Use the Musean and Plain definitions below as an editorial record (REG-1, REG-4; mechanical declaration, judgment of definitions).

```sh
champollion profile validate champollion.json
```

Generic disables English-derived copy and length heuristics. For this tiny exercise those heuristics would not prove independence anyway. Record the two-register production history and review instead.

## 3. Lay out one complete work

Create `works/sunrise.md`. Use the exact scalar front-matter schema in [SPEC §8.1](../SPEC.md), not nested YAML. Set `slug` to `sunrise`, `title` to `Sunrise`, `author` to `Champollion documentation`, `tradition` to `teaching`, `language` to `la`, `genre` to `two-line teaching composition`, and `period` to `contemporary`. Use this guide's repository URL for `source_url`, the stored snapshot path for `raw_snapshot`, `complete` for `completeness`, and `whole-work` for `source_scope`.

Supply your actual `musean_translator`, `plain_translator`, production notes, provenance date `as_of`, evidence-based `certainty`, local source-record reference `source`, draft `status`, and honest `unknowns`. Do not copy another contributor's credit or claim a review that has not happened (PRV-1–PRV-2; mechanical completeness, judgment of truthfulness). Complete the provider, separate rights, cleaning, aid, and attestation records referenced by the manifest; a front-matter table alone is not source evidence.

For this undivided work, use one `### Morning` unit in every section. The two source lines stay two target lines, in order. Declare the line-for-line policy in the edition record (SEG-1–SEG-2, SEG-6; mechanical grammar, alignment and counts, judgment of corresponding sense).

The following is the body only, not a complete work document:

```markdown
## Original

### Morning

Sol super colles oritur.
Avis in arbore cantat.

## Musean

### Morning

The sun rises above the hills.
A bird sings in the tree.

## Plain English

### Morning

Above the hills, the sun is coming up.
There is a bird singing in the tree.
```

These renderings illustrate register style; they are not evidence of independent production. For your own work, make Musean directly from the original, preserving imagery and cadence in clear modern English. Make Plain independently from the original in everyday English, retaining every claim. Do not rewrite the displayed Musean text into Plain (REG-2–REG-4; judgment, supported where applicable by a mechanical copy heuristic). With collaborators, give each task only one register and no other register's output (WRK-1–WRK-2; mechanical task records and judgment of separation).

## 4. Check and resolve findings

```sh
champollion check works/sunrise.md
champollion report --json
```

Resolve findings by their code and location, then rerun the affected checks:

| Class | Response |
|---|---|
| Usage, configuration, schema, or IO failure; exit 2 | Fix the named cause. The run is not a completed mechanical pass. |
| `SRC-…` | Restore the local snapshot, pin, hash, provider, or rights evidence. Never change a hash merely to hide altered bytes. Unknown rights require a new admissible source or a justified rights determination. |
| `SEG-…` | Compare the Original and targets. Fix unit headings, order, missing text, markers, and declared line counts against the source—not by renumbering the source. |
| `REG-…` | Restore a missing register or correct the reported language/name policy. For a copy finding, investigate how the register was made and retranslate from the original if it was derived. |
| `VER-…` | Inspect short units for omitted passages; remove scan debris; resolve quote balance and punctuation. A short-unit ratio is a prompt to compare source and target, not an instruction to pad the translation. |
| `PRV-…` | Complete honest credits and edition notes; keep production material out of reader-facing text. |
| `WRK-…` | Restore packet, numbering, assembly, or attestation evidence. Rework a failed unit before merging it. |
| Warning | Review it. Warnings allow exit 0 but are not an assertion that the text is right. |
| `[exception]` or overdue exception | Resolve or justify the exact finding with owner, reason, recorded date, and expiry. It stays visible debt; overdue exceptions block publication. |

These are mechanical finding responses with editorial decisions. The underlying rules and boundaries are SRC-1–SRC-8, SEG-1–SEG-10, REG-1–REG-11, VER-2–VER-9, PRV-1–PRV-5, and WRK-1–WRK-6 in [SPEC.md](../SPEC.md). An exception cannot repair missing source evidence or unknown rights (VER-12; mechanical matching/expiry, judgment of tolerance).

For a difficult but readable passage, translate the most probable reading and record uncertainty. For genuine damage, seek another witness of the same edition and attribute it; otherwise place `[illegible in the source]` once at the damaged stretch. Do not invent a bridge or skip a hard passage (SEG-8, SEG-10, WRK-4; judgment, with mechanical hygiene and disclosure checks).

## 5. Review and publish

A reviewer will ask whether the selected source is complete, both registers came from it independently, every unit covers exactly its source, and names, numbers, technical terms, and uncertainty are handled honestly. Compare first and last source/target lines in every unit, read at least one unit aloud per register, spot-check terminology, and check sense (VER-10; judgment).

Retain reviewer identity, person or model, actual review date, protocol version, work/units/registers, findings, and resolutions (VER-11; mechanical record completeness, judgment of resolutions). Retain each contributor's originality and source-form attestation (WRK-6; mechanical record presence, judgment of truthfulness).

After changes, rerun checks and update affected review evidence. Set `status: Published` only when no blocking finding or overdue exception remains and current required review records are present (VER-13; mechanical gate state and recorded judgment). Publish the work together with its source evidence and records through your project's own process—Champollion has no publish command and does not approve sense.
