from __future__ import annotations

import argparse
import csv
import hashlib
from collections.abc import Iterator, Sequence
from pathlib import Path
import sys


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from tools.egpack.egpack_codec import (
        LANGUAGE_SLOTS,
        classify_resource,
        extract_control_codes,
        has_manual_newline,
        is_control_only,
        parse_egpack,
    )
except ModuleNotFoundError:  # Direct script execution from tools/egpack.
    from egpack_codec import (  # type: ignore[no-redef]
        LANGUAGE_SLOTS,
        classify_resource,
        extract_control_codes,
        has_manual_newline,
        is_control_only,
        parse_egpack,
    )


MANIFEST_COLUMNS = (
    "relative_path",
    "egpack",
    "resource_kind",
    "file_size",
    "declared_size",
    "record_index",
    "id",
    "id_offset",
    "slot",
    "slot_crc32",
    "field_offset",
    "value_offset",
    "value_length",
    "value_sha256",
    "is_empty",
    "is_control_only",
    "has_manual_newline",
    "control_codes",
    "text",
)


def _input_files(input_path: Path) -> tuple[Path, list[Path]]:
    if input_path.is_file():
        if input_path.suffix.lower() != ".egpack":
            raise ValueError(f"input file is not an .egpack: {input_path}")
        return input_path.parent, [input_path]
    if input_path.is_dir():
        files = sorted(input_path.rglob("*.egpack"))
        if not files:
            raise ValueError(f"no .egpack files found under: {input_path}")
        return input_path, files
    raise FileNotFoundError(input_path)


def manifest_rows(input_path: Path) -> Iterator[dict[str, str | int | bool]]:
    root, files = _input_files(input_path)
    for path in files:
        document = parse_egpack(path)
        relative_path = path.relative_to(root).as_posix()
        for record in document.records:
            resource_kind = classify_resource(path.name, record.text_id)
            for slot in LANGUAGE_SLOTS:
                field = record.slots[slot]
                raw = document.data[field.value_offset : field.value_offset + field.value_length]
                yield {
                    "relative_path": relative_path,
                    "egpack": path.name,
                    "resource_kind": resource_kind,
                    "file_size": len(document.data),
                    "declared_size": document.declared_size,
                    "record_index": record.index,
                    "id": record.text_id,
                    "id_offset": record.id_offset,
                    "slot": slot,
                    "slot_crc32": field.crc32_hex,
                    "field_offset": field.field_offset,
                    "value_offset": field.value_offset,
                    "value_length": field.value_length,
                    "value_sha256": hashlib.sha256(raw).hexdigest(),
                    "is_empty": field.value_length == 0,
                    "is_control_only": is_control_only(field.text),
                    "has_manual_newline": has_manual_newline(field.text),
                    "control_codes": "|".join(extract_control_codes(field.text)),
                    "text": field.text,
                }


def write_manifest(input_path: Path, output_path: Path) -> int:
    rows = list(manifest_rows(input_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="精确导出 EGPACK 的全部语言槽长表。")
    parser.add_argument("input", type=Path, help="单个 EGPACK 文件或包含 EGPACK 的目录")
    parser.add_argument("--output", type=Path, required=True, help="UTF-8 BOM CSV 输出路径")
    args = parser.parse_args(argv)

    count = write_manifest(args.input, args.output)
    print(f"manifest_rows={count} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
