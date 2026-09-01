#!/usr/bin/env python3
"""Audit CN/JP/EN binding coverage for the Photon production image set.

This tool is deliberately metadata-only.  It verifies files and hashes in
place, but never copies localized candidates, official Japanese sources, or
official English references into the output snapshot.
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


SCHEMA = "muvluv-photon-locale-binding-audit/v2"
ROUTE_CLOSURE_SCHEMA = "photon-image-routes-1490/v1"
TRANSLATION_ROUTE_KIND = "translation_peer_native_range"
SHARED_ROUTE_KIND = "proven_shared_native_range"
ALLOWED_ROUTE_KINDS = {TRANSLATION_ROUTE_KIND, SHARED_ROUTE_KIND}
SHA256_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
WINDOWS_ABSOLUTE_ANYWHERE_RE = re.compile(r"(?<![A-Za-z0-9+.-])[A-Za-z]:[\\/]")
UNC_RE = re.compile(r"^(?:\\\\|//)[^/\\]+[/\\][^/\\]+")
TEXT_SUFFIXES = {".csv", ".json", ".md", ".txt"}
ENGLISH_BINDING_KEYS = (
    "official_english_source_png",
    "official_en_source_png",
    "english_source_png",
    "english_reference_png",
    "same_state_english_png",
    "same_state_en_png",
)


class BindingAuditError(RuntimeError):
    """Fail-closed audit error."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest().upper()


def sha256_json(value: Any) -> str:
    """Hash JSON metadata using one deterministic, path-independent encoding."""

    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256_text(encoded)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def is_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def looks_absolute(value: str) -> bool:
    return bool(
        WINDOWS_ABSOLUTE_RE.match(value)
        or UNC_RE.match(value)
        or PurePosixPath(value).is_absolute()
    )


def resolve_path(value: str, workspace_root: Path) -> Path:
    if looks_absolute(value):
        return Path(value).resolve(strict=False)
    return (workspace_root / Path(value.replace("/", os.sep))).resolve(strict=False)


def logical_ref(path_or_value: str | Path, workspace_root: Path) -> str:
    value = str(path_or_value)
    path = resolve_path(value, workspace_root)
    if is_under(path, workspace_root):
        return "workspace/" + path.relative_to(workspace_root).as_posix()
    suffix = Path(PureWindowsPath(value).name).suffix.lower()
    if not re.fullmatch(r"\.[A-Za-z0-9]{1,10}", suffix):
        suffix = ""
    return "external/redacted/" + sha256_text(value)[:20].lower() + suffix


def canonical_source_path(
    classification_entry: Mapping[str, Any], canonical_root: Path
) -> Path:
    raw_image = str(classification_entry.get("source", {}).get("raw_image") or "")
    if not raw_image:
        return canonical_root / "__missing_raw_image__"
    normalized = raw_image.replace("\\", "/")
    while normalized.startswith("../"):
        normalized = normalized[3:]
    return (canonical_root / Path(normalized.replace("/", os.sep))).resolve(strict=False)


