# Source-language review

`champollion review` prepares a review of every passage of every register against the
Original, in two independent readings, and applies only the corrections that survive
both readings. It is the tooling side of [VER-10 judgement](verification.md); the
reading itself is done by people or by external systems the operator chooses.
Champollion stays offline and provider-neutral: it writes packets to a directory and
reads reply files from a directory. It never calls a model and never uses the network.

A model-run review is a machine review. Record it as such under
[VER-11](verification.md), naming the reviewing system honestly, and never present it
as human editorial approval. The commands work for any profile's registers and any
language pair; nothing is specific to two registers or to English.

## What the review does

1. **Cut parallel passages.** Each unit of the Original and of every aligned register
   is cut into parallel passages of at most `--piece-chars` source characters
   (default 5000). Paragraph correspondence is tried first, then line correspondence;
   a register that matches neither is cut proportionally at its own paragraph
   boundaries, widened by one paragraph each side, and marked inexact in the packet.
2. **First reading.** One reviewer packet per passage shows the source passage and
   every register's passage, and asks for findings as JSON objects
   `{edition, type, severity, source, quote, fix, reason}`. `quote` must be an exact,
   contiguous quotation that occurs only once in the passage; `fix` is its
   replacement. Defects in the presentation of the Original itself are reported with
   edition `"original"`.
3. **Second reading.** Each locatable finding becomes a proposal in an independent
   second-reader packet. The second reader confirms, amends (with a better fix for the
   same quotation), or rejects each proposal. When in doubt, reject.
4. **Guarded application.** Only confirmed or amended findings are applied, by exact
   single-match replacement inside the reviewed passage. Source findings are recorded
   for the editor and never auto-applied. The Original section is never edited.
5. **Record.** A VER-11-shaped record names the reviewer, date, protocol version,
   work SHA-256, profile fingerprint, reviewed units and registers, every finding with
   its resolution, and the passages that were not reviewed.

## The workflow

```sh
# 1. Write reviewer packets and a binding index.json.
champollion review packets --work works/example.md --out review/packets --json

# 2. Run any reviewer on each <unit>-<piece>.review.md and store its reply as
#    <unit>-<piece>.review.json in the same directory (review/packets).

# 3. Validate the replies and write second-reader packets.
champollion review verify-packets --work works/example.md \
  --replies review/packets --out review/verify --json

# 4. Run an independent second reader on each <unit>-<piece>.verify.md and store
#    its reply as <unit>-<piece>.verify.json in review/verify.

# 5. Write the review record (bound to the reviewed work bytes; see below) and
#    reference it from the source record's reviews or the work's review_record
#    front-matter field.
champollion review record --work works/example.md --replies review/verify \
  --reviewer "name the person or system honestly" --out records/example-review.json --json

# 6. Apply the confirmed corrections (preview first with --dry-run).
champollion review apply --work works/example.md --replies review/verify --dry-run --json
champollion review apply --work works/example.md --replies review/verify --json
```

`record` and `apply` compute the same guarded result; `record` never writes the work.
Run `record` before `apply`: the record is bound to the reviewed work's SHA-256, and
once `apply` changes the work, VER-11 requires a fresh review of the changed bytes
(a `record` run afterwards reports the passages as changed since review).

Replies are read tolerantly: a `<<<BEGIN>>>` / `<<<END>>>` wrapper and code fences are
accepted around the JSON. Each stage's `index.json` binds its packets to the SHA-256
of the exact passages reviewed; `verify-packets` and `apply` read it from the replies
directory (or `--index`). Keep the packets, replies and indexes as review evidence.
Packets are deterministic: rerunning into the same directory is stable, and an
existing different file is refused rather than overwritten.

## What is applied, and what is refused

A confirmed replacement is written atomically, and only inside the reviewed register
passage. Application is refused, with a named reason in the output, when:

- the passage changed since review (its hash no longer matches the index);
- the quotation is not found, or is not unique, in the passage;
- the fix would change reference markers, line breaks, or headings;
- the fix is disproportionately longer or shorter than the quotation;
- the fix contains packet delimiters;
- the edit overlaps an earlier correction in the same run (the first wins);
- the second reader rejected the finding, or no valid second-reader reply exists.

Findings on the Original (`"original"`) are recorded with the resolution
"left for the editor" and never applied. Refused and source findings stay visible as
unresolved findings in the record, so the publication gate remains blocked until an
editor resolves them. Exit codes follow the toolkit convention: `0` success, `1`
invalid replies or refused corrections, `2` usage, configuration, schema or IO error.

## What the review is not

The two readings are judgement evidence, not certification. A clean apply run does
not prove that every remaining sentence is faithful, and an empty findings list is
not proof of a sound translation. Keep the mechanical `check` report, the review
record, and the editor's decisions together; publication still requires
[VER-13](verification.md).