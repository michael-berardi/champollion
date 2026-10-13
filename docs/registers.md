# Registers

A register is a declared, independently produced target text with its own purpose and constraints. A work carries at least two independent registers made from the same original. A profile names them and their alignment policies; it does not translate the text. Champollion checks declared structure and detectable defects. It cannot certify sense, beauty, or independence of composition from the final wording alone.

## REG-1 Every work carries the required registers

**Mechanical.** Include every register marked `required: true` in the profile. A historical or reference edition does not replace a required house register. Each declaration supplies an `id`, `label`, `required` flag, `alignment`, and accepted `sections` labels. Section matching is case-insensitive and trimmed; `same-units` requires the original's unit titles in the original's order.

Mouseia requires Musean and Plain English. Its existing section labels are `Mouseia translation` or `Curated translation`, and `Plain English translation` or `Plain translation` (Mouseia: `docs/translation-guidelines.md` §1; `seed/build.mjs`). See [verification](verification.md#ver-2-structure-gate) for the structure gate.

## REG-2 Each register is made directly from the original

**Judgement, with mechanically checked disclosure.** Produce each target text from the original-language source, never from another translation. A disclosed gloss or third-language rendering may help comprehension; it must not become the text being translated. Record aids under PRV-3 and credits and edition notes under PRV-1 and PRV-2. Checking that these records exist cannot establish that the declared process occurred.

The same rule applies when source and target share a language: Mouseia's American Founding editions independently render authoritative historical English into contemporary English (Mouseia: `corpus/SOURCES.md`, “American Founding policy”).

## REG-3 Registers are independent

**Judgement and mechanical screening.** No register may be an edit of another. Give collaborators separate register tasks without the other register's output for that unit; see [working with AI workers](ai-workers.md), WRK-2. Do not begin with Musean and replace “wrath” with “anger” or “slay” with “kill.” That preserves the first rendering's decisions and errors instead of making a second direct translation.

Independence is a rule because a real audit found that 53–77% of Plain lines in Iliad 4, 5, 8, 13 and Odyssey 11 were copied from Musean (Mouseia: `docs/translation-guidelines.md` §3). The audit measured lines; the gate measures qualifying sentence strings. These are different measures.

Mouseia's copy gate fails above 35% exact matches among Plain sentence strings, considering only strings of at least 40 characters and units with at least eight such Plain strings (Mouseia: `scripts/lint_corpus.py`, `sentences()` and the copy-ratio loop). Shared short declarations, names, and formulae need not be rewritten merely to look different. A low ratio does not prove independence; synonym substitution can evade it. See VER-5.

## REG-4 Register definitions

**Judgement.** Apply the declared purpose throughout the whole work. Mouseia defines the two house registers as follows (Mouseia: `docs/translation-guidelines.md` §§2–3; `corpus/SOURCES.md`, “Rules”):

- **Musean:** fidelity to the original joined to modern clarity, beauty, symbolism, and the source's structure. Use natural syntax; preserve ambiguity, imagery, rhetoric, parallelism, and cadence where the target language can carry them. Elevated language must remain living language.
- **Plain English:** everyday contemporary English. Use short sentences, ordinary word order, and common verbs. Render an idiom or epithet in plain words where appropriate, but keep its meaning and the names. Natural contractions are allowed if used consistently. Avoid stock poetic phrasing, ALL-CAPS emphasis, and unexplained scholarly abbreviations.

Two registers serve different reading purposes without reducing the source. Plain is simpler, never shorter in content: every claim, name, number, image, and argument step remains. Neither register is a summary, commentary, or explanation added to the original.

## REG-5 Sense, not word order

**Judgement.** Translate concepts in context, not cognates or source syntax. For each doubtful term, ask what action, claim, or relationship the passage expresses, then check whether the target says the same thing naturally. Preserve technical distinctions across the work.

Mouseia's Cicero examples make the test concrete (Mouseia: `docs/translation-guidelines.md` §2):

| Source expression | Sense in the cited context | Defect to reject |
|---|---|---|
| *vanitas* | Falsehood in a trade context | “Vanity” from the cognate alone |
| *in aerariis relinquere* | To strike from the tribal rolls, degrading someone to the lowest civic class | “Leave in the treasuries” |
| *officium* | Duty | A cognate or vague substitute that loses the ethical concept |

Do not turn these contextual readings into universal word replacements. The same guidelines reject “Care must be taken lest we use slownesses in walking softer” in favor of “We must take care not to walk with a slow, mincing gait.” A checker can find malformed text; it cannot decide this question of sense.

## REG-6 Poetry is kept

**Judgement, supported by alignment checks.** Preserve source line breaks, stanzas, parallelism, meaningful repetition, and formulae. Plain may express a formula in ordinary words; it may not discard its content or the source's form. Render each epithet once rather than duplicating its meaning through a calque.

The recorded defects are “wind-swift swift Iris” for ποδήνεμος ὠκέα Ἶρις and “to counsel counsel” for βουλὰς βουλεύειν (Mouseia: `docs/translation-guidelines.md` §2). Neither is an adjacent identical-word pair, so the doubled-word gate does not detect either. Ordered line and marker checks can reveal missing divisions, not certify poetry or cadence.

## REG-7 Modern English

**Judgement and profile-specific mechanical screening.** House English registers use modern English. Archaic forms may survive only inside a quotation of a source that is itself archaic, not as the translator's ordinary voice. Plain also forbids the profile's literary archaisms.

Mouseia's editorial list includes *thee*, *thou*, *thy*, *hath*, *doth*, *wherefore*, *whilst*, *amongst*, and archaic verb endings. Its implemented scanner uses separate common and Plain-only lists; the latter includes *slay*, *smite*, *behold*, and *oft* (Mouseia: `docs/translation-guidelines.md` §§2–3; `scripts/lint_corpus.py`, `ARCHAIC_ALL` and `ARCHAIC_PLAIN`). The scanner is not a complete grammar test and cannot recognize a justified quotation. Review a match in context; record any tolerated finding under VER-12. `archaisms: en-modern` and `plain_archaisms: true` select the Mouseia English screening rules, not a language-neutral requirement for Spanish or other targets.

## REG-8 One spelling per name per work

**Mechanical screening and judgement.** Use the work's house spelling for each name in every house register. The profile's `name_table` supplies spellings and variants. Do not alternate Achilles and Akhilleus merely because tasks chose different transliterations.

Where the source itself uses two names for one person, preserve both—Alexandros and Paris are not a normalization error. Mouseia recorded mixed Hektor/Hector, Aias/Ajax, and Telemachos/Telemachus across books; its table is `scripts/names.json`, used by `scripts/normalize_names.py` and the linter (Mouseia: `docs/translation-guidelines.md` §2; `scripts/lint_corpus.py`). A table match does not establish identity or detect every unknown name. Spot-check against the original.

## REG-9 Mechanics

**Judgement and mechanical screening.** Use an unspaced em dash for breaks, an en dash for ranges, and the single ellipsis character `…`. Mark direct speech with double quotation marks in every unit. Remove unintended doubled words. Match the source's numbers, dates, and figures exactly. Preserve intentional source repetition and deliberate blanks `——`.

Mouseia's punctuation rules and speech-mark audit are recorded in `docs/translation-guidelines.md` §§5–6. Its linter detects selected ellipsis forms, adjacent doubled words outside an allow-list, and unbalanced straight double quotes in Iliad and Odyssey; it does not enforce every dash, detect every unmarked speech, or compare the meanings of numeric expressions (Mouseia: `scripts/lint_corpus.py`). Ordered reference markers are a separate check under VER-4. Read punctuation and figures against the source rather than treating clean lint as approval.

## REG-10 Spelling profile per edition

**Mechanical screening and judgement.** House registers follow the declared locale and `spelling_profile`. Originals and historical editions retain their own spelling. Mouseia's house profile is `en-US`: *armor*, *honor*, *color*, *center*, *defense*, and *judgment*, among its prescribed forms (Mouseia: `docs/translation-guidelines.md` §5; `scripts/lint_corpus.py`, calls to `americanize()`). Do not apply house spelling replacements to the original or a transcribed historical edition.

A spelling profile defines the forms it can check; a clean result is not a complete spelling review. Language-specific tables belong in profiles and their associated data, not in the core protocol.

## REG-11 Adding a register

**Mechanical declaration and judgement.** Declare the new register in the profile and write its own purpose and constraints. Specify its stable ID, display label, required status, accepted section labels, and alignment policy. A newly produced register must satisfy REG-2 and REG-3 and receive the same applicable structure, coverage, numbering, hygiene, provenance, and review gates. Declare language-specific screening explicitly rather than inheriting English word lists.

The worked `latin-to-spanish` profile uses Latin (`la`) as source, Spanish (`es`) as target, registers `literaria` and `clara`, and spelling profile `es`. Define `literaria` as a complete literary rendering that preserves imagery and source form; define `clara` as a complete rendering in ordinary contemporary Spanish with direct syntax. Both are independent translations from Latin, not Spanish edits of one another. Keep their original-aligned units under `same-units`; use the profile's accepted section labels in the work.

See [the worked profile](../profiles/latin-to-spanish.json) and [example](../examples/latin-to-spanish/). Its register definitions serve the same two reading purposes without requiring Musean's English vocabulary or Mouseia's English copy threshold. Adding a label alone does not supply a definition, independence, or a recorded sense review.