def file_facts(path: Path, cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    key = os.path.normcase(str(path))
    if key not in cache:
        if path.is_file():
            cache[key] = {
                "exists": True,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        else:
            cache[key] = {"exists": False, "bytes": None, "sha256": None}
    return cache[key]


def expected_matches(actual: str | None, expected: str | None) -> bool | None:
    if not expected or not actual:
        return None
    return actual.upper() == expected.upper()


def source_facts(path: Path, workspace_root: Path) -> dict[str, Any]:
    return {
        "logical_ref": logical_ref(path, workspace_root),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def capture_hashes(paths: Mapping[str, Path]) -> dict[str, str]:
    return {name: sha256_file(path) for name, path in paths.items()}


def check_expected(name: str, actual: str, expected: str | None) -> None:
    if expected and actual.upper() != expected.upper():
        raise BindingAuditError(
            f"{name} SHA-256 changed: expected {expected.upper()}, got {actual.upper()}"
        )


def dimensions(entry: Mapping[str, Any]) -> tuple[Any, Any]:
    source = entry.get("source", {})
    return source.get("width"), source.get("height")


def route_asset_id(value: str) -> str:
    """Return the three-part native asset identity used by route closure.

    Production/classification IDs may append a codec qualifier (for example,
    ``:cr6ti``).  Route closure deliberately keys the actual archive endpoint,
    so the codec is stored in a separate field.  Reject shorter identities and
    normalize only the optional suffix; never guess a different offset.
    """

    parts = value.split(":")
    if len(parts) < 3 or not all(parts[:3]):
        raise BindingAuditError(f"invalid asset identity: {value!r}")
    return ":".join(parts[:3])


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def build_route_id_index(
    entries: Sequence[Mapping[str, Any]], id_key: str, label: str
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for entry in entries:
        value = str(entry.get(id_key) or "")
        if not value:
            raise BindingAuditError(f"{label} contains an empty {id_key}")
        normalized = route_asset_id(value)
        if normalized in result:
            raise BindingAuditError(
                f"{label} has duplicate normalized asset identity: {normalized}"
            )
        result[normalized] = entry
    return result


def _translation_authority_is_proven(authority: Mapping[str, Any]) -> bool:
    slot_map_proof = bool(
        is_sha256(authority.get("slot_map_sha256"))
        and isinstance(authority.get("evidence_count"), int)
        and authority.get("evidence_count", 0) > 0
        and isinstance(authority.get("evidence_sha256"), list)
        and all(is_sha256(value) for value in authority.get("evidence_sha256", []))
        and authority.get("confidence")
        and authority.get("slot_form")
    )
    handoff_proof = bool(
        authority.get("semantic_peer_proven") is True
        and is_sha256(authority.get("route_handoff_v2_sha256"))
    )
    return bool(authority.get("authority")) and (slot_map_proof or handoff_proof)


def _shared_authority_is_proven(authority: Mapping[str, Any]) -> bool:
    evidence = authority.get("evidence")
    return bool(
        authority.get("authority")
        and authority.get("shared_across_locales_proven") is True
        and is_sha256(authority.get("remaining42_manifest_sha256"))
        and is_sha256(authority.get("remaining42_parent_sha256"))
        and is_sha256(authority.get("family_shared_proof_sha256"))
        and is_sha256(authority.get("family_transports_sha256"))
        and isinstance(evidence, Mapping)
        and evidence.get("parent_evidence_id")
        and evidence.get("interpretation")
        and (
            evidence.get("authenticated_parent_plaintext_sha256") is None
            or is_sha256(evidence.get("authenticated_parent_plaintext_sha256"))
        )
        and (
            evidence.get("global_visual_peer_audit_sha256") is None
            or is_sha256(evidence.get("global_visual_peer_audit_sha256"))
        )
    )


def validate_route_closure(
    document: Mapping[str, Any],
    production_entries: Sequence[Mapping[str, Any]],
    expected_count: int,
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Any]]:
    """Validate route authority without relying on filenames or row order."""

    rows = document.get("rows")
    declared_count = document.get("count")
    if not isinstance(rows, list):
        raise BindingAuditError("route closure rows are missing")
    if declared_count != len(rows):
        raise BindingAuditError(
            f"route closure declared count {declared_count!r} != {len(rows)} rows"
        )
    if len(rows) != expected_count:
        raise BindingAuditError(
            f"route closure must contain exactly {expected_count} rows, got {len(rows)}"
        )
    production_by_route_id = build_route_id_index(
        production_entries, "asset_id", "production state"
    )
    route_by_source: dict[str, Mapping[str, Any]] = {}
    ordinals: set[int] = set()
    counts = Counter()
    for row in rows:
        if not isinstance(row, Mapping):
            raise BindingAuditError("route closure contains a non-object row")
        source = str(row.get("source_asset_id") or "")
        target = str(row.get("target_asset_id") or "")
        if not source or not target:
            raise BindingAuditError("route closure has an empty source/target identity")
        source = route_asset_id(source)
        target = route_asset_id(target)
        if source in route_by_source:
            raise BindingAuditError(f"duplicate route source identity: {source}")
        ordinal = row.get("ordinal")
        if not isinstance(ordinal, int) or ordinal < 1 or ordinal in ordinals:
            raise BindingAuditError(f"invalid/duplicate route ordinal: {ordinal!r}")
        ordinals.add(ordinal)
        kind = row.get("route_kind")
        if kind not in ALLOWED_ROUTE_KINDS:
            raise BindingAuditError(f"unsupported route kind for {source}: {kind!r}")
        authority = row.get("route_authority")
        if not isinstance(authority, Mapping):
            raise BindingAuditError(f"route authority missing for {source}")
        if kind == TRANSLATION_ROUTE_KIND:
            if target == source:
                raise BindingAuditError(
                    f"translation target equals Japanese source for {source}"
                )
            if not _translation_authority_is_proven(authority):
                raise BindingAuditError(
                    f"translation route lacks authenticated peer proof for {source}"
                )
            counts["authoritative_translation_peer_routes"] += 1
        else:
            if target != source:
                raise BindingAuditError(
                    f"shared endpoint target differs from source for {source}"
                )
            if not _shared_authority_is_proven(authority):
                raise BindingAuditError(
                    f"shared endpoint lacks authenticated common-parent proof for {source}"
                )
            counts["authoritative_shared_endpoint_routes"] += 1
        if not row.get("source_codec") or not row.get("target_codec"):
            raise BindingAuditError(f"route codec identity missing for {source}")
        target_size = row.get("target_size")
        if not (
            isinstance(target_size, list)
            and len(target_size) == 2
            and all(isinstance(value, int) and value > 0 for value in target_size)
        ):
            raise BindingAuditError(f"route target size is invalid for {source}")
        if not isinstance(row.get("target_kind"), int):
            raise BindingAuditError(f"route target kind is invalid for {source}")
        if not is_sha256(row.get("encoder_record_sha256")):
            raise BindingAuditError(f"route encoder-record hash is invalid for {source}")
        route_by_source[source] = row

    if ordinals != set(range(1, expected_count + 1)):
        raise BindingAuditError("route closure ordinals are not the exact contiguous set")
    production_ids = set(production_by_route_id)
    route_ids = set(route_by_source)
    if production_ids != route_ids:
        missing = sorted(production_ids - route_ids)
        extra = sorted(route_ids - production_ids)
        raise BindingAuditError(
            "route source set differs from production: "
            f"missing={len(missing)} {missing[:3]}, extra={len(extra)} {extra[:3]}"
        )
    counts["authoritative_route_bindings"] = len(route_by_source)
    counts["authoritative_route_source_set_exact"] = True
    counts["route_closure_declared_count"] = declared_count
    counts["route_closure_schema_expected"] = (
        document.get("schema") == ROUTE_CLOSURE_SCHEMA
    )
    return route_by_source, dict(counts)


def native_identity_record(route: Mapping[str, Any]) -> dict[str, Any]:
    """Copy only native identity/hash metadata; omit every materialized path."""

    native_range = route.get("native_range")
    record: dict[str, Any] = {
        "target_asset_id": route.get("target_asset_id"),
        "target_codec": route.get("target_codec"),
        "target_kind": route.get("target_kind"),
        "target_size": route.get("target_size"),
        "official_target_extent": route.get("official_target_extent"),
        "encoder_record_bytes": route.get("encoder_record_bytes"),
        "encoder_record_sha256": route.get("encoder_record_sha256"),
        "native_range_materialized": isinstance(native_range, Mapping),
    }
    if not isinstance(native_range, Mapping):
        record.update(
            {
                "official_exact_span_sha256": None,
                "official_header_sha256": None,
                "byte_level_identity_status": "route_identity_authenticated_exact_span_not_embedded",
                "reason": (
                    "the route closure authenticates the target endpoint, codec, kind, "
                    "geometry and extent; this row does not embed a materialized official "
                    "span/header hash"
                ),
            }
        )
        return record

    physical = native_range.get("physical_target") or {}
    official_span = native_range.get("official_exact_span") or {}
    candidate_prefix = native_range.get("candidate_record_prefix") or {}
    official_tail = native_range.get("official_tail") or {}
    candidate_span = native_range.get("candidate_exact_span") or {}
    rollback = native_range.get("rollback") or {}
    record.update(
        {
            "physical_target": {
                key: physical.get(key)
                for key in (
                    "game",
                    "filename",
                    "offset",
                    "offset_hex",
                    "extent",
                    "clean_volume_bytes",
                    "clean_volume_sha256",
                )
            },
            "official_exact_span": {
                "bytes": official_span.get("bytes"),
                "sha256": official_span.get("sha256"),
            },
            "candidate_record_prefix": {
                "bytes": candidate_prefix.get("bytes"),
                "sha256": candidate_prefix.get("sha256"),
                "header": candidate_prefix.get("header"),
                "complete_self_described_record": candidate_prefix.get(
                    "complete_self_described_record"
                ),
            },
            "official_tail": {
                "bytes": official_tail.get("bytes"),
                "sha256": official_tail.get("sha256"),
            },
            "candidate_exact_span": {
                "bytes": candidate_span.get("bytes"),
                "sha256": candidate_span.get("sha256"),
            },
            "rollback": {
                key: rollback.get(key)
                for key in ("kind", "offset", "extent", "official_span_sha256")
            },
            "official_exact_span_sha256": official_span.get("sha256"),
            # The closure embeds a candidate header object, but does not claim a
            # separate official header hash.  Preserve that distinction.
            "official_header_sha256": None,
            "byte_level_identity_status": "official_exact_span_authenticated",
        }
    )
    return record


def authoritative_route_record(
    route: Mapping[str, Any],
    classification_by_route_id: Mapping[str, Mapping[str, Any]],
    canonical_root: Path,
    workspace_root: Path,
    cache: dict[str, dict[str, Any]],
    route_closure_sha256: str,
    current_candidate_sha256: str | None,
) -> dict[str, Any]:
    target_id = route_asset_id(str(route.get("target_asset_id") or ""))
    target_entry = classification_by_route_id.get(target_id)
    decoded: dict[str, Any]
    if target_entry is None:
        decoded = {
            "status": "official_decoded_png_absent",
            "classification_asset_id": None,
            "logical_ref": None,
            "exists": False,
            "bytes": None,
            "sha256": None,
            "expected_sha256": None,
            "hash_matches_manifest": None,
            "reason": "translation target is absent from the classification/canonical PNG inventory",
        }
    else:
        target_path = canonical_source_path(target_entry, canonical_root)
        facts = file_facts(target_path, cache)
        expected = str(target_entry.get("source_png_sha256") or "").upper() or None
        matches = expected_matches(facts["sha256"], expected)
        if facts["exists"] and expected and matches is False:
            raise BindingAuditError(
                f"official target PNG hash mismatch for {target_id}"
            )
        if facts["exists"] and expected and matches:
            status = "official_decoded_png_verified"
            reason = None
        elif not facts["exists"]:
            status = "official_decoded_png_absent"
            reason = "classification binds the target, but the decoded canonical PNG is absent"
        else:
            status = "official_decoded_png_unhashed"
            reason = "decoded canonical PNG exists without an authenticated manifest hash"
        decoded = {
            "status": status,
            "classification_asset_id": target_entry.get("id"),
            "classification_decision": target_entry.get("decision", {}).get("code"),
            "logical_ref": logical_ref(target_path, workspace_root),
            "exists": facts["exists"],
            "bytes": facts["bytes"],
            "sha256": facts["sha256"],
            "expected_sha256": expected,
            "hash_matches_manifest": matches,
            "reason": reason,
        }

    route_candidate_sha = str(route.get("candidate_sha256") or "").upper() or None
    candidate_status = (
        "matches_current_production_candidate"
        if route_candidate_sha
        and current_candidate_sha256
        and route_candidate_sha == current_candidate_sha256.upper()
        else "historical_route_payload_differs_from_current_candidate"
    )
    authority = route.get("route_authority") or {}
    return {
        "authenticated": True,
        "route_kind": route.get("route_kind"),
        "source_asset_id": route.get("source_asset_id"),
        "target_asset_id": route.get("target_asset_id"),
        "route_closure_sha256": route_closure_sha256,
        "route_authority_sha256": sha256_json(authority),
        "route_authority": authority,
        "native_identity": native_identity_record(route),
        "official_decoded_target_png": decoded,
        "route_candidate_sha256": route_candidate_sha,
        "current_candidate_sha256": current_candidate_sha256,
        "route_candidate_binding_status": candidate_status,
        "release_authorized": route.get("release_authorized") is True,
        "runtime_state": route.get("runtime_state"),
        "blocker": route.get("blocker"),
        "github_copy_policy": "metadata_only_never_copy_official_image_or_native_span",
    }


def english_relation_record(
    source_entry: Mapping[str, Any],
    peer: Mapping[str, Any],
    canonical_root: Path,
    workspace_root: Path,
    cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    peer_path = canonical_source_path(peer, canonical_root)
    facts = file_facts(peer_path, cache)
    source_visual = source_entry.get("visual", {})
    peer_visual = peer.get("visual", {})
    expected = str(peer.get("source_png_sha256") or "").upper() or None
    decision = str(peer.get("decision", {}).get("code") or "")
    record = {
        "asset_id": peer.get("id"),
        "decision": decision,
        "locale_reference": peer_visual.get("locale_reference") is True,
        "logical_ref": logical_ref(peer_path, workspace_root),
        "exists": facts["exists"],
        "bytes": facts["bytes"],
        "sha256": facts["sha256"],
        "expected_sha256": expected,
        "hash_matches_manifest": expected_matches(facts["sha256"], expected),
        "same_dimensions": dimensions(source_entry) == dimensions(peer),
        "same_family": source_visual.get("family_id") == peer_visual.get("family_id"),
        "same_template": source_visual.get("template_id")
        == peer_visual.get("template_id"),
        "same_declared_state": source_visual.get("state") == peer_visual.get("state"),
    }
    record["metadata_exact_candidate"] = bool(
        record["locale_reference"]
        and decision.startswith("pass_english")
        and record["exists"]
        and record["hash_matches_manifest"] is not False
        and record["same_dimensions"]
        and record["same_family"]
        and record["same_template"]
        and record["same_declared_state"]
    )
    return record


def load_candidate_snapshot(
    snapshot_root: Path,
) -> tuple[dict[str, Mapping[str, Any]], Mapping[str, Any]]:
    manifest_path = snapshot_root / "portable_manifest.json"
    report_path = snapshot_root / "snapshot_report.json"
    manifest = read_json(manifest_path)
    report = read_json(report_path)
    entries = manifest.get("production_state", {}).get("entries")
    if not isinstance(entries, list):
        raise BindingAuditError("candidate snapshot has no production entries")
    by_asset = {str(entry.get("asset_id") or ""): entry for entry in entries}
    if not all(by_asset) or len(by_asset) != len(entries):
        raise BindingAuditError("candidate snapshot asset IDs are invalid")
    return by_asset, report


def load_vertical_evidence(
    root: Path | None,
    workspace_root: Path,
    cache: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if root is None:
        return {}
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise BindingAuditError("vertical evidence manifest is missing")
    manifest = read_json(manifest_path)
    evidence: dict[str, dict[str, Any]] = {}
    for row in manifest.get("rows", []):
        asset_id = str(row.get("asset_id") or "")
        qa_value = row.get("qa")
        if not asset_id or not isinstance(qa_value, str):
            continue
        qa_path = resolve_path(qa_value, workspace_root)
        if not qa_path.is_file():
            evidence[asset_id] = {
                "status": "qa_missing",
                "qa_logical_ref": logical_ref(qa_path, workspace_root),
            }
            continue
        qa = read_json(qa_path)
        same_state_value = qa.get("files", {}).get("same_state_en")
        if not isinstance(same_state_value, str) or not same_state_value:
            evidence[asset_id] = {
                "status": "same_state_file_not_recorded",
                "qa_logical_ref": logical_ref(qa_path, workspace_root),
            }
            continue
        same_state_path = resolve_path(same_state_value, workspace_root)
        facts = file_facts(same_state_path, cache)
        evidence[asset_id] = {
            "status": (
                "file_present_provenance_asset_id_missing"
                if facts["exists"]
                else "same_state_file_missing"
            ),
            "qa_logical_ref": logical_ref(qa_path, workspace_root),
            "logical_ref": logical_ref(same_state_path, workspace_root),
            "exists": facts["exists"],
            "bytes": facts["bytes"],
            "sha256": facts["sha256"],
            "official_source_asset_id_recorded": False,
            "official_source_sha256_recorded_separately": False,
        }
    return evidence


def explicit_english_binding(entry: Mapping[str, Any]) -> tuple[str | None, str | None]:
    for key in ENGLISH_BINDING_KEYS:
        value = entry.get(key)
        if isinstance(value, str) and value:
            return key, value
    return None, None


def scan_absolute_leaks(root: Path) -> list[dict[str, Any]]:
    leaks: list[dict[str, Any]] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if WINDOWS_ABSOLUTE_ANYWHERE_RE.search(line) or UNC_RE.search(line.strip()):
                leaks.append(
                    {
                        "file": path.relative_to(root).as_posix(),
                        "line": number,
                        "kind": "windows_or_unc_absolute_path",
                    }
                )
    return leaks


def write_binding_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = [
        "asset_id",
        "game",
        "production_status",
        "candidate_valid",
        "candidate_private_snapshot_backed",
        "japanese_source_valid",
        "japanese_classification_bound",
        "english_explicit_production_binding",
        "english_locale_relation_count",
        "english_metadata_exact_candidate_count",
        "authoritative_route_bound",
        "authoritative_route_kind",
        "authoritative_target_asset_id",
        "official_decoded_target_png_status",
        "route_candidate_binding_status",
        "english_mapping_status",
        "vertical_staging_evidence_status",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "asset_id": row["asset_id"],
                    "game": row["game"],
                    "production_status": row["production_status"],
                    "candidate_valid": row["candidate"]["valid"],
                    "candidate_private_snapshot_backed": row["candidate"][
                        "private_snapshot_backed"
                    ],
                    "japanese_source_valid": row["official_japanese_source"]["valid"],
                    "japanese_classification_bound": row[
                        "official_japanese_source"
                    ]["classification_bound"],
                    "english_explicit_production_binding": row[
                        "official_english_same_state"
                    ]["explicit_production_binding"],
                    "english_locale_relation_count": len(
                        row["official_english_same_state"]["classification_relations"]
                    ),
                    "english_metadata_exact_candidate_count": len(
                        row["official_english_same_state"][
                            "metadata_exact_candidates"
                        ]
                    ),
                    "authoritative_route_bound": bool(
                        row["official_english_same_state"].get(
                            "authoritative_route"
                        )
                    ),
                    "authoritative_route_kind": (
                        (
                            row["official_english_same_state"].get(
                                "authoritative_route"
                            )
                            or {}
                        ).get("route_kind")
                    ),
                    "authoritative_target_asset_id": (
                        (
                            row["official_english_same_state"].get(
                                "authoritative_route"
                            )
                            or {}
                        ).get("target_asset_id")
                    ),
                    "official_decoded_target_png_status": (
                        (
                            row["official_english_same_state"].get(
                                "authoritative_route"
                            )
                            or {}
                        )
                        .get("official_decoded_target_png", {})
                        .get("status")
                    ),
                    "route_candidate_binding_status": (
                        (
                            row["official_english_same_state"].get(
                                "authoritative_route"
                            )
                            or {}
                        ).get("route_candidate_binding_status")
                    ),
                    "english_mapping_status": row[
                        "official_english_same_state"
                    ]["status"],
                    "vertical_staging_evidence_status": (
                        (
                            row["official_english_same_state"].get(
                                "vertical_staging_evidence"
                            )
                            or {}
                        ).get("status")
                    ),
                }
            )


def make_readme(summary: Mapping[str, Any], snapshot_id: str) -> str:
    lines = [
        "# Photon locale-binding snapshot",
        "",
        f"Snapshot: `{snapshot_id}`",
        "",
        "This directory is metadata-only. It contains no candidate PNG, official",
        "Japanese/English image, Steam container, game binary, or API intermediate.",
        "",
        "## Result",
        "",
        f"- Production entries: {summary['production_entries']}",
        f"- Candidate files available: {summary['candidate_file_available']}",
        f"- Candidate files content-hashed by this audit: {summary['candidate_content_hashed']}",
        f"- Candidates with a valid state-declared SHA-256: {summary['candidate_valid']}",
        f"- Candidates verified in private LFS-ready snapshot: {summary['candidate_private_snapshot_backed']}",
        f"- Valid official Japanese sources: {summary['japanese_source_valid']}",
        f"- Japanese sources also bound by classification hash: {summary['japanese_classification_bound']}",
        f"- Explicit production English same-state bindings: {summary['english_explicit_production_binding']}",
        f"- Classification-derived exact metadata candidates: {summary['english_metadata_exact_candidate']}",
        f"- English same-state mappings still unproven: {summary['english_mapping_unproven']}",
        f"- Existing vertical-card English evidence files: {summary['vertical_staging_evidence_present']}",
    ]
    if summary.get("route_closure_present"):
        lines.extend(
            [
                f"- Authoritative translation-target routes: {summary['authoritative_route_bindings']}",
                f"- Translation-peer routes: {summary['authoritative_translation_peer_routes']}",
                f"- Proven shared endpoints: {summary['authoritative_shared_endpoint_routes']}",
                f"- Verified decoded official target PNGs: {summary['official_target_decoded_png_verified']}",
                f"- Authenticated targets without decoded PNG: {summary['official_target_decoded_png_absent']}",
                f"- Rows with official exact-span hashes embedded: {summary['official_target_exact_span_authenticated']}",
                "",
                "The external route-closure seal is authoritative for translation-target",
                "identity. Production-state English path fields remain separately reported",
                "for compatibility; their absence is not a route-evidence gap. A missing",
                "decoded PNG is recorded as an authenticated native target identity and is",
                "never replaced by a fabricated image.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "A classification-derived candidate is not promoted to an authoritative binding:",
                "the production entry must eventually record the official English asset ID,",
                "logical path, SHA-256, and same-state proof explicitly.",
                "",
            ]
        )
    return "\n".join(lines)


def export_audit(
    *,
    workspace_root: Path,
    production_state_path: Path,
    classification_path: Path,
    canonical_root: Path,
    candidate_snapshot_root: Path,
    output_path: Path,
    vertical_evidence_root: Path | None = None,
    route_closure_path: Path | None = None,
    expected_route_count: int = 1490,
    expected_state_sha256: str | None = None,
    expected_classification_sha256: str | None = None,
    expected_route_closure_sha256: str | None = None,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve(strict=True)
    production_state_path = production_state_path.resolve(strict=True)
    classification_path = classification_path.resolve(strict=True)
    canonical_root = canonical_root.resolve(strict=True)
    candidate_snapshot_root = candidate_snapshot_root.resolve(strict=True)
    output_path = output_path.resolve(strict=False)
    if vertical_evidence_root is not None:
        vertical_evidence_root = vertical_evidence_root.resolve(strict=True)
    if route_closure_path is not None:
        route_closure_path = route_closure_path.resolve(strict=True)

    if output_path.exists():
        raise BindingAuditError(f"output already exists: {output_path}")
    if not is_under(output_path, workspace_root):
        raise BindingAuditError("output must be inside the declared workspace root")

    sources = {
        "production_state": production_state_path,
        "classification_manifest": classification_path,
        "candidate_snapshot_manifest": candidate_snapshot_root
        / "portable_manifest.json",
        "candidate_snapshot_report": candidate_snapshot_root / "snapshot_report.json",
    }
    if route_closure_path is not None:
        sources["route_closure"] = route_closure_path
    before = capture_hashes(sources)
    check_expected("production_state", before["production_state"], expected_state_sha256)
    check_expected(
        "classification_manifest",
        before["classification_manifest"],
        expected_classification_sha256,
    )
    if route_closure_path is not None:
        check_expected(
            "route_closure",
            before["route_closure"],
            expected_route_closure_sha256,
        )

    state = read_json(production_state_path)
    classification = read_json(classification_path)
    production_entries = state.get("entries")
    classification_entries = classification.get("entries")
    if not isinstance(production_entries, list) or not isinstance(
        classification_entries, list
    ):
        raise BindingAuditError("state/classification entries are missing")
    classification_by_id = {
        str(entry.get("id") or ""): entry for entry in classification_entries
    }
    if not all(classification_by_id):
        raise BindingAuditError("classification contains an empty ID")
    classification_by_route_id = build_route_id_index(
        classification_entries, "id", "classification manifest"
    )

    route_by_source: dict[str, Mapping[str, Any]] = {}
    route_validation_summary: dict[str, Any] = {}
    if route_closure_path is not None:
        route_document = read_json(route_closure_path)
        if not isinstance(route_document, Mapping):
            raise BindingAuditError("route closure root is not an object")
        route_by_source, route_validation_summary = validate_route_closure(
            route_document, production_entries, expected_route_count
        )

    snapshot_by_id, candidate_snapshot_report = load_candidate_snapshot(
        candidate_snapshot_root
    )
    snapshot_state_sha = str(
        candidate_snapshot_report.get("source_sha256_before", {}).get(
            "production_state"
        )
        or ""
    ).upper()
    if snapshot_state_sha != before["production_state"]:
        raise BindingAuditError(
            "candidate snapshot was built from a different production_state"
        )

    cache: dict[str, dict[str, Any]] = {}
    vertical_evidence = load_vertical_evidence(
        vertical_evidence_root, workspace_root, cache
    )
    rows: list[dict[str, Any]] = []
    candidate_gaps: list[dict[str, Any]] = []
    japanese_gaps: list[dict[str, Any]] = []
    formal_english_gaps: list[str] = []
    english_evidence_gaps: list[dict[str, Any]] = []
    authoritative_route_gaps: list[dict[str, Any]] = []
    counts = Counter()

    for entry in production_entries:
        asset_id = str(entry.get("asset_id") or "")
        if not asset_id:
            raise BindingAuditError("production entry has an empty asset_id")
        normalized_asset_id = route_asset_id(asset_id)
        game = str(entry.get("game") or "").upper()
        classification_entry = classification_by_id.get(asset_id)
        if classification_entry is None:
            classification_entry = classification_by_route_id.get(normalized_asset_id)

        candidate_value = entry.get("candidate_png")
        candidate_expected = str(entry.get("candidate_png_sha256") or "").upper() or None
        candidate_path = (
            resolve_path(candidate_value, workspace_root)
            if isinstance(candidate_value, str) and candidate_value
            else workspace_root / "__missing_candidate__"
        )
        candidate_facts = file_facts(candidate_path, cache)
        candidate_matches = expected_matches(
            candidate_facts["sha256"], candidate_expected
        )
        candidate_valid = bool(
            candidate_value
            and candidate_expected
            and candidate_facts["exists"]
            and candidate_matches
        )

        snapshot_entry = snapshot_by_id.get(asset_id)
        snapshot_value = snapshot_entry.get("candidate_png") if snapshot_entry else None
        snapshot_path = (
            candidate_snapshot_root
            / Path(str(snapshot_value).replace("/", os.sep))
            if isinstance(snapshot_value, str)
            and snapshot_value
            and not looks_absolute(snapshot_value)
            else candidate_snapshot_root / "__missing_candidate_snapshot__"
        )
        snapshot_facts = file_facts(snapshot_path, cache)
        snapshot_expected = (
            str(snapshot_entry.get("candidate_png_sha256") or "").upper() or None
            if snapshot_entry
            else None
        )
        snapshot_matches = expected_matches(snapshot_facts["sha256"], snapshot_expected)
        candidate_snapshot_backed = bool(
            snapshot_entry
            and snapshot_facts["exists"]
            and candidate_facts["exists"]
            and snapshot_facts["sha256"] == candidate_facts["sha256"]
            and snapshot_matches is not False
        )

        raw_value = entry.get("raw_source_png")
        raw_expected = str(entry.get("raw_source_png_sha256") or "").upper() or None
        raw_path = (
            resolve_path(raw_value, workspace_root)
            if isinstance(raw_value, str) and raw_value
            else workspace_root / "__missing_japanese_source__"
        )
        raw_facts = file_facts(raw_path, cache)
        raw_matches = expected_matches(raw_facts["sha256"], raw_expected)
        japanese_valid = bool(
            raw_value and raw_expected and raw_facts["exists"] and raw_matches
        )
        classification_hash = (
            str(classification_entry.get("source_png_sha256") or "").upper() or None
            if classification_entry
            else None
        )
        japanese_classification_bound = bool(
            classification_entry
            and classification_hash == raw_expected
            and raw_matches
        )

        relation_records: list[dict[str, Any]] = []
        if classification_entry:
            for peer_id in classification_entry.get("visual", {}).get(
                "locale_relation", []
            ) or []:
                peer = classification_by_id.get(str(peer_id))
                if peer:
                    relation_records.append(
                        english_relation_record(
                            classification_entry,
                            peer,
                            canonical_root,
                            workspace_root,
                            cache,
                        )
                    )
                else:
                    relation_records.append(
                        {
                            "asset_id": str(peer_id),
                            "exists": False,
                            "metadata_exact_candidate": False,
                            "reason": "classification_relation_target_missing",
                        }
                    )
        exact_candidates = [
            relation
            for relation in relation_records
            if relation.get("metadata_exact_candidate")
        ]

        explicit_key, explicit_value = explicit_english_binding(entry)
        explicit_valid = False
        explicit_record: dict[str, Any] | None = None
        if explicit_key and explicit_value:
            explicit_path = resolve_path(explicit_value, workspace_root)
            explicit_facts = file_facts(explicit_path, cache)
            expected_key = explicit_key.removesuffix("_png") + "_png_sha256"
            explicit_expected = str(entry.get(expected_key) or "").upper() or None
            explicit_valid = bool(
                explicit_facts["exists"]
                and explicit_expected
                and expected_matches(explicit_facts["sha256"], explicit_expected)
            )
            explicit_record = {
                "key": explicit_key,
                "logical_ref": logical_ref(explicit_path, workspace_root),
                "exists": explicit_facts["exists"],
                "bytes": explicit_facts["bytes"],
                "sha256": explicit_facts["sha256"],
                "expected_sha256": explicit_expected,
                "valid": explicit_valid,
            }

        route = route_by_source.get(normalized_asset_id)
        authoritative_route: dict[str, Any] | None = None
        if route is not None and route_closure_path is not None:
            authoritative_route = authoritative_route_record(
                route,
                classification_by_route_id,
                canonical_root,
                workspace_root,
                cache,
                before["route_closure"],
                candidate_facts["sha256"],
            )

        if authoritative_route is not None:
            english_status = (
                "authoritative_translation_target_route"
                if authoritative_route["route_kind"] == TRANSLATION_ROUTE_KIND
                else "authoritative_shared_endpoint"
            )
        elif explicit_valid:
            english_status = "explicit_production_binding_valid"
        elif len(exact_candidates) == 1:
            english_status = "metadata_candidate_not_production_bound"
        elif relation_records:
            english_status = "relation_present_but_same_state_unproven"
        else:
            english_status = "missing_no_classification_relation"

        row = {
            "asset_id": asset_id,
            "route_asset_id": normalized_asset_id,
            "game": game,
            "production_status": entry.get("status"),
            "candidate": {
                "logical_ref": logical_ref(candidate_path, workspace_root),
                "exists": candidate_facts["exists"],
                "bytes": candidate_facts["bytes"],
                "sha256": candidate_facts["sha256"],
                "expected_sha256": candidate_expected,
                "hash_matches_state": candidate_matches,
                "state_sha256_present": candidate_expected is not None,
                "file_available": candidate_facts["exists"],
                "valid": candidate_valid,
                "private_snapshot_logical_ref": logical_ref(
                    snapshot_path, workspace_root
                ),
                "private_snapshot_backed": candidate_snapshot_backed,
            },
            "official_japanese_source": {
                "logical_ref": logical_ref(raw_path, workspace_root),
                "exists": raw_facts["exists"],
                "bytes": raw_facts["bytes"],
                "sha256": raw_facts["sha256"],
                "expected_sha256": raw_expected,
                "hash_matches_state": raw_matches,
                "classification_sha256": classification_hash,
                "classification_bound": japanese_classification_bound,
                "valid": japanese_valid,
                "github_copy_policy": "manifest_only_never_copy_official_image",
            },
            "official_english_same_state": {
                "explicit_production_binding": explicit_valid,
                "explicit_record": explicit_record,
                "classification_relations": relation_records,
                "metadata_exact_candidates": [
                    relation["asset_id"] for relation in exact_candidates
                ],
                "authoritative_route": authoritative_route,
                "status": english_status,
                "vertical_staging_evidence": vertical_evidence.get(asset_id),
                "github_copy_policy": "manifest_only_never_copy_official_image",
            },
        }
        rows.append(row)

        counts["production_entries"] += 1
        counts["candidate_file_available"] += int(candidate_facts["exists"])
        counts["candidate_content_hashed"] += int(
            candidate_facts["sha256"] is not None
        )
        counts["candidate_state_sha_present"] += int(candidate_expected is not None)
        counts["candidate_state_sha_matches"] += int(candidate_matches is True)
        counts["candidate_valid"] += int(candidate_valid)
        counts["candidate_private_snapshot_backed"] += int(
            candidate_snapshot_backed
        )
        counts["japanese_source_valid"] += int(japanese_valid)
        counts["japanese_classification_bound"] += int(
            japanese_classification_bound
        )
        counts["english_explicit_production_binding"] += int(explicit_valid)
        counts["english_has_locale_relation"] += int(bool(relation_records))
        counts["english_metadata_exact_candidate"] += int(
            len(exact_candidates) == 1
        )
        counts["english_mapping_unproven"] += int(
            authoritative_route is None
            and not explicit_valid
            and len(exact_candidates) != 1
        )
        counts["vertical_staging_evidence_present"] += int(
            vertical_evidence.get(asset_id, {}).get("exists") is True
        )
        if authoritative_route is not None:
            decoded_status = authoritative_route["official_decoded_target_png"][
                "status"
            ]
            counts["official_target_decoded_png_verified"] += int(
                decoded_status == "official_decoded_png_verified"
            )
            counts["official_target_decoded_png_absent"] += int(
                decoded_status == "official_decoded_png_absent"
            )
            counts["official_target_decoded_png_unhashed"] += int(
                decoded_status == "official_decoded_png_unhashed"
            )
            counts["official_target_exact_span_authenticated"] += int(
                authoritative_route["native_identity"][
                    "byte_level_identity_status"
                ]
                == "official_exact_span_authenticated"
            )
            counts["route_candidate_matches_current"] += int(
                authoritative_route["route_candidate_binding_status"]
                == "matches_current_production_candidate"
            )
            counts["route_candidate_historical_differs_current"] += int(
                authoritative_route["route_candidate_binding_status"]
                == "historical_route_payload_differs_from_current_candidate"
            )
        elif route_closure_path is not None:
            authoritative_route_gaps.append(
                {
                    "asset_id": asset_id,
                    "route_asset_id": normalized_asset_id,
                    "reason": "validated route closure unexpectedly lacks this source",
                }
            )

        if not candidate_valid or not candidate_snapshot_backed:
            candidate_gaps.append(
                {
                    "asset_id": asset_id,
                    "candidate_file_available": candidate_facts["exists"],
                    "state_sha256_present": candidate_expected is not None,
                    "candidate_valid": candidate_valid,
                    "private_snapshot_backed": candidate_snapshot_backed,
                }
            )
        if not japanese_valid or not japanese_classification_bound:
            japanese_gaps.append(
                {
                    "asset_id": asset_id,
                    "source_valid": japanese_valid,
                    "classification_bound": japanese_classification_bound,
                }
            )
        if not explicit_valid:
            formal_english_gaps.append(asset_id)
        if (
            authoritative_route is None
            and not explicit_valid
            and len(exact_candidates) != 1
        ):
            english_evidence_gaps.append(
                {
                    "asset_id": asset_id,
                    "status": english_status,
                    "classification_relation_count": len(relation_records),
                    "vertical_staging_evidence_status": vertical_evidence.get(
                        asset_id, {}
                    ).get("status"),
                }
            )

    rows.sort(key=lambda row: row["asset_id"])
    summary = dict(sorted(counts.items()))
    summary["route_closure_present"] = route_closure_path is not None
    if route_closure_path is not None:
        summary.update(route_validation_summary)
        summary["official_target_native_identity_authenticated"] = len(rows)
        summary["official_target_header_hash_embedded"] = 0
        summary["authoritative_route_binding_gaps"] = len(
            authoritative_route_gaps
        )
        summary["fabricated_official_target_pngs"] = 0
        if authoritative_route_gaps:
            raise BindingAuditError(
                "validated route closure did not produce one binding per production row"
            )
    if summary["production_entries"] != len(snapshot_by_id):
        raise BindingAuditError("candidate snapshot entry count differs from production")

    after = capture_hashes(sources)
    if after != before:
        raise BindingAuditError("an input manifest changed during the binding audit")

    snapshot_id = (
        "photon-bindings-"
        + before["production_state"][:12].lower()
        + "-"
        + before["classification_manifest"][:8].lower()
        + (
            "-" + before["route_closure"][:8].lower()
            if route_closure_path is not None
            else ""
        )
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.parent / (
        f".{output_path.name}.building-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    )
    temporary.mkdir(parents=False)
    try:
        manifest = {
            "schema": SCHEMA,
            "snapshot_id": snapshot_id,
            "source_inputs": {
                name: source_facts(path, workspace_root) for name, path in sources.items()
            },
            "canonical_root_logical_ref": logical_ref(
                canonical_root, workspace_root
            ),
            "candidate_snapshot_logical_ref": logical_ref(
                candidate_snapshot_root, workspace_root
            ),
            "summary": summary,
            "bindings": rows,
        }
        write_json(temporary / "binding_manifest.json", manifest)
        write_binding_csv(temporary / "binding_manifest.csv", rows)
        write_json(
            temporary / "missing_bindings.json",
            {
                "schema": "muvluv-photon-locale-binding-gaps/v1",
                "snapshot_id": snapshot_id,
                "candidate_or_private_snapshot_gaps": candidate_gaps,
                "japanese_source_or_classification_gaps": japanese_gaps,
                "formal_english_production_binding_gap_count": len(
                    formal_english_gaps
                ),
                "formal_english_production_binding_asset_ids": formal_english_gaps,
                "authoritative_route_binding_gap_count": len(
                    authoritative_route_gaps
                ),
                "authoritative_route_binding_gaps": authoritative_route_gaps,
                "english_same_state_evidence_gap_count": len(
                    english_evidence_gaps
                ),
                "english_same_state_evidence_gaps": english_evidence_gaps,
            },
        )
        write_json(
            temporary / "summary.json",
            {
                "schema": "muvluv-photon-locale-binding-summary/v1",
                "snapshot_id": snapshot_id,
                "summary": summary,
                "source_sha256_before": before,
                "source_sha256_after": after,
                "source_inputs_unchanged": True,
                "absolute_path_leaks": 0,
                "images_copied": 0,
                "official_resources_copied": 0,
            },
        )
        write_json(
            temporary / "copy_policy.json",
            {
                "schema": "muvluv-photon-binding-copy-policy/v1",
                "public_git_allowed": [
                    "binding_manifest.csv",
                    "metadata-only JSON manifests after copyright/privacy review",
                    "hashes, logical refs, schemas, tools, and synthetic tests",
                ],
                "private_lfs_only": ["localized candidate PNGs"],
                "never_copy_to_github": [
                    "official Japanese images",
                    "official English images",
                    "Steam RIO/002 containers",
                    "official EXE/DLL and API intermediates",
                ],
            },
        )
        (temporary / "README.md").write_text(
            make_readme(summary, snapshot_id), encoding="utf-8", newline="\n"
        )

        leaks = scan_absolute_leaks(temporary)
        if leaks:
            raise BindingAuditError(
                f"absolute path leakage detected in {len(leaks)} locations"
            )
        checksums = "".join(
            f"{sha256_file(path)}  {path.relative_to(temporary).as_posix()}\n"
            for path in sorted(p for p in temporary.rglob("*") if p.is_file())
        )
        (temporary / "SHA256SUMS.txt").write_text(
            checksums, encoding="utf-8", newline="\n"
        )
        final_hashes = capture_hashes(sources)
        if final_hashes != before:
            raise BindingAuditError("an input manifest changed before snapshot commit")
        if scan_absolute_leaks(temporary):
            raise BindingAuditError("absolute path leakage detected after checksums")
        os.replace(temporary, output_path)
        return {
            "snapshot_id": snapshot_id,
            "output": logical_ref(output_path, workspace_root),
            "summary": summary,
            "absolute_path_leaks": 0,
            "images_copied": 0,
            "source_inputs_unchanged": True,
        }
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--production-state", required=True, type=Path)
    parser.add_argument("--classification", required=True, type=Path)
    parser.add_argument("--canonical-root", required=True, type=Path)
    parser.add_argument("--candidate-snapshot", required=True, type=Path)
    parser.add_argument("--vertical-evidence-root", type=Path)
    parser.add_argument("--route-closure", type=Path)
    parser.add_argument("--expected-route-count", type=int, default=1490)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-state-sha256")
    parser.add_argument("--expected-classification-sha256")
    parser.add_argument("--expected-route-closure-sha256")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        result = export_audit(
            workspace_root=arguments.workspace_root,
            production_state_path=arguments.production_state,
            classification_path=arguments.classification,
            canonical_root=arguments.canonical_root,
            candidate_snapshot_root=arguments.candidate_snapshot,
            vertical_evidence_root=arguments.vertical_evidence_root,
            route_closure_path=arguments.route_closure,
            expected_route_count=arguments.expected_route_count,
            output_path=arguments.output,
            expected_state_sha256=arguments.expected_state_sha256,
            expected_classification_sha256=arguments.expected_classification_sha256,
            expected_route_closure_sha256=arguments.expected_route_closure_sha256,
        )
    except (OSError, ValueError, BindingAuditError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
