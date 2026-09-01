# Complete localization workflow: first translation to player feedback

[中文](workflow.md) · [Localization workspace](README.md) ·
[Start a new language](new-locale.md) · [Asset map](../docs/en/asset-map.md) ·
[Image workflow](image-workflow.md)

This is the process developed while working on the TDA, The Imperial Capital
Burns, and Photon texts. Its core is not “ask an AI to translate a whole
spreadsheet.” Story comprehension, terminology, first translation, independent
review, engine binding, in-game QA, and player feedback are separate stages with
different evidence.

```text
lawful extraction and stable source identity
        ↓
read the story; establish relationships and terminology
        ↓
first translation by complete scene
        ↓
independent review: keep / revise / question
        ↓
resolve questions; re-freeze terminology and cross-scene consistency
        ↓
AGE2 or rUGP binding, writeback, and automated validation
        ↓
full-route in-game QA
        ↓
test release and reproducible player reports
        ↓
return findings to maintained text/terminology/source and release again
```

Passing one stage never substitutes for the next. Fluent target text does not
prove the Japanese was understood; static decoding does not prove runtime
acceptance; a game launch does not prove complete text, image, and font coverage.

## 0. Freeze lawful inputs and stable identities

1. Extract source data from a game copy you lawfully own.
2. Record the game/build, Steam App ID, resource path, object identity or offset,
   and SHA-256 of every relevant source.
3. Do not use an absolute workstation path or a mutable spreadsheet row number
   as the only identity.
4. A public table may retain the exact source-field hash without mirroring the
   complete official script. Other contributors re-extract locally and join by
   stable identity plus hash.
5. Keep AGE2 and rUGP extraction, writer, and runtime paths independent.

Output: source manifest, stable IDs, hashes, scene order, and a list of still
unidentified structural questions.

## 1. Understand the story and establish terminology first

Do not start with randomly sampled rows. Before bulk translation:

- read the current route/scene in order and enough surrounding material;
- record character relationships, status differences, forms of address,
  speech habits, and current emotion;
- inventory names, organizations, ranks, machines, weapons, operations,
  locations, and recurring jokes;
- merge already established series terminology;
- put a new term into a candidate list instead of inventing a different answer
  every time it appears;
- mark uncertain story, speaker, address, or term decisions as `question`.

The glossary is a story-understanding tool established before the first pass,
not merely a cleanup table produced after translation.

Output: scene summary, relationship/address notes, frozen terminology baseline,
and unresolved questions.

## 2. First translation: produce candidates

Translate complete scenes or natural story blocks in stable resource order.
Every maintained row should retain the equivalent of:

| Field | Purpose |
| --- | --- |
| `id` / `stable_id` | Identity that survives sorting and export |
| `resource_file` / `egpack` / `rio_file` | Route back to the game resource |
| `scene`, `speaker_jp` | Story and speaker context |
| `source_text_sha256` | Exact source field used for the decision |
| target text | First-pass candidate |
| status | `translated`, `question`, or `blocked` |

This pass aims for accurate source understanding and natural target-language
writing. It does not perform engine writeback. English slots, old translations,
OCR, and machine translation can reveal discrepancies but cannot replace the
Japanese source.

Output: candidate text, terminology additions, questions, batch range, and the
next stable starting point.

## 3. Second pass: independent review

The second pass is not target-language polishing. The reviewer rereads the
Japanese, context, and character relationships and assigns exactly one result:

- `keep`: retain the candidate;
- `revise`: supply corrected text and the material reason;
- `question`: evidence remains insufficient; state what is needed.

Use another reviewer, another agent conversation, or at least a genuinely
independent pass when possible. Never default an entire batch to `keep`, and do
not make preference-only rewrites without source support. `revise` and
`question` are review results, not first-pass statuses.

Output: row-level decisions, before/after text, reasons, unresolved questions,
and review statistics.

## 4. Resolve questions and re-freeze terminology

