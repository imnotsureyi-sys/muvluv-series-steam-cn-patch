# AGE2 workflow

This is the intended workflow for a version-gated build. The maintained TDA translation snapshots are not themselves the `changes.csv` consumed by the writer; the documented `build_changes.py` join below supplies that text-only bridge from a legal local export. No complete public per-game command yet maps every text/image/font input to the historical Release ZIP, and historical Release alignment is still under audit. Follow each game's README and treat the remaining builder/authority work as an explicit reproducibility gap.

From the repository root, install the pinned cross-workflow dependencies first:

```powershell
python -m pip install -r requirements-dev.txt
```

## 1. Inspect and extract

First freeze the executable and `obb/pack.bin` identities. When you have the
matching clear-name Steam depot manifest, use the engine-neutral
[`verify_steam_depot_manifest.py`](../../localization/tools/verify_steam_depot_manifest.py)
content check described in the [new-locale guide](../../localization/new-locale.md#3-freeze-the-legal-source-baseline).

Obtain `Scrambler.cs` from the immutable FatePackageManager revision recorded in [`THIRD_PARTY.md`](../../THIRD_PARTY.md), verify its recorded SHA-256, and use your legally installed game:

```powershell
python age2/tools/fpd/fpd_codec.py "X:\game\obb\pack.bin" `
  --scrambler "X:\tools\FatePackageManager\Scrambler.cs" `
  --contains "assets/data_spec/adv/game/src/localized" --limit 20

python age2/tools/fpd/extract_fpd.py "X:\game\obb\pack.bin" `
  --scrambler "X:\tools\FatePackageManager\Scrambler.cs" `
  --contains "assets/data_spec/adv/game/src/localized" `
  --output "X:\work\fpd-extract"
```

Use a new output directory. Never commit the extraction.

## 2. Export EGPACK fields

```powershell
python age2/tools/egpack/extract_egpack_manifest.py "X:\work\fpd-extract" `
  --output "X:\work\egpack-manifest.csv"
```

Select the authoritative source-language slot by field key, not by the nearest readable byte sequence.

## 3. Prepare exact changes

The EGPACK writer's change CSV is `relative_path,id,slot,expected_text,replacement_text`. `expected_text` is an optimistic lock; if the installed version differs, the build stops. Preserve the format's control sequences explicitly. Do not pass a game's maintained translation snapshot directly to the repacker; first bind it to the legal local manifest with the strict converter:

```powershell
python age2/tools/egpack/build_changes.py `
  age2/games/tda00/translations/ja-zh-Hans.csv `
  --manifest "X:\work\egpack-manifest.csv" `
  --slot jp `
  --output "X:\work\changes.csv"

python age2/tools/egpack/repack_egpack.py "X:\work\fpd-extract" `
  --changes "X:\work\changes.csv" --output-dir "X:\work\localized"

python age2/tools/egpack/verify_egpack.py "X:\work\fpd-extract" `
  "X:\work\localized" --changes "X:\work\changes.csv"
```

`build_changes.py` refuses to overwrite an existing output by default. Use a
new path for the first build, `--check` to compare an existing artifact, and
`--force` only for an intentional atomic rebuild; see the
[EGPACK tool contract](../tools/egpack/README.md).

## 4. Build the loose tree

Place only changed EGPACK/WebP/config/font files under their original `root/...` relative paths. Validate every input hash and final manifest. Do not modify or redistribute the source `pack.bin`.

Before shipping a font, verify its target-language cmap and then perform
layout/in-game checks:

```powershell
python -m localization.tools.font_coverage "X:\fonts\TargetFont.ttf" `
  age2/games/tda00/translations/ja-zh-Hans.csv --column cn_text `
  --output "X:\work\font-coverage.json"
```

The font license/notice must travel with any redistributed font binary.

## 5. Test and release

Test clean install, update over the exact prior release, rollback/Steam restore, title/settings/first dialogue, every changed image family, full-route text, font coverage, and achievements. Publish the generated payload through Releases, not Git.
