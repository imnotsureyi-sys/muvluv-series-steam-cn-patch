# The Imperial Capital Burns / 帝都燃烧篇

- Player release: [beta0.1](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/imperial-capital-burns-beta0.1)
- Steam application used for the frozen baseline: `2630300`
- Container: FPD v2 `obb/pack.bin`
- Patch route: loose overlay; the original `pack.bin`, executable, and saves are not modified

## Maintained source

- [`translations/main.ja-zh-Hans.csv`](translations/main.ja-zh-Hans.csv): 5,564 portable dialogue rows (source hashes plus localized text; no bulk official script).
- [`translations/speakers.ja-zh-Hans.csv`](translations/speakers.ja-zh-Hans.csv), [`choices.ja-zh-Hans.csv`](translations/choices.ja-zh-Hans.csv), and [`ui-strings.ja-zh-Hans.tsv`](translations/ui-strings.ja-zh-Hans.tsv): speaker, choice and system-UI authority.
- [`translations/terminology.ja-zh-Hans.csv`](translations/terminology.ja-zh-Hans.csv): game terminology.
- [`images/copy/`](images/copy/): copy/layout manifests for boot notices, common UI, character names, telops, and date/location cards. Telop and event-card prose is represented by exact source hashes rather than republished Japanese lines. [`source-image-lock.v2.json`](images/copy/source-image-lock.v2.json) pins all 128 copied English UI inputs **and their Japanese overlay targets** to the frozen `pack.bin` baseline by SHA-256.
- [`evidence/initial-inventory.md`](evidence/initial-inventory.md): original format inventory and implementation boundary.
- [`releases/beta0.1.md`](releases/beta0.1.md): release-specific scope and install notes.

The translation was based on Japanese text/voice rather than an English or fuzzy fallback. The release covers dialogue, speakers, choices, system UI, image text, 37 character-name cards, 74 called telops, 61 date/location cards, and the configured Chinese font path.

## Build boundary

[`tools/build_phase1.py`](tools/build_phase1.py) is the game-specific **non-story
phase** loose-overlay builder. It handles UI strings, images, fonts, telops and
event cards, but it deliberately does not consume the 5,564-row dialogue table
or build the story/speaker EGPACK payload. It expects legally extracted source
resources and hash-locked redistributable fonts outside the repository, writes
a new staging tree, generates a payload manifest, and emits a hash-gated
installer plus manifest-aware uninstaller. It never rewrites the source FPD.
Both copy manifests must exactly match the public source-image lock; a missing,
extra, renamed, or byte-changed `_en.webp` input stops the build before that
asset is copied. The lock file itself is recorded in `payload-manifest.json`.

`--font-license` is mandatory and must point to the non-empty UTF-8 license
text supplied with the Source Han Sans SC font files. The builder copies it
byte-for-byte to
`payload/root/assets/data/gui/font/SourceHanSansSC-LICENSE.txt`; the file is
hashed in `payload-manifest.json`. Manifest generation refuses any payload
that contains either packaged Source Han Sans font without this license text.

The shared EGPACK manifest, `build_changes.py`, repacker and verifier are the
intended components for a future dialogue/speaker/choice phase, but their
current public support claim and layout regressions cover TDA00–03 only. The
Imperial EGPACK layout must be independently frozen and tested before those
components are called supported here. The public repository also lacks the
final per-game orchestration step that combines both phases into a
byte-identical reconstruction of historical beta0.1.

The non-story phase itself is invoked from the repository root as follows.
Every `X:\input\...` path is caller-supplied and must come from the exact legal
baseline or a separately redistributable dependency; none is downloaded by the
builder:

```powershell
python AGE2/games/imperial-capital-burns/tools/build_phase1.py `
  --repo . `
  --gui-root "X:\input\imperial\root\assets\data\gui\textures" `
  --data-spec-gui-root "X:\input\imperial\root\assets\data_spec\gui\textures" `
  --uistring-dec "X:\input\imperial\uistring.epk_dec" `
  --tda-font-root "X:\input\fonts\source-han-sans-sc" `
  --font-license "X:\input\fonts\SourceHanSansSC-LICENSE.txt" `
  --tda-boot-root "X:\input\approved-tda-boot-notices" `
  --fsnr-main "X:\tools\FSNr\main.exe" `
  --jp-script-root "X:\input\imperial\root\assets\data_spec\adv\game\scr" `
  --telop-reference-root "X:\input\imperial\root\assets\data_spec\adv\game\chr\00no_text_telop" `
  --location-date-card-root "X:\input\imperial\root\assets\data_spec\adv\game\bg\30イベント絵\010_TEイベント絵\050_帝都燃ゆ\140_テロップ" `
  --output "X:\build\imperial-phase1"
```

`--gui-root` and `--data-spec-gui-root` are the two extracted texture roots;
`--uistring-dec` is the already decrypted UI-string file; `--tda-font-root`
contains the two hash-locked font binaries; `--tda-boot-root` contains the two
approved Chinese notices named by `boot-notice.tsv`; `--jp-script-root` is the
Japanese script tree with its `localized/` child; the final two roots supply
the official layout references used for telop and event-card geometry. FSNr is
an external encryptor dependency and must be acquired and reviewed separately.
The output path must not exist.

The Release package—not this source directory—is the installable patch. New work must pass the shared AGE2 tests plus the Imperial manifest/image tests before publication.
