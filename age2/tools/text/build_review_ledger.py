#!/usr/bin/env python3
"""Project private text audits into a public, text-free review ledger."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Mapping, Sequence


class LedgerError(RuntimeError):
    """An audit row cannot be bound to the reviewed public authority."""


OUTPUT_COLUMNS = (
    "game",
    "call_order",
    "id",
    "egpack",
    "scene",
    "source_text_sha256",
    "audit_categories",
    "review_status",
)
TRANSLATION_REQUIRED = {
    "call_order",
    "id",
    "egpack",
    "scene",
    "source_text_sha256",
    "cn_text",
}
AUDIT_REQUIRED = {
    "chapter",
    "call_order",
    "id",
    "egpack",
    "scene",
    "jp_text",
    "cn_text",
}
SHA256_RE = re.compile(r"[0-9A-F]{64}\Z")
CHAPTER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
SKIPPED_FINDINGS = {"inner_double_corner_quote_preserved"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]], bytes]:
    payload = path.read_bytes()
    try:
        decoded = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise LedgerError(f"CSV is not valid UTF-8: {path.name}") from exc
    with io.StringIO(decoded, newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or ())
        rows = list(reader)
    if not fields:
        raise LedgerError(f"CSV has no header: {path}")
    if any(not field for field in fields):
        raise LedgerError(f"CSV has an empty header field: {path}")
    duplicates = sorted(field for field in set(fields) if fields.count(field) > 1)
    if duplicates:
        raise LedgerError(f"CSV has duplicate header fields {duplicates}: {path}")
    for number, row in enumerate(rows, start=2):
        if None in row or any(value is None for value in row.values()):
            raise LedgerError(f"{path}: row {number}: malformed CSV record")
    return fields, rows, payload


def _translation_index(
    translations: Mapping[str, Path],
) -> tuple[dict[tuple[str, str, str], dict[str, str]], dict[str, dict[str, object]]]:
    index: dict[tuple[str, str, str], dict[str, str]] = {}
    inputs: dict[str, dict[str, object]] = {}
    for chapter in sorted(translations):
        if not CHAPTER_RE.fullmatch(chapter):
            raise LedgerError(f"unsafe game/chapter label: {chapter!r}")
        path = translations[chapter]
        fields, rows, payload = _read_csv(path)
        missing = TRANSLATION_REQUIRED - set(fields)
        if missing:
            raise LedgerError(f"{path}: missing columns {sorted(missing)}")
        if "jp_text" in fields:
            raise LedgerError(f"{path}: public authority must not contain jp_text")
        for number, row in enumerate(rows, start=2):
            digest = row["source_text_sha256"].upper()
            if not SHA256_RE.fullmatch(digest):
                raise LedgerError(f"{path}: row {number}: invalid source hash")
            key = (chapter, row["egpack"], row["id"])
            if not all(key) or key in index:
                raise LedgerError(f"{path}: row {number}: empty or duplicate identity {key}")
            index[key] = {**row, "source_text_sha256": digest}
        inputs[chapter] = {
            "rows": len(rows),
            "bytes": len(payload),
            "sha256": sha256_bytes(payload),
        }
    return index, inputs


def build_ledger(
    translations: Mapping[str, Path],
    audits: Mapping[str, Path],
) -> tuple[bytes, dict[str, object]]:
    """Return a metadata-only ledger after exact private/public row binding."""

    public, translation_inputs = _translation_index(translations)
    findings: dict[tuple[str, str, str], set[str]] = {}
    audit_inputs: dict[str, dict[str, object]] = {}
    for audit_kind in sorted(audits):
        if not CHAPTER_RE.fullmatch(audit_kind):
            raise LedgerError(f"unsafe audit label: {audit_kind!r}")
        path = audits[audit_kind]
        fields, rows, payload = _read_csv(path)
        missing = AUDIT_REQUIRED - set(fields)
        if missing:
            raise LedgerError(f"{path}: missing columns {sorted(missing)}")
        finding_column = "issue_type" if "issue_type" in fields else "category"
        if finding_column not in fields:
            raise LedgerError(f"{path}: needs issue_type or category")
        for number, row in enumerate(rows, start=2):
            finding = row[finding_column]
            if not finding or not CHAPTER_RE.fullmatch(finding):
                raise LedgerError(f"{path}: row {number}: unsafe finding label")
            key = (row["chapter"], row["egpack"], row["id"])
            authority = public.get(key)
            if authority is None:
                raise LedgerError(f"{path}: row {number}: public identity not found: {key}")
            if row["call_order"] != authority["call_order"] or row["scene"] != authority["scene"]:
                raise LedgerError(f"{path}: row {number}: identity metadata drift: {key}")
            if sha256_bytes(row["jp_text"].encode("utf-8")) != authority["source_text_sha256"]:
                raise LedgerError(f"{path}: row {number}: source hash drift: {key}")
            if row["cn_text"] != authority["cn_text"]:
                raise LedgerError(f"{path}: row {number}: reviewed translation drift: {key}")
            if finding in SKIPPED_FINDINGS:
                continue
            findings.setdefault(key, set()).add(f"{audit_kind}:{finding}")
        audit_inputs[audit_kind] = {
            "rows": len(rows),
            "bytes": len(payload),
            "sha256": sha256_bytes(payload),
        }

    output_rows: list[dict[str, str]] = []
    for key, categories in findings.items():
        authority = public[key]
        output_rows.append(
            {
                "game": key[0],
                "call_order": authority["call_order"],
                "id": key[2],
                "egpack": key[1],
                "scene": authority["scene"],
                "source_text_sha256": authority["source_text_sha256"],
                "audit_categories": ";".join(sorted(categories)),
                "review_status": "pending_manual_review",
            }
        )
    output_rows.sort(key=lambda row: (row["game"].casefold(), int(row["call_order"])))
    if not output_rows:
        raise LedgerError("audits produced no pending findings")

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(output_rows)
    payload = stream.getvalue().encode("utf-8-sig")
    counts: dict[str, int] = {}
    for row in output_rows:
        counts[row["game"]] = counts.get(row["game"], 0) + 1
    report: dict[str, object] = {
        "schema": "age2-text-free-review-ledger/1",
        "rows": len(output_rows),
        "rows_by_game": dict(sorted(counts.items())),
        "output_columns": list(OUTPUT_COLUMNS),
        "output_bytes": len(payload),
        "output_sha256": sha256_bytes(payload),
        "contains_source_or_translation_text": False,
        "translation_inputs": translation_inputs,
        "private_audit_inputs": audit_inputs,
    }
    return payload, report


def write_new_outputs(
    output: Path,
    payload: bytes,
    report_path: Path,
    report: Mapping[str, object],
    *,
    inputs: Sequence[Path],
) -> None:
    """Create each file atomically and roll siblings back on ordinary errors."""

    resolved_inputs = {path.resolve(strict=True) for path in inputs}
    outputs = (output, report_path)
    resolved_outputs = [path.resolve(strict=False) for path in outputs]
    if len(set(resolved_outputs)) != len(resolved_outputs):
        raise LedgerError("ledger and report must resolve to different files")
    aliases_input = any(path in resolved_inputs for path in resolved_outputs) or any(
        output_path.exists()
        and any(os.path.samefile(output_path, input_path) for input_path in inputs)
        for output_path in outputs
    )
    if aliases_input:
        raise LedgerError("output/report must not alias an input")
    if any(path.exists() for path in outputs):
        raise LedgerError("refusing to overwrite existing ledger evidence")

    requested = {
        output: payload,
        report_path: (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    }
    temporaries: list[Path] = []
    published: list[Path] = []
    try:
        for path, data in requested.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
            ) as stream:
                temporary = Path(stream.name)
                temporaries.append(temporary)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError as error:
                raise LedgerError(f"refusing to overwrite existing file: {path}") from error
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


def _mapping(values: Sequence[str], flag: str) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise LedgerError(f"{flag} expects LABEL=PATH")
        label, raw_path = value.split("=", 1)
        if not label or label in result:
            raise LedgerError(f"{flag}: empty or duplicate label {label!r}")
        result[label] = Path(raw_path)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translation", action="append", required=True, metavar="GAME=PATH")
    parser.add_argument("--audit", action="append", required=True, metavar="KIND=PATH")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        translations = _mapping(args.translation, "--translation")
        audits = _mapping(args.audit, "--audit")
        payload, report = build_ledger(translations, audits)
        write_new_outputs(
            args.output,
            payload,
            args.report,
            report,
            inputs=(*translations.values(), *audits.values()),
        )
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
