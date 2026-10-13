# Provenance

Record where the source came from, how each edition was made and what remains uncertain. Keep those records outside the reader-facing text. Champollion checks the presence and shape of provenance; it cannot establish the truth of an attribution, the independence of a translation or its sense.

## Front matter

**PRV-1—mechanical schema completeness; judgment of the recorded facts.** The following table follows the `champollion/1` schema in [SPEC.md](../SPEC.md). Front matter is delimited by `---` lines and contains single-line `key: value` scalars only. No lists, nesting or multiline notes are allowed. Malformed front matter is a named error, not a silent default.

All values below are nonempty scalar strings, including dates and paths. Use quoted strings when needed. Use an explicit uncertainty statement rather than inventing an author, date or rights basis.

| Key | Type | Required | Meaning |
|---|---|---|---|
| `slug` | String | Yes | Stable work identifier. |
| `title` | String | Yes | Title of the complete named work. |
| `author` | String | Yes | Author or an honest attribution, including uncertainty where needed. |
| `tradition` | String | Yes | Project tradition or collection classification. |
| `language` | String | Yes | Source-language tag. |
| `genre` | String | Yes | Kind of work. |
| `period` | String | Yes | Historical period or dating statement. |
| `source_url` | String | Yes | Provider locator for the selected source; immutable evidence belongs in its source record too. |
| `raw_snapshot` | String | Yes | Project-relative path to the stored, unmodified provider export. |
| `completeness` | String | Yes | `complete`; for a damaged survival, all surviving text is included and the condition is disclosed. |
| `source_scope` | String | Yes | `whole-work`; no selection passed off as the named work. |
| `<register.id>_translator` | String | For each present register | Contributor or editorial credit for that edition. Required registers must be present. |
| `<register.id>_note` | String | For each present register | How that edition was produced, including machine assistance and consulted aids. |
| `as_of` | String, date | Yes | Date of the recorded state, in `YYYY-MM-DD` form. |
| `certainty` | String | Yes | Declared certainty of the provenance record; not a claim that sense is certified. |
| `source` | String | Yes | Local provenance record or source registry reference, normally `sources/manifest.json`. |
| `status` | String | Yes | Declared editorial status. Writing `Published` does not bypass the publication gate. |
| `unknowns` | String | Yes | Known unresolved questions; explicitly state when none are recorded. |

Replace `<register.id>` with the profile's register identifier: `musean_translator`, `musean_note`, `plain_translator` and `plain_note` for those two registers. These are key patterns, not literal keys to put in a work.

Mouseia uses `curated_translator` and `curated_note` for its Musean edition (`corpus/emerald-tablet.md`; `seed/build.mjs`). Those legacy names belong to the Mouseia adapter, not a new `champollion/1` work. Mouseia's builder also supplies default edition notes when they are absent; do not treat such a default as an honest production record (`seed/build.mjs`).

## Write an honest edition note

**PRV-2—judgment; mechanical note presence.** Say which original the edition used, whether it was made independently, what assistance contributed and what review actually occurred. Credit machine assistance without self-praise or apology. Do not claim review that was not performed.

Good example—an illustrative note to use only when each statement is true:

```yaml
musean_note: Musean edition made directly from the stored Latin original with assistance from a language model; each unit was reviewed against the source for endpoints, names and technical terms.
```

Bad example:

```yaml
musean_note: A flawless, fully verified translation by our team, with no need to discuss how it was produced.
```

The first describes a method and the scope of review. The second hides assistance and claims certainty that mechanical checks cannot provide. A note may refer to a longer local record rather than squeezing the entire acquisition and review history into one scalar.

## Disclose comprehension aids

**PRV-3—recorded judgment of disclosure completeness and how the aid was used.** Record which aid was consulted, whose work it is, its license and its role. Summarize relevant assistance in the affected edition note and keep detailed identification in the source record. A comprehension aid may inform reading; the edition must still be translated from the original under SRC-5.

Mouseia records TLA transliteration and lemma glosses with the TLA editors' German sentence renderings as comprehension aids for Egyptian translation, with CC BY-SA 4.0 attribution. It also records a discarded first pass after review found errors of sense (`corpus/SOURCES.md`, Egyptian expansion record). Naming the German aid does not mean that German was the source language; leaving it unnamed would conceal part of the method. See [sourcing](sourcing.md) for the distinction between consultation and derivation.

## Keep provenance out of the edition

**PRV-4—mechanical detection of production debris; judgment of proper placement.** Front matter carries concise identity, credits, notes and uncertainty. The provider registry carries shared provider information. The local source manifest carries work-specific pins, hashes, rights, cleaning decisions, witnesses and aids. Keep contributor attestations and dated review records outside the translated body, linked from provenance.

Never place production notes, worker instructions, counts, “Translation:” labels, apologies or review claims inside a reader-facing edition. A source's own editorial markers or a required lacuna marker are part of the text, not a place to insert production commentary. Mouseia states this boundary in `docs/translation-guidelines.md`, §6, and places edition notes in front matter and `corpus/SOURCES.md`.

A project may display credits and notes beside an edition choice or on a provenance page. It must not splice them into the passage a reader is reading.

## Attribute witnesses and aids

**PRV-5—recorded judgment of attribution completeness, identity, and license.** Name every consulted source, repair witness and aid, with its license. Identify the edition or object precisely enough to distinguish it from another witness. Record where a witness repaired the source and retain its snapshot; an unnamed replacement passage breaks reproducibility.

Mouseia names the Cornell scan `cu31924032346102` of the same 1920 printing used to repair Economic History of Rome and gives its raw-file path (`corpus/SOURCES.md`, per-text log). Its guidelines require witness repair to be recorded under `corpus/raw/` before using an illegibility marker (`docs/translation-guidelines.md`, §6).

A provider-level license label is not enough when a consulted aid has different rights. Record underlying-work and transcription rights separately under SRC-4. The reference checker flags missing required front-matter values as `PRV-INCOMPLETE`. Reviewers assess the linked witness/aid records, whether the account is complete and accurate, and whether the edition remains faithful to the original.
