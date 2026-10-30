# Verification

Verification requires mechanical checks and a recorded review of sense. Champollion does not translate or certify meaning. A clean report establishes only that the enabled checks found no detectable defect under the selected profile.

This document states the protocol requirements. Claims about existing Mouseia checks cite Mouseia file paths. Mouseia's linter does not already implement every gate below: ordered numbering, source hashes, and review records must not be presented as existing linter behavior.

## VER-1 Two halves

**Mechanical and judgement, kept separate.** Run the mechanical gates against the stored original and every applicable register. Then perform VER-10 and record it under VER-11. Never describe a length ratio, marker match, or populated provenance field as a sense check.

The gates are offline. They use local documents, profiles, tables, and snapshots; checking never depends on a provider answering a network request. A check run must not modify a work document.

### Mechanical gates at a glance

Thresholds below are the Mouseia parameters where language-specific. Other profiles declare their own parameters and applicability. A disabled or inapplicable check supplies no evidence of a pass.

| Gate | Finding code | Parameter or failure threshold |
|---|---|---|
| Required registers | `REG-1` | Any absent `required: true` register |
| Structure | `SEG-PARITY` | With `structure: true`, any duplicate section or mismatch under the declared alignment policy |
| Coverage and endpoints | `SEG-COVERAGE` | With `coverage: true`, any missing or empty aligned target unit, missing boundary-marker evidence, or omitted deliberate blank |
| Short-unit outlier | `VER-SHORT-UNIT` | `short_unit_ratio: 0.5`; source length ≥ `min_source_chars: 1500`; ≥ `min_units_for_ratio: 3` eligible units; target/source ratio strictly below 0.5 × median |
| Ordered numbering and line alignment | `SEG-NUMBERING` | With `numbering: true`, any mismatch in ordered source/target marker sequences or required one-to-one lines |
| Independence screening | `REG-PLAIN-COPY` | `copy_ratio: 0.35`; ≥ `min_sentences: 8` Plain strings of ≥ `min_sentence_chars: 40`; exact-match fraction strictly above 0.35 |
| Scan debris and raw markup | `VER-DEBRIS` | With `debris: true`, any configured debris-pattern match |
| OCR markers | `VER-OCR-MARKER` | With `debris: true`, any case-insensitive `[OCR unclear` match |
| Doubled words | `VER-DOUBLED-WORD` | With `debris: true`, any adjacent identical-word match outside the reviewed allow-list |
| Ellipsis form | `VER-ELLIPSIS` | `ellipsis: warn`; each configured malformed-ellipsis match is a warning |
| Common and Plain-only archaisms | `REG-ARCHAISM` | `archaisms: en-modern`, `plain_archaisms: true`; any applicable listed-form match |
| House spelling | `REG-SPELLING` | `spelling_profile: en-US`; any recognized non-house spelling |
| House names | `REG-NAME-VARIANT` | `name_table: names.json`; any recognized variant in the work's table |
| Speech-mark balance | `VER-SPEECH-MARKS` | `speech_marks: [musean, plain]`; any invalid opening/closing transition or unclosed speech within an applicable unit |
| Immutable pin | `SRC-NO-PIN` | Any missing immutable revision evidence or snapshot sha256 |
| Rights | `SRC-RIGHTS` | Unknown or disallowed rights; Mouseia's allowed set is `public-domain`, `cc-by-4.0`, `cc-by-sa-4.0` |
| Provider registry | `SRC-7` | Any missing provider registry entry or required provider record |
| Snapshot presence and integrity | `SRC-8`, `SRC-HASH-MISMATCH` | Missing or unverifiable snapshot; any difference from its recorded sha256 |
| Provenance completeness | `PRV-INCOMPLETE` | Any missing PRV-1 field or required edition credit/note |
| Review record | `VER-11` | Any missing reviewer, date, protocol version, findings, or resolutions record |
| Exception debt | `VER-12` | Any overdue exception; tolerated findings remain visible warnings until expiry |

### Reading the report

