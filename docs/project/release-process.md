# Release process

This checklist governs new releases. The five AGE2 beta packages currently linked from the root README predate it and do not consistently satisfy every manifest, version-gate, rollback, checksum and font-notice requirement; see the [player guide](../player/README.md).

## 1. Freeze inputs

- Record the game, Steam build/depot identity where available, and SHA-256 of every modified source file. A separately obtained clear-name depot manifest may be checked with [`verify_steam_depot_manifest.py`](../../localization/tools/verify_steam_depot_manifest.py); the result proves content-map agreement, not Steam-signature authenticity.
- Freeze canonical translation/image manifests and the source commit.
- Build in a fresh staging directory; never package a live game directory directly.

## 2. Build and verify

- Run the AGE2, rUGP, and engine-neutral localization test suites plus repository hygiene checks.
- Run the engine-specific builder with all version gates enabled.
- Rebuild in a second clean directory and compare normalized outputs.
- Verify every archive member against the generated manifest.

## 3. Audit contents

- Reject absolute local paths, credentials, logs, debug symbols, caches, original complete archives, and unapproved candidates.
- Confirm font licenses and third-party notices travel with their binaries.
- Confirm the installer touches only the named game and that restoration is documented.
- For PF/PM, require the confirmed Steam locale/app-ID preflight and revalidate its in-memory manifest seal immediately before the first write; a saved report alone is not authorization.

## 4. Publish

- Use a game-specific tag; do not use one Photon game's approval to publish the other.
- Attach the player package, SHA-256 list, support matrix, known limitations, and source commit.
- Update [`release-index.json`](../player/release-index.json) with the immutable asset name, byte size, SHA-256, install/overlay roots and known historical caveats.
- Keep the Git tree free of the generated ZIP/DLL/archive.

## 5. Post-release

- Install the downloaded asset, not the local staging copy, onto a clean supported game.
- Record full-route testing and triage feedback by game/version/resource identity.
- Preserve superseded releases for provenance unless they expose unsafe or unauthorized material; mark them obsolete rather than silently replacing bytes under the same tag.
