# AGE2 localization path

[中文概要](#中文概要) · [Tools](tools/) · [Games](games/) · [Evidence](evidence/translation-snapshots-v1/) · [Postmortems](docs/postmortems/) · [Tests](tests/)

This tree covers the newer AGE2 ports used by THE DAY AFTER and The Imperial Capital Burns. It is technically independent from `rugp/`.

## Mental model

```text
pack.bin (FPD v2 container)
  └─ root/assets/...
       ├─ localized/*.egpack     multilingual text fields
       ├─ gui/**/*.webp          directly viewable image resources
       ├─ uistring.epk           separate encrypted UI-string format
       └─ fonts/config/XML/etc.

localized files with the same root-relative paths
  └─ per-user AGE2 data cache (loose overlay, loaded ahead of pack.bin)
```

FPD and EGPACK are different layers. Extracting `pack.bin` reveals the inner file tree; parsing an `.egpack` then reveals its language fields. The current player patches leave Steam's `pack.bin` untouched and install only selected loose replacements into the game's per-user AGE2 data directory.

## Supported public work

| Game | Maintained translation snapshot | Current player release |
| --- | --- | --- |
| TDA00 | [`games/tda00/`](games/tda00/) | beta0.1 |
| TDA01 | [`games/tda01/`](games/tda01/) | beta0.2.2 |
| TDA02 | [`games/tda02/`](games/tda02/) | beta0.1 |
| TDA03 | [`games/tda03/`](games/tda03/) | beta0.1.6 |
| The Imperial Capital Burns | [`games/imperial-capital-burns/`](games/imperial-capital-burns/) | beta0.1 |

The tables are maintained translation snapshots, not a claim that the five historical Release ZIPs can already be rebuilt byte for byte. Their cross-branch and shipped-payload differences remain an explicit [authority-alignment audit](evidence/translation-snapshots-v1/authority-alignment-audit.md).

## Tools

- [`tools/fpd/`](tools/fpd/): strict FPD index reader and filtered extractor; key schedule comes from FatePackageManager's `Scrambler.cs`.
- [`tools/egpack/`](tools/egpack/): field-aware EGPACK export, exact-slot replacement, and byte-level verification for the supported TDA00–03 layouts.
- [`tools/text/`](tools/text/): fail-closed export of a private, source-bearing AGE2 review table to a public hash-bound translation table; it is not an EGPACK writer.
- [`tools/uistring/`](tools/uistring/): scoped string replacement in an already decrypted UI data file; it does not implement FSNr EPK encryption/decryption.
- [`tools/font/`](tools/font/): explains the removed lossy glyph-substitution workaround and points to the real engine-neutral font-coverage gate.
- [`evidence/text-review-ledger-v1/`](evidence/text-review-ledger-v1/README.md): a 246-identity, text-free queue for unresolved TDA00–03 symbol and quotation review; categories require human context and are not automatic edits.

See the [workflow](docs/workflow.md), [architecture](docs/architecture.md), [quality gates](docs/quality.md), and [provenance policy](docs/provenance.md).

## Test

```powershell
python -m pip install -r age2/requirements.txt
python -m unittest discover -s age2/tests -p "test_*.py" -v
```

That is sufficient for the AGE2 unit suite alone. The complete documented
workflow also calls engine-neutral localization tools such as font coverage;
install the root lock for that path:

```powershell
python -m pip install -r requirements-dev.txt
```

All committed tests use synthetic data; an installed game is not required.

## 中文概要

AGE2 的 `pack.bin` 是外层 FPD 容器，里面才是 EGPACK、WebP、字体配置等实际资源。补丁不重封原始 `pack.bin`，而是保持其中的 `root/...` 相对路径，把少量改好的文件放进游戏会优先读取的用户数据目录。`age2/` 只负责这条静态覆盖路线，不包含 rUGP 的 RIO、RUO 或 Hook。
