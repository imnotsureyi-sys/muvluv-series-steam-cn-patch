# Player install, rollback and troubleshooting guide

[简体中文](../player/README.md) · [Player downloads](README.md#player-downloads) · [Report a bug](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=bug-report.yml)

## Before you install

The current player packages are historical AGE2 prerelease/test patches. They install loose files into a per-user LocalAppData directory and do not rewrite Steam's original `pack.bin`, executable or saves. Photon source and the 1,490-image Photon Release are **not** player installers.

These beta packages predate the repository's current release gate. They do not consistently include an install manifest, input-version hash check, uninstall tool or bundled font-license notice. An `install.bat` completing successfully proves that files were copied; it does not prove that an updated or repacked game is compatible.

Use only the current historical versions listed on the repository home page. Do not install the superseded `tda01-beta0.1`, `tda01-beta0.2`, `tda01-beta0.2.1`, or `tda03-beta0.1`: `tda01-beta0.2` introduced 603 invisible dialogue slots, while `tda03-beta0.1` carried TDA02's UI/achievement mapping.

The historical builds also did not freeze and re-verify the Steam/in-game language selection used for every title. Surviving test machines contain both Japanese and English settings, so no uniform requirement can be inferred. Do not overwrite another title or language slot just to “make the patch appear.” If the game still shows Japanese or English, report the Steam language plus `UserConfig.language` and `MountedConfig.language` from that title's appmanifest; this guide will not guess a value before per-title retesting.

## Install on Windows

1. Purchase and install the matching Steam game. Launch it once if its per-user directory has not been created, then close it completely.
2. Download the exact game's ZIP from the [player download table](README.md#player-downloads). Do not use GitHub's repository source ZIP.
3. When a checksum file is published, download it too and verify the ZIP before opening it.
4. Extract the entire ZIP to a short writable path. Do not run `install.bat` from inside a compressed-folder preview.
5. If you already have another patch or manually edited loose files, make a recoverable backup of that game's exact `data\root` directory first.
6. Read the package's `README.txt` for its installation layout, then run `install.bat` next to its `payload` directory. For rollback safety, this central guide overrides broad deletion advice in an old package README.
7. Restart the game completely. Returning to the title screen is not enough. Check the title/settings screen and first dialogue before continuing an old save.

### Exact Windows destinations

| Game | Loose-overlay destination |
| --- | --- |
| TDA00 | `%LOCALAPPDATA%\ancr\tda00\data\root` |
| TDA01 | `%LOCALAPPDATA%\ancr\tda01\data\root` |
| TDA02 | `%LOCALAPPDATA%\ancr\tda02\data\root` |
| TDA03 | `%LOCALAPPDATA%\ancr\tda03\data\root` |
| The Imperial Capital Burns | `%LOCALAPPDATA%\ancr\tm\data\root` |

Do not copy one game's `root` into another game's directory. TDA03 beta0.1.6 deliberately removes only its own `...\tda03\data\root` before copying the replacement, so back up any custom loose files there before running it.

TDA03 beta0.1.6 also carries a historical `0.1.6-fix-report.json` whose
`source_package` and `package_dir` metadata contain absolute paths from the
builder's workstation. Those strings are not read or executed by `install.bat`
and are not install destinations; this guide and the public release index
describe the issue without republishing the paths.

Steam Deck instructions, when present, are inside the release package. Use the exact title's Proton prefix; never copy a Windows LocalAppData path literally into an unrelated prefix.

## Verify a download

Four current packages publish a SHA-256 text file beside the ZIP. TDA03 beta0.1.6 has no separate checksum attachment; its GitHub-recorded ZIP digest is `4B6CA4A531E9D07315E84DC2E02D7D8008C9B78EA4466172B45CAD1CEBA5C67D`. On Windows PowerShell:

```powershell
Get-FileHash -Algorithm SHA256 "C:\Downloads\patch.zip"
```

Compare the complete hexadecimal value with the release's checksum file. A matching download hash detects transfer or mirror corruption; it does not prove game-version compatibility.

## Restore and rollback

The present beta packages do not all contain a complete per-file install manifest, so a universal precise uninstaller cannot be promised retroactively.

1. Close the game.
2. Treat package rollback notes as historical. Never follow an instruction to delete the whole `%LOCALAPPDATA%\ancr\<game>\data` directory: TDA01 beta0.2.2 contains such obsolete advice. Do not delete `data\user`, saves or progress data.
3. If you made a pre-install backup, move the patched title's exact `data\root` out of the way and restore that backup. Prefer moving/renaming to immediate permanent deletion.
4. If no backup or complete manifest exists, do not guess at individual files and do not delete broad directories such as `%LOCALAPPDATA%\ancr`, a whole Proton prefix, `data\user`, or save/progress folders. Ask for title-specific help in a [bug report](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=bug-report.yml).
5. Steam **Verify integrity of game files** can repair files managed inside the Steam installation. It does **not** inspect or remove this patch's LocalAppData loose overlay, so verification is not a substitute for steps 2–4.

Future packages are expected to carry a complete install manifest and tested rollback path under the current [release process](../project/release-process.md).

## Compatibility

- Only the Steam title named by the release was tested. Other stores, consoles, mobile ports, future Steam updates and repacks are not assumed compatible.
- Current AGE2 beta installers do not enforce the original `pack.bin` hash. The five historical releases did not preserve an exact Steam build/depot identity or original `pack.bin` SHA-256, so compatibility with the current Steam build cannot be established before installation. Back up the exact overlay root, test cautiously, and do not treat a successful copy as validation.
- Do not layer two patches that replace the same text, image, font or cache paths.
- Back up custom loose files before installing an update. A newer package may intentionally clean stale files in the exact title's `root`.

## Troubleshooting and feedback

Start from one known patch on the correct title and reproduce the problem after a full game restart. Include:

- game and Release tag;
- Windows or Steam Deck/Proton environment;
- whether the game or patch was updated and whether another mod is installed;
- full screenshot, scene/date/route and surrounding dialogue;
- exact error text and whether the problem is missing/English text, wrong speaker, tofu glyphs, clipping, a missing/torn/discolored image, startup failure or achievement behavior;
- what rollback steps you tried. Do not report Steam verification alone as removing a LocalAppData patch.

[Open a patch/runtime bug](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=bug-report.yml). A wording preference should instead use the [translation correction form](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=translation-review.yml) with Japanese source and context. Never upload complete game archives.
