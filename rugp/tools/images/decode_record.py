#!/usr/bin/env python3
"""Read one catalogued rUGP image extent and create a review PNG safely."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Mapping, Sequence

from rugp.formats.images.cr6ti_decode import decode_standard_cr6ti_record, png_rgba_bytes
from rugp.formats.images.crip007_encode import decode_record_rgba
from rugp.formats.images.crip008_decode import (
    decode_crip008_kind2_native,
    decode_crip008_kind3_native,
    native_crip008_to_rgba,
    parse_crip008_header,
)


MAX_RECORD_BYTES = 256 * 1024 * 1024


class ImageExtractError(RuntimeError):
    """The requested extent or codec is not safely supported."""


def read_exact_extent(path: Path, offset: int, extent: int) -> bytes:
    if offset < 0 or extent <= 0 or extent > MAX_RECORD_BYTES:
        raise ImageExtractError("offset/extent is invalid or exceeds the safety limit")
    try:
        source = path.resolve(strict=True)
        before_path = source.stat()
    except OSError as exc:
        raise ImageExtractError("source file is missing or inaccessible") from exc
    if not stat.S_ISREG(before_path.st_mode) or offset + extent > before_path.st_size:
        raise ImageExtractError("requested image extent is outside the source file")
    with source.open("rb") as stream:
        before_handle = os.fstat(stream.fileno())
        identity = lambda value: (
            value.st_dev,
            value.st_ino,
            value.st_size,
            value.st_mtime_ns,
        )
        if identity(before_handle) != identity(before_path):
            raise ImageExtractError("source file changed before the extent was read")
        stream.seek(offset)
        record = stream.read(extent)
        after_handle = os.fstat(stream.fileno())
    after_path = source.stat()
    if len(record) != extent:
        raise ImageExtractError("requested image extent was truncated")
    if identity(before_handle) != identity(after_handle) or identity(
        before_handle
    ) != identity(after_path):
        raise ImageExtractError("source file changed while the image extent was read")
    return record


def decode_record(record: bytes, codec: str) -> tuple[int, int, bytes, dict[str, object]]:
    if codec == "cr6ti":
        result = decode_standard_cr6ti_record(record)
        return result.header.width, result.header.height, result.rgba, asdict(result.header)
    if codec == "crip007":
        header, rgba = decode_record_rgba(record)
        return header.width, header.height, rgba, asdict(header)
    if codec == "crip008":
        header = parse_crip008_header(record)
        declared = header.payload_start + header.payload_length
        if declared != len(record):
            raise ImageExtractError(
                f"CRip008 extent must equal the declared record length: {len(record)} != {declared}"
            )
        payload = record[header.payload_start:declared]
        if header.kind == 2:
            native = decode_crip008_kind2_native(payload, header)
        elif header.kind == 3:
            native = decode_crip008_kind3_native(payload, header)
        else:
            raise ImageExtractError(f"unsupported CRip008 kind: {header.kind}")
        rgba = bytes(native_crip008_to_rgba(native))
        return header.width, header.height, rgba, asdict(header)
    raise ImageExtractError(f"unsupported codec: {codec}")


def build_outputs(
    source: Path, offset: int, extent: int, codec: str, output_name: str
) -> tuple[bytes, dict[str, object]]:
    record = read_exact_extent(source, offset, extent)
    width, height, rgba, header = decode_record(record, codec)
    png = png_rgba_bytes(width, height, rgba)
    report: dict[str, object] = {
        "schema": "rugp-read-only-image-decode/1",
        "codec": codec,
        "source_file": source.name,
        "offset": offset,
        "extent": extent,
        "record_sha256": hashlib.sha256(record).hexdigest().upper(),
        "header": header,
        "output_file": output_name,
        "png_bytes": len(png),
        "png_sha256": hashlib.sha256(png).hexdigest().upper(),
        "input_modified": False,
    }
    return png, report


def write_new_outputs(
    source: Path,
    output: Path,
    png: bytes,
    report_path: Path,
    report: Mapping[str, object],
) -> None:
    """Create each output atomically; roll siblings back after ordinary failures."""

    source_identity = source.resolve(strict=True)
    output_paths = (output, report_path)
    output_identities = [path.resolve(strict=False) for path in output_paths]
    if len(set(output_identities)) != 2:
        raise ImageExtractError("PNG and report must resolve to different files")
    aliases_source = source_identity in set(output_identities) or any(
        path.exists() and os.path.samefile(path, source) for path in output_paths
    )
    if aliases_source:
        raise ImageExtractError("outputs must not alias the RIO/source input")
    if any(path.exists() for path in output_paths):
        raise ImageExtractError("refusing to overwrite existing image evidence")
    requested = {
        output: png,
        report_path: (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    }
    temporaries: list[Path] = []
    published: list[Path] = []
    try:
        for path, payload in requested.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
            ) as stream:
                temporary = Path(stream.name)
                temporaries.append(temporary)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError as error:
                raise ImageExtractError(f"refusing to overwrite existing file: {path}") from error
            published.append(path)
            temporary.unlink()
            temporaries.remove(temporary)
    except Exception:
        for path in reversed(published):
            path.unlink(missing_ok=True)
        raise
    finally:
        for path in temporaries:
            path.unlink(missing_ok=True)


def _integer(value: str) -> int:
    return int(value, 0)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--offset", required=True, type=_integer)
    parser.add_argument("--extent", required=True, type=_integer)
    parser.add_argument("--codec", required=True, choices=("cr6ti", "crip007", "crip008"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    report_path = args.report or args.output.with_suffix(args.output.suffix + ".json")
    try:
        png, report = build_outputs(
            args.source, args.offset, args.extent, args.codec, args.output.name
        )
        write_new_outputs(args.source, args.output, png, report_path, report)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
