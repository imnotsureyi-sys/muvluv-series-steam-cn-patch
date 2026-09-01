# AGE2 resource architecture

## FPD outer container

Steam's `pack.bin` is an FPD v2 archive. Its header and encrypted index provide logical paths, offsets, stored lengths, and output lengths; a nonzero output length marks a compressed entry. The observed v2 entry is four big-endian 64-bit fields and does **not** contain a per-file CRC. A file called `pack.bin` is not a folder on disk, but extraction turns its path table into an ordinary `root/assets/...` tree.

[`tools/fpd/fpd_codec.py`](../tools/fpd/fpd_codec.py) parses that index with strict bounds. It derives the key schedule from FatePackageManager's `Scrambler.cs`, so a target-version key file is explicit rather than hidden in this repository. [`tools/fpd/extract_fpd.py`](../tools/fpd/extract_fpd.py) rejects absolute/traversal paths, existing destinations, truncated entries, and bad decompressed lengths. Bind the complete source `pack.bin` by SHA-256 and, where available, a reviewed Steam depot manifest; the format does not supply the nonexistent per-entry CRC gate claimed by older project notes.

## Inner resource formats

An EGPACK is a multilingual record table, not another general-purpose archive. Supported TDA records contain CRC-keyed fields for `id`, `jp`, `en`, `zh_hans`, and other locale slots. WebP files are conventional images and can be inspected directly. `uistring.epk` is a separate encrypted format; treating every `.epk`/`.egpack` as interchangeable is incorrect.

## Loose overlay

AGE2 can resolve a loose file from its per-user data tree before the corresponding path inside `pack.bin`. The patch therefore recreates only the required `root/...` paths. The Imperial Capital Burns release installs under `%LOCALAPPDATA%\ancr\tm\data`; other titles must use their own verified application/cache identity rather than copying this path blindly.

The loose tree is not a second full `pack.bin` and the unmodified game does not necessarily extract its entire archive there. It is a writable override/cache layer populated only as needed by the game, updates, or a patch.
