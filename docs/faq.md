# Frequently asked questions

## Why two registers?

They offer two ways to read the same complete source: a source-shaped literary rendering and an everyday rendering, not a translation and its summary. Each is made independently from the original (REG-2–REG-4; judgment, with an applicable mechanical copy heuristic). Mouseia calls them Musean and Plain English in `docs/translation-guidelines.md` §2–§3; other profiles define their own registers.

## Is this machine translation?

No. Champollion specifies a method and checks local text and evidence. It produces no translation and cannot certify sense. Verification combines mechanical gates with recorded judgment (VER-1).

## Can an AI produce a register?

Yes. Give it the original, one unit, one register, and the numbering contract; do not show it the other register's output. Record the system's contribution, assistance, and attestation, then review the text (WRK-1–WRK-6, PRV-2; mechanical task/record checks, judgment of originality and sense). A model review must identify the model; it is not a mechanical proof.

## How is this different from a wiki?

Champollion defines work documents, pinned source evidence, profiles, gates, and review records. It does not define a collaborative website or edit history. A wiki can adopt it, but page edits alone do not satisfy the evidence and publication requirements (VER-9, VER-11–VER-13; mechanical records and gate state, recorded judgment).

## What about existing translations of the same text?

Keep them as attributed historical or reference editions when their rights permit it. Preserve their own divisions and declare alignment; they do not count as the two new independent house registers. Do not derive a new house register from them (SRC-4–SRC-5, SEG-7, REG-2; mechanical rights/mapping evidence, judgment of rights and derivation).

## May I consult a dictionary or scholarly gloss?

Yes. Name the aid, its author, license, and how you used it. Reading an aid to understand the original is allowed; translating the aid instead of the original is not (SRC-5, PRV-3, PRV-5; mechanical disclosure completeness, judgment of actual use).

## How do you know a work is complete?

An editor establishes the selected edition's boundaries and compares every unit, including its endpoints. The checker verifies declarations, structural coverage, markers, and applicable length evidence; it cannot establish semantic completeness (SRC-3, SEG-3, VER-3; mechanical evidence, VER-10; judgment). Complete surviving text is allowed when lost material is disclosed; an excerpt presented as a complete work is not.

## What happens to difficult or damaged passages?

Translate difficult readable passages and record uncertainty. Repair damage from another witness of the same edition when available, with attribution; otherwise use `[illegible in the source]` once in place of the damaged stretch. Never skip a hard passage or invent missing content (SEG-8, SEG-10, WRK-4; judgment, with mechanical hygiene/disclosure checks).

## How do I cite Champollion?

Cite Michael Berardi, *Champollion protocol*, version 1.0.0, the repository URL, and the tag or commit used. [CITATION.cff](../CITATION.cff) provides citation metadata. Cite your source edition and actual translators separately. The specification is CC BY 4.0; citation metadata is not release approval or a translation-quality claim.

## Can I use it for modern texts and non-ancient languages?

Yes, when you have an admissible source and rights to use it. Choose source/target languages, at least two register definitions, and language policies in a profile. The core does not require English or an ancient language; English archaism rules are profile-specific (REG-11; mechanical declaration and gate coverage, judgment of definition and independence). It does not solve copyright or translate the text for you.

## What does it cost?

There is no Champollion license fee, hosted-service subscription, or required translation-model service. The code is MIT; the specification and docs are CC BY 4.0. Your translation, review, source acquisition, computing, and any chosen AI service are your own costs. Checking uses the Python standard library and local evidence.

## Who maintains it?

Michael Berardi maintains the protocol. Report reproducible defects in the [repository issue tracker](https://github.com/michael-berardi/champollion/issues); include the work, unit, code, text, and profile so a false positive can become a fixture. There is no guaranteed response time. Projects maintain their corpus, profiles, pinned snapshots, and judgment records; see [CONTRIBUTING.md](../CONTRIBUTING.md).
