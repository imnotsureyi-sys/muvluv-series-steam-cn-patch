"""Extract a hash-verified selection from an AGE2 FPD package."""

from __future__ import annotations

import argparse
import os
import pathlib
from pathlib import PurePosixPath, PureWindowsPath
import shutil
import tempfile
from typing import Iterable
import zlib

try:
    from .fpd_codec import load_base_keys, make_keys, parse_pack, xor_bytes
except ImportError:  # Direct script execution.
    from fpd_codec import load_base_keys, make_keys, parse_pack, xor_bytes


def safe_path(base: pathlib.Path, name: str) -> pathlib.Path:
    normalized = name.replace("\\", "/")
    posix = PurePosixPath(normalized)
    windows = PureWindowsPath(name)
    if (
        not normalized
        or "\x00" in normalized
        or posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or not posix.parts
        or posix.as_posix() != normalized
        or any(part in ("", ".", "..") for part in posix.parts)
        or any(":" in part for part in posix.parts)
    ):
        raise ValueError(f"unsafe FPD member path: {name!r}")
    return base.joinpath(*posix.parts)


def plan_destinations(
    base: pathlib.Path, entries: Iterable[object]
) -> list[tuple[object, pathlib.Path]]:
    planned: list[tuple[object, pathlib.Path]] = []
    folded_paths: dict[tuple[str, ...], str] = {}
    for entry in entries:
        name = str(getattr(entry, "name"))
        destination = safe_path(base, name)
        folded = tuple(part.casefold() for part in destination.relative_to(base).parts)
        if folded in folded_paths:
            raise ValueError(
                "case-insensitive duplicate FPD destination: "
                f"{folded_paths[folded]!r} and {name!r}"
            )
        folded_paths[folded] = name
        planned.append((entry, destination))
    keys = set(folded_paths)
    for parts, name in folded_paths.items():
        if any(parts[:length] in keys for length in range(1, len(parts))):
            raise ValueError(f"FPD file/directory destination conflict: {name!r}")
    return planned


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=pathlib.Path)
    parser.add_argument("--scrambler", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--contains", default="", help="case-insensitive path filter")
    args = parser.parse_args()
    pack = args.pack.resolve(strict=True)
    scrambler = args.scrambler.resolve(strict=True)
    output = args.output.resolve(strict=False)
    if output in {pack, scrambler}:
        raise FileExistsError("extraction output must not alias an input")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite extraction directory: {output}")

    pack_identity = (pack.stat().st_size, pack.stat().st_mtime_ns)
    keys = make_keys(load_base_keys(scrambler))
    _, data_start, entries = parse_pack(pack, keys)
    selected = [
        entry
        for entry in entries
        if args.contains.casefold() in entry.name.casefold()
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = pathlib.Path(
        tempfile.mkdtemp(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent)
    )
    published = False
    planned: list[tuple[object, pathlib.Path]] = []
    try:
        planned = plan_destinations(staging, selected)
        with pack.open("rb") as stream:
            for entry, destination in planned:
                name, data_off, data_len, full_len = entry
                stream.seek(data_start + data_off)
                stored = stream.read(data_len)
                if len(stored) != data_len:
                    raise RuntimeError(f"short read for FPD member: {name}")
                data = xor_bytes(stored, keys)
                if full_len:
                    data = zlib.decompress(data)
                    if len(data) != full_len:
                        raise RuntimeError(
                            f"decompressed length mismatch for FPD member: {name}"
                        )
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("xb") as target:
                    target.write(data)
                    target.flush()
                    os.fsync(target.fileno())
        if (pack.stat().st_size, pack.stat().st_mtime_ns) != pack_identity:
            raise RuntimeError("source FPD changed during extraction")
        if output.exists():
            raise FileExistsError(f"refusing to overwrite extraction directory: {output}")
        os.rename(staging, output)
        published = True
    finally:
        if not published:
            shutil.rmtree(staging, ignore_errors=True)

    for _entry, destination in planned:
        print(output / destination.relative_to(staging))

    print(f"extracted={len(selected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
