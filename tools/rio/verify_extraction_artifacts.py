#!/usr/bin/env python3
"""Verify photonmelodies extraction artifacts listed in extraction_manifest_v2.json."""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path


def resolve_artifact(path: str, repo_root: Path) -> Path:
    artifact_path = Path(path)
    if artifact_path.is_absolute():
        return artifact_path
    return repo_root / artifact_path


def read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def check_equal(name: str, actual: int, expected: int) -> None:
    if actual != expected:
        fail(f"{name}: expected {expected}, got {actual}")
    print(f"OK: {name} = {actual}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    manifest_path = Path(__file__).with_name("extraction_manifest_v2.json")
    repo_root = Path(__file__).resolve().parents[2]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = {
        label: resolve_artifact(path, repo_root)
        for label, path in manifest["artifacts"].items()
    }
    expected = manifest["expected_counts"]

    for label, artifact_path in artifacts.items():
        if not artifact_path.exists():
            fail(f"missing artifact {label}: {artifact_path}")
        print(f"OK: found {label}: {artifact_path}")

    master = read_csv(artifacts["master_table"])
    runtime = read_csv(artifacts["runtime_afhook_table"])
    static = read_csv(artifacts["static_resource_table"])

    runtime_text = [row for row in runtime if row["section"] == "text"]
    runtime_ui = [row for row in runtime if row["section"] == "ui"]

    check_equal("master_rows", len(master), expected["master_rows"])
    if "extraction_table_native" in artifacts:
        extraction_native = read_csv(artifacts["extraction_table_native"])
        check_equal("extraction_table_native_rows", len(extraction_native), expected["extraction_table_native_rows"])
        required = ("chapter", "csv_row", "id", "stable_id", "egpack", "scene", "jp_text")
        check_equal(
            "extraction_table_native_empty_required_fields",
            sum(1 for row in extraction_native for field in required if not row[field]),
            expected["extraction_table_native_empty_required_fields"],
        )
    if "extraction_table_all_known" in artifacts:
        extraction_all = read_csv(artifacts["extraction_table_all_known"])
        check_equal("extraction_table_all_known_rows", len(extraction_all), expected["extraction_table_all_known_rows"])
        required = ("chapter", "csv_row", "id", "stable_id", "egpack", "scene", "jp_text")
        check_equal(
            "extraction_table_all_known_empty_required_fields",
            sum(1 for row in extraction_all for field in required if not row[field]),
            expected["extraction_table_all_known_empty_required_fields"],
        )
    check_equal("runtime_afhook_rows", len(runtime), expected["runtime_afhook_rows"])
    check_equal("runtime_afhook_text_rows", len(runtime_text), expected["runtime_afhook_text_rows"])
    check_equal("runtime_afhook_ui_rows", len(runtime_ui), expected["runtime_afhook_ui_rows"])
    check_equal("static_resource_rows", len(static), expected["static_resource_rows"])

    if "curation_evidence" in static[0]:
        static_evidence = Counter(row["curation_evidence"] for row in static)
        check_equal(
            "static_resource_high_confidence_rows",
            static_evidence["curated_v1_high_confidence"],
            expected["static_resource_high_confidence_rows"],
        )
        check_equal(
            "static_resource_afhook_confirmed_supplement_rows",
            static_evidence["rejected_by_curated_v1_but_exact_afhook_text_match"],
            expected["static_resource_afhook_confirmed_supplement_rows"],
        )

    stable_ids = [row["stable_id"] for row in master]
    check_equal("master_empty_stable_id", sum(not value for value in stable_ids), expected["master_empty_stable_id"])
    check_equal(
        "master_duplicate_stable_id",
        len(stable_ids) - len(set(stable_ids)),
        expected["master_duplicate_stable_id"],
    )
    check_equal("master_empty_jp_text", sum(not row["jp_text"] for row in master), expected["master_empty_jp_text"])
    check_equal(
        "master_empty_locator_scene",
        sum(not row["locator_scene"] for row in master),
        expected["master_empty_locator_scene"],
    )

    runtime_text_scene = sum(bool(row["scene"]) for row in runtime_text)
    runtime_text_segment = sum(row["locator_evidence"] == "unresolved_runtime_segment_between_crsa_anchors" for row in runtime_text)
    check_equal("runtime_text_true_or_inferred_scene", runtime_text_scene, expected["runtime_text_true_or_inferred_scene"])
    check_equal("runtime_text_segment_only", runtime_text_segment, expected["runtime_text_segment_only"])

    if "runtime_segment_index" in artifacts:
        runtime_segment_index = read_csv(artifacts["runtime_segment_index"])
        check_equal("runtime_segment_index_rows", len(runtime_segment_index), expected["runtime_segment_index_rows"])
        check_equal(
            "runtime_segment_index_covered_rows",
            sum(int(row["row_count"]) for row in runtime_segment_index),
            expected["runtime_text_segment_only"],
        )

    if "runtime_only_worklist" in artifacts:
        runtime_only = read_csv(artifacts["runtime_only_worklist"])
        check_equal("runtime_only_worklist_rows", len(runtime_only), expected["runtime_only_worklist_rows"])
        check_equal(
            "runtime_only_worklist_segments",
            len({row["runtime_segment_id"] for row in runtime_only}),
            expected["runtime_only_worklist_segments"],
        )
        check_equal(
            "runtime_only_worklist_duplicate_stable_id",
            len(runtime_only) - len({row["stable_id"] for row in runtime_only}),
            expected["master_duplicate_stable_id"],
        )

    if "translation_worklist" in artifacts:
        worklist = read_csv(artifacts["translation_worklist"])
        check_equal("translation_worklist_rows", len(worklist), expected["translation_worklist_rows"])
        required_locator_fields = ("chapter", "csv_row", "stable_id", "egpack", "locator_scene", "jp_text")
        empty_required = sum(
            1
            for row in worklist
            for field in required_locator_fields
            if not row[field]
        )
        check_equal(
            "translation_worklist_empty_required_locator_fields",
            empty_required,
            expected["translation_worklist_empty_required_locator_fields"],
        )
        check_equal(
            "translation_worklist_duplicate_stable_id",
            len(worklist) - len({row["stable_id"] for row in worklist}),
            expected["master_duplicate_stable_id"],
        )

    if "native_resource_worklist" in artifacts:
        native = read_csv(artifacts["native_resource_worklist"])
        check_equal("native_resource_worklist_rows", len(native), expected["native_resource_worklist_rows"])
        check_equal(
            "native_resource_worklist_scenes",
            len({row["scene"] for row in native}),
            expected["native_resource_worklist_scenes"],
        )
        native_required_fields = ("chapter", "csv_row", "stable_id", "egpack", "scene", "jp_text")
        empty_native_required = sum(
            1
            for row in native
            for field in native_required_fields
            if not row[field]
        )
        check_equal(
            "native_resource_worklist_empty_required_fields",
            empty_native_required,
            expected["native_resource_worklist_empty_required_fields"],
        )
        check_equal(
            "native_resource_worklist_duplicate_stable_id",
            len(native) - len({row["stable_id"] for row in native}),
            expected["native_resource_worklist_duplicate_stable_id"],
        )

        if "native_scene_index" in artifacts:
            native_scene_index = read_csv(artifacts["native_scene_index"])
            check_equal("native_scene_index_rows", len(native_scene_index), expected["native_scene_index_rows"])
            check_equal(
                "native_scene_index_covered_rows",
                sum(int(row["row_count"]) for row in native_scene_index),
                expected["native_scene_index_covered_rows"],
            )

        if "native_speaker_index" in artifacts:
            native_speaker_index = read_csv(artifacts["native_speaker_index"])
            check_equal("native_speaker_index_rows", len(native_speaker_index), expected["native_speaker_index_rows"])
            check_equal(
                "native_speaker_index_covered_rows",
                sum(int(row["row_count"]) for row in native_speaker_index),
                expected["native_speaker_index_covered_rows"],
            )

    if "speaker_coverage" in artifacts:
        speaker_coverage = read_csv(artifacts["speaker_coverage"])
        check_equal("speaker_coverage_rows", len(speaker_coverage), expected["speaker_coverage_rows"])

    if "sqlite_index" in artifacts:
        with sqlite3.connect(artifacts["sqlite_index"]) as connection:
            sqlite_tables = {
                "native_resource_worklist": "sqlite_native_resource_worklist_rows",
                "native_scene_index": "sqlite_native_scene_index_rows",
                "native_speaker_index": "sqlite_native_speaker_index_rows",
                "translation_worklist": "sqlite_translation_worklist_rows",
                "runtime_only_worklist": "sqlite_runtime_only_worklist_rows",
                "runtime_segment_index": "sqlite_runtime_segment_index_rows",
                "speaker_coverage": "sqlite_speaker_coverage_rows",
            }
            for table, expected_key in sqlite_tables.items():
                row_count = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                check_equal(expected_key, row_count, expected[expected_key])

    scene_status = Counter(row["scene_status"] for row in master)
    for status, count in manifest["scene_status_counts"].items():
        check_equal(f"scene_status:{status}", scene_status[status], count)

    if "checksums" in artifacts:
        checksum_path = artifacts["checksums"]
        checked = 0
        for line in checksum_path.read_text(encoding="ascii").splitlines():
            if not line.strip():
                continue
            expected_hash, relative_path = line.split("  ", 1)
            artifact_path = resolve_artifact(relative_path, repo_root)
            if not artifact_path.exists():
                fail(f"missing checksum target: {artifact_path}")
            actual_hash = sha256_file(artifact_path)
            if actual_hash != expected_hash:
                fail(f"sha256 mismatch for {artifact_path}: expected {expected_hash}, got {actual_hash}")
            checked += 1
        print(f"OK: sha256 checksums verified = {checked}")

    if "speaker_jp" not in master[0]:
        fail("master table missing speaker_jp field")
    print(f"OK: speaker_jp field present; populated rows = {sum(bool(row['speaker_jp']) for row in master)}")
    print("OK: photonmelodies extraction artifacts match manifest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
