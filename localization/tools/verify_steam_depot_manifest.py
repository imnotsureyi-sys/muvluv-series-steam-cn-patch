#!/usr/bin/env python3
"""Verify selected local files against a clear-name Steam depot manifest.

This is a content-identity check, not a Steam signature/authenticity verifier.
It reads a manifest already obtained by the user and never contacts Steam or
modifies the game installation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
from typing import Any, Iterable, Mapping

from localization.tools.safe_output import write_new_files


PAYLOAD_MAGIC = 0x71F617D0
METADATA_MAGIC = 0x1F4812BE


def _sha256_file(path: Path, chunk_size: int = 16 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(chunk_size):
            digest.update(block)
    return digest.hexdigest().upper()


def _sha1_file(path: Path, chunk_size: int = 16 * 1024 * 1024) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while block := handle.read(chunk_size):
            digest.update(block)
    return digest.hexdigest().upper()


def read_varint(data: bytes, position: int, end: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while position < end and shift < 70:
        byte = data[position]
        position += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, position
        shift += 7
    raise ValueError("truncated or oversized protobuf varint")


def protobuf_fields(data: bytes) -> list[tuple[int, int, Any]]:
    fields: list[tuple[int, int, Any]] = []
    position = 0
    while position < len(data):
        tag, position = read_varint(data, position, len(data))
        number = tag >> 3
        wire = tag & 7
        if number == 0:
            raise ValueError("invalid protobuf field zero")
        if wire == 0:
            value, position = read_varint(data, position, len(data))
        elif wire == 1:
            if position + 8 > len(data):
                raise ValueError("truncated protobuf fixed64")
            value = int.from_bytes(data[position : position + 8], "little")
            position += 8
        elif wire == 2:
            length, position = read_varint(data, position, len(data))
            if position + length > len(data):
                raise ValueError("truncated protobuf bytes")
            value = data[position : position + length]
            position += length
        elif wire == 5:
            if position + 4 > len(data):
                raise ValueError("truncated protobuf fixed32")
            value = int.from_bytes(data[position : position + 4], "little")
            position += 4
        else:
            raise ValueError(f"unsupported protobuf wire type {wire}")
        fields.append((number, wire, value))
    return fields


def _first(
    fields: Iterable[tuple[int, int, Any]], number: int, default: Any = None
) -> Any:
    for field_number, _wire, value in fields:
        if field_number == number:
            return value
    return default


def _safe_manifest_name(raw: bytes) -> str:
    try:
        name = raw.decode("utf-8").replace("\\", "/")
    except UnicodeDecodeError as exc:
        raise ValueError("manifest filename is not clear UTF-8") from exc
    path = PurePosixPath(name)
    if (
        not name
        or "\x00" in name
        or path.is_absolute()
        or path.as_posix() != name
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(":" in part for part in path.parts)
    ):
        raise ValueError(f"unsafe manifest filename: {name!r}")
    return name


def _parse_chunk(data: bytes) -> dict[str, Any]:
    fields = protobuf_fields(data)
    digest = bytes(_first(fields, 1, b""))
    if len(digest) != 20:
        raise ValueError("depot chunk SHA-1 must be exactly 20 bytes")
    return {
        "sha1": digest.hex().upper(),
        "crc32": int(_first(fields, 2, 0)),
        "offset": int(_first(fields, 3, 0)),
        "original_size": int(_first(fields, 4, 0)),
        "compressed_size": int(_first(fields, 5, 0)),
    }


def _parse_file_mapping(data: bytes) -> dict[str, Any]:
    fields = protobuf_fields(data)
    content_digest = bytes(_first(fields, 5, b""))
    if len(content_digest) != 20:
        raise ValueError("depot file content SHA-1 must be exactly 20 bytes")
    return {
        "filename": _safe_manifest_name(bytes(_first(fields, 1, b""))),
        "size": int(_first(fields, 2, 0)),
        "flags": int(_first(fields, 3, 0)),
        "sha_content": content_digest.hex().upper(),
        "chunks": [
            _parse_chunk(bytes(value))
            for number, wire, value in fields
            if number == 6 and wire == 2
        ],
    }


def _parse_metadata(data: bytes) -> dict[str, int]:
    fields = protobuf_fields(data)
    names = {
        1: "depot_id",
        2: "manifest_id",
        3: "creation_time",
        4: "filenames_encrypted",
        5: "disk_original_bytes",
        6: "disk_compressed_bytes",
        7: "unique_chunks",
        8: "encrypted_crc",
        9: "clear_crc",
    }
    return {
        names[number]: int(value)
        for number, _wire, value in fields
        if number in names
    }


def parse_depot_manifest(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) < 16:
        raise ValueError("truncated depot manifest")
    payload_magic, payload_length = struct.unpack_from("<II", data, 0)
    if payload_magic != PAYLOAD_MAGIC:
        raise ValueError(f"unexpected depot payload magic 0x{payload_magic:08X}")
    payload_end = 8 + payload_length
    if payload_end + 8 > len(data):
        raise ValueError("truncated depot payload or metadata header")
    metadata_magic, metadata_length = struct.unpack_from("<II", data, payload_end)
    if metadata_magic != METADATA_MAGIC:
        raise ValueError(f"unexpected depot metadata magic 0x{metadata_magic:08X}")
    metadata_start = payload_end + 8
    metadata_end = metadata_start + metadata_length
    if metadata_end > len(data):
        raise ValueError("truncated depot metadata")
    metadata = _parse_metadata(data[metadata_start:metadata_end])
    if metadata.get("filenames_encrypted", 0):
        raise ValueError("encrypted depot filenames are not supported")

    payload = protobuf_fields(data[8:payload_end])
    files = [
        _parse_file_mapping(bytes(value))
        for number, wire, value in payload
        if number == 1 and wire == 2
    ]
    folded = [row["filename"].casefold() for row in files]
    if len(folded) != len(set(folded)):
        raise ValueError("depot manifest contains case-insensitive duplicate filenames")
    return {
        "manifest_name": path.name,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest().upper(),
        "payload_length": payload_length,
        "metadata": metadata,
        "trailing_bytes": len(data) - metadata_end,
        "files": files,
    }


def verify_file_entry(path: Path, entry: Mapping[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"requested local input is not a file: {path}")
    actual_size = path.stat().st_size
    expected_size = int(entry["size"])
    chunks = sorted(entry["chunks"], key=lambda row: int(row["offset"]))
    cursor = 0
    coverage_exact = True
    for chunk in chunks:
        offset = int(chunk["offset"])
        size = int(chunk["original_size"])
        if offset != cursor or size < 0:
            coverage_exact = False
        cursor = offset + size
    if chunks:
        coverage_exact = coverage_exact and cursor == expected_size == actual_size
    else:
        coverage_exact = expected_size == actual_size == 0

    failed_chunks: list[dict[str, Any]] = []
    with path.open("rb") as handle:
        for index, chunk in enumerate(chunks):
            offset = int(chunk["offset"])
            size = int(chunk["original_size"])
            handle.seek(offset)
            value = handle.read(size)
            actual = hashlib.sha1(value).hexdigest().upper()
            if len(value) != size or actual != chunk["sha1"]:
                failed_chunks.append(
                    {
                        "index": index,
                        "offset": offset,
                        "bytes": size,
                        "expected_sha1": chunk["sha1"],
                        "actual_sha1": actual,
                        "bytes_read": len(value),
                    }
                )

    actual_sha1 = _sha1_file(path)
    result = {
        "local_name": path.name,
        "bytes": actual_size,
        "sha256": _sha256_file(path),
        "sha1": actual_sha1,
        "manifest_bytes": expected_size,
        "manifest_sha1": entry["sha_content"],
        "size_matches": actual_size == expected_size,
        "sha1_matches": actual_sha1 == entry["sha_content"],
        "chunk_count": len(chunks),
        "chunk_coverage_exact": coverage_exact,
        "failed_chunks": failed_chunks,
    }
    result["content_matches_manifest"] = all(
        (
            result["size_matches"],
            result["sha1_matches"],
            result["chunk_coverage_exact"],
            not failed_chunks,
        )
    )
    return result


def verify_named_files(
    manifest_path: Path, named_paths: Mapping[str, Path]
) -> dict[str, Any]:
    requested = [name.replace("\\", "/") for name in named_paths]
    folded = [name.casefold() for name in requested]
    if len(folded) != len(set(folded)):
        raise ValueError("requested manifest names must be case-insensitively unique")
    manifest = parse_depot_manifest(manifest_path)
    by_name = {str(row["filename"]).casefold(): row for row in manifest["files"]}
    verified: list[dict[str, Any]] = []
    missing: list[str] = []
    for requested_name, path in zip(requested, named_paths.values()):
        entry = by_name.get(requested_name.casefold())
        if entry is None:
            missing.append(requested_name)
            continue
        row = verify_file_entry(path, entry)
        row["manifest_filename"] = entry["filename"]
        verified.append(row)
    return {
        "schema": "steam-depot-content-check/v1",
        "authentication_scope": "content-map-only; Steam signature not verified",
        "manifest": {key: value for key, value in manifest.items() if key != "files"},
        "manifest_file_count": len(manifest["files"]),
        "verified_files": verified,
        "missing_manifest_entries": missing,
        "all_requested_files_match": (
            not missing
            and len(verified) == len(named_paths)
            and all(row["content_matches_manifest"] for row in verified)
        ),
    }


def _parse_file_argument(value: str) -> tuple[str, Path]:
    try:
        name, raw_path = value.split("=", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("file must be MANIFEST_NAME=LOCAL_PATH") from exc
    if not name or not raw_path:
        raise argparse.ArgumentTypeError("file must be MANIFEST_NAME=LOCAL_PATH")
    return name, Path(raw_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--file", action="append", type=_parse_file_argument, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    pairs = args.file
    names = [name.replace("\\", "/") for name, _path in pairs]
    if len({name.casefold() for name in names}) != len(names):
        parser.error("--file manifest names must be case-insensitively unique")
    result = verify_named_files(args.manifest, dict(pairs))
    encoded = (
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    if args.output is not None:
        write_new_files(
            {args.output: encoded},
            inputs=(args.manifest, *(path for _name, path in pairs)),
        )
    print(encoded.decode("utf-8"), end="")
    return 0 if result["all_requested_files_match"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
