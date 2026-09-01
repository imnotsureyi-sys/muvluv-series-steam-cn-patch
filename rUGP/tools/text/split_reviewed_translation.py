#!/usr/bin/env python3
"""Split a canonical reviewed Photon CSV into deterministic RIO-file shards."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
from typing import Mapping, Sequence

from rUGP.tools.text.export_reviewed_translation import (
    PUBLIC_COLUMNS,
    ExportError,
    public_csv_bytes,
    validate_public_rows,
)


class SplitError(RuntimeError):
    """The canonical table cannot be split without losing its contract."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def read_rows(payload: bytes) -> list[dict[str, str]]:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise SplitError(f"public table is not canonical UTF-8: {exc}") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    if tuple(reader.fieldnames or ()) != PUBLIC_COLUMNS:
        raise SplitError("public table header does not match the reviewed-text contract")
    rows = list(reader)
    try:
        validate_public_rows(rows)
    except ExportError as exc:
        raise SplitError(f"public table violates the reviewed-text contract: {exc}") from exc
    seen_rio: set[str] = set()
    rio_spellings: dict[str, str] = {}
    current_rio: str | None = None
    for order, row in enumerate(rows, start=1):
        rio_file = row["rio_file"]
        folded = rio_file.casefold()
        previous_spelling = rio_spellings.setdefault(folded, rio_file)
        if previous_spelling != rio_file:
            raise SplitError(
                "case-insensitive RIO/output filename collision: "
                f"{previous_spelling!r} and {rio_file!r}"
            )
        if rio_file != current_rio:
            if rio_file in seen_rio:
                raise SplitError(f"RIO rows are not one contiguous group: {rio_file}")
            seen_rio.add(rio_file)
            current_rio = rio_file
    if public_csv_bytes(rows) != payload:
        raise SplitError("input table is not in canonical deterministic CSV form")
    return rows


def split_payload(payload: bytes) -> tuple[dict[str, bytes], list[dict[str, object]]]:
    rows = read_rows(payload)
    grouped: dict[str, list[Mapping[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["rio_file"], []).append(row)
    files: dict[str, bytes] = {}
    manifest: list[dict[str, object]] = []
    for rio_file, members in grouped.items():
        name = f"{rio_file}.zh-Hans.csv"
        shard = public_csv_bytes(members)
        files[name] = shard
        manifest.append(
            {
                "path": name,
                "rio_file": rio_file,
                "rows": len(members),
                "call_order_first": int(members[0]["call_order"]),
                "call_order_last": int(members[-1]["call_order"]),
                "bytes": len(shard),
                "sha256": sha256_bytes(shard),
            }
        )
    return files, manifest


def combine_shards(payloads: Sequence[bytes]) -> bytes:
    rows: list[dict[str, str]] = []
    for payload in payloads:
        rows.extend(read_rows(payload) if not rows else _read_shard_rows(payload))
    combined = public_csv_bytes(rows)
    read_rows(combined)
    return combined


def _read_shard_rows(payload: bytes) -> list[dict[str, str]]:
    reader = csv.DictReader(
        io.StringIO(payload.decode("utf-8", errors="strict"), newline=""), strict=True
    )
    if tuple(reader.fieldnames or ()) != PUBLIC_COLUMNS:
        raise SplitError("shard header does not match the reviewed-text contract")
    rows = list(reader)
    if not rows:
        raise SplitError("reviewed-text shard is empty")
    return rows


def write_new_directory(directory: Path, files: Mapping[str, bytes]) -> None:
    if directory.exists():
        raise SplitError(f"refusing to reuse output directory: {directory}")
    directory.mkdir(parents=True)
    created: list[Path] = []
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        for name, payload in files.items():
            path = directory / name
            descriptor = os.open(path, flags, 0o666)
            created.append(path)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
    except Exception:
        for path in reversed(created):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        try:
            directory.rmdir()
        except OSError:
            pass
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        source = args.source.resolve(strict=True)
        output = args.output_dir.resolve(strict=False)
        if source == output or source in output.parents:
            raise SplitError("output directory must not contain or alias the source")
        payload = source.read_bytes()
        files, manifest = split_payload(payload)
        if combine_shards([files[row["path"]] for row in manifest]) != payload:
            raise SplitError("shards do not reconstruct the exact canonical input")
        write_new_directory(output, files)
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "source_sha256": sha256_bytes(payload),
                    "source_bytes": len(payload),
                    "rows": sum(int(row["rows"]) for row in manifest),
                    "shards": manifest,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
