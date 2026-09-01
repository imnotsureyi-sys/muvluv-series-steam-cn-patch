# AGE2 provenance

For each game record the Steam application/build identity, original `pack.bin` size/SHA-256, target-version `Scrambler.cs` source and hash, extractor version, extracted logical path, source-file hash, source-language field identity, localized output hash, and final release hash.

Public translation tables retain enough stable identity to audit a correction. Bulk original strings/images stay in the user's extraction. A developer's Steam-library path is never evidence; the relative resource path and content hash are.

FatePackageManager is a format reference and key-schedule provider, not proof that every AGE2 title has identical paths or overlay behavior. Each new game requires its own observed clean baseline and runtime test.
