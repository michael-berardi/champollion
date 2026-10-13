# Champollion protocol

- Version: **1.0.0**
- Status: **Reference specification.**
- Date: **2026-10-13.**

License: [CC BY 4.0](LICENSE-docs) for this specification and documentation; [MIT](LICENSE) for code.

## 1. Scope and terms

Champollion specifies how to source, segment, independently translate, verify, and disclose a work. It makes mechanical requirements enforceable and editorial judgement recorded and reviewable. It does not translate for anyone or certify sense.

“Must,” “must not,” and the imperative requirements below are normative. A **work** is a complete named work or independently issued document, including its complete surviving text when material is lost. A **unit** is a passage under a `###` heading. A **house register** is a new direct-source edition; a historical or reference edition is an attributed existing edition with its own divisions. At least two house registers are required.

A **mechanical** check compares observable text, structure, or records. A **judgement** check requires a person or reviewing model to read and assess the work. A mechanical pass is not evidence that a translation conveys the source's meaning. A judgement record identifies its reviewer; it does not turn an assessment into a mechanical fact.

Mouseia references below identify the source method and its original implementation. Champollion's implementation and executable evidence are documented in the [acceptance matrix](docs/acceptance-matrix.md). The compatibility gate preserves Mouseia's established checks; it does not certify legacy work under the new specification.

## 2. Work format: `champollion/1`

Store one UTF-8 Markdown document at `works/<slug>.md`. The slug in front matter must match the filename. The document begins with front matter and then contains `## Original` and the profile's required register sections. No check may modify the document.

### 2.1 Front-matter grammar

The opening and closing delimiters are lines containing exactly `---`. The opening delimiter is the first line. Normalize CRLF to LF for parsing, without changing stored snapshot bytes. Interpret front matter as scalar strings, not as YAML. Use this grammar:

```text
front-matter = delimiter LF, field-line { LF field-line }, LF delimiter [ LF ]
delimiter = "---"
field-line = key ":" { horizontal-space } scalar
key = lowercase-letter { lowercase-letter | digit | "_" }
horizontal-space = SPACE | TAB
scalar = unquoted-string | quoted-string
quoted-string = one JSON double-quoted string on one line
```

An unquoted string is the remainder of the line, trimmed at both ends. Do not interpret booleans, numbers, dates, colons, `#`, or the word `null` specially. A quoted string uses JSON string escapes and must occupy the entire trimmed value; text after its closing quote is invalid. No field may contain a literal newline. Do not accept nesting, list syntax, multiline indicators, comments, blank field lines, indented keys, or duplicate keys. Values beginning with `[`, `{`, `- `, `|`, or `>` must be quoted to be scalar strings. Empty values are invalid for required fields.

Reject missing delimiters, malformed field lines, invalid quoted strings, and forbidden compound values with a named `SEG-FRONT-MATTER` schema error. Name the file and line or field. Do not substitute a default, skip the work, or report a clean result. Missing or invalid required provenance values produce `PRV-INCOMPLETE`; §8.1 defines them. Preserve additional scalar fields, but do not let them replace required fields or change core rules.

### 2.2 Sections and units

Recognize body section lines `## <section label>` and unit lines `### <unit title>` at the start of a line. Trim section labels and compare them case-insensitively. Match `Original` to the source section and match register sections only against the profile's `sections` lists. A register's display `label` is not an implicit alias.

Keep unknown `##` sections and ignore their contents for register checks. Still reject duplicate normalized section labels, including unknown labels. Reject two sections that resolve to the same register, even when they use different aliases. Report these as `SEG-PARITY` errors rather than overwriting the first section.

Require at least one explicitly headed, nonempty unit in Original and every present register. Put reader-facing text under unit headings, not before the first unit. For a short undivided work, write one `###` heading. Do not synthesize an implicit whole-work unit. Preserve unit titles after trimming outer whitespace; compare them case-sensitively and in order. Reject empty titles and duplicate unit titles within a section.

Original carries the clean reading text derived reproducibly from the stored raw snapshot. Units in `same-units` registers must match its titles and order exactly. `by-position` requires equal unit counts and a recorded edition-specific mapping; it does not require identical titles. `none` declares no cross-edition unit mapping and cannot be used for either of the two required house registers. Historical/reference divisions remain their edition's own.

This excerpt illustrates one unit in Mouseia's section vocabulary; it is not a complete work document:

```markdown
## Original

### Clause 1

1. Verum, sine mendacio, certum et verissimum.

## Mouseia translation

### Clause 1

1. This is true, without falsehood, certain and most true.

## Plain English translation

### Clause 1

1. This is true and not a lie. It is certain, and completely true.
```

The excerpt comes from Mouseia `corpus/emerald-tablet.md`. That file uses `curated_translator` and `curated_note`; the core format uses the declared register ID, hence `musean_translator` and `musean_note`. A Mouseia adapter must map legacy keys explicitly and diagnose conflicting values, not silently choose one.

### 2.3 Refusals

Refuse a clean or conforming result for missing Original, missing required registers, empty required units, duplicate sections, broken alignment, missing source records, unknown rights, missing snapshots, or hash mismatches. Parsing, configuration, schema, and IO failures are named operational errors. Do not fetch a source to fill a missing local snapshot. Do not invent a unit, source pin, provenance value, or review result.

## 3. Profile contract: `champollion-profile/1`

A profile is a UTF-8 JSON object. Use a standard-library JSON parser. Reject duplicate object keys, trailing data, comments, trailing commas, nonfinite numbers, wrong types, and unknown fields. Validate the entire object before checking works. Do not coerce strings to booleans or numbers. JSON booleans are not integers for threshold validation.

