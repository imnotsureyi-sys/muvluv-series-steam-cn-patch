#!/usr/bin/env python3
"""Export a portable, private-backup-ready Photon project snapshot.

The default mode copies no image resources.  It emits a sanitized production
manifest, portable translation ledgers, a SHA-256/resource inventory, missing
resource report, and copyright/copy-policy classification.

``--copy-candidates`` is the only switch that copies bitmap resources.  Even in
that mode only the *current candidate* files referenced by production_state are
copied.  Raw/display sources, Steam containers, API intermediates, QA files,
and runtime backups are never copied by this tool.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import uuid
from collections import Counter
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Mapping, Sequence


SCHEMA = "muvluv-photon-portable-snapshot/v1"
RESOURCE_INVENTORY_SCHEMA = "muvluv-photon-portable-resource-inventory/v1"
SHA_INVENTORY_SCHEMA = "muvluv-photon-portable-sha256-inventory/v1"
COPYRIGHT_SCHEMA = "muvluv-photon-portable-copyright-classification/v1"
REPORT_SCHEMA = "muvluv-photon-portable-snapshot-report/v1"

WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
WINDOWS_ABSOLUTE_ANYWHERE_RE = re.compile(r"(?<![A-Za-z0-9+.-])[A-Za-z]:[\\/]")
UNC_RE = re.compile(r"^(?:\\\\|//)[^/\\]+[/\\][^/\\]+")

PATH_KEY_EXACT = {
    "asset_list",
    "audit_report",
    "audit_root",
    "candidate",
    "candidate_png",
    "display_source_png",
    "file",
    "font_manifest",
    "manifest",
    "path",
    "qa_path",
    "raw_source_png",
    "root",
    "scope_manifest",
    "source_path",
    "target",
    "visual_review",
}
PATH_KEY_SUFFIXES = (
    "_asset_list",
    "_audit_report",
    "_audit_root",
    "_candidate",
    "_file",
    "_manifest",
    "_path",
    "_png",
    "_report",
    "_root",
    "_target",
    "_visual_review",
)

RESOURCE_FIELDS = (
    (
        "raw_source",
        "raw_source_png",
        "raw_source_png_sha256",
        "official_game_derived_source",
        "never_copy_to_github",
    ),
    (
        "display_source",
        "display_source_png",
        "display_source_png_sha256",
        "official_game_derived_source",
        "never_copy_to_github",
    ),
    (
        "candidate",
        "candidate_png",
        "candidate_png_sha256",
        "localized_derivative_game_visual",
        "explicit_private_lfs_only",
    ),
    (
        "qa",
        "qa_path",
        None,
        "project_generated_qa_metadata",
        "reference_only_default",
    ),
)

TEXT_SUFFIXES = {
    ".csv",
    ".gitattributes",
    ".gitignore",
    ".json",
    ".jsonl",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
}


class SnapshotError(RuntimeError):
    """Fail-closed snapshot error."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def normalized_relative(value: str) -> str:
    text = value.replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    text = re.sub(r"/+", "/", text)
    parts = [part for part in text.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        return ""
    return "/".join(parts)


def looks_like_url(value: str) -> bool:
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", value))


def looks_absolute_path(value: str) -> bool:
    if not value or looks_like_url(value):
        return False
    if WINDOWS_ABSOLUTE_RE.match(value) or UNC_RE.match(value):
        return True
    return PurePosixPath(value).is_absolute()


def key_is_path_hint(key: str | None) -> bool:
    if not key:
        return False
    lowered = key.lower()
    return lowered in PATH_KEY_EXACT or lowered.endswith(PATH_KEY_SUFFIXES)


def is_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def resolve_resource_path(value: str, workspace_root: Path) -> Path:
    if WINDOWS_ABSOLUTE_RE.match(value) or UNC_RE.match(value):
        return Path(value).resolve(strict=False)
    if PurePosixPath(value).is_absolute():
        return Path(value).resolve(strict=False)
    return (workspace_root / Path(value.replace("/", os.sep))).resolve(strict=False)


def logical_path_ref(value: str, workspace_root: Path) -> str:
    """Map a filesystem value to a non-absolute, non-identifying reference."""

    if value.startswith("workspace/") or value.startswith("external/redacted/"):
        return normalized_relative(value)
    if looks_like_url(value):
        return value

    source_path = resolve_resource_path(value, workspace_root)
    if is_under(source_path, workspace_root):
        relative = source_path.relative_to(workspace_root).as_posix()
        return f"workspace/{relative}"

    fingerprint = sha256_bytes(value.encode("utf-8"))[:20]
    suffix = Path(PureWindowsPath(value).name).suffix.lower()
    safe_suffix = suffix if re.fullmatch(r"\.[A-Za-z0-9]{1,10}", suffix) else ""
    return f"external/redacted/{fingerprint}{safe_suffix}"


def replace_workspace_prefix(value: str, workspace_root: Path) -> str:
    result = value
    prefixes = {
        str(workspace_root),
        workspace_root.as_posix(),
        str(workspace_root).replace("\\", "/"),
    }
    for prefix in sorted(prefixes, key=len, reverse=True):
        if prefix:
            result = result.replace(prefix + "\\", "workspace/")
            result = result.replace(prefix + "/", "workspace/")
            if result == prefix:
                result = "workspace"
    if "workspace/" in result:
        head, tail = result.split("workspace/", 1)
        result = head + "workspace/" + tail.replace("\\", "/")
    return result


def sanitize_string(value: str, workspace_root: Path, key: str | None) -> str:
    result = replace_workspace_prefix(value, workspace_root)
    if looks_absolute_path(result):
        return logical_path_ref(result, workspace_root)
    if key_is_path_hint(key) and ("/" in result or "\\" in result):
        return logical_path_ref(result, workspace_root)
    return result


def sanitize_value(value: Any, workspace_root: Path, key: str | None = None) -> Any:
    if isinstance(value, str):
        return sanitize_string(value, workspace_root, key)
    if isinstance(value, list):
        return [sanitize_value(item, workspace_root, key) for item in value]
    if isinstance(value, dict):
        return {
            str(child_key): sanitize_value(child_value, workspace_root, str(child_key))
            for child_key, child_value in value.items()
        }
    return value


def iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)


