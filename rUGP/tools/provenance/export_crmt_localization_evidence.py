#!/usr/bin/env python3
"""Export path-redacted public evidence for the PF/PM CRmt localization pass."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Sequence


ABSOLUTE_PATH = re.compile(
    r"(?i)(?:[a-z]:[\\/]|\\\\[^\\]|/(?:home|users|tmp)(?:/|$))"
)
PRIVATE_LOCATOR_MARKERS = (
    ".codex",
    "codex-safe-workspace",
    "local-internal",
    "worktrees",
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(16 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def source(path: Path) -> dict[str, str]:
    return {"name": path.name, "sha256": sha256_file(path)}


def assert_portable_document(value: Any, location: str = "$") -> None:
    """Reject absolute/private locators anywhere in the public JSON tree."""

    if isinstance(value, dict):
        for key, child in value.items():
            assert_portable_document(str(key), f"{location}.<key>")
            assert_portable_document(child, f"{location}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            assert_portable_document(child, f"{location}[{index}]")
        return
    if not isinstance(value, str):
        return
    folded = value.casefold()
    if ABSOLUTE_PATH.search(value) or any(
        marker in folded for marker in PRIVATE_LOCATOR_MARKERS
    ):
        raise ValueError(f"private or absolute locator at {location}")


def resolve_from(path: Path, raw: str) -> Path:
    candidate = Path(raw)
    return candidate.resolve() if candidate.is_absolute() else (path.parent / candidate).resolve()


def write_new(path: Path, document: dict[str, Any]) -> None:
    assert_portable_document(document)
    payload = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def compact_occurrence(row: dict[str, Any]) -> dict[str, Any]:
    if "payload_pair_offset_hex" in row:
        association_kind = row.get(
            "association_kind", "exact_source_crmt_objref"
        )
        payload_offset_kind = "pair"
        payload_offset_hex = row["payload_pair_offset_hex"]
    elif "payload_key_offset_hex" in row:
        association_kind = row["association_kind"]
        payload_offset_kind = "key"
        payload_offset_hex = row["payload_key_offset_hex"]
    else:
        raise ValueError(
            f"unsupported trigger occurrence layout in {row.get('block_id')}"
        )
    compact: dict[str, Any] = {
        "block_id": row["block_id"],
        "association_kind": association_kind,
        "payload_offset_kind": payload_offset_kind,
        "payload_offset_hex": payload_offset_hex,
        "objref": {
            key: row["objref"].get(key)
            for key in (
                "proven",
                "record_start_payload_offset_hex",
                "raw_key_hex",
                "decoded_extent",
                "parent_trailer_bytes",
            )
        },
        "reviewed_context": [
            {
                key: context.get(key)
                for key in (
                    "dataset",
                    "work",
                    "scene",
                    "reviewed_rows",
                    "call_order_first",
                    "call_order_last",
                )
            }
            for context in row.get("reviewed_context", [])
        ],
    }
    if "japanese_peer" in row:
        peer = row["japanese_peer"]
        compact["japanese_peer"] = {
            key: peer.get(key)
            for key in (
                "game",
                "volume",
                "offset_hex",
                "dimensions",
                "raw_key_hex",
            )
        }
    if "related_state" in row:
        state = row["related_state"]
        compact["related_state"] = {
            key: state.get(key)
            for key in (
                "state_id",
                "source_visual",
                "localized_visual",
                "game",
                "volume",
                "offset_hex",
                "dimensions",
                "raw_key_hex",
            )
        }
    return compact


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visual-review", type=Path, required=True)
    parser.add_argument("--trigger-map", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--candidate-hashes", type=Path, required=True)
    parser.add_argument("--relationship-report", type=Path, required=True)
    parser.add_argument("--structure-audit", type=Path, required=True)
    parser.add_argument("--related-state-report", type=Path, required=True)
    parser.add_argument("--reencode-audit", type=Path, required=True)
    parser.add_argument("--public-codec-audit", type=Path, required=True)
    parser.add_argument("--crmt-batch", type=Path, required=True)
    parser.add_argument("--pf-overlay-report", type=Path, required=True)
    parser.add_argument("--pm-overlay-report", type=Path, required=True)
    parser.add_argument("--runtime-report", type=Path, required=True)
    parser.add_argument("--pm-runtime-report", type=Path, required=True)
    parser.add_argument("--steam-integrity-recheck", type=Path, required=True)
    parser.add_argument("--manual-qa-checklist", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    paths = {
        key: value.resolve()
        for key, value in vars(args).items()
        if key != "output" and isinstance(value, Path)
    }
    visual = load_json(paths["visual_review"])
    trigger = load_json(paths["trigger_map"])
    selection = load_json(paths["selection"])
    candidates = load_json(paths["candidate_hashes"])
    relationships = load_json(paths["relationship_report"])
    structure = load_json(paths["structure_audit"])
    related_state = load_json(paths["related_state_report"])
    reencode = load_json(paths["reencode_audit"])
    public_codec = load_json(paths["public_codec_audit"])
    batch = load_json(paths["crmt_batch"])
    pf_overlay = load_json(paths["pf_overlay_report"])
    pm_overlay = load_json(paths["pm_overlay_report"])
    runtime = load_json(paths["runtime_report"])
    pm_runtime = load_json(paths["pm_runtime_report"])
    steam_integrity = load_json(paths["steam_integrity_recheck"])
    manual_qa = load_json(paths["manual_qa_checklist"])
    repo_root = Path(__file__).resolve().parents[3]
    public_codec_copy = repo_root / "rUGP/evidence/photon/crmt/codec-audit.json"
    public_failure_log = repo_root / "rUGP/evidence/photon/crmt/failures.json"
    public_structure_copy = (
        repo_root / "rUGP/evidence/photon/crmt/structure-trigger-audit.json"
    )
    public_decoder = repo_root / "rUGP/formats/images/crmti_decode.py"
    public_encoder = repo_root / "rUGP/formats/images/crmti_encode.py"
    public_replacer = repo_root / "rUGP/tools/images/replace_crmt.py"
    if runtime.get("game") != "PF" or pm_runtime.get("game") != "PM":
        raise ValueError("runtime report game identity mismatch")
    if sha256_file(public_codec_copy) != sha256_file(paths["public_codec_audit"]):
        raise ValueError("published codec audit is not the exact audited report")
    if sha256_file(public_structure_copy) != sha256_file(paths["structure_audit"]):
        raise ValueError("published structure audit is not the exact audited report")
    failure_log = load_json(public_failure_log)
    if failure_log.get("schema") != "photon-crmt-public-failure-log/v1":
        raise ValueError("published failure log schema mismatch")
    assert_portable_document(failure_log)

    review_by_id = {
        str(row["unique_id"]): row
        for row in visual["rows"]
        if row.get("comprehension_target")
    }
    trigger_by_id = {str(row["unique_id"]): row for row in trigger["targets"]}
    selection_by_id = {str(row["asset_id"]): row for row in selection["assets"]}
    if not set(review_by_id) == set(trigger_by_id) == set(selection_by_id):
        raise ValueError("target IDs do not close across review, trigger map and selection")
    public_codec_summary = public_codec["summary"]
    if not public_codec_summary.get("all_checks_pass"):
        raise ValueError("public codec real-record audit did not pass")
    if (
        public_codec_summary["audited_records"] != batch["summary"]["member_records"]
        or public_codec_summary["mips"] != batch["summary"]["mips"]
    ):
        raise ValueError("public codec audit does not close over the localized batch")
    if not steam_integrity["summary"].get("all_steam_game_rows_unchanged"):
        raise ValueError("Steam original integrity recheck did not pass")

    route_summary = structure["visual_assets"]["relation_summary"]
    expected_route_summary = {
        "assets": 56,
        "crmt_member_records": 66,
        "crmti_children": 377,
        "localized_visual_states": 57,
        "localized_replacement_records": 67,
        "overlay_routes": 67,
        "assets_with_exact_crsa_block": 47,
        "structurally_proven_unresolved_language_pairs": 9,
        "runtime_proven_assets": 0,
        "steam_files_written": 0,
    }
    for key, expected in expected_route_summary.items():
        if int(route_summary[key]) != expected:
            raise ValueError(f"structure audit route summary {key} changed")

    public_related_states = [
        state
        for target in structure["visual_assets"]["targets"]
        for state in target.get("related_states", [])
    ]
    if len(public_related_states) != 1:
        raise ValueError("expected exactly one related visual state")
    public_related_state = public_related_states[0]
    if (
        related_state.get("schema") != "photon-related-crmt-state-evidence/v1"
        or related_state.get("state_id") != public_related_state.get("state_id")
        or related_state.get("target_id") != "U0823"
    ):
        raise ValueError("related-state identity mismatch")
    localized_state = related_state["localized_state"]
    if not localized_state.get("all_six_mips_read_back"):
        raise ValueError("related-state mip readback did not pass")
    if related_state["boundary"].get("runtime_proven"):
        raise ValueError("related state unexpectedly claims runtime proof")
    if int(related_state["boundary"].get("steam_files_written", -1)) != 0:
        raise ValueError("related-state report wrote Steam files")
    if (
        localized_state["replacement_record_sha256"]
        != public_related_state["replacement_record_sha256"]
        or localized_state["overlay_sha256"]
        != public_related_state["overlay_sha256"]
    ):
        raise ValueError("related-state public/private hash mismatch")

    targets: list[dict[str, Any]] = []
    for asset_id in sorted(review_by_id):
        review = review_by_id[asset_id]
        trigger_row = trigger_by_id[asset_id]
        selected = selection_by_id[asset_id]
        render_path = resolve_from(paths["selection"], str(selected["render_report"]))
        if sha256_file(render_path) != str(selected["render_report_sha256"]).upper():
            raise ValueError(f"render report hash mismatch: {asset_id}")
        render = load_json(render_path)
        targets.append(
            {
                "asset_id": asset_id,
                "classification": review["classification"],
                "priority": review["priority"],
                "translation": render.get("translation"),
                "image": {
                    "width": review["image"]["width"],
                    "height": review["image"]["height"],
                    "meta_hex": review["image"]["meta_hex"],
                    "exact_duplicate_count": review["image"]["exact_duplicate_count"],
                },
                "selected_variant": selected["selected_variant"],
                "members": [
                    {
                        key: member.get(key)
                        for key in (
                            "candidate_id",
                            "game",
                            "volume",
                            "offset_hex",
                            "evidence_mode",
                        )
                    }
                    for member in review["static_evidence"]["members"]
                ],
                "trigger": {
                    "status": trigger_row["static_trigger_status"],
                    "work_attribution": trigger_row["work_attribution"],
                    "exact_crsa_occurrences": [
                        compact_occurrence(row)
                        for row in trigger_row["exact_crsa_occurrences"]
                    ],
                    "manual_scene_hypotheses": trigger_row["manual_scene_hypotheses"],
                    "runtime_proven": trigger_row["runtime_proven"],
                },
            }
        )

    def overlay_public(report: dict[str, Any]) -> dict[str, Any]:
        output = {
            key: report["output"][key]
            for key in ("bytes", "sha256", "footer_offset", "redirects")
        }
        if report.get("schema") == "photon-crmt-local-overlay-extension/v1":
            verification = report["verification"]
            required_checks = (
                "all_inherited_redirects_identical",
                "inherited_data_region_byte_identical",
                "one_new_route_only",
                "new_route_readback_byte_exact",
                "replacement_all_mips_previously_audited",
                "parent_header_preserved",
                "parent_trailer_and_plain_state_objref_preserved",
            )
            if not all(verification.get(key) for key in required_checks):
                raise ValueError("cumulative overlay extension validation failed")
            target_records = int(report["base"]["replacement_records_from_base_report"])
            related_records = 1
            summary = {
                "target_member_replacement_records": target_records,
                "related_state_replacement_records": related_records,
                "replacement_records": target_records + related_records,
                "all_inherited_redirects_identical": verification[
                    "all_inherited_redirects_identical"
                ],
                "one_new_route_only": verification["one_new_route_only"],
                "new_route_readback_byte_exact": verification[
                    "new_route_readback_byte_exact"
                ],
                "steam_files_written": verification["steam_files_written"],
            }
            kind = "cumulative_extension_final"
        else:
            base_summary = report["summary"]
            target_records = int(base_summary["replacement_records"])
            summary = {
                "target_member_replacement_records": target_records,
                "related_state_replacement_records": 0,
                "replacement_records": target_records,
                "all_replacements_read_back_exactly": base_summary[
                    "all_replacements_read_back_exactly"
                ],
                "all_unaffected_inherited_redirects_identical": base_summary[
                    "all_unaffected_inherited_redirects_identical"
                ],
                "steam_files_written": base_summary["steam_files_written"],
            }
            kind = "complete_base"
        return {
            "game": report["game"],
            "kind": kind,
            "summary": summary,
            "output": output,
        }

    def runtime_public(
        report: dict[str, Any],
        *,
        app_id: int,
        scope: str,
        manual_visual_qa: dict[str, Any],
    ) -> dict[str, Any]:
        messages = [
            row.get("message", "")
            for row in report.get("debug_output", {}).get("all_messages", [])
        ]
        return {
            "game": report["game"],
            "scope": scope,
            "tested_overlay_sha256": report.get("inputs", {}).get("ruo_sha256"),
            "observed_seconds": report["process"]["observed_seconds"],
            "process_survived_observation": report["process"][
                "exit_code_after_observation"
            ]
            is None,
            "steam_integration": {
                "shadow_process_registered_for_app_id": any(
                    f"Game process added : AppID {app_id}" in message
                    for message in messages
                ),
                "game_overlay_started": any(
                    "GameOverlay: started" in message for message in messages
                ),
                "stats_and_achievements_received": any(
                    "Received stats and achievements from Steam" in message
                    for message in messages
                ),
            },
            "shadow_executable_disk_unchanged": report["process"][
                "exe_disk_bytes_unchanged"
            ],
            "steam_game_file_handles_observed": report["handle_probe"][
                "steam_game_file_handles_observed"
            ],
            "shadow_ruo_open_observed": report["handle_probe"][
                "shadow_ruo_open_observed"
            ],
            "shadow_archive_integrity_unchanged": report[
                "shadow_archive_integrity"
            ]["size_mtime_and_ruo_hash_unchanged"],
            "manual_visual_qa": manual_visual_qa,
            "boundary": (
                "The shadow process and Steam integration are proven; transient "
                "archive handles were not sampled, so archive-use and visual "
                "acceptance remain separate manual gates."
            ),
        }

    pf_runtime_public = runtime_public(
        runtime,
        app_id=889700,
        scope="U0002 single-target pilot",
        manual_visual_qa=runtime["manual_visual_qa"],
    )
    pm_runtime_public = runtime_public(
        pm_runtime,
        app_id=889710,
        scope=(
            "base PM 46-member CRmt overlay; the later selected-state extension "
            "is not covered by this launch"
        ),
        manual_visual_qa={
            "status": "pending",
            "scope": (
                "base PM 46-member CRmt overlay plus the later selected-state "
                "extension"
            ),
        },
    )
    public_overlays = [overlay_public(pf_overlay), overlay_public(pm_overlay)]
    overlay_by_game = {row["game"]: row for row in public_overlays}
    structure_overlay_by_game = {
        row["game"]: row for row in structure["local_overlay_outputs"]["outputs"]
    }
    if set(overlay_by_game) != {"PF", "PM"}:
        raise ValueError("final overlay game set mismatch")
    for game, row in overlay_by_game.items():
        if row["output"]["sha256"] != structure_overlay_by_game[game]["sha256"]:
            raise ValueError(f"{game} final overlay hash differs from structure audit")
    if sum(
        int(row["summary"]["replacement_records"])
        for row in public_overlays
    ) != int(route_summary["overlay_routes"]):
        raise ValueError("final overlay replacement count does not close route summary")
    qa_summary = manual_qa["summary"]
    expected_qa_summary = {
        "assets": 56,
        "exact_crsa_assets": 47,
        "archive_or_hypothesis_assets": 9,
        "exact_crsa_checkpoints": 30,
        "exact_crsa_reference_occurrences": 72,
        "related_state_checks": 1,
        "localized_visual_states": 57,
        "final_overlay_routes": 67,
    }
    for key, expected in expected_qa_summary.items():
        if int(qa_summary[key]) != expected:
            raise ValueError(f"manual QA checklist summary {key} changed")
    if not qa_summary["all_trigger_targets_covered_once_by_class"]:
        raise ValueError("manual QA checklist does not close all targets")
    qa_overlay_by_game = {row["game"]: row for row in manual_qa["final_overlays"]}
    for game, row in overlay_by_game.items():
        if qa_overlay_by_game[game]["sha256"] != row["output"]["sha256"]:
            raise ValueError(f"manual QA checklist has stale {game} overlay")
    for game, runtime_row in (
        ("PF", pf_runtime_public),
        ("PM", pm_runtime_public),
    ):
        final_hash = overlay_by_game[game]["output"]["sha256"]
        runtime_row["final_overlay_sha256"] = final_hash
        runtime_row["final_overlay_runtime_tested"] = (
            runtime_row["tested_overlay_sha256"] == final_hash
        )
    document: dict[str, Any] = {
        "schema": "photon-crmt-localization-public-evidence/v2",
        "scope": "PF and PM comprehension-bearing foreign visual text in CRmt/CRmti assets",
        "method_boundary": (
            "Static census, codec closure and 67-route local overlay readback are "
            "complete. The recorded PF shadow launch covers one pilot target and "
            "the PM launch covers the 46-member base overlay, not either final "
            "overlay hash; full-route runtime and manual visual QA remain required."
        ),
        "toolchain": {
            "decoder": source(public_decoder),
            "encoder": source(public_encoder),
            "standalone_replacer": source(public_replacer),
            "evidence_exporter": source(Path(__file__).resolve()),
        },
        "published_evidence": {
            "localized_record_codec_audit": source(public_codec_copy),
            "structure_trigger_audit": source(public_structure_copy),
            "failure_log": source(public_failure_log),
        },
        "inputs": {key: source(path) for key, path in paths.items()},
        "census": {
            **candidates["summary"],
            "exact_unique_top_images": visual["summary"]["exact_unique_top_images"],
            "visible_text_or_identifier_unique_images": visual["summary"][
                "visible_text_or_identifier_unique_images"
            ],
            "relationships": relationships["totals"],
            "interpretation": (
                "CRmt and CRimp are sibling children of CObjectOcean; CRmti are "
                "CRmt mip children."
            ),
        },
        "codec_closure": reencode["summary"],
        "localized_record_codec_closure": public_codec_summary,
        "related_visual_state_codec_closure": {
            "states": 1,
            "records": 1,
            "mips": 6,
            "all_mips_read_back": localized_state["all_six_mips_read_back"],
            "replacement_record_sha256": localized_state[
                "replacement_record_sha256"
            ],
            "steam_files_written": related_state["boundary"]["steam_files_written"],
        },
        "localization_closure": batch["summary"],
        "visual_route_closure": route_summary,
        "trigger_closure": trigger["summary"],
        "related_visual_states": public_related_states,
        "overlays": public_overlays,
        "runtime_pilot": {
            "target_asset": "U0002",
            "expected_text": "数周后",
            **pf_runtime_public,
        },
        "runtime_full_shadow": pm_runtime_public,
        "manual_visual_qa_plan": {
            "status": "pending",
            "summary": qa_summary,
            "result_values": manual_qa["result_values"],
            "final_overlays": manual_qa["final_overlays"],
            "archive_only_boundary": manual_qa["archive_only_boundary"],
        },
        "steam_original_integrity": steam_integrity["summary"],
        "targets": targets,
    }
    write_new(args.output.resolve(), document)
    print(
        json.dumps(
            {
                "targets": len(targets),
                "member_records": sum(len(row["members"]) for row in targets),
                "output_sha256": sha256_file(args.output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