The following tables are the schema. All fields are required except the three explicitly optional language/locale fields. There are no implicit check defaults. Relative paths resolve from the project root selected for the run, not from the current working directory or a remote URL.

### 3.1 Top-level fields

| Field | Type and requirement |
|---|---|
| `profile` | String; exactly `champollion-profile/1`. |
| `name` | Nonempty string identifying the profile. |
| `description` | Nonempty string describing its editorial scope. |
| `source` | Optional; `null` for any source language, or an object with exactly `tag` and `name`, both nonempty strings. `tag` is a BCP-47 language tag. |
| `target` | Optional; `null` for any target language, or the same language object shape as `source`. |
| `target_locale` | Optional; `null`, or a nonempty BCP-47 locale string. It must be compatible with a declared target language. |
| `registers` | Array of register objects defined in §3.2; at least two entries with `required: true` and `alignment: "same-units"`. |
| `checks` | Object containing exactly the fields in §3.3. |
| `rights` | Object containing exactly `allowed`, a nonempty array of unique nonempty license identifiers. An identifier's presence declares project compatibility, not a legal determination. |
| `exceptions` | Array of exception objects defined in §3.4; an empty array means no exceptions. |

Omitted language fields mean an unspecified language constraint, not an inferred English default. Null language fields explicitly allow any language. Record actual work languages in provenance. A nonnull `source` constrains front-matter `language`; record the register's target language in the profile or edition record when the profile allows any target.

### 3.2 Register objects

| Field | Type and requirement |
|---|---|
| `id` | Unique string matching `[a-z][a-z0-9_]*`; must not be `original`. It names provenance fields and check selections. |
| `label` | Nonempty display string. |
| `required` | Boolean. Optional registers are checked when present. |
| `alignment` | Exactly `same-units`, `by-position`, or `none`. |
| `sections` | Nonempty array of nonempty section-label strings. Normalize by trimming and case-folding. Every alias must be unique across the profile and must not be `original`. |

Do not add undeclared fields to register objects. Put each register's editorial definition in a project record; the shipped definitions are in REG-4. An optional historical register does not count toward the two independent house registers.

### 3.3 Check fields

| Field | Type and meaning |
|---|---|
| `structure` | Boolean; run unit-title/order parity and alignment checks. Required for conformance. |
| `coverage` | Boolean; run structural coverage and endpoint-evidence checks. Required for conformance. |
| `numbering` | Boolean; compare ordered source-marker sequences and declared line-for-line counts. Required for conformance. |
| `copy_ratio` | `null` to disable this heuristic, or a finite number from 0 through 1. Report identical-sentence ratios strictly greater than it. |
| `speech_marks` | Array of unique declared register IDs whose speech marks are checked. An empty array disables this gate. |
| `archaisms` | Exactly `off` or `en-modern`. `off` applies no English archaism list. |
| `plain_archaisms` | Boolean; apply the additional English Plain-only list to register `plain`. `true` requires `archaisms: "en-modern"` and a declared `plain` register. |
| `spelling_profile` | `null`, `en-US`, or `es`. Selects the spelling policy; it does not authorize changing source or historical spelling. |
| `name_table` | `null`, or a nonempty local path to the project's name table. Variants and source-attested alternative names belong in that table or an attributed edition record. |
| `debris` | Boolean; run scan-debris, OCR-marker, raw-markup, and doubled-word checks under the selected language policy. |
| `ellipsis` | Exactly `off`, `warn`, or `error`; sets the ellipsis-form gate's disposition. |
| `short_unit_ratio` | `null` to disable this heuristic, or a finite number greater than 0 and at most 1. Compare each eligible target/source ratio with this fraction of the work's register-specific median. |
| `min_source_chars` | Positive integer; minimum source-text length for the short-unit gate. |
| `min_units_for_ratio` | Integer at least 3; minimum eligible units before comparing ratios. |
| `min_sentences` | Positive integer; minimum eligible sentences in the compared register for the copy gate. |
| `min_sentence_chars` | Positive integer; minimum length of an eligible sentence for the copy gate. |

Disabled heuristics must remain visible in reports. They do not waive independence, completeness, or review. A checker unable to implement a selected spelling or language policy must name the unsupported setting as a configuration error, not silently skip it. Profiles must not embed executable code or cause a network call at check time.

### 3.4 Exception objects

| Field | Type and requirement |
|---|---|
| `code` | Nonempty stable uppercase finding code. |
| `work` | Nonempty work slug. |
| `unit` | Nonempty exact unit title. A work-level exception uses the work-level location reported by the checker; do not infer wildcard matching. |
| `owner` | Nonempty accountable person or project role. |
| `reason` | Nonempty explanation of the tolerated finding. |
| `recorded` | String containing a valid Gregorian date, `YYYY-MM-DD`. |
| `expires` | Same date type; strictly later than `recorded`. |

Match exceptions to code, work, and unit exactly. Reject duplicate exception selectors. An exception is overdue after its `expires` date, using the run's recorded UTC date. An unexpired matched exception changes the displayed finding to a warning with `[exception]`; it never removes the finding. An overdue exception remains blocking and is reported under VER-12. An exception cannot provide missing source evidence or make an unknown license admissible under SRC-4.

### 3.5 Shipped profiles and field changes

`profiles/generic.json` allows any source and target language. It requires `literal` and `plain` with `same-units` alignment, no spelling or name table, and no exceptions. It disables the English-derived copy and length heuristics; independence still requires recorded judgement.

`profiles/mouseia.json` requires `musean` and `plain` and declares an optional `historical` edition. The section aliases are those in Mouseia `scripts/lint_corpus.py` and `seed/build.mjs`: `mouseia translation`, `curated translation`, `plain english translation`, `plain translation`, and `historical translation`. Its name-table path is `names.json`, as in the build brief; a Mouseia adoption must resolve or provide the table from `scripts/names.json` explicitly. Undeclared `reference translation` sections remain preserved but ignored by this profile, not certified.

