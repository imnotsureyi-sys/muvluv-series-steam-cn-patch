"""Export every inline CRmti layer from a hash-locked CRmt; never follow guessed references."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence

from rUGP.formats.images.cr6ti_decode import png_rgba_bytes
from rUGP.formats.images.crmti_decode import decode_crmt
from rUGP.tools.images.decode_record import read_exact_extent


def export_layers(source: Path, offset: int, extent: int, expected_sha256: str, output: Path) -> dict:
    if output.exists():
        raise ValueError("output directory must be new")
    raw = read_exact_extent(source, offset, extent)
    digest = hashlib.sha256(raw).hexdigest().upper()
    if digest != expected_sha256.upper():
        raise ValueError("source record SHA-256 mismatch")
    decoded, trailer = decode_crmt(raw)
    payloads = []
    rows = []
    for layer in decoded:
        lv = layer.level
        png = png_rgba_bytes(lv.width, lv.height, layer.rgba)
        name = f"L{lv.index:02d}-{lv.width}x{lv.height}.png"
        rows.append({"level": lv.index, "width": lv.width, "height": lv.height,
                     "file": name, "png_sha256": hashlib.sha256(png).hexdigest().upper(),
                     "rgba_sha256": hashlib.sha256(layer.rgba).hexdigest().upper()})
        payloads.append((name, png))
    report = {"schema": "rugp-crmt-inline-layer-export/1", "source_file": source.name,
              "offset": offset, "extent": extent, "record_sha256": digest,
              "levels": rows, "trailer_bytes": len(trailer), "input_modified": False,
              "external_image_fetched": False,
              "boundary": "All inline layers only. Layer index is not an animation frame or a cross-language size match."}
    # Decode and validate before creating anything. Never delete partial output on I/O failure.
    output.mkdir(parents=True, exist_ok=False)
    for name, payload in payloads:
        with (output / name).open("xb") as stream:
            stream.write(payload)
    with (output / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--offset", required=True, type=lambda x: int(x, 0))
    parser.add_argument("--extent", required=True, type=lambda x: int(x, 0))
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = export_layers(args.source, args.offset, args.extent, args.sha256, args.output_dir)
    except (ValueError, OSError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
