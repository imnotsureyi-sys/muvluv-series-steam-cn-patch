# rUGP catalog tools

`rio_inventory.py` is a read-only command for turning an rUGP `.ici` object
directory into a portable list of logical resources. It reports each object's
logical path, rUGP class/type, declared RIO volume, byte offset inside that
volume, and byte extent.

The directory decoder is a maintained Python port of GARbro's
MIT-licensed [`ArcFormats/rUGP/ArcRIO.cs`](https://github.com/morkt/GARbro/blob/b09ee4570ccb1daf6ac56710ee8934dc0b8baeb0/ArcFormats/rUGP/ArcRIO.cs),
Copyright (C) 2016 by morkt. The complete upstream MIT notice is retained at
the top of `rio_inventory.py`. Newer Photon class labels, multi-volume
resolution, portable exports, and defensive bounds checks are project
extensions.

## What it does and does not do

- Reads the `.ici` plus the RIO volume containing its encrypted TOC.
- Optionally checks secondary split volumes supplied by the user.
- Decodes directory metadata only; it does not decode image, script, or audio
  payloads.
- Never opens an ICI or RIO input for writing.
- Does not include absolute workstation paths in the JSON report.
- Does not bypass ownership or distribution requirements. Use files from a
  legally obtained installation and do not commit the generated inventory if
  it contains names you are not entitled to redistribute.

## JSON inventory

Run from the repository root:

```powershell
python -m rUGP.tools.catalog.rio_inventory `
  --ici "D:\Games\Example\example.rio.ici" `
  --main-rio "D:\Games\Example\example.rio" `
  --volume "D:\Games\Example\example.rio.002" `
  --output ".\example-rio-inventory.json"
```

`--volume` may be repeated. Normally a secondary path is matched to the
filename declared by the ICI. If a local filename differs, bind it explicitly:

```powershell
--volume "example.rio.002=D:\My Copy\renamed-volume.bin"
```

The main RIO is always bound by its explicit `--main-rio` role, so a renamed
main file is accepted with a warning.

Omit `--output` to print UTF-8 JSON to stdout. The report contains:

- `volumes`: the ICI-declared global ranges and whether each supplied file is
  present;
- `nodes[].logical_path` and `logical_directory`;
- `nodes[].class` and the broad `kind` (`image`, `script`, `audio`, or
  `other`);
- `nodes[].volume`, `volume_offset`, `global_offset`, and byte `extent`;
- declared/provided volume-bound checks.

An output file must not already exist and must not alias an ICI/RIO input. The
completed report is fsynced under a same-directory temporary name and then
published atomically; reruns cannot silently replace an earlier inventory.

Decoded extents are already byte counts. The ICI allocation shift applies to
offsets, not to extents. Some game builds serialize anonymous object nodes
with the literal name `unrefix`; the catalog preserves that engine-visible
name instead of inventing a filename.

## CSV and filters

```powershell
python -m rUGP.tools.catalog.rio_inventory `
  --ici ".\example.rio.ici" `
  --main-rio ".\example.rio" `
  --format csv `
  --kind image `
  --class-name CRip008 `
  --output ".\crip008.csv"
```

Useful inspection filters are:

- `--kind image|script|audio|other`;
- `--class-name CRsa` (exact class match);
- `--near-global-offset 0x123400`;
- `--limit 20`.

Filtering affects only exported rows. No source file is changed. The command
also refuses an `--output` path that is one of its ICI/RIO inputs.

## Library use

```python
from pathlib import Path
from rUGP.tools.catalog.rio_inventory import build_inventory

report = build_inventory(
    ici=Path("example.rio.ici"),
    main_rio=Path("example.rio"),
    volumes=[Path("example.rio.002")],
)
for node in report["nodes"]:
    print(node["volume"], node["volume_offset"], node["extent"], node["logical_path"])
```

Synthetic tests build a tiny fake ICI and two fake volumes entirely at test
time. No game data is stored in this repository.