`profiles/latin-to-spanish.json` fixes source `la`, target `es`, locale `es`, and required `literaria` and `clara` registers. It disables English archaisms and automated spelling checks: the reference implementation has no Spanish variant list. Its report names disabled heuristics; editorial spelling review remains required. It has no name table or exceptions.

Allow a new field only after specifying its type, allowed values, missing-value behavior, validation errors, rule relationship, and a failing fixture. Do not accept arbitrary unknown fields as future extensions. Deprecate a field with a documented replacement and migration period; continue validating its old meaning during that period. Never reinterpret it silently. Removing a field, changing a default or threshold, enabling a previously inactive gate, or changing accepted inputs incompatibly requires a major version change. Track schema versions separately from the protocol version and individual profile revisions; see [migration policy](docs/migration-policy.md).

## 4. SRC—Sourcing and rights

For settings below, “core” means mandatory regardless of the profile; profiles cannot waive the requirement. Source and edition records are local records referenced by front-matter `source`; this version does not prescribe their JSON key names.

| ID and title | Requirement | Why it exists | Verification and profile setting |
|---|---|---|---|
| **SRC-1 Canonical original, stored not linked** | Commit the complete original-language text as an unmodified provider export; derive Original from it. Never fetch the text at read or check time. | Preserve a recoverable witness independently of a provider; Mouseia `corpus/SOURCES.md`, Rules. | Mechanical: local raw/clean presence. Judgement: canonical witness selection. Core; `source`. |
| **SRC-2 Immutable revision evidence** | Record an immutable revision and the snapshot's SHA-256. Use a wiki `oldid`, commit SHA, or catalogue identifier plus content hash; reject a bare URL, URN, or moving page as a pin. | Prevent an unchanged citation from pointing to changed text; pinned wiki and ORAEC recipes appear in Mouseia `corpus/SOURCES.md`. | Mechanical: evidence fields and hash verification. Judgement: edition identification. Core. |
| **SRC-3 Complete works only** | Include the complete named work or complete surviving text. Do not present an excerpt, selection, or abridgment as a work. State lost material and the surviving scope. | Prevent misleading completeness; Mouseia `corpus/SOURCES.md`, Rules and surviving-papyrus entries. | Mechanical: completeness/scope declarations. Judgement: source boundaries. Core. |
| **SRC-4 Rights gate** | Admit only public-domain or explicitly compatible sources. Record underlying-work and transcription rights separately, attribution, and share-alike duties. Refuse unknown rights. | A public-domain work can have a CC BY-SA transcription; Mouseia `corpus/SOURCES.md` identifies these separately for Wikisource and Herodotus. | Mechanical: records and allowed identifiers. Judgement: rights determination and compatibility. `rights.allowed`; core separation. |
| **SRC-5 Primary source only** | Translate from the original-language text, never from another translation. Consult aids only as aids and disclose them under PRV-3; do not derive the edition from them. | Distinguish aid-assisted source reading from translation of a translation; Mouseia `corpus/SOURCES.md` records TLA German aids. | Judgement, with mechanical disclosure completeness. `source`; required register definitions. |
| **SRC-6 Reproducible cleaning** | Record the cleaning script or an explicit transformation rule sufficient to regenerate Original from the raw snapshot. Preserve the raw bytes. | Prevent unexplained editorial changes; Mouseia `corpus/SOURCES.md` records Ali Baba correction decisions and Herodotus extraction. | Mechanical: transformation record exists. Judgement or reproducibility check: record matches the result. Core. |
| **SRC-7 Source registry** | Register every provider once with scope, originals/translations offered, access method, license, and fetch recipe. Link each work to that provider entry. | Avoid treating a translation-only provider as an original provider; see Mouseia `corpus/SOURCES.md` provider table. | Mechanical: reference and field completeness. Judgement: provider suitability. Core. |
| **SRC-8 Snapshot integrity** | Mark an entry incomplete if its snapshot is missing or unverifiable. Compute SHA-256 over stored bytes and refuse a mismatch. | Make reproducible sourcing depend on the actual witness, not a path alone; Mouseia `seed/build.mjs` checks raw-path existence, not hashes. | Mechanical: local existence and digest equality. Core. |

Do not treat a provider's general license label as proof of every work's rights. Record the selected edition's evidence. Checking stored evidence is offline; source acquisition is a separate operation.

## 5. SEG—Segmentation and alignment

