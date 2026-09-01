#!/usr/bin/env python3
"""Remove bulk official text while preserving an exact source hash contract."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from typing import Sequence


class ExportError(RuntimeError):
    """The source table cannot be converted without losing identity."""


BASE_SOURCE_COLUMNS = (
    "call_order",
    "id",
    "egpack",
    "scene",
    "speaker_jp",
    "jp_text",
    "cn_text",
)
OPTIONAL_REVIEW_COLUMNS = ("review_status", "audit_flags")
RECORD_KIND_TEXT = "text"
RECORD_KIND_STRUCTURAL_EMPTY = "structural_empty"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def portable_bytes(source: Path) -> tuple[bytes, dict[str, object]]:
    original = source.read_bytes()
    try:
        decoded = original.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExportError(f"source table is not valid UTF-8: {source.name}") from exc
    with io.StringIO(decoded, newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or ())
        if tuple(fields) not in {
            BASE_SOURCE_COLUMNS,
            BASE_SOURCE_COLUMNS + OPTIONAL_REVIEW_COLUMNS,
        }:
            raise ExportError(
                "source columns must be the reviewed AGE2 schema, optionally followed by "
                f"{','.join(OPTIONAL_REVIEW_COLUMNS)}; got {','.join(fields)}"
            )
        if "source_text_sha256" in fields:
            raise ExportError(f"source table is already portable: {source}")
        output_fields: list[str] = []
        for field in fields:
            if field == "jp_text":
                output_fields.extend(("source_text_sha256", "record_kind"))
            else:
                output_fields.append(field)
        rows: list[dict[str, str]] = []
        identities: set[tuple[str, str]] = set()
        record_kinds = {RECORD_KIND_TEXT: 0, RECORD_KIND_STRUCTURAL_EMPTY: 0}
        for number, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ExportError(f"row {number}: malformed CSV record")
            identity = (row.get("egpack", ""), row.get("id", ""))
            if not all(identity) or identity in identities:
                raise ExportError(f"row {number}: empty or duplicate identity {identity}")
            identities.add(identity)
            source_text = row.pop("jp_text")
            if source_text:
                if not row["cn_text"]:
                    raise ExportError(
                        f"row {number}: text record has an empty localized value"
                    )
                record_kind = RECORD_KIND_TEXT
            else:
                if row["speaker_jp"] or row["cn_text"]:
                    raise ExportError(
                        f"row {number}: empty jp_text is only valid for a fully empty structural slot"
                    )
                record_kind = RECORD_KIND_STRUCTURAL_EMPTY
            row["source_text_sha256"] = sha256_bytes(source_text.encode("utf-8"))
            row["record_kind"] = record_kind
            record_kinds[record_kind] += 1
            rows.append(row)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=output_fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    payload = output.getvalue().encode("utf-8-sig")
    return payload, {
        "rows": len(rows),
        "source_bytes": len(original),
        "source_sha256": sha256_bytes(original),
        "output_bytes": len(payload),
        "output_sha256": sha256_bytes(payload),
        "bulk_official_dialogue_included": False,
        "removed_source_columns": ["jp_text"],
        "retained_limited_source_context": ["speaker_jp"],
        "record_kinds": record_kinds,
        "output_columns": output_fields,
    }


def write_new_export(
    source: Path,
    output: Path,
    payload: bytes,
    report_path: Path | None,
    report: dict[str, object],
) -> None:
    """Create a portable table and sidecar without replacing prior evidence."""

    output_paths = [output, *((report_path,) if report_path is not None else ())]
    output_identities = [path.resolve(strict=False) for path in output_paths]
    if len(output_identities) != len(set(output_identities)):
        raise ExportError("output and report must resolve to different files")
    requested: dict[Path, bytes] = {output: payload}
    if report_path is not None:
        requested[report_path] = (
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
    source_identity = source.resolve(strict=True)
    if source_identity in output_identities:
        raise ExportError("output/report must not alias the source table")
    existing = [path for path in requested if path.exists()]
    if existing:
        raise ExportError(f"refusing to overwrite existing file: {existing[0]}")

    created: list[Path] = []
    temporaries: list[Path] = []
    try:
        for path, data in requested.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{path.name}.",
                suffix=".tmp",
                dir=path.parent,
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                temporaries.append(temporary)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError as error:
                raise ExportError(f"refusing to overwrite existing file: {path}") from error
            created.append(path)
            temporary.unlink()
            temporaries.remove(temporary)
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    finally:
        for path in temporaries:
            path.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        payload, report = portable_bytes(args.input)
        write_new_export(args.input, args.output, payload, args.report, report)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
