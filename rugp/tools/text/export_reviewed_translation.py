#!/usr/bin/env python3
"""Export a reviewed dialogue table without redistributing official source text.

The historical review CSV is a seven-column comparison table containing the
official Japanese text and the reviewed translation.  The public table keeps
the stable record identity, a SHA-256 commitment to the exact parsed Japanese
field, and the translated text.  It deliberately omits both ``speaker_jp`` and
``jp_text``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Mapping, Sequence


SOURCE_COLUMNS = (
    "call_order",
    "id",
    "rio_file",
    "scene",
    "speaker_jp",
    "jp_text",
    "cn_text",
)
PUBLIC_COLUMNS = (
    "call_order",
    "stable_id",
    "rio_file",
    "scene",
    "source_text_sha256",
    "translated_text",
)
SHA256_RE = re.compile(r"[0-9A-Fa-f]{64}\Z")
GIT_BLOB_RE = re.compile(r"git:([0-9A-Fa-f]{40})\Z")


class ExportError(RuntimeError):
    """The source comparison or existing public output violates the contract."""


def sha256_bytes(data: bytes) -> str:
    """Return the repository's canonical upper-case SHA-256 representation."""

    return hashlib.sha256(data).hexdigest().upper()


def _parse_identity(
    stable_id: str,
    *,
    rio_file: str,
    scene: str,
    row_number: int,
    expected_id_prefix: str | None,
) -> None:
    parts = stable_id.split(":")
    if len(parts) != 5:
        raise ExportError(f"row {row_number}: malformed stable identity {stable_id!r}")
    game, kind, embedded_rio, block, text_offset = parts
    if game not in {"pf", "pm"} or kind != "static":
        raise ExportError(f"row {row_number}: unsupported stable identity {stable_id!r}")
    if expected_id_prefix is not None and game != expected_id_prefix:
        raise ExportError(
            f"row {row_number}: stable identity prefix {game!r} does not match "
            f"expected {expected_id_prefix!r}"
        )
    if embedded_rio != rio_file:
        raise ExportError(
            f"row {row_number}: stable identity RIO {embedded_rio!r} does not match "
            f"rio_file {rio_file!r}"
        )
    if not block.isascii() or not block.isdecimal():
        raise ExportError(f"row {row_number}: non-decimal CRsa block in stable identity")
    if not text_offset.isascii() or not text_offset.isdecimal():
        raise ExportError(f"row {row_number}: non-decimal text offset in stable identity")
    expected_scene = f"crsa:{rio_file}@{int(block)}"
    if scene != expected_scene:
        raise ExportError(
            f"row {row_number}: scene {scene!r} does not match identity "
            f"({expected_scene!r})"
        )


def validate_public_rows(
    rows: Sequence[Mapping[str, str]],
    *,
    expected_id_prefix: str | None = None,
) -> None:
    """Validate the complete semantic contract of public reviewed-text rows."""

    if expected_id_prefix not in {None, "pf", "pm"}:
        raise ExportError(f"unsupported expected identity prefix {expected_id_prefix!r}")
    if not rows:
        raise ExportError("public comparison contains no records")

    stable_ids: set[str] = set()
    required = set(PUBLIC_COLUMNS)
    for row_number, row in enumerate(rows, start=2):
        if set(row) != required:
            raise ExportError(f"row {row_number}: malformed public CSV record")
        if any(not isinstance(row[field], str) for field in PUBLIC_COLUMNS):
            raise ExportError(f"row {row_number}: malformed public CSV record")

        for field in PUBLIC_COLUMNS:
            value = row[field]
            if "\x00" in value:
                raise ExportError(f"row {row_number}: embedded U+0000 in {field}")
            if "\ufffd" in value:
                raise ExportError(
                    f"row {row_number}: Unicode replacement character in {field}"
                )
            if any(
                ord(character) < 0x20 and character not in "\t\r\n"
                for character in value
            ):
                raise ExportError(f"row {row_number}: unsupported C0 control in {field}")

        expected_order = row_number - 1
        if row["call_order"] != str(expected_order):
            raise ExportError(
                f"row {row_number}: call_order must be contiguous canonical decimal; "
                f"expected {expected_order}, got {row['call_order']!r}"
            )
        for field in PUBLIC_COLUMNS[1:]:
            if row[field].strip() == "":
                raise ExportError(f"row {row_number}: empty required field {field}")
        for field in ("stable_id", "rio_file", "scene", "source_text_sha256"):
            if row[field] != row[field].strip():
                raise ExportError(f"row {row_number}: surrounding whitespace in {field}")

        rio_file = row["rio_file"]
        if (
            rio_file in {".", ".."}
            or "/" in rio_file
            or "\\" in rio_file
            or not re.fullmatch(r"[A-Za-z0-9_.-]+\.rio(?:\.\d{3})?", rio_file)
        ):
            raise ExportError(
                f"row {row_number}: unsafe or unsupported rio_file {rio_file!r}"
            )

        stable_id = row["stable_id"]
        if stable_id in stable_ids:
            raise ExportError(f"row {row_number}: duplicate stable identity {stable_id!r}")
        stable_ids.add(stable_id)
        _parse_identity(
            stable_id,
            rio_file=rio_file,
            scene=row["scene"],
            row_number=row_number,
            expected_id_prefix=expected_id_prefix,
        )

        source_hash = row["source_text_sha256"]
        if not SHA256_RE.fullmatch(source_hash) or source_hash != source_hash.upper():
            raise ExportError(
                f"row {row_number}: source_text_sha256 must be 64 upper-case hex digits"
            )