Text findings have the form `ERROR <work> [<unit>] <code>: <message>` or `WARN …`, followed by a summary. Read the code as the defect class, the work and unit as its scope, and the message as the evidence to inspect. Not every finding has a unit. A recorded, unexpired exception renders its finding as `WARN` with `[exception]`; it remains debt, not a clean result.

Use `check` or its alias `lint` for checks, `report` for the project report, and `--json` for machine-readable reporting. Exit `0` means no error-severity finding—warnings may remain. Exit `1` means at least one error-severity finding. Exit `2` means a usage, configuration, schema, or IO error; it is not a successful check. Malformed front matter is a named schema error, `SEG-FRONT-MATTER`, never an empty result or silent default.

## VER-2 Structure gate

**Mechanical.** With `checks.structure: true`, require the declared sections and alignment. `REG-1` identifies an absent required register. `SEG-PARITY` identifies duplicate sections, missing or extra units, changed unit titles, or changed unit order under `same-units`. Case-insensitive, trimmed register section labels do not make unit-title changes acceptable.

Apply each edition's policy: `same-units` compares titles and order; `by-position` uses declared positional alignment rather than requiring identical titles; `none` makes no unit-alignment claim. Historical editions retain their own divisions under SEG-7.

Mouseia's `seed/build.mjs`, `requireCompleteEdition()`, requires nonempty house editions and compares their ordered `###` headings with the original. This catches changed headings, not untranslated content behind matching headings. Read `SEG-PARITY` as a structural difference to repair, never as a diagnosis of sense.

## VER-3 Coverage gate

**Mechanical screening, followed by judgement.** With `checks.coverage: true`, every aligned source unit needs a nonempty target unit and observable beginning and ending evidence. Where ordered boundary markers exist, preserve the first and last markers; where they do not, nonempty endpoints establish presence only. Report missing evidence as `SEG-COVERAGE`. Preserve each deliberate source blank as `——`; an absent blank is also coverage loss. Matching blank counts alone cannot establish correct placement.

For the length screen, retain aligned units with at least `min_source_chars: 1500` characters of source text. Compute each target register's character-count/source-character-count ratio, sort the eligible ratios, and select the element at index `len(ratios) // 2` as the median—the upper middle value for an even count. Require at least `min_units_for_ratio: 3` eligible units. Flag a ratio strictly below `short_unit_ratio: 0.5` times that median as `VER-SHORT-UNIT`. Equality does not fail.

These are the actual Mouseia constants and median procedure; its linter forms aligned original/Musean/Plain triples and strips HTML comments from unit text before measuring (Mouseia: `scripts/lint_corpus.py`, short-unit loop and `load()`). The report gives the observed ratio and work median. Inspect the source span and endpoints; a legitimately compact rendering can be an outlier, while uniformly incomplete registers can avoid this screen. Profiles must not silently transplant English length expectations into another target language.

The Lucretius audit found 561 Latin lines in units 6–8 but English for only about 197; lines 552–920 were untranslated. Matching headings did not reveal this. Mouseia identifies the short-unit screen as the check that would have caught the loss (Mouseia: `docs/translation-guidelines.md` §§1, 7). Determining which lines were missing and whether a title described the passage still requires source comparison.

## VER-4 Numbering gate

**Mechanical.** With `checks.numbering: true`, compare source and aligned target marker sequences in order, including endpoints. Require exact identity, multiplicity, and order. Do not reduce this to equal counts or invent consecutive integers across a source's legitimate gaps. One-to-one line works additionally require one target line per source line, in order. Emit `SEG-NUMBERING` for a missing, extra, duplicated, reordered, or overrun marker, or a violated line contract. Read the report at the first divergence and inspect the surrounding passage.

Amenemope's audited English had 196 numbered lines against a 185-line source, ran up to two columns ahead of the papyrus, and ended with passages absent from it (Mouseia: `docs/translation-guidelines.md` §1). Marker and line comparison would catch the 196-for-185 mismatch. It would not establish whether text attached to otherwise correct markers translates the right line. The inspected `scripts/lint_corpus.py` has no ordered-numbering gate; this is a protocol requirement, not a claim about that script.

