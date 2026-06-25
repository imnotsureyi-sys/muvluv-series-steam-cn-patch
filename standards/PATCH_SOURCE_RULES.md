# Patch Source Rules

## Source Tables

Current TDA00-03 source tables live in `patch-sources/`.

Each source table should preserve:

- stable row order
- game text id
- source package/container
- scene locator
- Japanese speaker field
- Japanese source text
- current Chinese text
- review/audit metadata

## Editing Rules

- Edit only the intended chapter table.
- Keep row count and stable locators aligned.
- Preserve control codes, ruby/display markers, and line-break markers.
- Do not remove a line only because the JP text looks empty; confirm the actual
  display slot first.

## Required QA After Edits

After edits, check at minimum:

- Text ID Not Found
- empty `cn_text`
- row/order mismatch
- abnormal duplicate text
- mojibake/encoding damage
- English sentence residue
- Japanese/kana residue where it should not remain
- control-code damage
- speaker/name/rank consistency

Release packages should be distributed through GitHub Releases, not committed
as zip files.
