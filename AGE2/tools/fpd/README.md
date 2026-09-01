# FPD v2 reader and filtered extractor

These tools handle the outer AGE2 `pack.bin` container. Files extracted from it—EGPACK, WebP, XML, fonts, and others—remain separate formats.

## Why `Scrambler.cs` is an input

The FPD structure and key schedule were learned from the MIT-licensed [FatePackageManager](https://github.com/DaZombieKiller/FatePackageManager/tree/080c2cac36391e2d2de473f8f8a841b08cf752dc). Instead of embedding a second key table that can silently drift, these tools parse the reviewed upstream `Scrambler.cs` supplied on the command line. The reviewed file SHA-256 is `5AA8BCEFB9F2F1D14917FE11027B32FFFFD0A8C8C3F25C3AE8D690827EEAE33E`; verify it before interpreting an AGE2 baseline.

## Inspect

```powershell
python AGE2/tools/fpd/fpd_codec.py "X:\game\obb\pack.bin" `
  --scrambler "X:\tools\FatePackageManager\Scrambler.cs" `
  --contains "localized" --limit 30
```

The output lists logical path, stored/output length, offset and compression state. FPD v2's observed four-field entry has no per-file CRC; verify the complete `pack.bin` identity separately. This command does not turn EGPACK bytes into translated dialogue; use `AGE2/tools/egpack/` for that second layer.

## Extract a scoped subset

```powershell
python AGE2/tools/fpd/extract_fpd.py "X:\game\obb\pack.bin" `
  --scrambler "X:\tools\FatePackageManager\Scrambler.cs" `
  --contains "assets/data_spec/adv/game/src/localized" `
  --output "X:\work\fpd-extract"
```

The extractor plans the complete destination set before writing, rejects path
traversal, noncanonical names, Windows case collisions, file/directory
conflicts, truncated reads and invalid decompressed sizes, and stages into a
same-parent temporary directory. The requested output appears only after the
source file has remained stable and every selected member is complete; an
existing output is never replaced. Do not commit extracted game data.

This repository currently uses FPD read/extract support plus AGE2 loose-file overlay. It does not claim a production-grade `pack.bin` repacker.