def absolute_value_count(value: Any) -> int:
    return sum(1 for item in iter_strings(value) if looks_absolute_path(item))


def source_facts(path: Path, workspace_root: Path) -> dict[str, Any]:
    return {
        "logical_ref": logical_path_ref(str(path), workspace_root),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def capture_source_hashes(paths: Mapping[str, Path]) -> dict[str, str]:
    return {name: sha256_file(path) for name, path in paths.items()}


def check_expected_hash(name: str, actual: str, expected: str | None) -> None:
    if expected and actual.upper() != expected.upper():
        raise SnapshotError(
            f"{name} SHA-256 changed: expected {expected.upper()}, got {actual.upper()}"
        )


def portable_ledger_json(source: Path, destination: Path, workspace_root: Path) -> int:
    value = sanitize_value(read_json(source), workspace_root)
    if absolute_value_count(value):
        raise SnapshotError("portable JSON ledger still contains an absolute path")
    write_json(destination, value)
    if isinstance(value, dict) and isinstance(value.get("entries"), list):
        return len(value["entries"])
    if isinstance(value, list):
        return len(value)
    return 0


def portable_ledger_csv(source: Path, destination: Path, workspace_root: Path) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("r", encoding="utf-8-sig", newline="") as input_handle:
        reader = csv.DictReader(input_handle)
        if not reader.fieldnames:
            raise SnapshotError("translation ledger CSV has no header")
        rows = [
            {
                key: sanitize_string(value or "", workspace_root, key)
                for key, value in row.items()
            }
            for row in reader
        ]
    with destination.open("w", encoding="utf-8", newline="") as output_handle:
        writer = csv.DictWriter(
            output_handle,
            fieldnames=reader.fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    text = destination.read_text(encoding="utf-8")
    if WINDOWS_ABSOLUTE_ANYWHERE_RE.search(text) or UNC_RE.search(text):
        raise SnapshotError("portable CSV ledger still contains an absolute path")
    return len(rows)


def file_facts(path: Path, cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cache_key = os.path.normcase(str(path))
    if cache_key in cache:
        return cache[cache_key]
    if not path.is_file():
        facts = {"exists": False, "bytes": None, "sha256": None}
    else:
        facts = {
            "exists": True,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    cache[cache_key] = facts
    return facts


def inspect_resources(
    entries: Sequence[Mapping[str, Any]],
    workspace_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    file_cache: dict[str, dict[str, Any]] = {}

    for entry in entries:
        asset_id = str(entry.get("asset_id") or "")
        game = str(entry.get("game") or "unknown").lower()
        for role, path_field, hash_field, classification, copy_policy in RESOURCE_FIELDS:
            path_value = entry.get(path_field)
            expected_hash = entry.get(hash_field) if hash_field else None
            if not isinstance(path_value, str) or not path_value:
                record = {
                    "asset_id": asset_id,
                    "game": game,
                    "role": role,
                    "logical_ref": None,
                    "exists": False,
                    "bytes": None,
                    "sha256": None,
                    "expected_sha256": expected_hash,
                    "hash_matches_state": None,
                    "classification": classification,
                    "copy_policy": copy_policy,
                    "inside_workspace": None,
                }
                records.append(record)
                missing.append(
                    {
                        "asset_id": asset_id,
                        "game": game,
                        "role": role,
                        "logical_ref": None,
                        "reason": "path_not_recorded",
                    }
                )
                continue

            path = resolve_resource_path(path_value, workspace_root)
            facts = file_facts(path, file_cache)
            actual_hash = facts["sha256"]
            hash_matches = None
            if expected_hash and actual_hash:
                hash_matches = str(expected_hash).upper() == str(actual_hash).upper()
            record = {
                "asset_id": asset_id,
                "game": game,
                "role": role,
                "logical_ref": logical_path_ref(path_value, workspace_root),
                "exists": facts["exists"],
                "bytes": facts["bytes"],
                "sha256": actual_hash,
                "expected_sha256": str(expected_hash).upper() if expected_hash else None,
                "hash_matches_state": hash_matches,
                "classification": classification,
                "copy_policy": copy_policy,
                "inside_workspace": is_under(path, workspace_root),
            }
            records.append(record)
            if not facts["exists"]:
                missing.append(
                    {
                        "asset_id": asset_id,
                        "game": game,
                        "role": role,
                        "logical_ref": record["logical_ref"],
                        "reason": "file_missing",
                    }
                )
    return records, missing, file_cache


def candidate_record_by_asset(
    resource_records: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    return {
        str(record["asset_id"]): record
        for record in resource_records
        if record.get("role") == "candidate"
    }


def copy_candidates(
    entries: Sequence[Mapping[str, Any]],
    records: Sequence[dict[str, Any]],
    workspace_root: Path,
    output_root: Path,
) -> tuple[dict[str, str], int, int]:
    by_asset = candidate_record_by_asset(records)
    refs: dict[str, str] = {}
    copied_hashes: set[str] = set()
    copied_bytes = 0

    bad = [
        record
        for record in by_asset.values()
        if not record.get("exists")
        or not record.get("inside_workspace")
        or record.get("hash_matches_state") is False
    ]
    if bad:
        reason_counts = Counter(
            "missing"
            if not record.get("exists")
            else "outside_workspace"
            if not record.get("inside_workspace")
            else "state_hash_mismatch"
            for record in bad
        )
        raise SnapshotError(
            "candidate copy refused; integrity failures: "
            + ", ".join(f"{key}={value}" for key, value in sorted(reason_counts.items()))
        )

    for entry in entries:
        asset_id = str(entry.get("asset_id") or "")
        source_value = entry.get("candidate_png")
        record = by_asset.get(asset_id)
        if not isinstance(source_value, str) or not record:
            continue
        actual_hash = str(record["sha256"])
        relative = f"assets/candidates/{actual_hash[:2].lower()}/{actual_hash.lower()}.png"
        refs[asset_id] = relative
        record["snapshot_ref"] = relative
        record["copied"] = True
        if actual_hash in copied_hashes:
            continue
        source = resolve_resource_path(source_value, workspace_root)
        destination = output_root / Path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        if sha256_file(destination) != actual_hash:
            raise SnapshotError(f"candidate copy verification failed for asset {asset_id}")
        copied_hashes.add(actual_hash)
        copied_bytes += destination.stat().st_size

    attributes = "assets/candidates/**/*.png filter=lfs diff=lfs merge=lfs -text\n"
    (output_root / ".gitattributes").write_text(
        attributes,
        encoding="utf-8",
        newline="\n",
    )
    return refs, len(copied_hashes), copied_bytes


def resource_summary(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    roles = Counter(str(record.get("role")) for record in records)
    missing = Counter(
        str(record.get("role")) for record in records if not record.get("exists")
    )
    mismatches = Counter(
        str(record.get("role"))
        for record in records
        if record.get("hash_matches_state") is False
    )
    unique_by_role: dict[str, int] = {}
    bytes_by_role: dict[str, int] = {}
    for role in roles:
        role_records = [record for record in records if record.get("role") == role]
        unique = {
            str(record.get("sha256") or record.get("logical_ref"))
            for record in role_records
            if record.get("sha256") or record.get("logical_ref")
        }
        unique_by_role[role] = len(unique)
        bytes_by_role[role] = sum(
            {
                str(record.get("sha256") or record.get("logical_ref")): int(
                    record.get("bytes") or 0
                )
                for record in role_records
                if record.get("sha256") or record.get("logical_ref")
            }.values()
        )
    return {
        "records_by_role": dict(sorted(roles.items())),
        "missing_by_role": dict(sorted(missing.items())),
        "hash_mismatches_by_role": dict(sorted(mismatches.items())),
        "unique_resources_by_role": dict(sorted(unique_by_role.items())),
        "unique_bytes_by_role": dict(sorted(bytes_by_role.items())),
    }


def build_copyright_classification(
    records: Sequence[Mapping[str, Any]],
    copy_candidate_mode: bool,
) -> dict[str, Any]:
    counts = Counter(str(record.get("classification")) for record in records)
    return {
        "schema": COPYRIGHT_SCHEMA,
        "policy": {
            "project_authored_manifest_and_qa": {
                "github_tier": "public_or_private_after_secret_and_path_review",
                "copied_by_default": True,
            },
            "translation_text_mixed_source_target": {
                "github_tier": "private_by_default; public only after copyright decision",
                "copied_by_default": True,
            },
            "localized_derivative_game_visual": {
                "github_tier": "private_lfs_only",
                "copied_by_default": False,
                "copied_in_this_snapshot": copy_candidate_mode,
            },
            "official_game_derived_source": {
                "github_tier": "never_copy_to_github",
                "copied_by_default": False,
                "copied_in_this_snapshot": False,
            },
            "steam_container_or_full_binary": {
                "github_tier": "never_copy_to_github",
                "copied_by_default": False,
                "copied_in_this_snapshot": False,
            },
            "api_intermediate_runtime_backup_and_cache": {
                "github_tier": "offline_encrypted_backup_only",
                "copied_by_default": False,
                "copied_in_this_snapshot": False,
            },
        },
        "resource_record_counts": dict(sorted(counts.items())),
        "explicit_exclusions": [
            "raw_source_png",
            "display_source_png",
            "Steam .rio/.002 and original EXE/DLL",
            "API request/response intermediate images",
            "runtime session backups",
            "review thumbnails, caches, virtual environments, and failed pilots",
        ],
    }


def list_output_files(root: Path, excluded: set[str] | None = None) -> list[Path]:
    excluded = excluded or set()
    return sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and path.relative_to(root).as_posix() not in excluded
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def scan_text_outputs_for_absolute_paths(root: Path) -> list[dict[str, Any]]:
    leaks: list[dict[str, Any]] = []
    for path in list_output_files(root):
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != ".gitattributes":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if WINDOWS_ABSOLUTE_ANYWHERE_RE.search(line) or UNC_RE.search(line.strip()):
                leaks.append(
                    {
                        "file": path.relative_to(root).as_posix(),
                        "line": line_number,
                        "kind": "windows_or_unc_absolute_path",
                    }
                )
            stripped = line.strip()
            if stripped.startswith("/") and not stripped.startswith("//"):
                leaks.append(
                    {
                        "file": path.relative_to(root).as_posix(),
                        "line": line_number,
                        "kind": "posix_absolute_path",
                    }
                )
    return leaks


def make_markdown_report(report: Mapping[str, Any]) -> str:
    resources = report["resources"]
    lines = [
        "# Portable Photon snapshot report",
        "",
        f"- Snapshot ID: `{report['snapshot_id']}`",
        f"- Source production entries: {report['production_entries']}",
        f"- Translation ledger entries: {report['translation_ledger_entries']}",
        f"- Candidate copy mode: `{str(report['copy_candidates']).lower()}`",
        f"- Unique candidates copied: {report['unique_candidates_copied']}",
        f"- Candidate bytes copied: {report['candidate_bytes_copied']}",
        f"- Missing resource records: {report['missing_resource_records']}",
        f"- Candidate hash mismatches: {report['candidate_hash_mismatches']}",
        f"- Absolute path leaks: {report['absolute_path_leaks']}",
        f"- Source inputs unchanged: `{str(report['source_inputs_unchanged']).lower()}`",
        "",
        "## Resource summary",
        "",
        "| Role | Records | Unique | Unique bytes | Missing | Hash mismatch | Copied policy |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for role in sorted(resources["records_by_role"]):
        copy_policy = {
            "candidate": "explicit private LFS only",
            "raw_source": "never",
            "display_source": "never",
            "qa": "reference only",
        }.get(role, "reference only")
        lines.append(
            "| {role} | {records} | {unique} | {bytes_} | {missing} | {mismatch} | {policy} |".format(
                role=role,
                records=resources["records_by_role"].get(role, 0),
                unique=resources["unique_resources_by_role"].get(role, 0),
                bytes_=resources["unique_bytes_by_role"].get(role, 0),
                missing=resources["missing_by_role"].get(role, 0),
                mismatch=resources["hash_mismatches_by_role"].get(role, 0),
                policy=copy_policy,
            )
        )
    lines.extend(
        [
            "",
            "This snapshot intentionally contains no raw/display images, Steam containers,",
            "full official binaries, API intermediates, runtime backups, or review caches.",
            "",
        ]
    )
    return "\n".join(lines)


def export_snapshot(
    *,
    workspace_root: Path,
    production_state_path: Path,
    ledger_json_path: Path,
    ledger_csv_path: Path,
    output_path: Path,
    copy_candidate_files: bool = False,
    expected_state_sha256: str | None = None,
    expected_ledger_json_sha256: str | None = None,
    expected_ledger_csv_sha256: str | None = None,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve(strict=True)
    production_state_path = production_state_path.resolve(strict=True)
    ledger_json_path = ledger_json_path.resolve(strict=True)
    ledger_csv_path = ledger_csv_path.resolve(strict=True)
    output_path = output_path.resolve(strict=False)

    if output_path.exists():
        raise SnapshotError(f"output already exists: {output_path}")
    if not is_under(output_path, workspace_root):
        raise SnapshotError("output must be inside the declared workspace root")

    source_paths = {
        "production_state": production_state_path,
        "translation_ledger_json": ledger_json_path,
        "translation_ledger_csv": ledger_csv_path,
    }
    before_hashes = capture_source_hashes(source_paths)
    check_expected_hash("production_state", before_hashes["production_state"], expected_state_sha256)
    check_expected_hash(
        "translation_ledger_json",
        before_hashes["translation_ledger_json"],
        expected_ledger_json_sha256,
    )
    check_expected_hash(
        "translation_ledger_csv",
        before_hashes["translation_ledger_csv"],
        expected_ledger_csv_sha256,
    )

    source_state = read_json(production_state_path)
    if not isinstance(source_state, dict) or not isinstance(source_state.get("entries"), list):
        raise SnapshotError("production_state must contain an entries array")
    entries: list[Mapping[str, Any]] = source_state["entries"]
    asset_ids = [str(entry.get("asset_id") or "") for entry in entries]
    if not all(asset_ids) or len(asset_ids) != len(set(asset_ids)):
        raise SnapshotError("production_state asset_id values must be non-empty and unique")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.parent / f".{output_path.name}.building-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    if temporary.exists():
        raise SnapshotError("temporary output unexpectedly exists")
    temporary.mkdir(parents=False)

    try:
        ledger_json_out = temporary / "translations/translation_ledger.portable.json"
        ledger_csv_out = temporary / "translations/translation_ledger.portable.csv"
        ledger_json_entries = portable_ledger_json(
            ledger_json_path, ledger_json_out, workspace_root
        )
        ledger_csv_entries = portable_ledger_csv(
            ledger_csv_path, ledger_csv_out, workspace_root
        )
        if ledger_json_entries != ledger_csv_entries:
            raise SnapshotError(
                "translation ledger JSON/CSV entry counts differ: "
                f"{ledger_json_entries} != {ledger_csv_entries}"
            )

        records, missing, _ = inspect_resources(entries, workspace_root)
        summary = resource_summary(records)
        candidate_refs: dict[str, str] = {}
        unique_candidates_copied = 0
        candidate_bytes_copied = 0
        if copy_candidate_files:
            (
                candidate_refs,
                unique_candidates_copied,
                candidate_bytes_copied,
            ) = copy_candidates(entries, records, workspace_root, temporary)

        portable_state = sanitize_value(source_state, workspace_root)
        for entry in portable_state["entries"]:
            asset_id = str(entry.get("asset_id") or "")
            if asset_id in candidate_refs:
                entry["candidate_png"] = candidate_refs[asset_id]
        if absolute_value_count(portable_state):
            raise SnapshotError("sanitized production state still contains absolute path values")

        snapshot_id = (
            "photon-portable-"
            + before_hashes["production_state"][:12].lower()
            + "-"
            + before_hashes["translation_ledger_json"][:8].lower()
        )
        input_facts = {
            name: source_facts(path, workspace_root) for name, path in source_paths.items()
        }
        manifest = {
            "schema": SCHEMA,
            "snapshot_id": snapshot_id,
            "snapshot_time_source": source_state.get("updated_utc")
            or source_state.get("generated_utc"),
            "copy_candidates": copy_candidate_files,
            "input_files": input_facts,
            "translation_ledgers": {
                "json": "translations/translation_ledger.portable.json",
                "csv": "translations/translation_ledger.portable.csv",
                "entries": ledger_json_entries,
            },
            "resource_inventory": "resource_inventory.json",
            "copyright_classification": "copyright_classification.json",
            "missing_resources": "missing_resources.json",
            "resource_summary": summary,
            "production_state": portable_state,
        }
        write_json(temporary / "portable_manifest.json", manifest)
        write_json(
            temporary / "resource_inventory.json",
            {
                "schema": RESOURCE_INVENTORY_SCHEMA,
                "snapshot_id": snapshot_id,
                "resources": records,
                "summary": summary,
            },
        )
        write_json(
            temporary / "missing_resources.json",
            {
                "schema": "muvluv-photon-portable-missing-resources/v1",
                "snapshot_id": snapshot_id,
                "count": len(missing),
                "resources": missing,
            },
        )
        write_json(
            temporary / "copyright_classification.json",
            build_copyright_classification(records, copy_candidate_files),
        )

        after_hashes = capture_source_hashes(source_paths)
        if after_hashes != before_hashes:
            raise SnapshotError("source state or translation ledger changed during export")

        report: dict[str, Any] = {
            "schema": REPORT_SCHEMA,
            "snapshot_id": snapshot_id,
            "production_entries": len(entries),
            "translation_ledger_entries": ledger_json_entries,
            "copy_candidates": copy_candidate_files,
            "unique_candidates_copied": unique_candidates_copied,
            "candidate_bytes_copied": candidate_bytes_copied,
            "missing_resource_records": len(missing),
            "candidate_hash_mismatches": summary["hash_mismatches_by_role"].get(
                "candidate", 0
            ),
            "absolute_path_leaks": 0,
            "source_inputs_unchanged": True,
            "source_sha256_before": before_hashes,
            "source_sha256_after": after_hashes,
            "resources": summary,
            "raw_display_steam_api_files_copied": 0,
        }
        write_json(temporary / "snapshot_report.json", report)
        (temporary / "SNAPSHOT_REPORT.md").write_text(
            make_markdown_report(report),
            encoding="utf-8",
            newline="\n",
        )

        pre_inventory_leaks = scan_text_outputs_for_absolute_paths(temporary)
        if pre_inventory_leaks:
            raise SnapshotError(
                f"absolute path leakage detected in {len(pre_inventory_leaks)} output locations"
            )

        excluded = {"sha256_inventory.json", "SHA256SUMS.txt"}
        exported_files = []
        for path in list_output_files(temporary, excluded):
            exported_files.append(
                {
                    "path": path.relative_to(temporary).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        sha_inventory = {
            "schema": SHA_INVENTORY_SCHEMA,
            "snapshot_id": snapshot_id,
            "source_inputs": input_facts,
            "exported_files": exported_files,
            "resource_summary": summary,
            "source_inputs_unchanged": True,
        }
        write_json(temporary / "sha256_inventory.json", sha_inventory)

        checksum_files = list_output_files(temporary, {"SHA256SUMS.txt"})
        checksums = "".join(
            f"{sha256_file(path)}  {path.relative_to(temporary).as_posix()}\n"
            for path in checksum_files
        )
        (temporary / "SHA256SUMS.txt").write_text(
            checksums,
            encoding="utf-8",
            newline="\n",
        )

        final_hashes = capture_source_hashes(source_paths)
        if final_hashes != before_hashes:
            raise SnapshotError("source state or translation ledger changed before commit")
        final_leaks = scan_text_outputs_for_absolute_paths(temporary)
        if final_leaks:
            raise SnapshotError(
                f"absolute path leakage detected in {len(final_leaks)} final output locations"
            )

        os.replace(temporary, output_path)
        return report
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--production-state", required=True, type=Path)
    parser.add_argument("--ledger-json", required=True, type=Path)
    parser.add_argument("--ledger-csv", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--copy-candidates",
        action="store_true",
        help="Explicitly copy only current candidate PNGs into LFS-ready staging.",
    )
    parser.add_argument("--expected-state-sha256")
    parser.add_argument("--expected-ledger-json-sha256")
    parser.add_argument("--expected-ledger-csv-sha256")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        report = export_snapshot(
            workspace_root=arguments.workspace_root,
            production_state_path=arguments.production_state,
            ledger_json_path=arguments.ledger_json,
            ledger_csv_path=arguments.ledger_csv,
            output_path=arguments.output,
            copy_candidate_files=arguments.copy_candidates,
            expected_state_sha256=arguments.expected_state_sha256,
            expected_ledger_json_sha256=arguments.expected_ledger_json_sha256,
            expected_ledger_csv_sha256=arguments.expected_ledger_csv_sha256,
        )
    except (OSError, ValueError, SnapshotError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
