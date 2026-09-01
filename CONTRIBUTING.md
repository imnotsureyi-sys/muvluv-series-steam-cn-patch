# Contributing

Contributions for Simplified Chinese or another locale are welcome. The project accepts durable source, reproducible tools, tests, documentation, and evidence-backed corrections; it does not accept extracted game dumps or unexplained generated output.

## Choose the correct boundary

1. Human translation, terminology, review, and image-authoring policy belongs in `localization/`.
2. FPD, EGPACK, AGE2 WebP/loose-overlay work belongs in `age2/`.
3. RIO, ICI, RUO, CRsa, CRip/Cr6Ti, Photon runtime and packaging work belongs in `rugp/`.
4. A game-specific translation, manifest, or release note belongs under that engine's `games/<game>/` directory.

AGE2 must not import rUGP code and rUGP must not import AGE2 code. Cross-engine code proposed at the repository root will be rejected unless it is truly engine-neutral human-workflow tooling.

## Locale and source-data rules

- Use BCP 47-style locale names in filenames and directories, for example `zh-Hans`, `ko`, or `ru`.
- Preserve stable resource IDs, source hashes, control-code contracts, and row identity.
- Translate from the authoritative source-language slot. Do not silently fall back to English, an old fan translation, OCR, or fuzzy matching.
- Record a review status separately from the translated text.
- Never commit credentials, API keys, workstation paths, or private source archives.

See [`localization/standards/`](localization/standards/) for detailed table and review rules.

## Copyright and clean-room boundary

Do not submit complete game archives, executables, official fonts, audio/video, or bulk extracted images. A format fixture must be synthetic or independently constructed and small enough to demonstrate only the structure being tested. Where original bytes cannot be published, commit hashes, stable locators, dimensions, and a reproducible extraction recipe instead.

Localized or derived images require the policy in [`docs/asset-and-release-policy.md`](docs/asset-and-release-policy.md). A code license does not license those images.

## Tool quality bar

A public tool must:

- accept inputs and outputs through a documented CLI rather than hard-coded local paths;
- fail closed on unsupported layouts, versions, hashes, or ambiguous matches;
- avoid overwriting an input or existing output by default;
- verify its own output and expose useful errors;
- have a synthetic test or a documented reason why one is impossible;
- run from a clean clone with declared dependencies.

One-off probes and rejected experiments should be distilled into a postmortem or regression test, not promoted as supported tools.

## Local checks

Install Python 3.12 and the pinned dependencies:

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s age2/tests -p "test_*.py" -v
python -m unittest discover -s rugp/tests -p "test_*.py" -v
python -m unittest discover -s localization/tests -p "test_*.py" -v
python -m unittest discover -s .github/scripts/tests -p "test_*.py" -v
python -m compileall -q age2 rugp localization .github/scripts
python .github/scripts/verify_repository.py
```

Native Photon runtime changes also require Zig 0.16.0 and both pinned PF/PM builds described in [`rugp/runtime/README.md`](rugp/runtime/README.md).

## Pull requests

Explain the affected game, engine, resource identity, before/after behavior, test evidence, and whether any new redistribution rights are required. Keep generated releases outside the commit. A correction to translation text should include enough Japanese context and scene identity for another reviewer to reproduce the decision.
