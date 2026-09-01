# AGE2 portable translation snapshots

These reports bind the five public Simplified-Chinese translation tables to
the exact private source-bearing snapshots from which they were exported.
The Git tables retain resource identity, limited Japanese speaker/scene
context, a SHA-256 of each Japanese dialogue field, the localized text and
review metadata, but do not mirror the complete official dialogue script.

Use `age2/tools/egpack/extract_egpack_manifest.py` on a legally installed game,
then `age2/tools/egpack/build_changes.py` to join the public translation to the
exact local source text. A source hash mismatch stops the build.

The five JSON files are provenance records from their respective exports. See
the current [portable-export contract](../../tools/text/README.md) before
preparing a new public snapshot. They are not statements that the current
tables are byte-for-byte identical to every historical player Release. A
second audit found meaningful differences between these snapshots, older
chapter branches and post-release correction branches. Release alignment must
be resolved per stable ID against the downloaded Release payload before any
table is labelled a final release authority; see
[`authority-alignment-audit.md`](authority-alignment-audit.md).
