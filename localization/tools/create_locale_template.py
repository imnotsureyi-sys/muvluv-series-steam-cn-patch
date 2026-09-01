#!/usr/bin/env python3
"""Create a blank, manifest-bound work template for a new target locale.

The input is an existing public translation table, not source-language
authority.  Callers must explicitly identify the stable identity, source hash,
existing localized-text column, and any non-prose context columns to retain.
The existing translation is removed; every output row receives a canonical
``target_locale`` and an empty ``target_text``.
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
from typing import Sequence


OUTPUT_COLUMNS = ("target_locale", "target_text")
SHA256_RE = re.compile(r"[0-9A-Fa-f]{64}\Z")
LOCALE_RE = re.compile(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*\Z")
KNOWN_TEXT_COLUMNS = {
    "cn_text",
    "final_cn_text",
    "native_field_text",
    "replacement_text",
    "runtime_text",
    "source_text",
    "target_text",
    "translation",
    "translated_text",
    "translation_text",
    "writer_replacement_text",
    "zh_cn",
}


class TemplateError(RuntimeError):
    """The requested template cannot be created without unsafe guessing."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def canonical_locale(value: str) -> str:
    """Validate and apply conventional casing to a BCP 47-style tag."""

    if not LOCALE_RE.fullmatch(value):
        raise TemplateError(f"invalid BCP 47-style target locale {value!r}")
    parts = value.split("-")
    canonical = [parts[0].lower()]
    for subtag in parts[1:]:
        if len(subtag) == 4 and subtag.isalpha():
            canonical.append(subtag.title())
        elif len(subtag) == 2 and subtag.isalpha():
            canonical.append(subtag.upper())
        else:
            canonical.append(subtag.lower())
    result = "-".join(canonical)
    folded = result.casefold()
    if (
        folded == "zh"
        or folded == "zh-hans"
        or folded.startswith("zh-hans-")
        or folded in {"zh-cn", "zh-sg"}
        or folded.startswith(("zh-cn-", "zh-sg-"))
    ):
        raise TemplateError(
            f"target locale {result!r} is the repository's existing zh-Hans target"
        )
    return result