| ID and title | Requirement | Why it exists | Verification and profile setting |
|---|---|---|---|
| **SEG-1 One work per document; units** | Use one document per work and units with titles that describe their actual contents. | Mouseia's Lucretius unit titled “Against Anaxagoras” contained none of that passage; `docs/translation-guidelines.md` §1. | Mechanical: document/unit grammar. Judgement: title accuracy. `checks.structure`; core work format. |
| **SEG-2 House editions carry the original's units, in order, exactly** | Match Original's unit titles and order exactly in each house edition; use SEG-7 for historical/reference editions. | Matching structure is not safe to assume; Mouseia `seed/build.mjs`, `requireCompleteEdition`, refuses differing headings. | Mechanical. `registers[].alignment: "same-units"`, `checks.structure`. |
| **SEG-3 Every unit translates exactly the source under the same heading** | Render all and only the source under that unit's heading. | Lucretius I units 6–8 carried 561 Latin lines but English for about 197, with lines 552–920 untranslated; Mouseia `docs/translation-guidelines.md` §1. | Mechanical: coverage evidence and outliers. Judgement: actual semantic coverage. `checks.coverage`, short-unit settings. |
| **SEG-4 Source form is part of the text** | Preserve source lines, stanzas, parallel units, recitation boundaries, and paragraphs. Do not flatten verse or borrow breaks from another translation. | Form carries meaning and cadence; Mouseia `corpus/SOURCES.md`, Rules. | Mechanical where boundaries are declared. Judgement: functional form. `checks.coverage`; alignment policy. |
| **SEG-5 The source keeps its own numbering** | Preserve every source reference marker in its original order; do not renumber, duplicate, or continue past the source endpoint. Validate sequences, not just counts. | Amenemope's English had 196 numbered lines for a 185-line source and ended with absent passages; Mouseia `docs/translation-guidelines.md` §1. | Mechanical. `checks.numbering`; edition-specific marker policy. |
| **SEG-6 Line-for-line works stay line-for-line** | Return one target line for each source line, in order, for a declared line-for-line work. | Line counts and correct endpoints constrain invention and omissions; Mouseia `docs/translation-guidelines.md` §1. | Mechanical counts/order; judgement alignment of sense. `checks.numbering`; recorded line-for-line policy. |
| **SEG-7 Historical and reference editions keep their own divisions** | Preserve the edition's divisions and declare its alignment policy. Use positional alignment only with equal counts and an edition-specific mapping. | Haines's Meditations has different divisions; Godley's Herodotus needs a positional numbering mapping; Mouseia `README.md`, Corpus conventions, and `corpus/SOURCES.md`, Herodotus. | Mechanical: declared mapping/counts. Judgement: suitability. `registers[].alignment`. |
| **SEG-8 Damage and lacunae** | Repair damage from another witness of the same edition when available and record the witness. Otherwise substitute `[illegible in the source]` once for the entire damaged stretch. | Tenney Frank's Economic History carried about 60 OCR fragments; another scan of the same 1920 printing restored prose; Mouseia `docs/translation-guidelines.md` §6. | Mechanical: forbidden OCR markers/disclosure. Judgement: witness repair and reading. `checks.debris`; core witness record. |
| **SEG-9 Deliberate blanks stay visible** | Render every deliberately printed blank as `——`; do not delete it. | Thoughts on Government lost blanks and read “The Colony of to A. B.”; Mouseia `docs/translation-guidelines.md` §6. | Mechanical: visible blank markers where source blanks are identified. Judgement: blank identification. `checks.coverage`. |
| **SEG-10 No summaries and no silent omissions** | Translate difficult passages rather than summarize, skip, or substitute “and so on.” Use SEG-8 only for genuine damage. | A shorter account can conceal missing text; the Lucretius audit in Mouseia `docs/translation-guidelines.md` §1 supplies a concrete omission case. | Judgement with mechanical coverage evidence. `checks.coverage`; short-unit settings. |

Marker extraction must declare the supported notation and preserve ordered values, including inline page/section markers and verse-end markers. A checker unable to parse a work's declared notation must report that limitation, not claim numbering passed. Numerical equality alone does not establish that a target line renders the corresponding source line.

## 6. REG—Registers

| ID and title | Requirement | Why it exists | Verification and profile setting |
|---|---|---|---|
| **REG-1 Every work carries the required registers** | Include every register marked required by the profile, with complete text. Require at least two house registers. | Mouseia requires Musean and Plain, not a single default edition; `docs/translation-guidelines.md` §1. | Mechanical presence; judgement completeness. `registers[].required`. |
| **REG-2 Each register is made directly from the original** | Make every new register directly from Original and its source witness. Do not translate a historical edition or another house register. | Preserve direct-source accountability; Mouseia `docs/translation-guidelines.md` §1–§3. | Judgement and contributor attestation. `registers`; core. |
| **REG-3 Registers are independent** | Produce registers independently, not by editing one into the other. Run the declared copy gate and record the independence review. | Plain lines in Iliad 4, 5, 8, 13 and Odyssey 11 were 53–77% copied from Musean; Mouseia `docs/translation-guidelines.md` §3. | Mechanical heuristic plus judgement; neither proves production history alone. `checks.copy_ratio`, `min_sentences`, `min_sentence_chars`. |
| **REG-4 Register definitions** | Apply the declared register definition without sacrificing completeness or adding commentary. | Mouseia defines different reading registers while retaining the same content; `docs/translation-guidelines.md` §2–§3. | Judgement. `registers[].id`, `label`; project register definitions. |
| **REG-5 Sense, not word order** | Translate false friends and technical terms as concepts in intelligible target syntax. | Both Cicero On Duties I editions were calques; Mouseia `docs/translation-guidelines.md` §2 gives the “slownesses in walking softer” example. | Judgement. Target language and register definition. |
| **REG-6 Poetry is kept** | Preserve line breaks, parallelism, repetition, and formulae; render each epithet once. | “wind-swift swift Iris” and “to counsel counsel” duplicated source material; Mouseia `docs/translation-guidelines.md` §2. | Mechanical line evidence; judgement poetic form and epithet fidelity. Alignment and `checks.coverage`. |
| **REG-7 Modern English** | In English house registers, reject listed archaisms; apply the additional Plain list to Plain. Retain archaic forms only when quoting an archaic source and record the reviewed context. | Modern reading registers require living English; Mouseia `docs/translation-guidelines.md` §2–§3 and `scripts/lint_corpus.py`, `ARCHAIC_ALL`/`ARCHAIC_PLAIN`. | Mechanical lists; judgement quotation context. `checks.archaisms`, `plain_archaisms`. Off for non-English profiles. |
| **REG-8 One spelling per name per work** | Use the house name table consistently across house registers. Keep source-attested alternative names and record why both occur. | Iliad and Odyssey mixed Hektor/Hector, Aias/Ajax, and Telemachos/Telemachus; Mouseia `docs/translation-guidelines.md` §2. | Mechanical variants; judgement identity and alternatives. `checks.name_table`. |
| **REG-9 Mechanics** | Use unspaced em dashes for breaks, en dashes for ranges, a single ellipsis character, and double quotation marks for direct speech. Reject unintended doubled words. Match source numbers and figures. | About half the Iliad and Odyssey books lacked speech marks; Mouseia `docs/translation-guidelines.md` §5. | Mechanical form, balance, and marker checks; judgement intended repetitions, figures, and speech identification. `checks.ellipsis`, `speech_marks`, `debris`, `numbering`. |
| **REG-10 Spelling profile per edition** | Apply the declared locale to house editions; leave originals and historical editions in their own spelling. | Prevent accidental mixed house spelling without rewriting witnesses; Mouseia `docs/translation-guidelines.md` §4–§5. | Mechanical known variants; judgement deliberate forms. `target_locale`, `checks.spelling_profile`. |
| **REG-11 Adding a register** | Declare the new register in the profile, supply its own editorial definition, and apply REG-2, REG-3, and the same applicable gates. | An added register must not become an unchecked derivative. | Mechanical declaration/gate coverage; judgement definition and independence. `registers`; applicable `checks`. |

