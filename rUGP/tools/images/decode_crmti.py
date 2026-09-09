"""Decode one reference-confirmed standalone CRmti extent to create-only review files."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Sequence

from rUGP.formats.images.cr6ti_decode import png_rgba_bytes
from rUGP.formats.images.crmti_record import decode_standalone_crmti
from rUGP.tools.images.decode_record import read_exact_extent, write_new_outputs


def build_outputs(source: Path, offset: int, extent: int, output_name: str) -> tuple[bytes, dict]:
    record = read_exact_extent(source, offset, extent)
    result = decode_standalone_crmti(record)
    level = result.level
    png = png_rgba_bytes(level.width, level.height, result.rgba)
    report = {
        "schema": "rugp-read-only-standalone-crmti-decode/1",
        "codec": "standalone_crmti",
        "source_file": source.name,
        "offset": offset,
        "extent": extent,
        "record_sha256": hashlib.sha256(record).hexdigest().upper(),
        "compact_header_hex": record[:2].hex(),
        "width": level.width,
        "height": level.height,
        "meta_hex": f"0x{level.meta:08X}",
        "blob_length": level.blob_length,
        "decoded_size_hint": level.decoded_size_hint,
        "active_row_count": level.active_row_count,
        "rgba_sha256": hashlib.sha256(result.rgba).hexdigest().upper(),
        "decode_stats": asdict(result.stats),
        "output_file": output_name,
        "png_bytes": len(png),
        "png_sha256": hashlib.sha256(png).hexdigest().upper(),
        "input_modified": False,
        "standalone_not_inline_child": True,
        "runtime_acceptance": False,
        "language_pair_inferred": False,
    }
    return png, report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--offset", required=True, type=lambda s: int(s, 0))
    parser.add_argument("--extent", required=True, type=lambda s: int(s, 0))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    report_path = args.report or args.output.with_suffix(args.output.suffix + ".json")
    try:
        png, report = build_outputs(args.source, args.offset, args.extent, args.output.name)
        write_new_outputs(args.source, args.output, png, report_path, report)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except (ValueError, OSError, RuntimeError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
