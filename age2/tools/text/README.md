# AGE2 portable translation export

`export_portable_translation.py` converts a private, reviewed AGE2 dialogue
table that still contains official Japanese text into a public translation
table. It replaces each full `jp_text` field with an exact source hash while
retaining the resource identity, limited speaker/scene context, Chinese text
and optional review metadata needed for a later local join.

This is a publication/redaction exporter. It does **not** extract EGPACKs,
write localized EGPACKs, prove alignment with a historical Release, or build a
player patch.

## Accepted source schema

The header must be exactly one of these two ordered schemas:

```text
call_order,id,egpack,scene,speaker_jp,jp_text,cn_text
```

```text
call_order,id,egpack,scene,speaker_jp,jp_text,cn_text,review_status,audit_flags
```

Unknown, missing, duplicated or reordered columns are rejected. Every row must
be a well-formed CSV record with a non-empty `egpack` and `id`; the pair
`(egpack, id)` must be unique. An ordinary row requires both non-empty
`jp_text` and `cn_text`. A fully empty engine bookkeeping slot is accepted only
when `jp_text`, `speaker_jp` and `cn_text` are all empty.

The public header replaces `jp_text` with two fields:

```text
source_text_sha256,record_kind
```

`record_kind` is `text` for an ordinary translated record or
`structural_empty` for that strict empty-slot exception. The source hash is
still SHA-256 of the exact empty byte sequence for the latter. Builders verify
the local source slot, then skip this explicit no-op; they never turn it into
an empty replacement operation.

The retained `speaker_jp` field is deliberately limited source context, not a
copy of the complete official dialogue. Review its publication status together
with the rest of the table before release.

## Export

Run the exporter only against a private source-bearing table derived from a
legally installed game:

```powershell
python age2/tools/text/export_portable_translation.py `
  "X:\private\tda00-source-bearing.csv" `
  --output "X:\work\tda00.portable.csv" `
  --report "X:\work\tda00.portable.json"
```

Input, output and report must be distinct paths. Existing output or report
targets are refused by default. Each completed file is fsynced under a
same-directory temporary name and published through a create-only atomic link;
if an ordinary error occurs while publishing a later sibling, the exporter
removes earlier newly created outputs. This is not a crash-atomic multi-file
transaction. Choose new paths and compare the result before deliberately
replacing a maintained snapshot.

The optional JSON report binds the exact source and output file bytes with
byte counts and SHA-256 values, records the row count and exported columns, and
states that full official dialogue was removed. It does not include the full
Japanese dialogue or an absolute workstation path. Keep a reviewed report next
to every published snapshot; older checked-in reports may reflect the fields
emitted by the exporter version used at that time.

## Hash contract

For every parsed row:

```text
source_text_sha256 = UPPERCASE_HEX(SHA256(UTF8(exact parsed jp_text)))
```

The exporter does not normalize Unicode, punctuation, control sequences or
embedded line endings inside `jp_text`. A later local join must hash the exact
text field by the same rule and stop on any mismatch.

## From a legal game to a writer input

1. Export the relevant local EGPACK records with
   [`extract_egpack_manifest.py`](../egpack/README.md).
2. Export the reviewed source-bearing table with this command and review the
   public CSV plus JSON sidecar.
3. On the builder's machine, use
   [`build_changes.py`](../egpack/README.md) to join the public table back to
   the exact locally extracted source by identity and hash.
4. Treat the resulting changes table as a separate, engine-specific writer
   input and apply the EGPACK verification gates.

The private source-bearing table is not committed. The portable table alone
cannot reconstruct official Japanese text, and success here is not an
end-to-end release proof.

Unresolved symbol and quotation findings use the separate
[text-free review ledger](../../evidence/text-review-ledger-v1/README.md). Its
generator binds private audit rows back to these public identities/hashes and
publishes no source or translated line text.

## Test

```powershell
python -m unittest age2.tests.text.test_export_portable_translation -v
python -m unittest age2.tests.text.test_build_review_ledger -v
```