The shipped definitions under REG-4 are:

- **Mouseia Musean:** fidelity joined to modern clarity, beauty, symbolism, and the source's structure.
- **Mouseia Plain English:** everyday contemporary English, complete and direct, never a summary, shorter in content, or commentary.
- **Generic literal:** source-near wording in intelligible target syntax, preserving technical distinctions and source form without calques that distort sense.
- **Generic plain:** complete source content in ordinary contemporary target-language wording and direct syntax, without added explanation.
- **Spanish literaria:** complete direct-source Spanish preserving imagery, rhetorical structure, technical distinctions, and cadence in contemporary literary language.
- **Spanish clara:** complete independent direct-source Spanish using familiar contemporary words and direct syntax, without summaries or added explanations.

The last four are Champollion profile definitions, not claims about Mouseia. The core does not impose English word lists on another language.

## 7. VER—Verification and publication

| ID and title | Requirement | Why it exists | Verification and profile setting |
|---|---|---|---|
| **VER-1 Two halves** | Run mechanical gates and record human/model judgement separately. Do not present either as the other. | A linter cannot certify sense; Mouseia separates lint and review in `docs/translation-guidelines.md` §7. | Mechanical run record plus judgement record. All applicable `checks`; core review. |
| **VER-2 Structure gate** | Check SEG-2/SEG-3 structural parity for every applicable edition. | Mouseia `seed/build.mjs` refuses missing editions and mismatched headings. | Mechanical. `checks.structure`, per-register alignment. |
| **VER-3 Coverage gate** | Check per-unit source/target endpoint evidence and run the enabled length-outlier detector. | The Lucretius omission case motivates the detector; Mouseia `scripts/lint_corpus.py`, `triples`/`SHORT_UNIT`, and `docs/translation-guidelines.md` §1. | Mechanical, not semantic endpoint reading. `checks.coverage`, short-unit settings. |
| **VER-4 Numbering gate** | Check SEG-5/SEG-6 ordered-marker continuity and declared line counts before accepting alignment. | Amenemope's excess numbered lines demonstrate why headings alone are insufficient; Mouseia `docs/translation-guidelines.md` §1. | Mechanical. `checks.numbering`; edition-specific marker/line policy. |
| **VER-5 Independence gate** | Run the enabled REG-3 identical-sentence detector and report its denominator and ratio. | Copied Plain passages motivated Mouseia's 35% threshold; `docs/translation-guidelines.md` §3 and `scripts/lint_corpus.py`. | Mechanical heuristic. Copy settings. |
| **VER-6 Hygiene gates** | Check scan debris, OCR markers, raw markup, unintended doubled words, and ellipsis form. | Economic History OCR fragments and historical Haines scan errors are documented in Mouseia `docs/translation-guidelines.md` §4/§6. | Mechanical with reviewed intended-repetition handling. `checks.debris`, `ellipsis`; language policy. |
| **VER-7 Language gates** | Run selected archaism, Plain-only archaism, spelling, and name-variant policies. | Mixed Homeric name spellings are documented in Mouseia `docs/translation-guidelines.md` §2. | Mechanical policy checks, not language-quality assessment. Language/name settings. |
| **VER-8 Speech-mark gate** | Check quotation balance in every selected register under its recorded speech notation. | Unclosed speeches are the stated scope in Mouseia `scripts/lint_corpus.py`; absent speech marks also required editorial repair in `docs/translation-guidelines.md` §5. | Mechanical balance; judgement presence where speech occurs. `checks.speech_marks`. |
| **VER-9 Rights, pin and provenance gate** | Verify SRC-2/4/7/8 evidence and PRV-1 completeness locally. | Mouseia `seed/build.mjs` requires completeness, scope, and raw-path existence; `corpus/SOURCES.md` supplies source evidence. Hash/pin enforcement is an additional normative requirement. | Mechanical evidence checking; judgement rights interpretation. `rights.allowed`; core provenance. |
| **VER-10 Judgement** | Read at least one unit aloud per house register. Compare first/last source and target lines or sections in every unit. Spot-check terms, names, and numbers, and perform an honest sense check. | These are Mouseia's review checklist, `docs/translation-guidelines.md` §7, not linter results. | Judgement. Every house register; project register definitions. |
| **VER-11 Review record** | Record reviewer identity, whether person or model, date, protocol version, findings, and resolutions for every review. Identify reviewed work, units, and registers and retain unresolved findings. Bind the record to the reviewed work's SHA-256 and the profile fingerprint; changed text or settings require a fresh review. | Make judgement inspectable instead of assuming a clean linter means review occurred. | Mechanical record completeness; judgement findings/resolutions. Core. |
| **VER-12 Exceptions** | Record each tolerated finding with owner, reason, recorded date, and expiry. Show it as debt, not a silent pass. Restore blocking status when overdue. | Mouseia `scripts/lint-baseline.json`, as described in `scripts/lint_corpus.py`, tracks exceptions but supplies no owner/expiry fields; the protocol makes that debt explicit. | Mechanical matching/date handling; judgement tolerance. `exceptions`. |
| **VER-13 Publication gate** | Do not publish while any blocking finding or overdue exception remains, or while required judgement/review records are absent. Re-run affected gates after a resolution. | Mouseia requires lint, seed build, and review before publication or merge; `docs/translation-guidelines.md` §7. | Mechanical gate/report status plus recorded judgement decision. All required gates and exceptions. |

