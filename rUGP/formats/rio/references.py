from __future__ import annotations

import argparse
import json
import mmap
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:
    from .crypto import (
        ENCRYPTED_SIZE_XOR_1,
        ENCRYPTED_SIZE_XOR_2,
        RIO_KEY,
        RioRebuildError,
        decode_encrypted_block,
        encode_extent_offset,
        encode_extent_size,
        encrypted_storage_size,
    )
except ImportError:  # Direct script execution.
    from crypto import (
        ENCRYPTED_SIZE_XOR_1,
        ENCRYPTED_SIZE_XOR_2,
        RIO_KEY,
        RioRebuildError,
        decode_encrypted_block,
        encode_extent_offset,
        encode_extent_size,
        encrypted_storage_size,
    )


U32_MASK = np.uint32(0xFFFFFFFF)


def parse_int(value: str) -> int:
    return int(value, 0)


@dataclass(frozen=True)
class HeaderCandidate:
    offset: int
    plain_size: int


def find_all(data: mmap.mmap, needle: bytes) -> list[int]:
    positions: list[int] = []
    start = 0
    while True:
        position = data.find(needle, start)
        if position < 0:
            return positions
        positions.append(position)
        start = position + 1


def iter_encrypted_header_candidates(
    data: mmap.mmap,
    *,
    minimum_plain_size: int = 1,
    maximum_plain_size: int = 64 * 1024 * 1024,
    chunk_size: int = 32 * 1024 * 1024,
):
    """Yield size-consistent encrypted-block headers at every byte alignment.

    The two four-byte header words encode the same plaintext length in
    different forms.  Splitting the file into the four possible modulo-four
    phases lets NumPy inspect every byte offset without allocating an
    eight-byte sliding window for the whole multi-gigabyte archive.
    """

    if minimum_plain_size < 0 or maximum_plain_size < minimum_plain_size:
        raise RioRebuildError("invalid encrypted-block size range")
    if chunk_size <= 0 or chunk_size % 4:
        raise RioRebuildError("chunk_size must be a positive multiple of four")

    file_size = len(data)
    for start in range(0, file_size, chunk_size):
        core_end = min(file_size, start + chunk_size)
        read_end = min(file_size, core_end + 8)
        view = memoryview(data)[start:read_end]
        try:
            for phase in range(4):
                word_count = (len(view) - phase) // 4
                if word_count < 2:
                    continue
                words = np.frombuffer(view, dtype="<u4", count=word_count, offset=phase)
                first = words[:-1]
                second = words[1:]
                size1 = np.bitwise_not(
                    np.bitwise_xor(first, np.uint32(ENCRYPTED_SIZE_XOR_1))
                )
                size2 = np.right_shift(
                    np.bitwise_xor(second, np.uint32(ENCRYPTED_SIZE_XOR_2)), 3
                )
                mask = (
                    (size1 == size2)
                    & (size1 >= np.uint32(minimum_plain_size))
                    & (size1 <= np.uint32(maximum_plain_size))
                )
                for index in np.flatnonzero(mask):
                    offset = start + phase + int(index) * 4
                    if offset >= core_end:
                        continue
                    plain_size = int(size1[index])
                    if offset + encrypted_storage_size(plain_size) <= file_size:
                        yield HeaderCandidate(offset, plain_size)
        finally:
            view.release()


def scan_volume(
    path: Path,
    pair: bytes,
    *,
    key: int = RIO_KEY,
    maximum_plain_size: int = 64 * 1024 * 1024,
    chunk_size: int = 32 * 1024 * 1024,
) -> dict[str, object]:
    raw_hits: list[int] = []
    encrypted_hits: list[dict[str, object]] = []
    valid_blocks = 0
    candidate_count = 0

    with path.open("rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
        raw_hits = find_all(data, pair)
        for candidate in iter_encrypted_header_candidates(
            data,
            maximum_plain_size=maximum_plain_size,
            chunk_size=chunk_size,
        ):
            candidate_count += 1
            storage_size = encrypted_storage_size(candidate.plain_size)
            raw = data[candidate.offset : candidate.offset + storage_size]
            try:
                block = decode_encrypted_block(raw, key)
            except RioRebuildError:
                continue
            valid_blocks += 1
            positions: list[int] = []
            start = 0
            while True:
                position = block.plaintext.find(pair, start)
                if position < 0:
                    break
                positions.append(position)
                start = position + 1
            if positions:
                encrypted_hits.append(
                    {
                        "block_offset": candidate.offset,
                        "block_offset_hex": f"0x{candidate.offset:X}",
                        "plain_size": candidate.plain_size,
                        "storage_size": storage_size,
                        "pair_positions": positions,
                        "pair_count": len(positions),
                        "plain_prefix_hex": block.plaintext[:16].hex(),
                    }
                )

    return {
        "path": str(path),
        "file_size": path.stat().st_size,
        "candidate_header_count": candidate_count,
        "checksum_valid_encrypted_block_count": valid_blocks,
        "raw_pair_positions": raw_hits,
        "raw_pair_count": len(raw_hits),
        "encrypted_hits": encrypted_hits,
        "encrypted_pair_count": sum(int(item["pair_count"]) for item in encrypted_hits),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Find all raw and checksum-valid encrypted references to one encoded RIO extent pair."
        )
    )
    parser.add_argument("--volume", action="append", required=True)
    parser.add_argument("--unit-size", type=parse_int, required=True)
    parser.add_argument("--target-offset", type=parse_int, required=True)
    parser.add_argument("--target-size", type=parse_int, required=True)
    parser.add_argument("--key", type=parse_int, default=RIO_KEY)
    parser.add_argument("--maximum-plain-size", type=parse_int, default=64 * 1024 * 1024)
    parser.add_argument("--chunk-size", type=parse_int, default=32 * 1024 * 1024)
    parser.add_argument("--output")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    raw_offset = encode_extent_offset(args.target_offset, args.unit_size)
    raw_size = encode_extent_size(args.target_size)
    pair = raw_offset.to_bytes(4, "little") + raw_size.to_bytes(4, "little")
    volumes = [Path(item).resolve() for item in args.volume]
    for path in volumes:
        if not path.is_file():
            raise SystemExit(f"missing volume: {path}")

    report = {
        "schema": 1,
        "target": {
            "logical_offset": args.target_offset,
            "logical_offset_hex": f"0x{args.target_offset:X}",
            "extent_size": args.target_size,
            "unit_size": args.unit_size,
            "raw_offset_hex": f"0x{raw_offset:08X}",
            "raw_size_hex": f"0x{raw_size:08X}",
            "pair_hex": pair.hex(),
        },
        "volumes": [
            scan_volume(
                path,
                pair,
                key=args.key,
                maximum_plain_size=args.maximum_plain_size,
                chunk_size=args.chunk_size,
            )
            for path in volumes
        ],
    }
    report["totals"] = {
        "raw_pair_count": sum(int(item["raw_pair_count"]) for item in report["volumes"]),
        "encrypted_pair_count": sum(
            int(item["encrypted_pair_count"]) for item in report["volumes"]
        ),
        "checksum_valid_encrypted_block_count": sum(
            int(item["checksum_valid_encrypted_block_count"]) for item in report["volumes"]
        ),
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).resolve().write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
