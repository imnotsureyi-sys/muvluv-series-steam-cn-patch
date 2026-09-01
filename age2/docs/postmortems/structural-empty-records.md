# Structural empty EGPACK records

## Symptom

A completeness audit found five published AGE2 rows with empty source and
localized text: four in TDA02 and one in TDA03. Treating every empty target as
an untranslated line made the tables look incomplete; deleting the rows would
change the frozen resource sequence.

## Controlled comparison

The private source-bearing tables and fresh local EGPACK manifests agreed that
all five identities were fully empty engine slots: `jp_text`, `speaker_jp` and
`cn_text` were empty, and the exact source hash was SHA-256 of the empty UTF-8
byte sequence. TDA00, TDA01 and Imperial Capital Burns had no such rows.

## Correction

The portable schema now has an explicit `record_kind`:

- `text` requires non-empty local source and localized text;
- `structural_empty` requires the exact empty-source hash and empty local slot,
  then becomes a verified no-op rather than a write.

The exporter, local-source join, frozen counts and regression tests all enforce
this distinction. `--allow-empty` cannot turn a malformed current row into a
legal structural record.

## Production rule

Completeness means preserving and classifying every stable resource identity,
not forcing visible text into bookkeeping slots. Empty, absent, control-only
and intentionally cleared values are different states and must never be
collapsed into one CSV convention.