### 7.1 Mechanical coverage and its limits

Check that each source unit maps to a nonempty target unit and that the first and last nonempty lines or sections exist. Where endpoints have source reference markers, verify their presence and order in the target. Check declared line/paragraph/stanza counts and identified deliberate blanks where a project supplies the corresponding source-form policy. Report absent or inconsistent evidence as `SEG-COVERAGE`; report a marker-sequence mismatch as `SEG-NUMBERING`.

This cannot compare the meaning of two unnumbered endpoint lines. That comparison is VER-10. Do not describe a nonempty last line or a plausible length ratio as proof that the final source passage was translated. Report unsupported structural policies or missing marker evidence explicitly rather than declaring them passed.

### 7.2 Mouseia's practised parameters

The following algorithms transcribe Mouseia `scripts/lint_corpus.py`. They are profile-specific heuristics, not universal translation measures.

**Short units:** pair Original, Musean, and Plain by unit position; select triples whose stripped source text has at least **1,500 characters**. Count characters in the linter's unit text, after removing HTML comments and stripping outer whitespace, including internal whitespace and reference markers. For each house register independently, compute target-character/source-character ratios. Require at least **3 eligible units**. Sort the ratios and use element `len(ratios) // 2`—the upper-middle value for an even count. Report a ratio **strictly below 0.5 times that median** as `VER-SHORT-UNIT`. Equality is not a finding. Do not include ineligible units in the median.

**Copied registers:** compare every pair of house registers in profile order, using the later register as the denominator. Mouseia's Musean/Plain comparison retains its established code and wording. Other pairs use rule code `REG-3`. For the Mouseia pair, split stripped unit text at a newline or whitespace following `.`, `!`, `?`, `;`, or `:`. Trim each result and retain only sentences of at least **40 characters**. Build a set of eligible Musean sentences; retain Plain sentences as a list, including repeated occurrences. If a Plain unit has at least **8 eligible sentences**, count its sentences exactly equal, case-sensitively, to a member of that set. Report a fraction **strictly greater than 0.35** as `REG-PLAIN-COPY`. Equality is not a finding. Shorter units are inapplicable, not proof of independence. The brief's single ellipsis requirement does not change this historical sentence splitter.

**Ellipsis:** Mouseia warns for the patterns `(?<!\.)\.\.(?!\.)` and `\(\.\.\)`. Its existing linter does not catch every violation of REG-9, including a conventional three-dot ellipsis. Preserve that distinction when reporting oracle parity. The profile's disposition is **warning**, not a publication-blocking error by itself.

**Speech marks:** the profile selects registers **`musean` and `plain`**. Mouseia's existing linter further limits the structural check to **`iliad` and `odyssey`**. It considers a straight double quote opening when it is at line start or follows a space, `(`, or an em dash; otherwise it considers it closing. Track state through a unit and report an opening within an open speech, a closing without an opening, or an unclosed speech at the unit's end. Do not claim this check detects every missing speech mark. The work scope belongs to the Mouseia adapter's existing-gate policy; it is not an invented profile field.

**Language and hygiene:** Mouseia selects `en-modern`, the additional Plain-only list, `en-US`, its house name table, and debris checks. Its actual regular expressions and reviewed doubled-word allow-list are in `scripts/lint_corpus.py`; spelling and names are supplied there through `scripts/americanize.py` and `scripts/normalize_names.py`. Do not call those lists universal. The historical/reference section contents are not checked by that house-register linter.

Mouseia's loader can silently skip malformed documents or documents without Original, overwrite recognized sections, and align with `zip`. Champollion must refuse the corresponding invalid inputs under §2 before interpreting ratios. Oracle parity for legacy valid inputs is separate from enabling new gates. `seed/build.mjs` supplies heading and publication-metadata checks; it does not compute snapshot hashes or perform semantic endpoint reading.

### 7.3 Findings, run output, and reports

Findings use stable uppercase family-prefixed codes. Preserve the rule ID responsible for each finding separately from its check-specific code. Use these check codes when applicable:

```text
VER-SHORT-UNIT  REG-PLAIN-COPY  REG-ARCHAISM  REG-SPELLING
REG-NAME-VARIANT  SEG-NUMBERING  SEG-PARITY  SEG-COVERAGE
VER-SPEECH-MARKS  VER-DEBRIS  VER-OCR-MARKER  VER-DOUBLED-WORD
VER-ELLIPSIS  SRC-NO-PIN  SRC-HASH-MISMATCH  SRC-RIGHTS  PRV-INCOMPLETE
```

For requirements without a specialized check code, use their fixed rule ID, such as `REG-1` for a missing required register, `SRC-7` for an incomplete provider reference, `SRC-8` for a missing snapshot, `VER-11` for missing review records, and `VER-12` for an overdue exception. `SEG-FRONT-MATTER` names malformed front-matter syntax. Do not rename findings when wording changes.

