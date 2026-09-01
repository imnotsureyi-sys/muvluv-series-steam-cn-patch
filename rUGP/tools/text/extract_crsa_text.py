#!/usr/bin/env python3
"""Extract read-only CRsa text inventories from a portable RIO catalog.

The command consumes JSON produced by ``rUGP.tools.catalog.rio_inventory`` and
explicit ``DECLARED_NAME=PATH`` bindings for the user's legally installed RIO
volumes.  Inputs are opened read-only.  A local audit CSV may contain source
text; the portable template deliberately contains only stable identities and
hashes, with an empty target-language field.
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
import sys
import tempfile
from typing import Any, Mapping, Sequence, TextIO

from rUGP.formats.rio.crsa import CrsaRebuildError, read_crsa_record
from rUGP.formats.rio.crsa_text import extract_text_slots


GAME_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]*\Z")
SEED_COLUMNS = ("rio_file", "block_offset", "payload_offset")
LOCAL_COLUMNS = (
    "stable_id",
    "game_id",
    "rio_file",
    "logical_path",
    "block_offset",
    "payload_offset",
    "source_end",
    "translation_offset",
    "identity_start",
    "identity_end",
    "slot_kind",
    "extraction_evidence",
    "source_text",
    "source_text_visible",
    "existing_translation_text",
    "source_code_units",
    "control_codes",
    "source_field_sha256",
    "source_identity_sha256",
    "record_sha256",
    "payload_sha256",
)
TEMPLATE_COLUMNS = (
    "stable_id",
    "game_id",
    "rio_file",
    "logical_path",
    "block_offset",
    "payload_offset",
    "source_end",
    "translation_offset",
    "identity_start",
    "identity_end",
    "slot_kind",
    "extraction_evidence",
    "source_code_units",
    "control_codes",
    "source_field_sha256",
    "source_identity_sha256",
    "record_sha256",
    "payload_sha256",
    "target_text",
    "review_status",
)


class CrsaTextExtractError(ValueError):
    """The catalog, volume binding, CRsa record, or output contract is invalid."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _integer(value: str) -> int:
    try:
        result = int(value, 16) if value.lower().startswith("0x") else int(value, 10)
    except ValueError as error:
        raise CrsaTextExtractError(f"invalid integer {value!r}") from error
    if result < 0:
        raise CrsaTextExtractError(f"integer must be non-negative: {value!r}")
    return result


def _visible(text: str) -> str:
    rendered: list[str] = []
    for character in text:
        code = ord(character)
        if code < 0x20 and character not in "\r\n\t":
            rendered.append(f"<{code:02X}>")
        else:
            rendered.append(character)
    return "".join(rendered)


def make_stable_id(
    game_id: str,
    rio_file: str,
    block_offset: int,
    payload_offset: int,
) -> str:
    if not GAME_ID_RE.fullmatch(game_id):
        raise CrsaTextExtractError(
            "--game-id must contain lowercase ASCII letters, digits, or hyphens"
        )
    if not rio_file or any(character in rio_file for character in "\r\n:/\\"):
        raise CrsaTextExtractError(f"invalid declared RIO filename: {rio_file!r}")
    return (
        f"{game_id}:static:{rio_file}:"
        f"{block_offset:010d}:{payload_offset:08d}"
    )


