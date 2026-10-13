# Sourcing a text

Store a complete, pinned original before translation begins. Preserve the provider export and record how it becomes the reading text. Champollion checks records and bytes; choosing an edition, establishing rights and reading it correctly require recorded judgment. It does not translate or certify sense.

## Choose and register a provider

**SRC-7—mechanical completeness; judgment of suitability.** Register a provider once with its scope, whether it offers originals or translations, access method, license and fetch recipe. Each source record must point to that entry. A provider's reputation does not establish the rights or completeness of a particular export.

Mouseia's `corpus/SOURCES.md` is the worked registry pattern. Its provider table distinguishes Sanskrit Wikisource originals, Internet Archive scans and ORAEC's Egyptian originals with German sentence renderings. Its per-text log connects works to providers and witnesses. Copy the pattern, not its language-specific acquisition priorities. Labels such as “academic,” “educational” or “free for use” in a registry are not an explicit compatible license; resolve them for the chosen text before accepting it.

## Pin the edition

**SRC-2—mechanical evidence and hash completeness; judgment of edition identity.** Record immutable revision evidence and the raw snapshot's SHA-256. A URL or catalog identifier alone is insufficient. These Mouseia records illustrate the three pin patterns:

| Pattern | Recorded example | What to preserve |
|---|---|---|
| Wiki revision | Isha Upanishad, Sanskrit Wikisource `oldid=37761` (`corpus/SOURCES.md`, per-text log) | The revision export, not just the current reading-page URL. For transcluded works, pin every contributing page. |
| Repository commit | ORAEC Egyptian exports at commit `b83a0ee` (`corpus/SOURCES.md`, Egyptian expansion records) | The export path and resolved full commit SHA, plus the raw-file hash. Mouseia records an abbreviated commit; resolve it before making a new pin. |
| Catalog identifier plus content hash | Gallic War, CTS edition `urn:cts:latinLit:phi0448.phi001.perseus-lat2`, with `source_xml_sha256` of `d1a330891be6983f8f00fe07c6a857873355cc4c0cc22fe1a33ceaeb9d2e1079` (`corpus/raw/roman-complete/manifest.json`) | The identified edition and the hashed provider XML. This Mouseia record also supplies a repository commit. The hash is not the hash of the cleaned Latin. |

A catalog number names an object; its paired hash fixes the captured content. A CTS URN without that evidence remains a locator, not a pin. If an export is a container, hash the stored container bytes and record the revisions of its members.

## Store the export and derive the reading text

**SRC-1—mechanical snapshot presence; judgment of canonical source.** Commit the complete original-language provider export unmodified under `sources/raw/`. Keep the provider's XML, JSON, wikitext or scan export, including material the reading edition will omit. Put the derived reading text in `## Original` of `works/<slug>.md`; readers and checks use stored text, not a live provider request.

**SRC-6—mechanical recipe completeness; judgment of cleaning decisions and reproducibility.** Record the cleaning script and its inputs, or a precise transformation rule. Include ordering, markup removal, variant choices, correction decisions and witness repairs. Retain source numbering and meaningful divisions. Keep raw and clean files separate; never overwrite the export with the cleaned result.

Mouseia's Ali Baba record identifies stored page wikitext, `corpus/raw/ali-baba/clean.py`, revision evidence and correction decisions. It distinguishes accepted misprint corrections from changes to Galland's historic present (`corpus/SOURCES.md`, Ali Baba record). This is the level of detail needed to reproduce editorial cleaning, not merely a note saying “markup removed.”

## Accept only a complete work

**SRC-3—mechanical declarations; judgment of scope and survival.** Accept the whole named work or complete independently issued document. Do not present selected chapters, an opening, an abridgment or a sample as a work. If only part survives, include all surviving text and state the condition in provenance. `completeness: complete` then means complete surviving text, not an undamaged ancient original.

Mouseia records the lost opening of Man and His Ba and the broken ending of Journey of Wenamun while specifying the complete surviving papyri (`corpus/SOURCES.md`, per-text log). A checker can inspect declarations and coverage markers; it cannot establish that every surviving witness has been found.

## Resolve both layers of rights

**SRC-4—mechanical rights gate; judgment of the rights basis.** Record the underlying work's rights separately from the transcription's rights. Accept only public domain or an explicitly compatible license allowed by the profile. Unknown rights refuse the source.

