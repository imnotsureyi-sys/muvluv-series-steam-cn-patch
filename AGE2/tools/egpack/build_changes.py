#!/usr/bin/env python3
"""Join reviewed translations to a legal EGPACK extraction manifest.

The public translation authority may contain either the exact source text or
only its SHA-256. The exact `expected_text` used by the optimistic-lock writer
always comes from a freshly exported manifest of the user's own game files.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import os
from pathlib import Path
import re
import tempfile
from typing import Mapping, Sequence

try:
    from AGE2.tools.egpack.repack_egpack import CHANGE_COLUMNS, _normalize_relative_path
except ModuleNotFoundError:  # Direct execution from AGE2/tools/egpack.
    from repack_egpack import CHANGE_COLUMNS, _normalize_relative_path  # type: ignore[no-redef]


SHA256_RE = re.compile(r"[0-9A-Fa-f]{64}\Z")
EMPTY_TEXT_SHA256 = hashlib.sha256(b"").hexdigest().upper()
RECORD_KINDS = {"text", "structural_empty"}


class ChangeBuildError(RuntimeError):
    """A translation cannot be bound to the extracted source exactly."""


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or ())
        if not fields:
            raise ChangeBuildError(f"CSV has no header: {path}")
        if any(not field for field in fields):
            raise ChangeBuildError(f"CSV has an empty header field: {path}")
        duplicates = sorted(
            field for field in set(fields) if fields.count(field) > 1
        )
        if duplicates:
            raise ChangeBuildError(
                f"CSV has duplicate header fields {duplicates}: {path}"
            )
        rows = list(reader)
    for number, row in enumerate(rows, start=2):
        if None in row or any(value is None for value in row.values()):
            raise ChangeBuildError(f"{path}: row {number}: malformed CSV record")
    return fields, rows


def _manifest_index(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    fields, rows = _read_csv(path)
    required = {"relative_path", "id", "slot", "value_sha256", "text"}
    missing = required - set(fields)
    if missing:
        raise ChangeBuildError(f"manifest is missing columns: {sorted(missing)}")
    index: dict[tuple[str, str, str], dict[str, str]] = {}
    for number, row in enumerate(rows, start=2):
        key = (
            _normalize_relative_path(row["relative_path"]),
            row["id"],
            row["slot"],
        )
        if key in index:
            raise ChangeBuildError(f"manifest row {number}: duplicate target {key}")
        source_hash = text_sha256(row["text"])
        if row["value_sha256"].upper() != source_hash:
            raise ChangeBuildError(
                f"manifest row {number}: text/value_sha256 mismatch for {key}"
            )
        index[key] = row
    return index


def _exact_changes(path: Path) -> list[dict[str, str]]:
    fields, rows = _read_csv(path)
    if tuple(fields) != CHANGE_COLUMNS:
        raise ChangeBuildError(
            f"{path}: columns must be exactly {','.join(CHANGE_COLUMNS)}"
        )
    result: list[dict[str, str]] = []
    for row in rows:
        result.append(
            {
                **row,
                "relative_path": _normalize_relative_path(row["relative_path"]),
            }
        )
    return result


def build_changes(
    translations: Path,
    manifest: Path,
    *,
    path_column: str = "egpack",
    id_column: str = "id",
    translation_column: str = "cn_text",
    source_column: str = "jp_text",
    source_hash_column: str = "source_text_sha256",
    slot: str,
    append: Sequence[Path] = (),
    allow_empty: bool = False,
) -> list[dict[str, str]]:
    fields, rows = _read_csv(translations)
    required = {path_column, id_column, translation_column}
    missing = required - set(fields)
    if missing:
        raise ChangeBuildError(f"translation table is missing columns: {sorted(missing)}")
    has_source = source_column in fields
    has_hash = source_hash_column in fields
    has_record_kind = "record_kind" in fields
    if not (has_source or has_hash):
        raise ChangeBuildError(
            f"translation table needs {source_column!r} or {source_hash_column!r}"
        )
    index = _manifest_index(manifest)
    changes: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for number, row in enumerate(rows, start=2):
        relative_path = _normalize_relative_path(row[path_column])
        key = (relative_path, row[id_column], slot)
        if key in seen:
            raise ChangeBuildError(f"translation row {number}: duplicate target {key}")
        seen.add(key)
        source = index.get(key)
        if source is None:
            raise ChangeBuildError(f"translation row {number}: source target not found: {key}")
        source_text = source["text"]
        if has_source and row[source_column] != source_text:
            raise ChangeBuildError(
                f"translation row {number}: exact source text drift for {key}"
            )
        if has_hash:
            expected_hash = row[source_hash_column].upper()
            if not SHA256_RE.fullmatch(expected_hash):
                raise ChangeBuildError(
                    f"translation row {number}: invalid {source_hash_column}"
                )
            if expected_hash != text_sha256(source_text):
                raise ChangeBuildError(
                    f"translation row {number}: source hash drift for {key}"
                )
        replacement = row[translation_column]
        if has_record_kind:
            record_kind = row["record_kind"]
            if record_kind not in RECORD_KINDS:
                raise ChangeBuildError(
                    f"translation row {number}: invalid record_kind {record_kind!r}"
                )
            if record_kind == "structural_empty":
                if source_text or replacement:
                    raise ChangeBuildError(
                        f"translation row {number}: structural_empty must remain an empty no-op for {key}"
                    )
                if has_hash and row[source_hash_column].upper() != EMPTY_TEXT_SHA256:
                    raise ChangeBuildError(
                        f"translation row {number}: structural_empty has a non-empty source hash"
                    )
                continue
            if not source_text:
                raise ChangeBuildError(
                    f"translation row {number}: text record has an empty source for {key}"
                )
            if not replacement:
                raise ChangeBuildError(
                    f"translation row {number}: text record has an empty replacement for {key}"
                )
        if not replacement and not allow_empty:
            raise ChangeBuildError(f"translation row {number}: empty replacement for {key}")
        changes.append(
            {
                "relative_path": relative_path,
                "id": row[id_column],
                "slot": slot,
                "expected_text": source_text,
                "replacement_text": replacement,
            }
        )
    for path in append:
        for row in _exact_changes(path):
            key = (row["relative_path"], row["id"], row["slot"])
            if key in seen:
                raise ChangeBuildError(f"appended duplicate target {key}: {path}")
            source = index.get(key)
            if source is None or source["text"] != row["expected_text"]:
                raise ChangeBuildError(f"appended source drift for {key}: {path}")
            if not row["replacement_text"] and not allow_empty:
                raise ChangeBuildError(f"appended empty replacement for {key}: {path}")
            seen.add(key)
            changes.append(row)
    if not changes:
        raise ChangeBuildError("translation table produced no changes")
    return changes


def csv_bytes(rows: Sequence[Mapping[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHANGE_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


def materialize_output(
    output: Path,
    payload: bytes,
    *,
    inputs: Sequence[Path],
    check: bool = False,
    force: bool = False,
) -> None:
    """Check or safely create one generated changes file.

    Input aliases are always forbidden.  Normal generation exclusively creates
    a new path, so a concurrent writer cannot be overwritten after validation.
    ``force`` uses a same-directory temporary followed by ``os.replace`` and is
    intentionally incompatible with the read-only ``check`` mode.
    """

    if check and force:
        raise ChangeBuildError("--check and --force cannot be used together")
    output_identity = output.resolve(strict=False)
    resolved_inputs = [path.resolve(strict=True) for path in inputs]
    aliases_input = output_identity in set(resolved_inputs)
    if output.exists() and not aliases_input:
        aliases_input = any(os.path.samefile(output, path) for path in resolved_inputs)
    if aliases_input:
        raise ChangeBuildError(f"output must not overwrite an input: {output}")
    if check:
        if not output.is_file() or output.read_bytes() != payload:
            raise ChangeBuildError(f"generated changes file is missing or stale: {output}")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    if not force:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        try:
            descriptor = os.open(output, flags, 0o666)
        except FileExistsError as error:
            raise ChangeBuildError(
                f"refusing to overwrite existing output without --force: {output}"
            ) from error
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            output.unlink(missing_ok=True)
            raise
        return

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=output.parent,
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, output)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("translations", type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--path-column", default="egpack")
    parser.add_argument("--id-column", default="id")
    parser.add_argument("--translation-column", default="cn_text")
    parser.add_argument("--source-column", default="jp_text")
    parser.add_argument("--source-hash-column", default="source_text_sha256")
    parser.add_argument(
        "--slot",
        required=True,
        help="exact EGPACK language field to replace, for example jp",
    )
    parser.add_argument("--append", action="append", default=[], type=Path)
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="atomically replace an existing output; never permits overwriting an input",
    )
    args = parser.parse_args(argv)
    try:
        payload = csv_bytes(
            build_changes(
                args.translations,
                args.manifest,
                path_column=args.path_column,
                id_column=args.id_column,
                translation_column=args.translation_column,
                source_column=args.source_column,
                source_hash_column=args.source_hash_column,
                slot=args.slot,
                append=args.append,
                allow_empty=args.allow_empty,
            )
        )
        materialize_output(
            args.output,
            payload,
            inputs=(args.translations, args.manifest, *args.append),
            check=args.check,
            force=args.force,
        )
        print(f"changes={sum(1 for _ in csv.reader(io.StringIO(payload.decode('utf-8-sig')))) - 1}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
