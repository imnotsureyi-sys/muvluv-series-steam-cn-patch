# Engine-neutral localization workflow

This directory contains work that remains valid regardless of whether the target is AGE2 or legacy rUGP. It must not contain archive parsers, hook code, game binaries, or engine-specific package builders.

## Workflow

1. **Freeze source authority.** Identify the exact game build, source-language slot, resource ID/path, and source hash.
2. **Export a stable table.** Keep identity and control-code fields separate from editable translation text.
3. **Translate from the source.** Glossary and scene context may assist; English, OCR, old patches, or machine output must not silently replace the Japanese authority.
4. **Review in layers.** Linguistic review, terminology review, structural validation, layout/image review, then in-game review.
5. **Build through the engine path.** Use either `age2/` or `rugp/`; never improvise a cross-engine packer.
6. **Publish a manifest-bound package.** State supported input hashes, output hashes, source commit, font licenses, and known limitations.

## Contents

- [`glossaries/`](glossaries/): shared Muv-Luv terminology.
- [`standards/translation.md`](standards/translation.md): translation principles.
- [`standards/terminology.md`](standards/terminology.md): terminology change process.
- [`standards/source-data.md`](standards/source-data.md): stable source-table rules.
- [`standards/review.md`](standards/review.md): review and feedback rules.
- [`image-workflow.md`](image-workflow.md): textless-background, deterministic typography, AI-edit and image QA workflow.
- [`tools/images/`](tools/images/): deterministic textless-background and localized-text builders, plus single-image and grouped-image consistency checks.
- [`tools/font_coverage.py`](tools/font_coverage.py): a cmap glyph-coverage gate; it does not prove runtime font selection, metrics, wrapping, or clipping.
- [`tools/verify_steam_depot_manifest.py`](tools/verify_steam_depot_manifest.py): read-only content matching for selected local files against a clear-name Steam depot manifest; it does not authenticate Steam signatures or contact Steam.
- [`new-locale.md`](new-locale.md): engine choice, locale identity, source boundary, build manifests and release gates for a new target language.
- [`tools/create_locale_template.py`](tools/create_locale_template.py): fail-closed CSV/TSV exporter that removes the existing translation and creates a blank, manifest-bound work table for another locale.

## Dependencies and tests

Run commands from the repository root with Python 3.12. For only the
engine-neutral workflow, install its pinned dependencies and run its complete
synthetic test suite:

```powershell
python -m pip install -r localization/requirements.txt
python -m unittest discover -s localization/tests -p "test_*.py" -v
python -m compileall -q localization
```

Before a pull request, install the repository-wide pinned set and run the full
quality gate documented in [`CONTRIBUTING.md`](../CONTRIBUTING.md):

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s age2/tests -p "test_*.py" -v
python -m unittest discover -s rugp/tests -p "test_*.py" -v
python -m unittest discover -s localization/tests -p "test_*.py" -v
python -m unittest discover -s .github/scripts/tests -p "test_*.py" -v
python -m compileall -q age2 rugp localization .github/scripts
python .github/scripts/verify_repository.py
```

These tests use copyright-safe fixtures. Passing them does not validate a
particular installed game build, a font license, a final package or in-game
layout.

## Starting another locale

Use a BCP 47-style identifier such as `ko`, `ru`, or `zh-Hans`. Create a new locale column/file without replacing the source text or the existing locale. A new language may reuse verified format code, but it needs independent translation authority, font coverage, layout QA, runtime/package manifest, and player testing. Follow the [new-language guide](new-locale.md); it also records the current AGE2 and rUGP end-to-end gaps.

Do not begin by copying Chinese into a Russian, Korean, or other target column.
Use the template exporter to retain explicitly selected stable IDs, source hashes
and non-prose context while replacing the existing localized-text column with
blank `target_text` cells. The generated sidecar labels the result as a working
template, not an AGE2/rUGP writer input. Official Japanese must still be
reconstructed from a legally obtained game and verified against the retained
source hash.