## VER-5 Independence gate

**Mechanical screening.** For Mouseia, split text after `.`, `!`, `?`, `;`, or `:` followed by whitespace, and at newlines. Trim each string and discard strings shorter than `min_sentence_chars: 40`. Make a set of qualifying Musean strings; retain the qualifying Plain strings as a list, including repeats. If fewer than `min_sentences: 8` Plain strings remain, the comparison is inapplicable. Otherwise divide the number of Plain strings present exactly in the Musean set by the Plain count. Fail strictly above `copy_ratio: 0.35` as `REG-PLAIN-COPY`.

Matching is literal and case-sensitive, not semantic similarity (Mouseia: `scripts/lint_corpus.py`, `sentences()` and copy-ratio loop). Read the reported numerator, denominator, and percentage, then inspect the matching strings. Passing does not prove independent work. The recorded 53–77% copying in Iliad 4, 5, 8, 13 and Odyssey 11 concerns lines, not the gate's sentence measure (Mouseia: `docs/translation-guidelines.md` §3). See REG-3 for the production rule that the screen supports.

## VER-6 Hygiene gates

**Mechanical screening.** `checks.debris: true` selects the configured debris, OCR-marker, and doubled-word checks. `checks.ellipsis` selects ellipsis severity. Mouseia scans Musean and Plain lines, skipping lines whose left-trimmed text starts with an HTML comment (Mouseia: `scripts/lint_corpus.py`). Its exact predicates are:

- `VER-OCR-MARKER`: a case-insensitive match for `[OCR unclear`.
- `VER-DEBRIS`: after removing paired strong spans and footnote tokens, and treating pipe-prefixed lines as tables, flags a caret, vertical bar, guillemet, brace, tilde, or backslash; `**` or `__`; or an entity of the form `&lt;`, `&gt;`, `&amp;`, `&nbsp;`, `&quot;`, or `&#` followed by decimal digits and `;`. This legacy screen does not check debris inside removed strong spans or validate table syntax; the strict checker applies its configured pattern to the raw line.
- `VER-DOUBLED-WORD`: the case-sensitive pattern `\b([A-Za-z][a-z]+)\s+\1\b`, unless the captured word, lowercased, belongs to the reviewed allow-list.
- `VER-ELLIPSIS`: the strict checker flags two or more adjacent periods and requires `…`. The Mouseia compatibility lane preserves its original two-period predicate and warning severity; it deliberately does not add a new failure to an established build.

The doubled-word allow-list in Mouseia's `scripts/lint_corpus.py`, `DOUBLED_OK`, is: `cao`, `yan`, `had`, `that`, `very`, `far`, `so`, `on`, `o`, `ah`, `woe`, `come`, `go`, `again`, `by`, `out`, `more`, `round`, `ever`, `two`, `one`, `deep`, `do`, `yes`, `no`, `is`, `long`, `little`, `many`, `fast`, `slowly`, `away`, `well`, `in`, `cry`, `imitate`, `happens`, `ambition`, `it`, `hope`, `all`, `up`, `down`, `back`, `high`, `now`, `here`, `there`, `soon`, `blessed`, `holy`, `kill`, `strike`, `burn`, `hear`, `listen`, `look`, `see`, `alas`, `oh`, `ha`, `hush`, and `quick`. It is an English screening parameter, not permission to add repetition absent from the source.

Read hygiene findings by line and matched text. Check against the stored witness before deleting anything: a detected character may belong to the source, while unlisted OCR misspellings may evade the gate. The gate does not detect all markup, running heads, page numbers, or production notes.

Tenney Frank's *Economic History* carried about 60 raw OCR fragments in both English editions. A second scan of the same 1920 printing restored all prose passages (Mouseia: `docs/translation-guidelines.md` §6; `corpus/SOURCES.md`, `economic-history-rome` row). A fragment containing a configured debris character or raw OCR marker would be caught automatically. Plausible-looking garbled words may not be. Choosing the restored reading and checking the repair against that witness are judgement under SEG-8; the witness must be recorded.

