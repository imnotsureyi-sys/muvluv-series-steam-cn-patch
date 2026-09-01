from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    from .crypto import (
        decode_extent_offset,
        decode_extent_size,
        encode_extent_offset,
        encode_extent_size,
        round_up,
    )
except ImportError:  # Direct script execution.
    from crypto import (
        decode_extent_offset,
        decode_extent_size,
        encode_extent_offset,
        encode_extent_size,
        round_up,
    )


@dataclass(frozen=True)
class Redirect:
    source_raw_offset: int
    ruo_raw_offset: int
    replacement_raw_size: int

    def pack(self) -> bytes:
        return struct.pack(
            "<III",
            self.source_raw_offset,
            self.ruo_raw_offset,
            self.replacement_raw_size,
        )


def signed_u32(value: int) -> int:
    return value if value < 0x80000000 else value - 0x100000000


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_u32(value: str) -> int:
    result = int(value, 0)
    if not 0 <= result <= 0xFFFFFFFF:
        raise argparse.ArgumentTypeError("value must fit in an unsigned 32-bit integer")
    return result


def read_footer(path: Path, unit_size: int) -> tuple[int, list[Redirect]]:
    size = path.stat().st_size
    if size < 4:
        raise ValueError("RUO is too short for a footer count")
    with path.open("rb") as stream:
        stream.seek(-4, 2)
        count = struct.unpack("<I", stream.read(4))[0]
        if count >= 0x20000:
            raise ValueError(f"RUO redirect count 0x{count:X} is rejected by the game loader")
        table_size = count * 12
        table_offset = size - 4 - table_size
        if table_offset < 0:
            raise ValueError("RUO footer count points before the start of the file")
        stream.seek(table_offset)
        table = stream.read(table_size)
    redirects = [Redirect(*values) for values in struct.iter_unpack("<III", table)]
    for item in redirects:
        destination = decode_extent_offset(item.ruo_raw_offset, unit_size)
        extent_size = decode_extent_size(item.replacement_raw_size)
        if destination + extent_size > table_offset:
            raise ValueError(
                f"replacement extent 0x{destination:X}+0x{extent_size:X} overlaps the footer"
            )
    return table_offset, redirects