- A public-domain work needs a recorded basis and jurisdiction. Public-domain status does not impose CC attribution or share-alike, but PRV-5 still requires source credit.
- A CC BY-SA transcription of that work still carries its own license. Record the transcriber or provider attribution, source and license links, required notices, changes and applicable share-alike obligations. Distribute adaptations of that transcription under the required compatible license. Do not erase these obligations by labeling the ancient work public domain.

Mouseia's Sanskrit and Chinese Wikisource entries make this distinction explicit; the ORAEC transcription and German aids are recorded as CC BY-SA 4.0 (`corpus/SOURCES.md`). Assess the rights of aids separately too. A configured allowance for `cc-by-sa-4.0` checks a declaration, not legal compliance or the license of every resulting edition.

## Translate from the original; disclose aids

**SRC-5—judgment, with mechanically checked disclosure under PRV-3.** Translate each edition from the original-language text. A scholarly gloss or third-language rendering may help comprehension; it must not become the text being translated. Do not modernize another translation or derive one house register from another.

Mouseia's Middle Egyptian method uses TLA transliteration, lemma glosses and the TLA editors' German sentence renderings through ORAEC. The German renderings are disclosed comprehension aids under CC BY-SA 4.0. Mouseia records that a first pass without the German aid was discarded after review found errors of sense (`corpus/SOURCES.md`, Egyptian expansion record). The lesson is to disclose useful assistance and review sense—not to hide the aid or treat its rendering as the primary source.

Record which aid, whose work it is, its license and how it was consulted in the source record; summarize its use in the affected edition note. Neither the presence of an aid nor passing checks proves that translation was direct.

## Verify the snapshot

**SRC-8—mechanical integrity; judgment of what the snapshot represents.** Hash the exact stored bytes. A missing or unverifiable snapshot leaves the entry incomplete; a mismatch is refused as `SRC-HASH-MISMATCH`. Pin omissions are reported as `SRC-NO-PIN`; incompatible or unknown rights as `SRC-RIGHTS`. Checks operate locally without a network request.

A new provider revision is a new acquisition: retain the old record, capture the new export and review the resulting changes. Never replace a recorded hash merely to silence a mismatch. Mouseia's `seed/build.mjs` checks that `raw_snapshot` exists; that existence check must not be described as SHA-256 verification.

## Worked example: add a pinned Latin source

These commands add a source record, not a translated or publishable work. They use Mouseia's stored, unmodified Gallic War XML and the commit recorded in `corpus/raw/roman-complete/manifest.json`; no acquisition request is needed.

1. From the directory containing sibling `mouseia` and `champollion` checkouts, scaffold a new project:

   ```sh
   champollion init gallic-war-project
   ```

2. Register `perseus` in the project's source registry with the Greek/Latin scope, originals and translations, raw repository XML access, CC BY-SA 4.0 transcription license, and commit-pinned fetch recipe. Record the underlying 1914 edition's public-domain basis separately. Use Mouseia's provider 5 and the work-specific rights record as evidence, not the provider label alone.
3. Verify the input bytes against the recorded raw XML hash:

   ```sh
   python3 -c 'from pathlib import Path; import hashlib; p=Path("mouseia/corpus/raw/roman-complete/provider-raw/phi0448.phi001.perseus-lat2.xml"); h=hashlib.sha256(p.read_bytes()).hexdigest(); print(h); raise SystemExit(0 if h == "d1a330891be6983f8f00fe07c6a857873355cc4c0cc22fe1a33ceaeb9d2e1079" else 1)'
   ```

4. If the hash matches, add the export:

   ```sh
   champollion source add --id gallic-war --file mouseia/corpus/raw/roman-complete/provider-raw/phi0448.phi001.perseus-lat2.xml --provider perseus --edition "Rice Holmes, Clarendon, 1914; phi0448.phi001.perseus-lat2" --revision ea33cbdb10131fd319522426a70df0070d5b0b68 --rights cc-by-sa-4.0 --note "Underlying 1914 edition public domain in the United States; Perseus transcription CC BY-SA 4.0. Preserve attribution and share-alike obligations." --root gallic-war-project
   ```

5. Complete the source record with the pinned provider URL, license link and attribution, whole-work evidence, and a reproducible XML-to-reading-text transformation before creating `## Original`. Source acquisition does not run a language model, certify rights or supply either translation register.