def _read_source_rows(
    source_bytes: bytes,
    *,
    expected_id_prefix: str | None,
    expected_rows: int | None,
) -> list[dict[str, str]]:
    try:
        source_text = source_bytes.decode("utf-8-sig", errors="strict")
    except UnicodeError as exc:
        raise ExportError(f"cannot decode source comparison as UTF-8: {exc}") from exc

    reader = csv.DictReader(io.StringIO(source_text, newline=""), strict=True)
    if tuple(reader.fieldnames or ()) != SOURCE_COLUMNS:
        raise ExportError(
            "source comparison header must be exactly "
            f"{list(SOURCE_COLUMNS)!r}; got {reader.fieldnames!r}"
        )

    public_rows: list[dict[str, str]] = []
    stable_ids: set[str] = set()
    required = ("id", "rio_file", "scene", "jp_text", "cn_text")
    try:
        for row_number, source in enumerate(reader, start=2):
            if None in source or any(value is None for value in source.values()):
                raise ExportError(f"row {row_number}: malformed CSV record")
            for field, value in source.items():
                if "\x00" in value:
                    raise ExportError(f"row {row_number}: embedded U+0000 in {field}")
                if "\ufffd" in value:
                    raise ExportError(f"row {row_number}: Unicode replacement character in {field}")
                if any(ord(character) < 0x20 and character not in "\t\r\n" for character in value):
                    raise ExportError(f"row {row_number}: unsupported C0 control in {field}")

            call_order = source["call_order"]
            expected_order = len(public_rows) + 1
            if call_order != str(expected_order):
                raise ExportError(
                    f"row {row_number}: call_order must be contiguous canonical decimal; "
                    f"expected {expected_order}, got {call_order!r}"
                )
            for field in required:
                if source[field].strip() == "":
                    raise ExportError(f"row {row_number}: empty required field {field}")
            for field in ("id", "rio_file", "scene"):
                if source[field] != source[field].strip():
                    raise ExportError(f"row {row_number}: surrounding whitespace in {field}")

            rio_file = source["rio_file"]
            if (
                rio_file in {".", ".."}
                or "/" in rio_file
                or "\\" in rio_file
                or not re.fullmatch(r"[A-Za-z0-9_.-]+\.rio(?:\.\d{3})?", rio_file)
            ):
                raise ExportError(f"row {row_number}: unsafe or unsupported rio_file {rio_file!r}")

            stable_id = source["id"]
            if stable_id in stable_ids:
                raise ExportError(f"row {row_number}: duplicate stable identity {stable_id!r}")
            stable_ids.add(stable_id)
            _parse_identity(
                stable_id,
                rio_file=rio_file,
                scene=source["scene"],
                row_number=row_number,
                expected_id_prefix=expected_id_prefix,
            )

            source_hash = sha256_bytes(source["jp_text"].encode("utf-8", errors="strict"))
            public_rows.append(
                {
                    "call_order": call_order,
                    "stable_id": stable_id,
                    "rio_file": rio_file,
                    "scene": source["scene"],
                    "source_text_sha256": source_hash,
                    "translated_text": source["cn_text"],
                }
            )
    except csv.Error as exc:
        raise ExportError(f"malformed source CSV: {exc}") from exc

    if not public_rows:
        raise ExportError("source comparison contains no records")
    if expected_rows is not None and len(public_rows) != expected_rows:
        raise ExportError(
            f"source record count mismatch: {len(public_rows)} != {expected_rows}"
        )
    validate_public_rows(public_rows, expected_id_prefix=expected_id_prefix)
    return public_rows


def public_csv_bytes(rows: Sequence[Mapping[str, str]]) -> bytes:
    """Serialize public rows deterministically as UTF-8 with LF record endings."""

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=PUBLIC_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8", errors="strict")


def export_bytes(
    input_path: Path,
    *,
    expected_id_prefix: str | None = None,
    expected_rows: int | None = None,
) -> bytes:
    """Validate one private comparison and return its deterministic public CSV."""

    try:
        source_bytes = input_path.read_bytes()
    except OSError as exc:
        raise ExportError(f"cannot read source comparison: {input_path}: {exc}") from exc
    return export_source_bytes(
        source_bytes,
        expected_id_prefix=expected_id_prefix,
        expected_rows=expected_rows,
    )


