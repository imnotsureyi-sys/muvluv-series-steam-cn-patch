# 参与贡献

[返回首页](../../README.md) · [贡献者与致谢](CONTRIBUTORS.md) · [完整本地化工作流](../../localization/workflow.md) · [资产地图](../research/asset-map.md)

> English contributors can use the concise summaries in each major README and
> open an Issue or Pull Request in English. The Chinese rules below are the
> current project authority.

Contributions for Simplified Chinese or another locale are welcome. The project accepts durable source, reproducible tools, tests, documentation, and evidence-backed corrections; it does not accept extracted game dumps or unexplained generated output.

## Choose the correct boundary

1. Human translation, terminology, review, and image-authoring policy belongs in `localization/`.
2. FPD, EGPACK, AGE2 WebP/loose-overlay work belongs in `AGE2/`.
3. RIO, ICI, RUO, CRsa, CRip/Cr6Ti, Photon runtime and packaging work belongs in `rUGP/`.
4. A game-specific translation, manifest, or release note belongs under that engine's `games/<game>/` directory.

AGE2 must not import rUGP code and rUGP must not import AGE2 code. Cross-engine code proposed at the repository root will be rejected unless it is truly engine-neutral human-workflow tooling.

完整官方文本、原始图片和游戏容器不进入 `localization/` 或其他公开目录。具体游戏的
译文、图片文案、资源身份和源哈希跟随该游戏；跨引擎的方法、共用术语和通用 QA 工具
才进入 `localization/`。详见[资产地图](../research/asset-map.md)。

## Locale and source-data rules

- Use BCP 47-style locale names in filenames and directories, for example `zh-Hans`, `ko`, or `ru`.
- Preserve stable resource IDs, source hashes, control-code contracts, and row identity.
- Translate from the authoritative source-language slot. Do not silently fall back to English, an old fan translation, OCR, or fuzzy matching.
- Record a review status separately from the translated text.
- Never commit credentials, API keys, workstation paths, or private source archives.

See [`localization/standards/`](../../localization/standards/) for detailed table and review rules.

## Copyright and clean-room boundary

Do not submit complete game archives, executables, official fonts, audio/video, or bulk extracted images. A format fixture must be synthetic or independently constructed and small enough to demonstrate only the structure being tested. Where original bytes cannot be published, commit hashes, stable locators, dimensions, and a reproducible extraction recipe instead.

Localized or derived images require the [asset and release policy](asset-and-release-policy.md). A code license does not license those images.

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
python -m unittest discover -s AGE2/tests -p "test_*.py" -v
python -m unittest discover -s rUGP/tests -p "test_*.py" -v
python -m unittest discover -s localization/tests -p "test_*.py" -v
python -m unittest discover -s .github/scripts/tests -p "test_*.py" -v
python -m compileall -q AGE2 rUGP localization .github/scripts
python .github/scripts/verify_repository.py
```

Native Photon runtime changes also require Zig 0.16.0 and both pinned PF/PM builds described in [`rUGP/runtime/README.md`](../../rUGP/runtime/README.md).

## Pull requests

Explain the affected game, engine, resource identity, before/after behavior, test evidence, and whether any new redistribution rights are required. Keep generated releases outside the commit. A correction to translation text should include enough Japanese context and scene identity for another reviewer to reproduce the decision.