Render one finding per line, followed by a summary:

```text
ERROR emerald-tablet [Clause 1] SEG-NUMBERING: target marker sequence differs from Original
WARN emerald-tablet [Clause 1] VER-ELLIPSIS: use a single ellipsis character
```

A unit location is omitted for a work-level finding. Unexpired matched exceptions render as `WARN` with `[exception]` and retain the original code. Use exit **0** for no error findings, with warnings allowed; **1** for at least one error finding; **2** for usage, configuration, schema, or IO failure. An operational failure must name its cause and cannot claim a completed clean run. `check` and its `lint` alias use the same output and exit codes. Reporting commands support `--json` according to the CLI contract in the build brief.

Every verification report must contain:

- Protocol and checker versions; run UTC date; project root; work paths/slugs; selected profile identity and the exact effective settings or a local fingerprint identifying them.
- Source/provider and edition identities, snapshot paths, immutable revision evidence, expected and computed SHA-256, and separate rights records or references to them.
- Required/present registers and alignment policies; gates run, disabled, inapplicable, unsupported, or failed, including work-scoped adapter choices. Never merge these states into “passed.”
- Each finding's severity, code, rule ID, work, register where relevant, unit or work-level location, message, and available line/marker evidence. Include measured ratios, thresholds, denominators, and eligible-unit counts for ratio findings.
- Every exception's owner, reason, recorded/expiry dates, match status, and overdue status, including unmatched entries as visible debt rather than hiding them.
- Review records or their local references, reviewer identities, judgement findings/resolutions, unresolved blockers, and explicit publication-gate status.
- Summary counts of works, errors, warnings, and exception debt, with any incomplete run identified. Report mechanical results and judgement records in separate fields or sections.

A clean `check` run is only the mechanical result. Publication additionally requires the current work's VER-10/VER-11 record. A profile that disables core structure, coverage, or numbering gates cannot support a conformance claim. A changed source, unit structure, or edition invalidates the affected earlier gate/review evidence until it is checked again.

## 8. PRV—Provenance and disclosure

### 8.1 PRV-1 front-matter schema

**PRV-1 Front-matter schema.** Record the identity and provenance below as scalar strings. Require each base field and the credit/note pair for every present register; do not replace missing values with guesses. Why: a reader and checker need the source, edition responsibility, scope, and uncertainty outside the text. Verification is mechanical completeness plus judgement about truthfulness. Settings: declared register IDs and language constraints; otherwise core. Mouseia's related fields appear in `corpus/emerald-tablet.md`; its additional `type: article` belongs to its own build contract in `seed/build.mjs`, not this core schema.

| Key | Type and constraint | Required |
|---|---|---|
| `slug` | Nonempty string matching `[a-z0-9]+(?:-[a-z0-9]+)*`; matches filename stem. | Yes |
| `title` | Nonempty string naming the work, not an undisclosed selection. | Yes |
| `author` | Nonempty string; state anonymous, attributed, or uncertain authorship honestly. | Yes |
| `tradition` | Nonempty project classification string. | Yes |
| `language` | Nonempty BCP-47 string for the actual original language. | Yes |
| `genre` | Nonempty descriptive string. | Yes |
| `period` | Nonempty historical-period string; uncertainty may be stated. | Yes |
| `source_url` | Nonempty source-identifying URI string; does not itself satisfy pinning. | Yes |
| `raw_snapshot` | Nonempty project-relative local snapshot path; must exist and identify stored raw bytes. | Yes |
| `completeness` | String exactly `complete`; includes complete surviving text when loss is disclosed. | Yes |
| `source_scope` | String exactly `whole-work`; explain surviving limits in the source record and `unknowns`. | Yes |
| `musean_translator` | Nonempty credit string for register `musean`. | When Musean is present |
| `musean_note` | Nonempty edition-production/disclosure string for register `musean`. | When Musean is present |
| `plain_translator` | Nonempty credit string for register `plain`. | When Plain is present |
| `plain_note` | Nonempty edition-production/disclosure string for register `plain`. | When Plain is present |
| `as_of` | Valid Gregorian date string, `YYYY-MM-DD`, for the provenance statement. | Yes |
| `certainty` | Nonempty epistemic-status string, such as `observed`; state its basis in the source record. | Yes |
| `source` | Nonempty local provenance-record path/reference identifying the source registry/manifest entry. | Yes |
| `status` | Nonempty publication-state string; `Published` requires the publication gate. | Yes |
| `unknowns` | Nonempty statement of known uncertainty; say `none recorded` only when truthful. | Yes |

For each other declared register, the exact additional keys are `<id>_translator` and `<id>_note`, both nonempty strings required when that section is present. Thus Generic uses `literal_translator`, `literal_note`, `plain_translator`, `plain_note`; Spanish uses `literaria_translator`, `literaria_note`, `clara_translator`, `clara_note`; a present Historical section uses `historical_translator` and `historical_note`. Do not require `musean_*` in a profile without Musean. An absent optional register requires neither key.

The core list is the table plus those declared-register pairs. Additional project scalar fields may be preserved under §2.1 but are not substitutes for core provenance. Put compound source evidence, aids, cleaning decisions, witness repairs, attestations, and review records in the referenced local records, not nested front matter. Check their presence under the relevant rules; the table alone is not sufficient evidence of source integrity.

### 8.2 Other disclosure rules

