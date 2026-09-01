#!/usr/bin/env python3
"""Export portable PF/PM translation sources from a sealed CString audit.

The private audit contains full official source strings and workstation paths.
The public tables deliberately retain only stable identities, source hashes,
the localized text, and the exact runtime-writing contract needed to rebuild a
patch from files extracted from a legally obtained game installation.
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
import tempfile
from typing import Iterable, Mapping, Sequence


GAME_SLUGS = {"pf": "photonflowers", "pm": "photonmelodies"}
SOURCE_TO_PUBLIC = {
    "stable_id": "stable_id",
    "rio_file": "rio_file",
    "block_offset": "block_offset",
    "payload_offset": "payload_offset",
    "text_offset": "text_offset",
    "writer_mode": "writer_mode",
    "delimiter": "delimiter",
    "field_sha256": "source_field_sha256",
    "full_cstring_identity_sha256": "source_identity_sha256",
    "final_cn_text": "translation_text",
    "writer_replacement_text": "runtime_text",
    "writer_inline_controls": "inline_controls",
    "allow_control_change": "allow_control_change",
    "control_delta_reason": "control_delta_reason",
    "production_runtime_binding": "runtime_binding",
    "production_native_capacity_units": "native_capacity_units",
    "production_replacement_units": "replacement_units",
    "production_padding_codepoint": "padding_codepoint",
    "production_padding_units": "padding_units",
    "translation_source": "translation_source",
}
PUBLIC_COLUMNS = tuple(SOURCE_TO_PUBLIC.values())
SHA256_RE = re.compile(r"[0-9A-Fa-f]{64}\Z")


class ExportError(RuntimeError):
    """The sealed input or an existing portable output violates the contract."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _portable_csv(rows: Iterable[Mapping[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=PUBLIC_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _csv_record_count(data: bytes) -> int:
    """Count logical CSV rows rather than physical lines inside quoted text."""

    stream = io.StringIO(data.decode("utf-8"), newline="")
    count = sum(1 for _ in csv.reader(stream)) - 1
    if count < 0:
        raise ExportError("portable CSV is missing its header")
    return count


def export_rows(input_path: Path) -> dict[str, bytes]:
    """Return deterministic, game-keyed public CSV bytes."""

    with input_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = set(SOURCE_TO_PUBLIC) - set(reader.fieldnames or ())
        if missing:
            raise ExportError(f"sealed CString audit is missing columns: {sorted(missing)}")
        grouped: dict[str, list[dict[str, str]]] = {game: [] for game in GAME_SLUGS}
        stable_ids: set[str] = set()
        for number, source in enumerate(reader, start=2):
            game = source.get("game", "").strip().lower()
            if game not in grouped:
                raise ExportError(f"row {number}: unsupported game {game!r}")
            stable_id = source["stable_id"]
            if not stable_id or stable_id in stable_ids:
                raise ExportError(f"row {number}: empty or duplicate stable_id {stable_id!r}")
            stable_ids.add(stable_id)
            for name in ("field_sha256", "full_cstring_identity_sha256"):
                if not SHA256_RE.fullmatch(source[name]):
                    raise ExportError(f"row {number}: invalid {name}")
            for name in ("final_cn_text", "writer_replacement_text"):
                if "\x00" in source[name]:
                    raise ExportError(f"row {number}: embedded U+0000 in {name}")
            grouped[game].append({public: source[private] for private, public in SOURCE_TO_PUBLIC.items()})
    if not all(grouped.values()):
        raise ExportError("sealed CString audit must contain both PF and PM rows")
    return {game: _portable_csv(rows) for game, rows in grouped.items()}


def manifest_bytes(
    *,
    source_label: str,
    source_bytes: int,
    source_sha256: str,
    exports: Mapping[str, bytes],
) -> bytes:
    games = {
        GAME_SLUGS[game]: {
            "path": f"rugp/games/{GAME_SLUGS[game]}/translations/zh-Hans.csv",
            "rows": _csv_record_count(data),
            "bytes": len(data),
            "sha256": sha256_bytes(data),
        }
        for game, data in exports.items()
    }
    document = {
        "schema": "muvluv-photon-portable-text-sources/v1",
        "status": "portable_from_sealed_production_audit",
        "locale": "zh-Hans",
        "official_source_text_included": False,
        "source_audit": {
            "logical_name": source_label,
            "bytes": source_bytes,
            "sha256": source_sha256,
        },
        "columns": list(PUBLIC_COLUMNS),
        "games": games,
        "policy": {
            "translation_text": "human-facing localized authority",
            "runtime_text": "exact text consumed by the production writer; may intentionally differ",
            "source_reconstruction": "extract official source text from a legally obtained game and match by stable_id plus hashes",
        },
    }
    return (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


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


def _check_exact(path: Path, expected: bytes) -> None:
    if not path.is_file() or path.read_bytes() != expected:
        raise ExportError(f"portable output is missing or stale: {path}")


def run(
    input_path: Path,
    games_root: Path,
    manifest_path: Path,
    *,
    source_label: str,
    expected_source_sha256: str | None,
    check: bool,
) -> dict[str, object]:
    input_path = input_path.resolve(strict=True)
    source_sha256 = sha256_file(input_path)
    if expected_source_sha256 and source_sha256 != expected_source_sha256.upper():
        raise ExportError(
            f"sealed CString audit hash mismatch: {source_sha256} != {expected_source_sha256.upper()}"
        )
    exports = export_rows(input_path)
    targets = {
        game: games_root / GAME_SLUGS[game] / "translations" / "zh-Hans.csv"
        for game in GAME_SLUGS
    }
    manifest = manifest_bytes(
        source_label=source_label,
        source_bytes=input_path.stat().st_size,
        source_sha256=source_sha256,
        exports=exports,
    )
    if check:
        for game, target in targets.items():
            _check_exact(target, exports[game])
        _check_exact(manifest_path, manifest)
    else:
        for game, target in targets.items():
            _atomic_write(target, exports[game])
        _atomic_write(manifest_path, manifest)
    return {
        "status": "PASS",
        "mode": "check" if check else "write",
        "source_sha256": source_sha256,
        "games": {
            GAME_SLUGS[game]: {
                "rows": _csv_record_count(data),
                "sha256": sha256_bytes(data),
            }
            for game, data in exports.items()
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="sealed production CString audit CSV")
    parser.add_argument("--games-root", type=Path, default=Path("rugp/games"))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("rugp/evidence/photon-text-v1/manifest.json"),
    )
    parser.add_argument(
        "--source-label",
        default="photon-native-cstring-target-audit.production-safe.v1",
    )
    parser.add_argument("--expect-source-sha256")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run(
            args.input,
            args.games_root,
            args.manifest,
            source_label=args.source_label,
            expected_source_sha256=args.expect_source_sha256,
            check=args.check,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