## VER-7 Language gates

**Mechanical screening, language-specific.** Mouseia's `archaisms: en-modern` uses case-insensitive whole-word/phrase matches. Its common list is: *thee, thou, thy, thine, thyself, hast, hath, dost, doth, shalt, wouldst, couldst, shouldst, canst, mayest, art thou, 'tis, 'twas, whence, whither, hither, thither, wherefore, wherein, whereof, verily, forsooth, perchance, mayhap, methinks, unto, yonder, betwixt, whosoever, whomsoever, ere, nay, is wont, was wont, were wont, haply, must needs, straightway, forthwith, well-nigh,* and *sore afraid*.

With `plain_archaisms: true`, Plain additionally screens *slay, slays, slew, slain, smite, smote, bade, behold, beheld, lo, oft, hitherto, henceforth, albeit, naught, aught,* and *thence*. The common list emits `REG-ARCHAISM`; the additional Plain list emits `REG-PLAIN-ARCHAISM`. These are Mouseia's implemented `ARCHAIC_ALL` and `ARCHAIC_PLAIN` lists, not its entire editorial prohibition (Mouseia: `scripts/lint_corpus.py`; `docs/translation-guidelines.md` §§2–3). Quotation of an archaic source requires contextual review; the scanner does not recognize that exception.

`spelling_profile: en-US` emits `REG-SPELLING` when a configured non-house form is recognized. Mouseia's exact recognized forms and exclusions are the `STEMS`, `WORDS`, `ISE`, and `STEM_SKIP` tables and substitution predicates in `scripts/americanize.py`; `scripts/lint_corpus.py` reports when the resulting count exceeds zero. This includes word-start stem matches with retained suffixes, whole-word replacements, and listed *-ise* forms. Inspect the matches and register, not just the count. Originals and historical editions are outside house spelling normalization.

`name_table: names.json` emits `REG-NAME-VARIANT` for any recognized variant in the work's table. Mouseia uses case-sensitive, escaped whole-word matching against the keys for that slug (Mouseia: `scripts/normalize_names.py`; `scripts/names.json`; `scripts/lint_corpus.py`). A missing work table is not evidence that all names are correct. Review genuine source alternatives rather than collapsing Alexandros and Paris into one name. None of these scanners tests sense or all possible spelling errors.

## VER-8 Speech-mark gate

**Mechanical screening.** Apply `checks.speech_marks` only to registers declared to mark direct speech. Mouseia's current implementation additionally limits the check to slugs `iliad` and `odyssey`. Broadening that scope is an explicit profile/adoption change, not parity with the old linter (Mouseia: `scripts/lint_corpus.py`, `SPEECH_MARK_WORKS`).

For its straight-double-quote scanner, an opening quote is at column zero or follows a space, `(`, or em dash. Other straight double quotes are treated as closing. Track state within each unit. Report `VER-SPEECH-MARKS` for a new opening while a speech remains open, a closing with none open, or an open speech at unit end. The report points to the problematic line and, where relevant, the earlier opening line.

An entirely unmarked speech produces no balance failure. Curly quotation marks are not scanned by this predicate. The editorial rule still requires marked direct speech in every unit (Mouseia: `docs/translation-guidelines.md` §5). Read-aloud review must inspect what the scanner cannot.

## VER-9 Rights, pin, and provenance gate

**Mechanical completeness and integrity, not legal or historical certification.** Require the source records specified under SRC-2, SRC-4, SRC-7, SRC-8, and PRV-1. Check stored records and files, not live provider pages.

