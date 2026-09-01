# Notice and content rights

This is an unofficial, non-commercial fan project. It is not affiliated with, endorsed by, or sponsored by Muv-Luv's rights holders, publishers, Steam, or the authors of the referenced tools.

## What the MIT license covers

The root [`LICENSE`](LICENSE) covers original software code authored for this repository unless a file says otherwise. It does not automatically cover every file stored beside that code.

## What it does not license

The MIT license does not grant permission for:

- Muv-Luv names, characters, scripts, images, audio, video, archives, executables, or other game content;
- translated text, terminology data, screenshots, derived or localized images, and patch payloads;
- fonts or third-party components distributed under their own terms;
- any content supplied only as an identity hash or required from a user's legal game installation.

Those materials remain subject to their respective authors' and rights holders' terms. Their presence in a source table, manifest, test release, or technical description does not transfer ownership or imply a general redistribution license.

## Distribution boundary

The Git tree contains source code, localization data, documentation, synthetic fixtures, and narrow provenance records. It intentionally excludes complete original archives and resources capable of replacing the games. Generated player packages and approved derived-image bundles are distributed separately through GitHub Releases when appropriate.

When redistributing a modified patch, verify the rights for every non-code component, preserve relevant notices, do not bundle the game, and clearly identify the supported game version. See [`THIRD_PARTY.md`](THIRD_PARTY.md) and [`docs/asset-and-release-policy.md`](docs/asset-and-release-policy.md).

The currently published AGE2 beta packages predate the repository's current release process and do not consistently carry every manifest, input-version gate, rollback tool, or font-license notice now required for a new release. Their presence on the Releases page is not a claim that those later requirements were applied retroactively.

## Recovery boundary

Current AGE2 patches use loose files in a per-user LocalAppData tree. Steam **Verify integrity of game files** repairs Steam-managed installation files, but it does not inspect or remove those LocalAppData overrides. Follow the exact-title rollback guidance in [`docs/player-guide.md`](docs/player-guide.md#restore-and-rollback) before using Steam verification, and never delete a broad LocalAppData directory, Proton prefix, or save/progress tree as a generic cleanup step.

## Warranty

Patches and tools are provided without warranty. They may be incompatible with future game updates. Use them only on legally obtained copies. Remove or restore the patch's per-user loose files according to the player guide; use Steam verification only for Steam-managed originals.
