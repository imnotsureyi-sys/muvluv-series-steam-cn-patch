"""Read one exact CRimp metadata extent and print typed JSON; create no files."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence

from rUGP.formats.images.crimp import parse_crimp
from rUGP.tools.images.decode_record import ImageExtractError, read_exact_extent


def inspect_record(data: bytes) -> dict:
    record = parse_crimp(data)
    return {"schema": "rugp-crimp-typed-properties/1", "record_bytes": len(data),
            "record_sha256": hashlib.sha256(data).hexdigest().upper(),
            "property_count": len(record.properties), "lossless_readback": record.to_bytes() == data,
            "post_map_bytes_hex": record.post_map_bytes.hex(" "),
            "post_map_cache_identity_resolved": False,
            "properties": [{"name": p.name, "name_offset": p.name_offset, "value_offset": p.value_offset,
                            "end_offset": p.end_offset, "value_hex": p.value.to_bytes().hex(" "),
                            "value_kind": p.value.kind, "decoded_value": p.value.as_dict()}
                           for p in record.properties]}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--offset", type=lambda x: int(x, 0), required=True)
    parser.add_argument("--extent", type=lambda x: int(x, 0), required=True)
    args = parser.parse_args(argv)
    try:
        data = read_exact_extent(args.source, args.offset, args.extent)
        report = inspect_record(data)
        report.update(source_file=args.source.name, offset=args.offset, extent=args.extent,
                      files_written=0, is_raster_image=False)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except (ValueError, OSError, ImageExtractError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