def _load_inventory(path: Path) -> Mapping[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CrsaTextExtractError(f"cannot read inventory JSON {path.name}: {error}") from error
    if not isinstance(document, dict) or not isinstance(document.get("nodes"), list):
        raise CrsaTextExtractError("inventory JSON has no nodes array")
    schema = document.get("schema")
    if schema != "muvluv-rugp-rio-inventory/v1":
        raise CrsaTextExtractError(f"unsupported inventory schema: {schema!r}")
    return document


def _parse_volume_bindings(values: Sequence[str]) -> dict[str, Path]:
    bindings: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise CrsaTextExtractError(
                f"--volume requires DECLARED_NAME=PATH, got {value!r}"
            )
        name, raw_path = value.split("=", 1)
        if not name or not raw_path or name in bindings:
            raise CrsaTextExtractError(f"invalid or duplicate volume binding: {value!r}")
        path = Path(raw_path).resolve(strict=True)
        if not path.is_file():
            raise CrsaTextExtractError(f"volume is not a file: {path.name}")
        bindings[name] = path
    if not bindings:
        raise CrsaTextExtractError("at least one --volume DECLARED_NAME=PATH is required")
    return bindings


def _load_seeds(path: Path | None) -> dict[tuple[str, int], tuple[int, ...]]:
    if path is None:
        return {}
    grouped: dict[tuple[str, int], set[int]] = {}
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not set(SEED_COLUMNS).issubset(reader.fieldnames or ()):
                raise CrsaTextExtractError(
                    f"seed CSV requires columns {','.join(SEED_COLUMNS)}"
                )
            for number, row in enumerate(reader, start=2):
                try:
                    block = _integer(row["block_offset"])
                    payload = _integer(row["payload_offset"])
                except CrsaTextExtractError as error:
                    raise CrsaTextExtractError(f"seed row {number}: {error}") from error
                grouped.setdefault((row["rio_file"], block), set()).add(payload)
    except OSError as error:
        raise CrsaTextExtractError(f"cannot read seed CSV {path.name}: {error}") from error
    return {key: tuple(sorted(values)) for key, values in grouped.items()}


def _csv_bytes(columns: Sequence[str], rows: Sequence[Mapping[str, object]], *, bom: bool) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    encoding = "utf-8-sig" if bom else "utf-8"
    return stream.getvalue().encode(encoding)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
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


def build_rows(
    inventory: Mapping[str, Any],
    volumes: Mapping[str, Path],
    *,
    game_id: str,
    seeds: Mapping[tuple[str, int], Sequence[int]] | None = None,
    limit: int | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[str], int]:
    if not GAME_ID_RE.fullmatch(game_id):
        raise CrsaTextExtractError(
            "--game-id must contain lowercase ASCII letters, digits, or hyphens"
        )
    seeds = seeds or {}
    nodes = [node for node in inventory["nodes"] if node.get("class") == "CRsa"]
    try:
        for node in nodes:
            int(node.get("volume_offset", -1))
            int(node.get("extent", -1))
    except (TypeError, ValueError) as error:
        raise CrsaTextExtractError("CRsa catalog node has a non-integer offset or extent") from error
    nodes.sort(
        key=lambda node: (
            str(node.get("volume", "")),
            int(node.get("volume_offset", -1)),
            str(node.get("logical_path", "")),
        )
    )
    if limit is not None:
        nodes = nodes[:limit]
    if not nodes:
        raise CrsaTextExtractError("inventory contains no selected CRsa nodes")

    local_rows: list[dict[str, object]] = []
    template_rows: list[dict[str, object]] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    used_seed_keys: set[tuple[str, int]] = set()
    for node in nodes:
        rio_file = str(node.get("volume", ""))
        volume = volumes.get(rio_file)
        if volume is None:
            raise CrsaTextExtractError(f"missing --volume binding for {rio_file!r}")
        block_offset = int(node.get("volume_offset", -1))
        extent = int(node.get("extent", -1))
        if block_offset < 0 or extent <= 0 or block_offset + extent > volume.stat().st_size:
            raise CrsaTextExtractError(
                f"catalog extent is outside {rio_file}: offset={block_offset} extent={extent}"
            )
        try:
            record = read_crsa_record(volume, block_offset)
        except (OSError, CrsaRebuildError) as error:
            raise CrsaTextExtractError(
                f"cannot decode CRsa {rio_file}@0x{block_offset:X}: {error}"
            ) from error
        if len(record.record) != extent:
            raise CrsaTextExtractError(
                f"CRsa extent mismatch for {rio_file}@0x{block_offset:X}: "
                f"catalog={extent} decoded={len(record.record)}"
            )
        seed_key = (rio_file, block_offset)
        if seed_key in seeds:
            used_seed_keys.add(seed_key)
        try:
            extracted = extract_text_slots(
                record.plaintext,
                known_text_offsets=seeds.get(seed_key, ()),
            )
        except (UnicodeDecodeError, ValueError) as error:
            raise CrsaTextExtractError(
                f"text scan failed for {rio_file}@0x{block_offset:X}: {error}"
            ) from error
        logical_path = str(node.get("logical_path", ""))
        context = f"{rio_file}@0x{block_offset:X}"
        warnings.extend(f"{context}:{warning}" for warning in extracted.warnings)
        if extracted.ambiguous_ascii_pairs:
            warnings.append(
                f"{context}:ambiguous_ascii_display_pairs="
                f"{len(extracted.ambiguous_ascii_pairs)}"
            )
        record_sha256 = sha256_bytes(record.record)
        payload_sha256 = sha256_bytes(record.plaintext)
        for slot in extracted.slots:
            if not (
                0 <= slot.payload_offset <= slot.source_end <= len(record.plaintext)
                and 0 <= slot.identity_start <= slot.identity_end <= len(record.plaintext)
            ):
                raise AssertionError("text extractor returned an out-of-range slot")
            stable_id = make_stable_id(
                game_id,
                rio_file,
                block_offset,
                slot.payload_offset,
            )
            if stable_id in seen_ids:
                raise CrsaTextExtractError(f"duplicate extracted stable_id: {stable_id}")
            seen_ids.add(stable_id)
            source_raw = record.plaintext[slot.payload_offset : slot.source_end]
            identity_raw = record.plaintext[slot.identity_start : slot.identity_end]
            common: dict[str, object] = {
                "stable_id": stable_id,
                "game_id": game_id,
                "rio_file": rio_file,
                "logical_path": logical_path,
                "block_offset": block_offset,
                "payload_offset": slot.payload_offset,
                "source_end": slot.source_end,
                "translation_offset": "" if slot.translation_offset is None else slot.translation_offset,
                "identity_start": slot.identity_start,
                "identity_end": slot.identity_end,
                "slot_kind": slot.slot_kind,
                "extraction_evidence": slot.evidence,
                "source_code_units": len(source_raw) // 2,
                "control_codes": " ".join(
                    f"U+{code:04X}" for code in sorted(set(slot.control_codes))
                ),
                "source_field_sha256": sha256_bytes(source_raw),
                "source_identity_sha256": sha256_bytes(identity_raw),
                "record_sha256": record_sha256,
                "payload_sha256": payload_sha256,
            }
            local_rows.append(
                {
                    **common,
                    "source_text": slot.source_text,
                    "source_text_visible": _visible(slot.source_text),
                    "existing_translation_text": slot.existing_translation_text,
                }
            )
            template_rows.append(
                {
                    **common,
                    "target_text": "",
                    "review_status": "untranslated",
                }
            )
    unused_seeds = sorted(set(seeds) - used_seed_keys)
    if unused_seeds:
        rendered = ", ".join(f"{rio}@0x{offset:X}" for rio, offset in unused_seeds[:10])
        raise CrsaTextExtractError(f"seed CSV contains records absent from the selected catalog: {rendered}")
    return local_rows, template_rows, warnings, len(nodes)


def run(
    *,
    inventory_path: Path,
    volume_arguments: Sequence[str],
    game_id: str,
    local_output: Path | None,
    template_output: Path | None,
    seed_path: Path | None = None,
    limit: int | None = None,
    expect_slots: int | None = None,
    fail_on_warning: bool = False,
    overwrite: bool = False,
) -> dict[str, object]:
    if expect_slots is not None and expect_slots < 0:
        raise CrsaTextExtractError("expected slot count must be non-negative")
    inventory_path = inventory_path.resolve(strict=True)
    volumes = _parse_volume_bindings(volume_arguments)
    seed_path = seed_path.resolve(strict=True) if seed_path else None
    outputs = [path.resolve() for path in (local_output, template_output) if path]
    if not outputs:
        raise CrsaTextExtractError("request --local-output, --template-output, or both")
    if len(set(outputs)) != len(outputs):
        raise CrsaTextExtractError("local and template outputs must be different files")
    inputs = {inventory_path, *volumes.values()}
    if seed_path:
        inputs.add(seed_path)
    if any(output in inputs for output in outputs):
        raise CrsaTextExtractError("an output must not overwrite an inventory, seed, or RIO input")
    existing = [output.name for output in outputs if output.exists()]
    if existing and not overwrite:
        raise CrsaTextExtractError(
            "refusing to overwrite existing output without --force: "
            + ", ".join(existing)
        )
    inventory = _load_inventory(inventory_path)
    local_rows, template_rows, warnings, records = build_rows(
        inventory,
        volumes,
        game_id=game_id,
        seeds=_load_seeds(seed_path),
        limit=limit,
    )
    actual_slots = len(local_rows)
    if expect_slots is not None and actual_slots != expect_slots:
        raise CrsaTextExtractError(
            f"slot count mismatch: expected {expect_slots}, extracted {actual_slots}"
        )
    if fail_on_warning and warnings:
        raise CrsaTextExtractError(
            f"extraction produced {len(warnings)} warning(s): {warnings[0]}"
        )
    if local_output:
        _atomic_write(local_output.resolve(), _csv_bytes(LOCAL_COLUMNS, local_rows, bom=True))
    if template_output:
        _atomic_write(
            template_output.resolve(),
            _csv_bytes(TEMPLATE_COLUMNS, template_rows, bom=False),
        )
    return {
        "status": "PASS",
        "mode": "read_only_inputs",
        "records": records,
        "slots": actual_slots,
        "expected_slots": expect_slots,
        "fail_on_warning": fail_on_warning,
        "warnings": warnings,
        "local_output": local_output.name if local_output else None,
        "template_output": template_output.name if template_output else None,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument(
        "--volume",
        action="append",
        default=[],
        metavar="DECLARED_NAME=PATH",
        help="bind a catalog volume name to a local file; repeat as needed",
    )
    parser.add_argument("--game-id", required=True, help="stable ID prefix, for example pf or pm")
    parser.add_argument("--local-output", type=Path, help="local audit CSV including source text")
    parser.add_argument(
        "--template-output",
        type=Path,
        help="portable hash-only translation template CSV",
    )
    parser.add_argument(
        "--seeds",
        type=Path,
        help="optional CSV with rio_file,block_offset,payload_offset source anchors",
    )
    parser.add_argument("--limit", type=int, help="maximum CRsa records to inspect")
    parser.add_argument(
        "--expect-slots",
        type=int,
        help="fail unless the extraction produces exactly this many text slots",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="fail before writing outputs if any structural warning is reported",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace existing output CSVs; never permits overwriting an input",
    )
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if args.expect_slots is not None and args.expect_slots < 0:
        parser.error("--expect-slots must be non-negative")
    if not args.local_output and not args.template_output:
        parser.error("request --local-output, --template-output, or both")
    return args


def main(argv: Sequence[str] | None = None, *, stdout: TextIO = sys.stdout) -> int:
    try:
        args = parse_args(argv)
        report = run(
            inventory_path=args.inventory,
            volume_arguments=args.volume,
            game_id=args.game_id,
            local_output=args.local_output,
            template_output=args.template_output,
            seed_path=args.seeds,
            limit=args.limit,
            expect_slots=args.expect_slots,
            fail_on_warning=args.fail_on_warning,
            overwrite=args.force,
        )
    except (OSError, CrsaTextExtractError) as error:
        print(f"extract_crsa_text: error: {error}", file=sys.stderr)
        return 2
    stdout.write(json.dumps(report, ensure_ascii=False, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
