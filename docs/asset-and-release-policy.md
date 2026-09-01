# Asset and release policy

## Asset classes

| Class | Git policy | Release policy |
| --- | --- | --- |
| Original game file | Never track | Never redistribute as a replacement for the game |
| Source identity/hash/locator | Track | Include in manifests where useful |
| Translation table | Track when needed for maintenance, with rights notice | May be embedded in a patch |
| Localized/derived image | Prefer manifest plus reviewed release bundle | Distribute only when necessary and with an explicit content-rights notice |
| Font | Track license/identity, not the binary by default | Bundle only if its license permits redistribution |
| Compiled code | Do not track | Build from tagged source and attach with hashes |
| Generated archive/delta | Do not track | Attach to the corresponding release |

## Provenance chain

Every production item should answer:

1. Which legal game/version and stable resource identity supplied the input?
2. Which source-language text or visual region was localized?
3. Which reviewed translation or textless background is authoritative?
4. Which deterministic tool, font, parameters, and format encoder produced the runtime form?
5. Which manifest and SHA-256 bind the published bytes?

Absolute workstation paths are not provenance. Use logical game IDs, relative resource paths, hashes, and tool versions.

## Image publication

Do not commit bulk official-language images merely to make comparison convenient. For a localized image, retain the smallest useful public set: a stable resource locator, input hash, output hash, dimensions/mode, translation copy, method, review status, and—when redistribution is justified—the final localized result or a release-bundle entry.

The Photon V6 image evidence follows this model: Git stores the manifest and verification records, while the approved image bundle is a separate release asset. Some entries are represented by a native encoded record rather than a preview PNG; the manifest identifies the actual packaging authority.

## Release gate

A release must be rejected if any of these are unknown:

- exact game and supported input hashes;
- complete file list and output hashes;
- installation destination and uninstall/restore path;
- source commit and reproducible build command;
- font and third-party licenses;
- test/QA status and known limitations;
- whether the package accidentally contains original archives, credentials, local paths, debug symbols, or unapproved candidates.

See [`release-process.md`](release-process.md) for the operational checklist.