def build_ruo(
    output: Path,
    unit_size: int,
    replacements: list[tuple[int, bytes]],
    data_offset: int = 0,
    base_ruo: Path | None = None,
) -> dict[str, object]:
    if unit_size <= 0:
        raise ValueError("unit size must be positive")
    if data_offset < 0 or data_offset % unit_size:
        raise ValueError("data offset must be non-negative and aligned to unit size")
    if not replacements:
        raise ValueError("at least one replacement is required")
    if len({raw for raw, _ in replacements}) != len(replacements):
        raise ValueError("duplicate source offsets are not allowed")

    inherited_redirects: list[Redirect] = []
    inherited_data_size = 0
    base_ruo_sha256: str | None = None
    if base_ruo is not None:
        if data_offset:
            raise ValueError("data offset cannot be combined with a base RUO")
        if output.resolve() == base_ruo.resolve():
            raise ValueError("output must not overwrite the base RUO")
        inherited_data_size, inherited_redirects = read_footer(base_ruo, unit_size)
        base_bytes = base_ruo.read_bytes()
        base_ruo_sha256 = sha256(base_bytes)
        blob = bytearray(base_bytes[:inherited_data_size])
    else:
        blob = bytearray(data_offset)

    redirect_by_source = {item.source_raw_offset: item for item in inherited_redirects}
    records: list[dict[str, object]] = []
    for source_raw_offset, record in replacements:
        destination = round_up(len(blob), unit_size)
        blob.extend(b"\0" * (destination - len(blob)))
        blob.extend(record)
        padded_end = round_up(len(blob), unit_size)
        blob.extend(b"\0" * (padded_end - len(blob)))
        replacement_extent_size = len(record)
        placement_span = padded_end - destination
        redirect = Redirect(
            source_raw_offset=source_raw_offset,
            ruo_raw_offset=encode_extent_offset(destination, unit_size),
            replacement_raw_size=encode_extent_size(replacement_extent_size),
        )
        replaced_inherited = source_raw_offset in redirect_by_source
        redirect_by_source[source_raw_offset] = redirect
        records.append(
            {
                "source_raw_offset_hex": f"0x{source_raw_offset:08X}",
                "destination_byte_offset": destination,
                "destination_byte_offset_hex": f"0x{destination:X}",
                "ruo_raw_offset_hex": f"0x{redirect.ruo_raw_offset:08X}",
                "input_record_size": len(record),
                "replacement_extent_size": replacement_extent_size,
                "placement_span_with_alignment": placement_span,
                "replacement_raw_size_hex": f"0x{redirect.replacement_raw_size:08X}",
                "record_sha256": sha256(record),
                "replaced_inherited_redirect": replaced_inherited,
            }
        )

    redirects = list(redirect_by_source.values())
    if len(redirects) >= 0x20000:
        raise ValueError("the game loader requires fewer than 0x20000 redirect records")
    redirects.sort(key=lambda item: signed_u32(item.source_raw_offset))
    footer_offset = len(blob)
    for redirect in redirects:
        blob.extend(redirect.pack())
    blob.extend(struct.pack("<I", len(redirects)))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(blob)
    parsed_footer_offset, parsed = read_footer(output, unit_size)
    if parsed_footer_offset != footer_offset or parsed != redirects:
        raise RuntimeError("RUO footer readback did not match the data that was written")

    return {
        "schema": 1,
        "format": "rUGP relative archive redirect overlay (RUO)",
        "output": str(output.resolve()),
        "unit_size": unit_size,
        "data_offset": data_offset,
        "base_ruo": str(base_ruo.resolve()) if base_ruo is not None else None,
        "base_ruo_sha256": base_ruo_sha256,
        "inherited_data_size": inherited_data_size,
        "inherited_redirect_count": len(inherited_redirects),
        "footer_offset": footer_offset,
        "footer_offset_hex": f"0x{footer_offset:X}",
        "redirect_count": len(redirects),
        "file_size": len(blob),
        "file_sha256": sha256(blob),
        "records": records,
        "footer_records": [
            {
                **asdict(item),
                "source_raw_offset_hex": f"0x{item.source_raw_offset:08X}",
                "ruo_raw_offset_hex": f"0x{item.ruo_raw_offset:08X}",
                "replacement_raw_size_hex": f"0x{item.replacement_raw_size:08X}",
            }
            for item in redirects
        ],
        "verification": {
            "footer_readback": True,
            "deterministic_signed_source_order": True,
            "replacement_extents_before_footer": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the smallest known RUO overlay for one existing RIO object."
    )
    parser.add_argument("--unit-size", type=int, required=True, choices=(1, 2, 4, 8))
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-raw-offset", type=parse_u32)
    source.add_argument("--source-byte-offset", type=lambda value: int(value, 0))
    record_source = parser.add_mutually_exclusive_group(required=True)
    record_source.add_argument("--record", type=Path, help="complete replacement object record")
    record_source.add_argument(
        "--record-container",
        type=Path,
        help="file containing the complete replacement object record at --record-offset",
    )
    parser.add_argument("--record-offset", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--record-size", type=lambda value: int(value, 0))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--base-ruo",
        type=Path,
        help="merge an existing RUO's data and redirects into one cumulative output",
    )
    parser.add_argument(
        "--data-offset",
        type=lambda value: int(value, 0),
        default=0,
        help="optional zero prefix before replacement storage (default: 0)",
    )
    args = parser.parse_args()

    source_raw_offset = args.source_raw_offset
    if source_raw_offset is None:
        source_raw_offset = encode_extent_offset(args.source_byte_offset, args.unit_size)
    if args.record is not None:
        record = args.record.read_bytes()
    else:
        if args.record_size is None or args.record_size <= 0:
            parser.error("--record-container requires a positive --record-size")
        if args.record_offset < 0:
            parser.error("--record-offset must be non-negative")
        with args.record_container.open("rb") as stream:
            stream.seek(args.record_offset)
            record = stream.read(args.record_size)
        if len(record) != args.record_size:
            parser.error(
                f"record slice is truncated: requested {args.record_size}, read {len(record)}"
            )

    report = build_ruo(
        args.output,
        args.unit_size,
        [(source_raw_offset, record)],
        args.data_offset,
        args.base_ruo,
    )
    manifest = args.manifest or args.output.with_suffix(args.output.suffix + ".json")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