A `question` must not silently disappear before packaging. Consult as needed:

- later scenes and other occurrences of the same expression;
- Japanese voice, speaker, expression, and staging;
- screenshots and the actual resource call site;
- official setting material or established series usage;
- control codes, locale slots, and image context.

After resolution, update the text, shared glossary, game glossary, and every
repeated occurrence. Keep genuinely unresolved items blocked rather than
guessing from an English slot or from what merely sounds plausible.

## 5. Bind and write through the correct engine

Only semantically reviewed text enters the engine layer:

- **AGE2:** extract required FPD members from a lawful `pack.bin`; build exact
  EGPACK changes; handle UI, WebP, and fonts; publish as a LocalAppData loose
  overlay.
- **rUGP:** locate CRsa, Cr6Ti, CRip, and related objects through ICI/RIO;
  select a proven static RUO route or an exact-build guarded runtime; verify
  capacity, parents, endpoints, and constraints such as error 8311.

Record input hash, output hash, tool version, and the fields permitted to change.
Extraction does not imply repacking, and one passing record does not prove every
record carrying the same class label.

## 6. Automated quality gates

At minimum check:

- stable IDs, row counts, duplicates, and missing records;
- source hashes against the frozen build;
- control codes, encoding, capacity, offsets, and parent references;
- terminology consistency and retired translations;
- font coverage across every maintained target string;
- image dimensions, mode, alpha, hashes, and state/family layout;
- package members, destinations, and rollback information;
- absence of original containers, workstation paths, secrets, test images, and
  fonts without provenance.

Automated tests prove only their explicit assertions; they are not in-game
evidence.

## 7. In-game QA

Cover the title and settings screens, first dialogue, save/load, backlog, every
route and choice, speakers, achievements, fonts, each modified image family, and
rollback. Image QA must detect more than visibility: colour swaps, tearing,
alpha damage, wrong endpoints, English fallback, Japanese/translation route
differences, and shared/common behavior all matter.

Each finding should identify game/build, route/date/scene, surrounding dialogue,
screenshot, stable resource ID, and exact reproduction steps.

## 8. Close the player-feedback loop

A player report is a third layer of real-environment evidence, not permission to
replace one generated file in a Release manually.

1. Confirm the game, patch version, locale selection, and other installed mods.
2. Use the screenshot, scene, and surrounding dialogue to find the stable ID.
3. Return to Japanese source and terminology to distinguish translation,
   binding, font, image, installation, and game-version problems.
4. Fix maintained source or code—not only a generated EGPACK, RIO, or WebP.
5. Rerun relevant automated checks and routes.
6. Document the fix and produce a new reproducible Release.

## 9. What becomes public

Publish:

- stable translation tables, glossaries, and durable review states;
- image copy, lawful textless/localized authorities or manifests, hashes, and
  production method;
- font source, license, coverage report, and reproducible build method;
- codecs, package tools, tests, incident reports, and reproducible commands.

Do not publish by default:

- original game containers or complete official resources;
- transient prompts, chat logs, failed batches, and personal notes;
- workstation paths, credentials, or fonts without explainable provenance;
- intermediate output that cannot reproduce or explain the final result.

Record an image-generation/edit request only when it materially affects a
reproducible visual result. Ordinary text translation does not require every
prompt; rules, maintained data state, and verification tools are more useful.

## 10. Apply the method to Korean, Russian, or another locale

Reuse the stages and identities, not Chinese prose conventions:

1. Re-extract lawful source and join it by the published hashes.
2. Create separate `ko`, `ru`, or other target files; never overwrite Japanese
   evidence or `zh-Hans` output.
3. Establish locale-specific terminology, address, punctuation, typography,
   line breaking, and font policy.
4. Complete both passes, question resolution, engine binding, in-game QA, and
   the player-feedback loop.

Continue with the [new-locale guide](new-locale.md) and the
[asset map](../docs/en/asset-map.md).
