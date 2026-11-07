# Summaries

A summary is an opt-in study guide to a complete work, with a machine index for
agents. Generate it only after both editions pass their checks, review it against
the edition, and regenerate it when the basis changes. Mechanical checks cannot
establish completeness or correctness of interpretation.

Place a JSON sidecar at `summaries/<work-id>.json`; the id is the front matter
slug or filename stem. `champollion summary schema` prints the structured-output
schema for the generated `summary` and `index` fields. The operator stamps the
remaining fields: `schema` is `champollion-summary/1`; `work`, `title` and
`author` identify the work; `basis` contains `register`, `sha256` and `units`;
`aid` is a free-text disclosure; `generated` is an ISO date; `review` has status
`unreviewed` or `reviewed` (with `by`, `date` and `notes`).

The `summary` has a short `gist`, complete `overview`, authorial `context`,
optional-string `key_facts`, and `key_ideas` with ids, explanations and unit
references. `units` supplies each numbered unit's exact label, summary and idea
ids. `figures` and `terms` identify their roles or meanings and units; `passages`
quote and explain located excerpts. The `index` contains genres, forms, themes,
concepts, people, places, period, keywords and related corpus works with typed
relations and notes. Slug arrays use lowercase kebab-case. The schema specifies
array bounds; the validator also enforces word limits and cross-references.

`champollion summary units work.md --json` gives the labels, character counts and
basis hash. The hash covers the section body with HTML comments removed, CRLF
normalised to LF and outer whitespace stripped. Headings divide units; leading
body is a separate unlabelled unit, as is a whole section without headings.
`champollion summary check --root . --require --json` checks schema, identity,
freshness, unit alignment, limits, references, quotations and related links;
unreviewed summaries warn. Use `--dir` to choose the sidecar directory and
`--works-glob 'corpus/*.md'` to choose corpus works. Checks never alter files.
