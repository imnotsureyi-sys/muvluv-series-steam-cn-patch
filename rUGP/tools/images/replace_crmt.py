#!/usr/bin/env python3
"""Build a standalone CRmt replacement from one audited top-level PNG.

The tool reads exactly one source extent, regenerates every CRmti mip with
premultiplied-alpha Lanczos filtering, independently decodes the result, and
publishes a new standalone CRmt record plus JSON audit.  It never writes to the
RIO/source input and deliberately has no in-place injection mode.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
from io import BytesIO
import json
from pathlib import Path
from typing import Sequence

from PIL import Image

from rUGP.formats.images.crmti_capacity import capacity_for_ranges

from rUGP.formats.images.crmti_decode import decode_crmt, parse_crmt
from rUGP.formats.images.crmti_encode import encode_crmt
from rUGP.tools.images.decode_record import read_exact_extent, write_new_outputs


class CrmtReplacementError(RuntimeError):
    """The source extent, PNG, or encoded readback did not close safely."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def _premultiplied_resize(
    rgba: bytes, source_size: tuple[int, int], target_size: tuple[int, int]
) -> bytes:
    source = Image.frombytes("RGBA", source_size, rgba)
    resized = source.convert("RGBa").resize(target_size, Image.Resampling.LANCZOS)
    return resized.convert("RGBA").tobytes()


def build_replacement(
    *,
    source: Path,
    offset: int,
    extent: int,
    top_png: Path,
    output_name: str,
) -> tuple[bytes, dict[str, object]]:
    template = read_exact_extent(source, offset, extent)
    source_levels, source_trailer = parse_crmt(template)
    try:
        top_extent = top_png.resolve(strict=True).stat().st_size
        top_payload = read_exact_extent(top_png, 0, top_extent)
        with Image.open(BytesIO(top_payload)) as opened:
            top = opened.convert("RGBA")
    except OSError as exc:
        raise CrmtReplacementError("top PNG is missing or invalid") from exc
    top_size = (source_levels[0].width, source_levels[0].height)
    if top.size != top_size:
        raise CrmtReplacementError(
            f"top PNG is {top.width}x{top.height}; template top is {top_size[0]}x{top_size[1]}"
        )
    top_rgba = top.tobytes()
    rgba_levels = [top_rgba]
    for level in source_levels[1:]:
        rgba_levels.append(
            _premultiplied_resize(
                top_rgba,
                top_size,
                (level.width, level.height),
            )
        )
    replacement, expected_levels, encode_stats = encode_crmt(
        template, rgba_levels
    )
    decoded, replacement_trailer = decode_crmt(replacement)
    replacement_levels, parsed_trailer = parse_crmt(replacement)
    parent_preamble_end = source_levels[0].wrapper_offset
    if replacement[:parent_preamble_end] != template[:parent_preamble_end]:
        raise CrmtReplacementError("CRmt parent header changed")
    if not source_trailer == replacement_trailer == parsed_trailer:
        raise CrmtReplacementError("CRmt parent trailer changed")
    if len(decoded) != len(source_levels):
        raise CrmtReplacementError("CRmti child count changed")

    level_rows: list[dict[str, object]] = []
    for source_level, replacement_level, result, expected in zip(
        source_levels, replacement_levels, decoded, expected_levels, strict=True
    ):
        immutable_before = (
            source_level.width,
            source_level.height,
            source_level.meta,
        )
        immutable_after = (
            replacement_level.width,
            replacement_level.height,
            replacement_level.meta,
        )
        if immutable_before != immutable_after:
            raise CrmtReplacementError(
                f"CRmti immutable fields changed at level {source_level.index}"
            )
        if result.rgba != expected:
            raise CrmtReplacementError(
                f"CRmti pixel readback differs at level {source_level.index}"
            )
        capacity = capacity_for_ranges(replacement_level.width, replacement_level.height,
                                       replacement_level.active_row_count, result.active_ranges)
        if replacement_level.decoded_size_hint != capacity.replacement_hint(source_level.decoded_size_hint):
            raise CrmtReplacementError(f"CRmti capacity readback differs at level {source_level.index}")
        level_rows.append(
            {
                "index": source_level.index,
                "width": source_level.width,
                "height": source_level.height,
                "meta_hex": f"0x{source_level.meta:08X}",
                "source_blob_bytes": source_level.blob_length,
                "replacement_blob_bytes": replacement_level.blob_length,
                "active_row_count": replacement_level.active_row_count,
                "source_decoded_size_hint": source_level.decoded_size_hint,
                "replacement_decoded_size_hint": replacement_level.decoded_size_hint,
                "native_capacity_check_passed": True,
                "capacity": asdict(capacity),
                "rgba_sha256": _sha256(result.rgba),
                "decode": asdict(result.stats),
                "immutable_fields_preserved": True,
            }
        )

    report: dict[str, object] = {
        "schema": "rugp-standalone-crmt-replacement/2",
        "mode": "create_only_no_in_place_injection",
        "source_file": source.name,
        "offset": offset,
        "extent": extent,
        "source_record_sha256": _sha256(template),
        "top_png_file": top_png.name,
        "top_png_sha256": _sha256(top_payload),
        "top_rgba_sha256": _sha256(top_rgba),
        "output_file": output_name,
        "output_bytes": len(replacement),
        "output_sha256": _sha256(replacement),
        "level_count": len(level_rows),
        "parent_prefix_hex": template[:4].hex(" "),
        "child_table_offset": parent_preamble_end,
        "child_wrapper_hex": template[
            source_levels[0].wrapper_offset : source_levels[0].header_offset
        ].hex(" "),
        "mip_strategy": "premultiplied-alpha Lanczos from audited top image",
        "all_levels_read_back_as_expected": True,
        "all_levels_native_capacity_checked": True,
        "parent_header_and_trailer_preserved": True,
        "input_modified": False,
        "levels": level_rows,
        "encode": encode_stats,
    }
    return replacement, report


def _integer(value: str) -> int:
    return int(value, 0)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--offset", type=_integer, required=True)
    parser.add_argument("--extent", type=_integer, required=True)
    parser.add_argument("--top-png", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    report_path = args.report or args.output.with_suffix(args.output.suffix + ".json")
    try:
        replacement, report = build_replacement(
            source=args.source,
            offset=args.offset,
            extent=args.extent,
            top_png=args.top_png,
            output_name=args.output.name,
        )
        write_new_outputs(
            args.source, args.output, replacement, report_path, report
        )
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
