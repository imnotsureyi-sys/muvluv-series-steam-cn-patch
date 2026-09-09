#!/usr/bin/env python3
"""Export path-redacted PF/PM CRmt, CRmti, CRimp and trigger evidence."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Sequence

from rUGP.formats.images.crimp import decode_value
from rUGP.tools.provenance.export_crmt_localization_evidence import (
    assert_portable_document,
)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def source(path: Path) -> dict[str, object]:
    return {
        "name": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def publish(path: Path, document: dict[str, Any]) -> None:
    assert_portable_document(document)
    payload = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def compact_crimp(record: dict[str, Any]) -> dict[str, Any]:
    # Historical reports guessed fixed16 from a four-byte length. Re-decode the
    # preserved wire bytes instead of propagating that incorrect projection.
    properties = []
    for prop in record["property_envelope"]["properties"]:
        raw = bytes.fromhex(prop["value_hex"])
        value, end = decode_value(raw)
        if end != len(raw):
            raise ValueError("CRimp property has trailing value bytes")
        properties.append({"name": prop["name"], "value_kind": value.kind,
                           "value_hex": raw.hex(" "), "decoded_value": value.as_dict()})
    return {
        "game": record["game"],
        "volume": record["volume"],
        "offset_hex": record["offset_hex"],
        "extent": record["extent"],
        "sha256": record["sha256"],
        "property_value_decoder": "native_tagged_values_v1",
        "properties": properties,
        "declared_occurrence_count": record["declared_occurrence_count"],
        "catalog_node_count": record["catalog_node_count"],
    }


def compact_crimp_section(document: dict[str, Any]) -> dict[str, Any]:
    records = [compact_crimp(record) for record in document["records"]]
    summary = {key: value for key, value in document["summary"].items()
               if key not in {"decoded_value_kind_distribution", "unit_vector_norm_range"}}
    summary["decoded_value_kind_distribution"] = dict(Counter(
        prop["value_kind"] for record in records for prop in record["properties"]))
    summary["property_value_decoder"] = "native_tagged_values_v1"
    summary["scene_coordinate_units_established"] = False
    return {"summary": summary, "records": records}


def compact_layout_decode(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": record["candidate_id"],
        "game": record["game"],
        "volume": record["volume"],
        "offset_hex": record["offset_hex"],
        "extent": record["extent"],
        "record_sha256": record["record_sha256"],
        "layout": record["layout"],
        "selection_reasons": record["selection_reasons"],
        "mips": [
            {
                key: mip[key]
                for key in (
                    "index",
                    "dimensions",
                    "meta_hex",
                    "blob_length",
                    "rgba_sha256",
                )
            }
            for mip in record["mips"]
        ],
        "status": record["status"],
    }


def compact_layout_reencode(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": record["candidate_id"],
        "game": record["game"],
        "volume": record["volume"],
        "offset_hex": record["offset_hex"],
        "layout": record["layout"],
        "selection_features": record["selection_features"],
        "source_bytes": record["source_bytes"],
        "source_sha256": record["source_sha256"],
        "encoded_bytes": record["encoded_bytes"],
        "encoded_sha256": record["encoded_sha256"],
        "record_byte_delta": record["record_byte_delta"],
        "size_direction": record["size_direction"],
        "byte_deterministic_second_encode": record[
            "byte_deterministic_second_encode"
        ],
        "parent_preamble_and_trailer_preserved": record[
            "parent_preamble_and_trailer_preserved"
        ],
        "all_mips_pixel_identical": record["all_mips_pixel_identical"],
        "mips": [
            {
                key: mip[key]
                for key in (
                    "index",
                    "dimensions",
                    "meta_hex",
                    "source_blob_bytes",
                    "encoded_blob_bytes",
                    "rgba_sha256",
                    "immutable_fields_preserved",
                    "wrapper_preserved",
                )
            }
            for mip in record["mips"]
        ],
    }


def compact_member(member: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": member["candidate_id"],
        "game": member["game"],
        "volume": member["volume"],
        "offset_hex": member["offset_hex"],
        "extent": member["extent"],
        "record_sha256": member["record_sha256"],
        "evidence_mode": member["evidence_mode"],
        "crmti_children": len(member["crmti_children"]),
        "crimp_peers": [
            {
                "relation_modes": peer["relation_modes"],
                "game": peer["record"]["game"],
                "volume": peer["record"]["volume"],
                "offset_hex": peer["record"]["offset_hex"],
                "extent": peer["record"]["extent"],
                "sha256": peer["record"]["sha256"],
            }
            for peer in member["crimp_peers"]
        ],
        "localized_record_sha256": member["localized_replacement"][
            "record_sha256"
        ],
        "overlay_validation": member["overlay_route"]["validation"],
    }


def compact_target(row: dict[str, Any]) -> dict[str, Any]:
    related_states = []
    for state in row["related_states"]:
        occurrence = state["exact_crsa_occurrences"][0]
        route = state["overlay_route"]
        related_states.append(
            {
                "state_id": state["state_id"],
                "source_visual": state["source_visual"],
                "localized_visual": state["localized_visual"],
                "pixel_comparison": state["relation_proof"]["pixel_comparison"],
                "tail_objref_to_base_state": state["relation_proof"]["tail_objref"],
                "exact_crsa_block_id": occurrence["block_id"],
                "work_attribution": state["work_attribution"],
                "source": {
                    key: route[key]
                    for key in (
                        "game",
                        "volume",
                        "offset_hex",
                        "source_raw_key_hex",
                        "source_extent",
                        "source_record_sha256",
                    )
                },
                "replacement_record_sha256": route["replacement_record_sha256"],
                "overlay_sha256": route["overlay_sha256"],
                "overlay_byte_offset": route["overlay_byte_offset"],
                "overlay_extent": route["overlay_extent"],
                "runtime_proven": state["runtime_proven"],
            }
        )
    return {
        "asset_id": row["asset_id"],
        "classification": row["classification"],
        "priority": row["priority"],
        "observed_text": row["observed_text"],
        "zh_hans": row["zh_hans"],
        "dimensions": row["dimensions"],
        "placement": row["placement"],
        "trigger": {
            "static_status": row["trigger"]["static_status"],
            "exact_crsa_occurrences": len(row["trigger"]["exact_crsa_occurrences"]),
            "exact_crsa_block_ids": row["trigger"]["exact_crsa_block_ids"],
            "manual_scene_hypotheses": row["trigger"]["manual_scene_hypotheses"],
            "runtime_proven": row["trigger"]["runtime_proven"],
        },
        "language_variant_pair": row["language_variant_pair"] is not None,
        "language_variant_pair_structure": (
            row["language_variant_pair_structure"] is not None
        ),
        "members": [compact_member(member) for member in row["members"]],
        "related_states": related_states,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--structural-census", type=Path, required=True)
    parser.add_argument("--strict-reencode", type=Path, required=True)
    parser.add_argument("--layout-decode-audit", type=Path, required=True)
    parser.add_argument("--layout-reencode-audit", type=Path, required=True)
    parser.add_argument("--visual-review", type=Path, required=True)
    parser.add_argument("--crimp-audit", type=Path, required=True)
    parser.add_argument("--corrected-crsa-scan", type=Path, required=True)
    parser.add_argument("--public-crsa-verification", type=Path, required=True)
    parser.add_argument("--relation-manifest", type=Path, required=True)
    parser.add_argument("--language-pairs", type=Path, required=True)
    parser.add_argument("--unresolved-pair-structure", type=Path, required=True)
    parser.add_argument("--archive-only-boundary", type=Path, required=True)
    parser.add_argument("--overlay-determinism", type=Path, required=True)
    parser.add_argument("--scan-postmortem", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    paths = {
        key: value.resolve()
        for key, value in vars(args).items()
        if key != "output" and isinstance(value, Path)
    }
    documents = {key: load(path) for key, path in paths.items()}
    census = documents["structural_census"]
    strict = documents["strict_reencode"]
    layout_decode = documents["layout_decode_audit"]
    layout_reencode = documents["layout_reencode_audit"]
    visual = documents["visual_review"]
    crimp = documents["crimp_audit"]
    crsa = documents["corrected_crsa_scan"]
    public_crsa = documents["public_crsa_verification"]
    relation = documents["relation_manifest"]
    pairs = documents["language_pairs"]
    unresolved = documents["unresolved_pair_structure"]
    archive_boundary = documents["archive_only_boundary"]
    determinism = documents["overlay_determinism"]
    postmortem = documents["scan_postmortem"]

    required = {
        "logical_crmt_records": 15536,
        "logical_crmti_mips": 89063,
        "frozen_strict_covered": 895,
    }
    for key, expected in required.items():
        if int(census["summary"][key]) != expected:
            raise ValueError(f"structural census {key} changed")
    if (
        int(strict["summary"]["candidates"]) != 895
        or int(strict["summary"]["mips"]) != 5040
    ):
        raise ValueError("strict codec subset changed")
    decode_summary = layout_decode["summary"]
    if (
        int(decode_summary["selected_parents"]) != 139
        or int(decode_summary["decoded_parents"]) != 139
        or int(decode_summary["decoded_mips"]) != 751
        or int(decode_summary["failures"]) != 0
        or not decode_summary["all_five_observed_parent_layouts_covered"]
        or not decode_summary["all_four_observed_profiles_covered"]
        or int(decode_summary["steam_files_written"]) != 0
    ):
        raise ValueError("public generalized layout decode cover changed")
    expected_layouts = {
        "80 04 02 05 | 0x2D | 0a 80 40 c0",
        "80 04 02 05 | 0x40 | 0c 80 40 c0",
        "80 04 02 05 | 0x53 | 0e 80 40 c0",
        "80 04 02 06 | 0x40 | 0d 80 40 c0",
        "80 04 02 06 | 0x53 | 0f 80 40 c0",
    }
    expected_profiles = {
        "0x0505050F",
        "0x0606060F",
        "0x07070707",
        "0x0707070F",
    }
    if set(decode_summary["layout_distribution"]) != expected_layouts:
        raise ValueError("public decode layout set changed")
    if set(decode_summary["profile_distribution"]) != expected_profiles:
        raise ValueError("public decode profile set changed")
    if len(layout_decode["results"]) != 139 or any(
        row["status"] != "public_decode_matches_independent_audit"
        for row in layout_decode["results"]
    ):
        raise ValueError("public layout decode result closure failed")

    reencode_summary = layout_reencode["summary"]
    if (
        int(reencode_summary["selected_parents"]) != 11
        or int(reencode_summary["successful_parents"]) != 11
        or int(reencode_summary["reencoded_mips"]) != 57
        or int(reencode_summary["failures"]) != 0
        or reencode_summary["missing_required_features"]
        or not reencode_summary["all_selected_second_encodes_byte_identical"]
        or not reencode_summary["all_selected_mips_pixel_identical"]
        or int(reencode_summary["steam_files_written"]) != 0
    ):
        raise ValueError("public generalized layout reencode cover changed")
    required_features = set(layout_reencode["selection"]["required_features"])
    if not {
        *(f"layout:{layout}" for layout in expected_layouts),
        *(f"profile:{profile}" for profile in expected_profiles),
        "condition:normalized-prefix-alias-group",
    }.issubset(required_features):
        raise ValueError("public reencode feature cover is incomplete")
    if len(layout_reencode["results"]) != 11 or any(
        not row["byte_deterministic_second_encode"]
        or not row["parent_preamble_and_trailer_preserved"]
        or not row["all_mips_pixel_identical"]
        or any(
            not mip["immutable_fields_preserved"] or not mip["wrapper_preserved"]
            for mip in row["mips"]
        )
        for row in layout_reencode["results"]
    ):
        raise ValueError("public layout reencode result closure failed")
    if int(visual["summary"]["exact_unique_top_images"]) != 867:
        raise ValueError("strict visual gallery count changed")
    if int(crimp["summary"]["all_unique_physical_records"]) != 102:
        raise ValueError("CRimp physical-record count changed")
    if int(public_crsa["summary"]["checksum_valid_crsa_blocks"]) != 466:
        raise ValueError("public CRsa verification count changed")
    if not public_crsa["summary"][
        "all_offsets_extents_and_plaintext_hashes_exact"
    ]:
        raise ValueError("public CRsa iterator did not reproduce corrected scan")
    expected_relation = {
        "assets": 56,
        "crmt_member_records": 66,
        "crmti_children": 377,
        "overlay_routes": 67,
        "assets_with_exact_crsa_block": 47,
        "structurally_proven_unresolved_language_pairs": 9,
        "runtime_proven_assets": 0,
    }
    for key, expected in expected_relation.items():
        if int(relation["summary"][key]) != expected:
            raise ValueError(f"relation summary {key} changed")
    if int(pairs["summary"]["confirmed_pairs"]) != 23:
        raise ValueError("language-pair count changed")
    if (
        int(unresolved["summary"]["pairs_with_immediately_adjacent_exact_objrefs"])
        != 9
    ):
        raise ValueError("unresolved structural-pair count changed")
    archive_summary = archive_boundary["summary"]
    required_archive_boundary = (
        "all_pairs_are_adjacent_japanese_then_english_objrefs",
        "all_english_refs_are_complete_class_cache_72_objrefs",
        "all_pairs_outside_checksum_valid_crsa_extents",
        "all_pairs_share_one_crsa_free_archive_interval",
    )
    if (
        int(archive_summary["targets"]) != 9
        or int(archive_summary["known_crmt_objrefs_in_shared_interval"]) != 25
        or int(archive_summary["corrected_crsa_blocks_considered"]) != 466
        or int(archive_summary["runtime_proven_targets"]) != 0
        or int(archive_summary["steam_files_read"]) != 0
        or int(archive_summary["steam_files_written"]) != 0
        or not all(archive_summary[key] for key in required_archive_boundary)
        or len(archive_boundary["rows"]) != 9
        or any(
            row["inside_any_checksum_valid_crsa_extent"]
            or row["static_trigger_precision"] != "archive_objref_only"
            for row in archive_boundary["rows"]
        )
    ):
        raise ValueError("archive-only trigger boundary changed")
    if not all(
        determinism["verification"][key]
        for key in (
            "two_clean_rebuilds_byte_identical",
            "clean_rebuild_matches_published_overlay",
            "temporary_candidates_removed",
        )
    ):
        raise ValueError("selected-state overlay determinism did not pass")
    if int(postmortem["comparison"]["old_checksum_valid_blocks"]) != 185:
        raise ValueError("old CRsa scan count changed")

    census_volumes = []
    for volume in census["volumes"]:
        census_volumes.append(
            {
                "game": volume["game"],
                "volume": volume["volume"],
                "bytes_scanned": volume["bytes"],
                "structural_prefix_candidates": volume[
                    "structural_prefix_candidates"
                ],
                "logical_crmt_records": len(volume["matches"]),
                "nested_prefix_alias_starts_excluded": sum(
                    int(row["prefix_alias_count"]) for row in volume["matches"]
                ),
                "logical_crmti_mips": sum(
                    len(row["levels"]) for row in volume["matches"]
                ),
            }
        )

    crsa_volumes = []
    for game in crsa["games"]:
        for volume in game["volumes"]:
            crsa_volumes.append(
                {
                    "game": game["game"],
                    "volume": volume["volume"],
                    **volume["summary"],
                }
            )

    language_pairs = []
    pair_keys = (
        "target_id",
        "certainty",
        "pairing_group",
        "english_or_localized_text",
        "english_or_localized_dimensions",
        "english_or_localized_records",
        "japanese_edition_text",
        "japanese_edition_dimensions",
        "japanese_edition_rgba_sha256",
        "japanese_edition_records",
    )
    for row in pairs["rows"]:
        language_pairs.append({key: row[key] for key in pair_keys})

    structural_pairs = []
    for row in unresolved["rows"]:
        structural_pairs.append(
            {
                "target_id": row["target_id"],
                "english_state": {
                    "candidate_id": row["english_state"]["candidate_id"],
                    "volume_offset_hex": row["english_state"]["volume_offset_hex"],
                    "objref": row["english_state"]["objref"],
                },
                "japanese_state": {
                    "volume": row["japanese_state"]["volume"],
                    "volume_offset_hex": row["japanese_state"]["volume_offset_hex"],
                    "serialized_extent": row["japanese_state"]["serialized_extent"],
                    "objref": row["japanese_state"]["objref"],
                },
                "pair_proof": row["pair_proof"],
                "trigger_status": row["trigger_status"],
            }
        )

    output_overlays = []
    for row in relation["overlay_outputs"]:
        output_overlays.append(
            {
                "game": row["game"],
                "kind": row.get("kind", "complete_base"),
                "bytes": row["binary"]["bytes"],
                "sha256": row["binary"]["sha256"],
                "summary": {
                    key: row[key]
                    for key in (
                        "redirects",
                        "target_member_replacements_inherited",
                        "related_state_replacements_added",
                    )
                    if key in row
                },
            }
        )

    document = {
        "schema": "photon-crmt-structure-trigger-public-evidence/v1",
        "scope": (
            "PF/PM CRmt, CRmti and CRimp structure plus visual-text trigger closure"
        ),
        "method_boundary": (
            "Whole-volume structure, stratified generalized-layout codec coverage, "
            "strict-subset codec closure, serialized references and local overlay "
            "routing are separate proof layers. Runtime execution and human visible-"
            "frame acceptance remain pending for these 56 targets."
        ),
        "inputs": {key: source(path) for key, path in paths.items()},
        "structural_census": {
            "summary": census["summary"],
            "volumes": census_volumes,
            "strict_reencode_subset": strict["summary"],
        },
        "generalized_layout_codec_cover": {
            "decode_summary": decode_summary,
            "decode_boundary": layout_decode["boundary"],
            "decoded_records": [
                compact_layout_decode(row) for row in layout_decode["results"]
            ],
            "reencode_selection": layout_reencode["selection"],
            "reencode_summary": reencode_summary,
            "reencode_boundary": layout_reencode["boundary"],
            "reencoded_records": [
                compact_layout_reencode(row)
                for row in layout_reencode["results"]
            ],
        },
        "crimp": compact_crimp_section(crimp),
        "crsa_census": {
            "fixed_prefix_bytes": 6,
            "outer_header_bytes": 11,
            "old_checksum_valid_blocks": postmortem["comparison"][
                "old_checksum_valid_blocks"
            ],
            "corrected_checksum_valid_blocks": postmortem["comparison"][
                "corrected_checksum_valid_blocks"
            ],
            "recovered_blocks": postmortem["comparison"]["recovered_blocks"],
            "volumes": crsa_volumes,
            "public_iterator_verification": public_crsa["summary"],
        },
        "visual_assets": {
            "strict_gallery_unique_images": 867,
            "comprehension_targets": 56,
            "other_images": 811,
            "strict_candidate_records": 895,
            "target_member_records": 66,
            "target_crmti_children": 377,
            "relation_summary": relation["summary"],
            "targets": [compact_target(row) for row in relation["assets"]],
        },
        "language_pairs": {
            "summary": pairs["summary"],
            "pairs": language_pairs,
            "archive_only_structural_pair_summary": unresolved["summary"],
            "archive_only_structural_pairs": structural_pairs,
        },
        "archive_only_trigger_boundary": {
            "summary": archive_summary,
            "shared_crsa_free_interval": archive_boundary[
                "shared_crsa_free_interval"
            ],
            "rows": archive_boundary["rows"],
            "interpretation": archive_boundary["interpretation"],
        },
        "local_overlay_outputs": {
            "outputs": output_overlays,
            "selected_state_determinism": determinism["verification"],
            "distributed_binaries": False,
        },
        "evidence_boundary": {
            "static_targets_with_exact_checksum_valid_crsa_block": 47,
            "archive_only_targets": 9,
            "runtime_proven_targets": 0,
            "steam_files_written_by_this_evidence_pass": 0,
        },
    }
    publish(args.output.resolve(), document)
    print(
        json.dumps(
            {
                "logical_crmt_records": census["summary"]["logical_crmt_records"],
                "logical_crmti_mips": census["summary"]["logical_crmti_mips"],
                "generalized_layout_decode_parents": decode_summary[
                    "decoded_parents"
                ],
                "generalized_layout_reencode_parents": reencode_summary[
                    "successful_parents"
                ],
                "crimp_records": len(crimp["records"]),
                "gallery": "56 + 811 = 867",
                "crsa_blocks": 466,
                "output_sha256": sha256_file(args.output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