def delimiter_for(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix == ".csv":
        return ","
    if suffix == ".tsv":
        return "\t"
    raise TemplateError(f"table must use a .csv or .tsv suffix: {path}")


def _looks_like_text_content(column: str) -> bool:
    folded = column.casefold()
    return (
        folded in KNOWN_TEXT_COLUMNS
        or folded.endswith("_text")
        or folded.endswith("_translation")
        or folded.startswith("localized_")
    )


def _read_rows(
    source_bytes: bytes,
    *,
    delimiter: str,
    identity_column: str,
    source_hash_column: str,
    text_column: str,
    keep_columns: Sequence[str],
) -> tuple[list[str], list[dict[str, str]]]:
    try:
        source_text = source_bytes.decode("utf-8-sig", errors="strict")
    except UnicodeError as exc:
        raise TemplateError(f"input table is not valid UTF-8: {exc}") from exc

    reader = csv.DictReader(io.StringIO(source_text, newline=""), delimiter=delimiter, strict=True)
    fieldnames = list(reader.fieldnames or ())
    if not fieldnames or any(name == "" for name in fieldnames):
        raise TemplateError("input table has no valid header")
    if len(fieldnames) != len(set(fieldnames)):
        raise TemplateError("input table contains duplicate column names")
    reserved = [name for name in OUTPUT_COLUMNS if name in fieldnames]
    if reserved:
        raise TemplateError(f"input already contains reserved output columns: {reserved}")

    mappings = (identity_column, source_hash_column, text_column)
    if len(set(mappings)) != len(mappings):
        raise TemplateError("identity, source-hash and text columns must be distinct")
    requested = list(mappings) + list(keep_columns)
    missing = [name for name in requested if name not in fieldnames]
    if missing:
        raise TemplateError(f"input is missing explicitly requested columns: {missing}")
    if len(keep_columns) != len(set(keep_columns)):
        raise TemplateError("--keep-column values must be unique")
    forbidden_keep = [
        name
        for name in keep_columns
        if name in mappings or name in OUTPUT_COLUMNS or _looks_like_text_content(name)
    ]
    if forbidden_keep:
        raise TemplateError(
            "refusing text-like, reserved, or already-mapped --keep-column values: "
            f"{forbidden_keep}"
        )

    selected = {identity_column, source_hash_column, *keep_columns}
    metadata_columns = [name for name in fieldnames if name in selected]
    output_rows: list[dict[str, str]] = []
    identities: set[str] = set()
    try:
        for row_number, source in enumerate(reader, start=2):
            if None in source or any(value is None for value in source.values()):
                raise TemplateError(f"row {row_number}: malformed delimited record")
            for field, value in source.items():
                if "\x00" in value:
                    raise TemplateError(f"row {row_number}: embedded U+0000 in {field}")

            identity = source[identity_column]
            if identity == "" or identity != identity.strip():
                raise TemplateError(f"row {row_number}: empty or padded stable identity")
            if identity in identities:
                raise TemplateError(f"row {row_number}: duplicate stable identity {identity!r}")
            identities.add(identity)

            source_hash = source[source_hash_column]
            if not SHA256_RE.fullmatch(source_hash):
                raise TemplateError(
                    f"row {row_number}: missing or invalid SHA-256 in {source_hash_column}"
                )

            output = {name: source[name] for name in metadata_columns}
            output["target_locale"] = ""  # filled by create_template_bytes
            output["target_text"] = ""
            output_rows.append(output)
    except csv.Error as exc:
        raise TemplateError(f"malformed input table: {exc}") from exc

    if not output_rows:
        raise TemplateError("input table contains no records")
    return metadata_columns, output_rows


def create_template_bytes(
    source_bytes: bytes,
    *,
    input_delimiter: str,
    output_delimiter: str,
    target_locale: str,
    identity_column: str,
    source_hash_column: str,
    text_column: str,
    keep_columns: Sequence[str],
) -> tuple[bytes, list[str], int, str]:
    """Return deterministic template bytes and its validated schema summary."""

    locale = canonical_locale(target_locale)
    metadata_columns, rows = _read_rows(
        source_bytes,
        delimiter=input_delimiter,
        identity_column=identity_column,
        source_hash_column=source_hash_column,
        text_column=text_column,
        keep_columns=keep_columns,
    )
    columns = [*metadata_columns, *OUTPUT_COLUMNS]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=columns,
        delimiter=output_delimiter,
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        row["target_locale"] = locale
        writer.writerow(row)
    return stream.getvalue().encode("utf-8", errors="strict"), columns, len(rows), locale


def manifest_bytes(
    *,
    input_name: str,
    input_format: str,
    input_bytes: bytes,
    input_columns: Sequence[str],
    output_name: str,
    output_format: str,
    output_bytes: bytes,
    output_columns: Sequence[str],
    rows: int,
    locale: str,
    identity_column: str,
    source_hash_column: str,
    text_column: str,
    keep_columns: Sequence[str],
) -> bytes:
    document = {
        "schema": "muvluv-locale-work-template/v1",
        "status": "working_template_not_writer_input",
        "target_locale": locale,
        "rows": rows,
        "input": {
            "name": input_name,
            "format": input_format,
            "bytes": len(input_bytes),
            "sha256": sha256_bytes(input_bytes),
            "columns": list(input_columns),
            "identity_column": identity_column,
            "source_hash_column": source_hash_column,
            "removed_text_column": text_column,
            "explicitly_kept_columns": list(keep_columns),
        },
        "output": {
            "name": output_name,
            "format": output_format,
            "bytes": len(output_bytes),
            "sha256": sha256_bytes(output_bytes),
            "columns": list(output_columns),
        },
        "safeguards": {
            "existing_translation_included": False,
            "official_source_text_included": False,
            "target_text_initially_blank": True,
            "source_rule": (
                "reconstruct official source text from a legally obtained game and verify "
                "the retained source hash; never use the removed existing translation as source"
            ),
            "writer_rule": (
                "this is a language-work template, not an AGE2 or rUGP writer input"
            ),
        },
    }
    return (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _exclusive_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    except FileExistsError as exc:
        raise TemplateError(f"refusing to overwrite existing output: {path}") from exc
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


def run(
    input_path: Path,
    output_path: Path,
    *,
    target_locale: str,
    identity_column: str,
    source_hash_column: str,
    text_column: str,
    keep_columns: Sequence[str] = (),
    manifest_path: Path | None = None,
) -> dict[str, object]:
    """Create a new blank locale template and deterministic sidecar manifest."""

    input_path = input_path.resolve(strict=True)
    output_path = output_path.resolve(strict=False)
    manifest_path = (
        manifest_path.resolve(strict=False)
        if manifest_path is not None
        else Path(f"{output_path}.manifest.json")
    )
    if len({input_path, output_path, manifest_path}) != 3:
        raise TemplateError("input, output and manifest paths must be distinct")
    if output_path.exists():
        raise TemplateError(f"refusing to overwrite existing output: {output_path}")
    if manifest_path.exists():
        raise TemplateError(f"refusing to overwrite existing output: {manifest_path}")

    input_delimiter = delimiter_for(input_path)
    output_delimiter = delimiter_for(output_path)
    try:
        source_bytes = input_path.read_bytes()
    except OSError as exc:
        raise TemplateError(f"cannot read input table: {input_path}: {exc}") from exc
    try:
        source_text = source_bytes.decode("utf-8-sig", errors="strict")
        source_reader = csv.reader(io.StringIO(source_text, newline=""), delimiter=input_delimiter)
        input_columns = next(source_reader)
    except (UnicodeError, csv.Error, StopIteration) as exc:
        raise TemplateError(f"cannot read input header: {exc}") from exc

    output_bytes, output_columns, rows, locale = create_template_bytes(
        source_bytes,
        input_delimiter=input_delimiter,
        output_delimiter=output_delimiter,
        target_locale=target_locale,
        identity_column=identity_column,
        source_hash_column=source_hash_column,
        text_column=text_column,
        keep_columns=keep_columns,
    )
    manifest = manifest_bytes(
        input_name=input_path.name,
        input_format=input_path.suffix.casefold().lstrip("."),
        input_bytes=source_bytes,
        input_columns=input_columns,
        output_name=output_path.name,
        output_format=output_path.suffix.casefold().lstrip("."),
        output_bytes=output_bytes,
        output_columns=output_columns,
        rows=rows,
        locale=locale,
        identity_column=identity_column,
        source_hash_column=source_hash_column,
        text_column=text_column,
        keep_columns=keep_columns,
    )

    created: list[Path] = []
    try:
        _exclusive_write(output_path, output_bytes)
        created.append(output_path)
        _exclusive_write(manifest_path, manifest)
        created.append(manifest_path)
    except Exception:
        for path in reversed(created):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        raise

    return {
        "schema": "muvluv-locale-work-template/v1",
        "status": "PASS",
        "target_locale": locale,
        "rows": rows,
        "output": output_path.name,
        "output_sha256": sha256_bytes(output_bytes),
        "manifest": manifest_path.name,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--target-locale", required=True)
    parser.add_argument("--identity-column", required=True)
    parser.add_argument("--source-hash-column", required=True)
    parser.add_argument("--text-column", required=True)
    parser.add_argument(
        "--keep-column",
        action="append",
        default=[],
        help="non-prose context/metadata column to retain; repeat as needed",
    )
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        report = run(
            args.input,
            args.output,
            target_locale=args.target_locale,
            identity_column=args.identity_column,
            source_hash_column=args.source_hash_column,
            text_column=args.text_column,
            keep_columns=args.keep_column,
            manifest_path=args.manifest,
        )
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
