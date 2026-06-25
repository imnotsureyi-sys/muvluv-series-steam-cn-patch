# Translation Rules

## Source Priority

1. Use Japanese source text as the translation basis.
2. Use Japanese speaker/source metadata to resolve voice, rank, name, and role.
3. Use the shared JP-CN glossary for confirmed terminology.
4. Use surrounding JP context when a line is ambiguous.

English slots are not translation source material.

## Forbidden Fallbacks

- Do not translate from English slots.
- Do not restore English fallback text.
- Do not use old Chinese fallback text.
- Do not use fuzzy matching to silently assign a line to a different source.

## Terminology

- Confirmed terms should be added to `glossary/muvluv_jp_cn_terms.csv`.
- Chapter-specific discoveries should be reviewed before becoming global terms.
- Do not rewrite another chapter's body text just to force terminology
  consistency; make a clear issue for that chapter instead.

## Feedback Handling

Player feedback should include a screenshot, chapter, scene/context, and the
visible Chinese line when possible.

For each feedback item, locate:

- chapter
- CSV row
- id
- egpack
- scene
- speaker_jp
- jp_text
- current cn_text

Only then decide whether a Chinese line should be changed.