- `SRC-NO-PIN`: require immutable revision evidence and the raw snapshot's sha256. A bare URL or URN is insufficient.
- `SRC-RIGHTS`: require separate underlying-work and transcription rights, with recorded attribution and share-alike obligations where applicable. Unknown rights refuse the source. Compare each applicable license with `rights.allowed`; Mouseia's declared allowed set is `public-domain`, `cc-by-4.0`, and `cc-by-sa-4.0`.
- `SRC-7`: require the work's provider entry and its scope, originals/translations offered, access method, license, and fetch recipe.
- `SRC-8`: require a present, verifiable local raw snapshot. `SRC-HASH-MISMATCH` means its computed sha256 differs from the recorded digest; do not replace the digest merely to silence the finding.
- `PRV-INCOMPLETE`: require the complete [front-matter schema](provenance.md), including register-specific translator credits and edition notes. Malformed scalar front matter is a schema error, not an incomplete-field default.

Read the code as a missing record, disallowed value, or integrity failure. Trace it to the source entry or named field. A recorded compatible license can still be wrong; a populated note can still conceal machine assistance. Assess those claims in review. Mouseia's `seed/build.mjs` checks completeness, whole-work scope, a raw path, and file existence; it does not compute snapshot hashes or enforce all these provenance and rights requirements.

## VER-10 Judgement

**Judgement.** Review the actual source and each target register, not only the report:

1. Read at least one complete unit aloud per register. Check whether the literary register carries the source's form and cadence, and whether the plain register reads naturally without reducing content.
2. For every unit, read its first source line or section against its first target line or section, and its last source line or section against its last target line or section, in every register. Confirm that the boundaries translate the correct source span, not just that boundary markers exist.
3. Spot-check names, numbers, dates, figures, and technical terms against the original. Inspect false friends and context-dependent terms. Ask whether the text preserves each claim, image, qualification, and argument step.
4. Inspect witnessed repairs and provenance claims, including comprehension aids and machine assistance. Resolve doubtful sense by source reading, not by a low copy ratio or a normal length ratio.

This procedure follows Mouseia's `docs/translation-guidelines.md` §7. A person or reviewing model can perform it; either must name uncertainties and record findings. Sampling and endpoints are review evidence, not proof that every interior line is faithful.

## VER-11 Review record

**Mechanical record completeness; judgement in its contents.** Record the reviewer, date, protocol version, findings, and resolutions for every review. Identify a person or model accurately. Record which units were read aloud, endpoint coverage, spot-check scope, and any unresolved questions so another reviewer can understand what was examined.

Record a clean review explicitly rather than leaving findings absent. A resolution names the correction or the reason for a recorded exception; it is not merely “reviewed.” `VER-11` indicates missing review evidence. Champollion can check record presence and required fields; it cannot verify that a reviewer performed the reading or that a resolution is sound.

## VER-12 Exceptions

**Mechanical debt tracking and judgement about toleration.** Record each tolerated finding with `code`, `work`, applicable `unit`, `owner`, `reason`, `recorded` date, and `expires` date in the profile's `exceptions`. Give it an accountable owner and a bounded expiry. Do not remove a rule or conceal a finding to obtain a clean report.

A matching unexpired exception changes the finding to `WARN` with `[exception]`. The report still exposes the defect and its debt. An overdue exception is a blocking `VER-12` finding. The owner must resolve the defect or obtain a reasoned, dated review of any renewal before publication. Toleration cannot make an unknown license compatible or establish missing sense.

Mouseia's older baseline format records slugs, check names, and unit headings or `*`; it demotes matching findings to warnings but supplies no owner or expiry (Mouseia: `scripts/lint_corpus.py`, `report()`, and `scripts/lint-baseline.json`). That baseline is not already a VER-12 exception record. Migration and activation must preserve existing gate behavior while making the debt explicit.

## VER-13 Publication gate

**Mechanical blocking status and recorded judgement.** Do not publish while an error-severity finding or overdue exception remains. Do not publish after a failed check invocation, an incomplete review record, or unresolved blocking review findings. Run the selected profile against the assembled work and inspect warnings and exception debt before release.

Exit `0` alone is insufficient: it permits warnings and says nothing about unperformed judgement. Resolve blocking defects, record the review and resolutions, and keep tolerated debt visible. Passing these requirements establishes a documented process and mechanical evidence—not certification of sense or retroactive approval of an existing edition.