| ID and title | Requirement | Why it exists | Verification and profile setting |
|---|---|---|---|
| **PRV-2 Honest edition notes** | Describe how each edition was made, including machine assistance, without self-praise or apology. | Mouseia requires honest front-matter notes in `docs/translation-guidelines.md` §7; `corpus/emerald-tablet.md` identifies machine assistance. | Mechanical note presence; judgement accuracy. Register credit/note pairs. |
| **PRV-3 Comprehension aids disclosed** | Record which aid, whose work it is, its license, and how it was used. Distinguish consultation from derivation. | Mouseia records TLA lemma glosses and German renderings, including discarding an earlier unaided pass after review found sense errors; `corpus/SOURCES.md`, 2026-09-27 expansion. | Mechanical record completeness; judgement actual use. Core, linked `source` record. |
| **PRV-4 Provenance is not in the text** | Keep production notes, tallies, “Translation:” labels, and apologies out of reader-facing editions. Put provenance in front matter and the registry. | Process material is not source content; Mouseia `docs/translation-guidelines.md` §6. | Mechanical known labels/debris; judgement contextual identification. `checks.debris`; register notes. |
| **PRV-5 Witnesses and aids are attributed** | Name every consulted source, repair witness, and aid with its license and required attribution. | Repairs and aids need their own evidence; Mouseia `corpus/SOURCES.md` records the Cornell Frank scan and licensed TLA aids. | Mechanical attribution fields; judgement completeness. `rights.allowed`; linked source/edition records. |

## 9. WRK—Working with collaborators

| ID and title | Requirement | Why it exists | Verification and profile setting |
|---|---|---|---|
| **WRK-1 Per-unit packets** | Give each task one source unit, its numbering, one register, constraints, and an exact output shape. Include enough source-form and lacuna information to preserve it. | Mouseia requires original units and numbering in worker tasks; `docs/translation-guidelines.md` §8. | Mechanical packet fields; judgement adequate context. `registers`; alignment and numbering policies. |
| **WRK-2 Register separation** | Use one register per task. Do not show that task another register's output for the same unit. | Separate tasks prevent derivative Plain editions; Mouseia `docs/translation-guidelines.md` §8. | Mechanical dispatch record; judgement attestations. Register IDs; core task separation. |
| **WRK-3 Numbering contract** | Return the source's numbering unchanged. Have the coordinating parent validate marker sequences and counts mechanically before integration. | Amenemope's numbering defect and worker guidance are in Mouseia `docs/translation-guidelines.md` §1/§8. | Mechanical. `checks.numbering`; packet marker/line contract. |
| **WRK-4 No invention** | Never fill a gap with a neighboring paraphrase or add an explanation absent from the source. Translate the most probable reading; apply SEG-8 for genuinely illegible material. | Mouseia explicitly prohibits gap-filling invention in `docs/translation-guidelines.md` §8. | Judgement with source comparison. Register definition; core. |
| **WRK-5 Assembly refuses gaps** | Reject a unit failing its packet contract; re-dispatch it rather than merging. Refuse missing, duplicate, unknown, or out-of-order units and mismatched markers. | A partial assembly can conceal omissions despite matching headings. | Mechanical assembly validation; judgement resolution of failed work. Alignment, structure, coverage, and numbering settings. |
| **WRK-6 Attestation** | Require each contributor, person or system, to attest that their text is their own work, made from the original, with source form preserved. Identify the contributor and contribution in a retained record. | Mouseia `README.md`, Community + API, describes submission attestation of originality and a public-domain source; source-form attestation here is the protocol requirement, not a claim about that server. | Mechanical record presence; judgement truthfulness. Core. |

Keep attestations and dispatch records outside reader-facing unit text. Assembly validates a mechanical contract; it does not approve the translation's sense. Follow [collaborator guidance](docs/ai-workers.md) for packet and response presentation without weakening these rules.

## 10. Conformance

A project claiming **Champollion 1.0 conformance** must identify protocol version 1.0.0, the exact profile revision, the works and house registers in scope, and its checker/gate configuration. Store conforming work documents, source evidence, records, and the mechanical report and judgement review record for the versions being published.

Run every mandatory core gate and every enabled applicable profile gate. Record inapplicability and disabled optional heuristics explicitly. Follow SRC, SEG, REG, PRV, and WRK requirements where applicable, and satisfy VER-13 before publication. A historical or unknown section ignored by a profile must not be included in a house-register conformance claim. A legacy baseline without owner and expiry is not a VER-12 exception record.

Conformance means the required gates ran and the review record exists, with no unresolved blocking finding or overdue exception. It never means the translation is good, faithful in sense, legally certified, or independently proven to have a particular production history. A project may report a mechanical check without claiming protocol conformance.

The reference implementation targets Python 3.9+ and the standard library only. Checks read local evidence, make no network calls, and do not require a hosted service or a translation model. Checks never edit work documents. Writing commands are `init`, `source add`, `vendor`, `packets --out`, and `assemble`. Packets without `--out` print to stdout; assembly writes a separate copy and leaves the input unchanged.

## 11. Versioning and change discipline

Version the protocol, implementation, profile schema, and project profiles explicitly. Preserve existing rule IDs and meanings. Clarify an unchanged rule under its ID; assign a new ID and retire the old one when its meaning changes. Do not reuse a retired ID.

For each new gate or changed rule, supply a failing fixture, its rule ID, profile setting, report code, migration note, and changelog entry. Do not silently activate a new check in a deployed profile. Preserve an independently frozen oracle when claiming compatibility with Mouseia's legacy linter; compare outputs and exit codes, not the replacement with itself.

Pin adopted implementations to an immutable tagged snapshot with local integrity evidence. Separate a clarification from a behavior-changing release; changing accepted inputs, gate behavior, or publication requirements incompatibly requires a major bump. Define field deprecation, exception expiry, rollback evidence, and profile migration under [docs/migration-policy.md](docs/migration-policy.md). Neither a version number nor a successful mechanical run replaces the judgement record.