def export_source_bytes(
    source_bytes: bytes,
    *,
    expected_id_prefix: str | None = None,
    expected_rows: int | None = None,
) -> bytes:
    """Validate raw comparison bytes and return a deterministic public CSV."""

    rows = _read_source_rows(
        source_bytes,
        expected_id_prefix=expected_id_prefix,
        expected_rows=expected_rows,
    )
    return public_csv_bytes(rows)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _exclusive_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(path, flags, 0o666)
    except FileExistsError as exc:
        raise ExportError(f"refusing to overwrite public review output: {path}") from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def read_git_blob(spec: str, repository: Path) -> bytes:
    """Read one exact Git blob without a shell text pipeline."""

    match = GIT_BLOB_RE.fullmatch(spec)
    if match is None:
        raise ExportError("Git input must be git:<40-hex-object-id>")
    repository = repository.resolve(strict=True)
    result = subprocess.run(
        ["git", "cat-file", "blob", match.group(1).lower()],
        cwd=repository,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ExportError(f"cannot read historical Git blob: {detail or match.group(1)}")
    return result.stdout


def run(
    input_path: Path,
    output_path: Path,
    *,
    expected_source_sha256: str | None = None,
    expected_id_prefix: str | None = None,
    expected_rows: int | None = None,
    check: bool = False,
    force: bool = False,
) -> dict[str, object]:
    """Write or verify one redacted review export and return a compact report."""

    input_path = input_path.resolve(strict=True)
    output_path = output_path.resolve(strict=False)
    if input_path == output_path:
        raise ExportError("input and output paths must be different")
    if expected_id_prefix not in {None, "pf", "pm"}:
        raise ExportError(f"unsupported expected identity prefix {expected_id_prefix!r}")
    if expected_rows is not None and expected_rows <= 0:
        raise ExportError("expected row count must be positive")

    try:
        source_bytes = input_path.read_bytes()
    except OSError as exc:
        raise ExportError(f"cannot read source comparison: {input_path}: {exc}") from exc
    return run_source_bytes(
        source_bytes,
        output_path,
        expected_source_sha256=expected_source_sha256,
        expected_id_prefix=expected_id_prefix,
        expected_rows=expected_rows,
        check=check,
        force=force,
    )


def run_source_bytes(
    source_bytes: bytes,
    output_path: Path,
    *,
    expected_source_sha256: str | None = None,
    expected_id_prefix: str | None = None,
    expected_rows: int | None = None,
    check: bool = False,
    force: bool = False,
) -> dict[str, object]:
    """Write or verify an export from exact in-memory source bytes.

    This entry point is useful when a caller reads a historical Git blob
    directly and must avoid checkout-time line-ending conversion.
    """

    output_path = output_path.resolve(strict=False)
    if expected_id_prefix not in {None, "pf", "pm"}:
        raise ExportError(f"unsupported expected identity prefix {expected_id_prefix!r}")
    if expected_rows is not None and expected_rows <= 0:
        raise ExportError("expected row count must be positive")
    if check and force:
        raise ExportError("check and force modes are mutually exclusive")

    source_sha256 = sha256_bytes(source_bytes)
    if expected_source_sha256 is not None:
        if not SHA256_RE.fullmatch(expected_source_sha256):
            raise ExportError("expected source SHA-256 must contain exactly 64 hex digits")
        if source_sha256 != expected_source_sha256.upper():
            raise ExportError(
                f"source SHA-256 mismatch: {source_sha256} != {expected_source_sha256.upper()}"
            )

    output = export_source_bytes(
        source_bytes,
        expected_id_prefix=expected_id_prefix,
        expected_rows=expected_rows,
    )
    record_count = sum(
        1
        for _ in csv.DictReader(
            io.StringIO(output.decode("utf-8", errors="strict"), newline="")
        )
    )
    if check:
        if not output_path.is_file() or output_path.read_bytes() != output:
            raise ExportError(f"public review output is missing or stale: {output_path}")
    else:
        if force:
            _atomic_write(output_path, output)
        else:
            _exclusive_write(output_path, output)

    return {
        "status": "PASS",
        "mode": "check" if check else "write",
        "records": record_count,
        "source_sha256": source_sha256,
        "output_sha256": sha256_bytes(output),
        "output_bytes": len(output),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        help=(
            "private seven-column review comparison CSV, '-' for exact bytes on stdin, "
            "or git:<40-hex-blob>"
        ),
    )
    parser.add_argument("output", type=Path, help="redacted public review CSV")
    parser.add_argument("--expect-source-sha256")
    parser.add_argument("--expect-id-prefix", choices=("pf", "pm"))
    parser.add_argument("--expect-rows", type=int)
    parser.add_argument(
        "--git-repository",
        type=Path,
        default=Path.cwd(),
        help="repository used with git:<blob>; defaults to the current directory",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify output instead of writing it")
    mode.add_argument(
        "--force",
        action="store_true",
        help="atomically replace an existing output after all validation passes",
    )
    args = parser.parse_args(argv)
    try:
        options = {
            "expected_source_sha256": args.expect_source_sha256,
            "expected_id_prefix": args.expect_id_prefix,
            "expected_rows": args.expect_rows,
            "check": args.check,
            "force": args.force,
        }
        if args.input == "-":
            report = run_source_bytes(sys.stdin.buffer.read(), args.output, **options)
        elif args.input.startswith("git:"):
            report = run_source_bytes(
                read_git_blob(args.input, args.git_repository), args.output, **options
            )
        else:
            report = run(Path(args.input), args.output, **options)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
