from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rugp.tools.provenance import audit_photon_locale_bindings as MODULE


class PhotonLocaleBindingAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name).resolve()
        self.state_path = self.workspace / "checkpoint" / "production_state.json"
        self.classification_path = self.workspace / "classification" / "manifest.json"
        self.canonical_root = self.workspace / "canonical"
        self.snapshot_root = self.workspace / "private-lfs-snapshot"
        self.vertical_root = self.workspace / "vertical-evidence"
        self.route_path = self.workspace / "routes" / "routes_2.v1.json"

        state_entries = []
        classification_entries = []
        snapshot_entries = []
        for index in (1, 2):
            asset_id = f"pf:rio000:0x0000000{index}"
            raw = self.canonical_root / "pf" / "images" / f"jp-{index}.png"
            candidate = self.workspace / "candidates" / f"cn-{index}.png"
            raw.parent.mkdir(parents=True, exist_ok=True)
            candidate.parent.mkdir(parents=True, exist_ok=True)
            raw.write_bytes(f"official-japanese-{index}".encode())
            candidate.write_bytes(f"localized-candidate-{index}".encode())
            raw_hash = MODULE.sha256_file(raw)
            candidate_hash = MODULE.sha256_file(candidate)
            state_entries.append(
                {
                    "asset_id": asset_id,
                    "game": "PF",
                    "status": "ready_confirmed",
                    "raw_source_png": str(raw),
                    "raw_source_png_sha256": raw_hash,
                    "candidate_png": str(candidate),
                    "candidate_png_sha256": candidate_hash,
                }
            )
            classification_entries.append(
                {
                    "id": asset_id,
                    "game": "PF",
                    "source_png_sha256": raw_hash,
                    "source": {
                        "raw_image": f"../pf/images/jp-{index}.png",
                        "width": 148,
                        "height": 228,
                    },
                    "decision": {"code": "must_translate"},
                    "visual": {
                        "family_id": "family-one",
                        "template_id": "template-one",
                        "state": "enabled",
                        "locale_reference": False,
                        "locale_relation": (
                            ["pf:rio000:0x00001001"] if index == 1 else []
                        ),
                    },
                }
            )

            snapshot_relative = (
                f"assets/candidates/{candidate_hash[:2].lower()}/"
                f"{candidate_hash.lower()}.png"
            )
            snapshot_candidate = self.snapshot_root / snapshot_relative
            snapshot_candidate.parent.mkdir(parents=True, exist_ok=True)
            snapshot_candidate.write_bytes(candidate.read_bytes())
            snapshot_entries.append(
                {
                    "asset_id": asset_id,
                    "candidate_png": snapshot_relative,
                    "candidate_png_sha256": candidate_hash,
                }
            )

        english = self.canonical_root / "pf" / "images" / "en-1.png"
        english.write_bytes(b"official-english-one")
        classification_entries.append(
            {
                "id": "pf:rio000:0x00001001",
                "game": "PF",
                "source_png_sha256": MODULE.sha256_file(english),
                "source": {
                    "raw_image": "../pf/images/en-1.png",
                    "width": 148,
                    "height": 228,
                },
                "decision": {"code": "pass_english_numeric"},
                "visual": {
                    "family_id": "family-one",
                    "template_id": "template-one",
                    "state": "enabled",
                    "locale_reference": True,
                    "locale_relation": [],
                },
            }
        )

        self.state_path.parent.mkdir(parents=True)
        self.state_path.write_text(
            json.dumps({"entries": state_entries}, indent=2) + "\n",
            encoding="utf-8",
        )
        self.classification_path.parent.mkdir(parents=True)
        self.classification_path.write_text(
            json.dumps({"entries": classification_entries}, indent=2) + "\n",
            encoding="utf-8",
        )
        self.state_hash = MODULE.sha256_file(self.state_path)
        self.classification_hash = MODULE.sha256_file(self.classification_path)

        self.snapshot_root.mkdir(exist_ok=True)
        (self.snapshot_root / "portable_manifest.json").write_text(
            json.dumps(
                {"production_state": {"entries": snapshot_entries}}, indent=2
            )
            + "\n",
            encoding="utf-8",
        )
        (self.snapshot_root / "snapshot_report.json").write_text(
            json.dumps(
                {
                    "source_sha256_before": {
                        "production_state": self.state_hash
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        staged_english = self.vertical_root / "same-state-en.png"
        staged_english.parent.mkdir(parents=True)
        staged_english.write_bytes(b"unproven-staged-english-evidence")
        qa = self.vertical_root / "qa.json"
        qa.write_text(
            json.dumps({"files": {"same_state_en": str(staged_english)}}, indent=2)
            + "\n",
            encoding="utf-8",
        )
        (self.vertical_root / "manifest.json").write_text(
            json.dumps(
                {
                    "rows": [
                        {
                            "asset_id": "pf:rio000:0x00000002",
                            "qa": str(qa),
                        }
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        candidate_hashes = [
            entry["candidate_png_sha256"] for entry in state_entries
        ]
        self.route_document = {
            "schema": "photon-image-routes-test/v1",
            "count": 2,
            "release": False,
            "rows": [
                {
                    "ordinal": 1,
                    "source_asset_id": "pf:rio000:0x00000001",
                    "target_asset_id": "pf:rio000:0x00001001",
                    "route_kind": MODULE.TRANSLATION_ROUTE_KIND,
                    "route_authority": {
                        "authority": "synthetic_authenticated_peer",
                        "semantic_peer_proven": True,
                        "route_handoff_v2_sha256": "1" * 64,
                    },
                    "source_codec": "Cr6Ti",
                    "target_codec": "Cr6Ti",
                    "target_kind": 2,
                    "candidate_sha256": candidate_hashes[0],
                    "candidate_size": [148, 228],
                    "target_size": [148, 228],
                    "encoder_record_bytes": 100,
                    "encoder_record_sha256": "2" * 64,
                    "official_target_extent": 120,
                    "release_authorized": False,
                    "runtime_state": "STATIC_ONLY",
                    "blocker": "synthetic runtime not tested",
                    "native_range": {
                        "physical_target": {
                            "game": "PF",
                            "filename": "synthetic.rio",
                            "offset": 4096,
                            "offset_hex": "0x1000",
                            "extent": 120,
                            "clean_volume_bytes": 9999,
                            "clean_volume_sha256": "3" * 64,
                        },
                        "official_exact_span": {
                            "path": "C:\\must-not-leak\\official.bin",
                            "bytes": 120,
                            "sha256": "4" * 64,
                        },
                        "candidate_record_prefix": {
                            "path": "C:\\must-not-leak\\candidate.bin",
                            "bytes": 100,
                            "sha256": "2" * 64,
                            "header": {
                                "width": 148,
                                "height": 228,
                                "kind": 2,
                            },
                            "complete_self_described_record": True,
                        },
                        "official_tail": {"bytes": 20, "sha256": "5" * 64},
                        "candidate_exact_span": {
                            "bytes": 120,
                            "sha256": "6" * 64,
                        },
                        "rollback": {
                            "kind": "restore_exact_official_span",
                            "offset": 4096,
                            "extent": 120,
                            "official_span_path": "C:\\must-not-leak\\official.bin",
                            "official_span_sha256": "4" * 64,
                        },
                    },
                },
                {
                    "ordinal": 2,
                    "source_asset_id": "pf:rio000:0x00000002",
                    "target_asset_id": "pf:rio000:0x00000002",
                    "route_kind": MODULE.SHARED_ROUTE_KIND,
                    "route_authority": {
                        "authority": "synthetic_authenticated_common_parent",
                        "shared_across_locales_proven": True,
                        "remaining42_manifest_sha256": "7" * 64,
                        "remaining42_parent_sha256": "8" * 64,
                        "family_shared_proof_sha256": "9" * 64,
                        "family_transports_sha256": "C" * 64,
                        "evidence": {
                            "parent_evidence_id": "SYNTHETIC_COMMON_PARENT",
                            "authenticated_parent_plaintext_sha256": "A" * 64,
                            "interpretation": "synthetic endpoint is common across locales",
                        },
                    },
                    "source_codec": "Cr6Ti",
                    "target_codec": "Cr6Ti",
                    "target_kind": 2,
                    "candidate_sha256": candidate_hashes[1],
                    "candidate_size": [148, 228],
                    "target_size": [148, 228],
                    "encoder_record_bytes": 110,
                    "encoder_record_sha256": "B" * 64,
                    "official_target_extent": 130,
                    "release_authorized": False,
                    "runtime_state": "STATIC_ONLY",
                    "blocker": "synthetic runtime not tested",
                    "native_range": None,
                },
            ],
        }
        self._write_route_closure()
        self.input_hashes = {
            "state": MODULE.sha256_file(self.state_path),
            "classification": MODULE.sha256_file(self.classification_path),
            "snapshot_manifest": MODULE.sha256_file(
                self.snapshot_root / "portable_manifest.json"
            ),
            "snapshot_report": MODULE.sha256_file(
                self.snapshot_root / "snapshot_report.json"
            ),
            "route_closure": MODULE.sha256_file(self.route_path),
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_route_closure(self) -> None:
        self.route_path.parent.mkdir(parents=True, exist_ok=True)
        self.route_path.write_text(
            json.dumps(self.route_document, indent=2) + "\n", encoding="utf-8"
        )

    def test_metadata_only_binding_audit_reports_exact_gaps(self) -> None:
        output = self.workspace / "binding-snapshot"
        result = MODULE.export_audit(
            workspace_root=self.workspace,
            production_state_path=self.state_path,
            classification_path=self.classification_path,
            canonical_root=self.canonical_root,
            candidate_snapshot_root=self.snapshot_root,
            vertical_evidence_root=self.vertical_root,
            output_path=output,
            expected_state_sha256=self.state_hash,
            expected_classification_sha256=self.classification_hash,
        )

        summary = result["summary"]
        self.assertEqual(summary["production_entries"], 2)
        self.assertEqual(summary["candidate_file_available"], 2)
        self.assertEqual(summary["candidate_valid"], 2)
        self.assertEqual(summary["candidate_private_snapshot_backed"], 2)
        self.assertEqual(summary["japanese_source_valid"], 2)
        self.assertEqual(summary["japanese_classification_bound"], 2)
        self.assertEqual(summary["english_explicit_production_binding"], 0)
        self.assertEqual(summary["english_metadata_exact_candidate"], 1)
        self.assertEqual(summary["english_mapping_unproven"], 1)
        self.assertEqual(summary["vertical_staging_evidence_present"], 1)
        self.assertEqual(result["absolute_path_leaks"], 0)
        self.assertEqual(result["images_copied"], 0)

        gaps = json.loads((output / "missing_bindings.json").read_text("utf-8"))
        self.assertEqual(gaps["candidate_or_private_snapshot_gaps"], [])
        self.assertEqual(gaps["japanese_source_or_classification_gaps"], [])
        self.assertEqual(gaps["formal_english_production_binding_gap_count"], 2)
        self.assertEqual(gaps["english_same_state_evidence_gap_count"], 1)
        self.assertEqual(list(output.rglob("*.png")), [])
        self.assertEqual(MODULE.scan_absolute_leaks(output), [])

        self.assertEqual(MODULE.sha256_file(self.state_path), self.input_hashes["state"])
        self.assertEqual(
            MODULE.sha256_file(self.classification_path),
            self.input_hashes["classification"],
        )
        self.assertEqual(
            MODULE.sha256_file(self.snapshot_root / "portable_manifest.json"),
            self.input_hashes["snapshot_manifest"],
        )
        self.assertEqual(
            MODULE.sha256_file(self.snapshot_root / "snapshot_report.json"),
            self.input_hashes["snapshot_report"],
        )

    def test_wrong_expected_hash_fails_without_output(self) -> None:
        output = self.workspace / "refused"
        with self.assertRaises(MODULE.BindingAuditError):
            MODULE.export_audit(
                workspace_root=self.workspace,
                production_state_path=self.state_path,
                classification_path=self.classification_path,
                canonical_root=self.canonical_root,
                candidate_snapshot_root=self.snapshot_root,
                output_path=output,
                expected_state_sha256="0" * 64,
            )
        self.assertFalse(output.exists())

    def test_authoritative_route_closure_proves_all_targets_metadata_only(self) -> None:
        output = self.workspace / "route-binding-snapshot"
        result = MODULE.export_audit(
            workspace_root=self.workspace,
            production_state_path=self.state_path,
            classification_path=self.classification_path,
            canonical_root=self.canonical_root,
            candidate_snapshot_root=self.snapshot_root,
            vertical_evidence_root=self.vertical_root,
            route_closure_path=self.route_path,
            expected_route_count=2,
            output_path=output,
            expected_state_sha256=self.state_hash,
            expected_classification_sha256=self.classification_hash,
            expected_route_closure_sha256=MODULE.sha256_file(self.route_path),
        )

        summary = result["summary"]
        self.assertTrue(summary["route_closure_present"])
        self.assertTrue(summary["authoritative_route_source_set_exact"])
        self.assertEqual(summary["authoritative_route_bindings"], 2)
        self.assertEqual(summary["authoritative_translation_peer_routes"], 1)
        self.assertEqual(summary["authoritative_shared_endpoint_routes"], 1)
        self.assertEqual(summary["official_target_decoded_png_verified"], 2)
        self.assertEqual(summary["official_target_decoded_png_absent"], 0)
        self.assertEqual(summary["official_target_exact_span_authenticated"], 1)
        self.assertEqual(summary["official_target_header_hash_embedded"], 0)
        self.assertEqual(summary["route_candidate_matches_current"], 2)
        self.assertEqual(summary["english_mapping_unproven"], 0)
        self.assertEqual(summary["fabricated_official_target_pngs"], 0)

        gaps = json.loads((output / "missing_bindings.json").read_text("utf-8"))
        self.assertEqual(gaps["authoritative_route_binding_gap_count"], 0)
        self.assertEqual(gaps["english_same_state_evidence_gap_count"], 0)
        # Production-state compatibility fields remain informationally absent.
        self.assertEqual(gaps["formal_english_production_binding_gap_count"], 2)

        manifest = json.loads((output / "binding_manifest.json").read_text("utf-8"))
        by_id = {row["asset_id"]: row for row in manifest["bindings"]}
        first = by_id["pf:rio000:0x00000001"]["official_english_same_state"][
            "authoritative_route"
        ]
        self.assertEqual(first["target_asset_id"], "pf:rio000:0x00001001")
        self.assertEqual(
            first["native_identity"]["official_exact_span_sha256"], "4" * 64
        )
        self.assertNotIn("path", first["native_identity"]["official_exact_span"])
        self.assertNotIn("official_span_path", first["native_identity"]["rollback"])
        self.assertEqual(list(output.rglob("*.png")), [])
        self.assertEqual(MODULE.scan_absolute_leaks(output), [])
        self.assertEqual(
            MODULE.sha256_file(self.route_path), self.input_hashes["route_closure"]
        )

    def test_absent_decoded_target_keeps_authenticated_native_identity(self) -> None:
        self.route_document["rows"][0][
            "target_asset_id"
        ] = "pf:rio000:0x00abcdef"
        self._write_route_closure()
        output = self.workspace / "route-target-without-png"
        result = MODULE.export_audit(
            workspace_root=self.workspace,
            production_state_path=self.state_path,
            classification_path=self.classification_path,
            canonical_root=self.canonical_root,
            candidate_snapshot_root=self.snapshot_root,
            route_closure_path=self.route_path,
            expected_route_count=2,
            output_path=output,
        )
        self.assertEqual(result["summary"]["authoritative_route_bindings"], 2)
        self.assertEqual(result["summary"]["official_target_decoded_png_absent"], 1)
        manifest = json.loads((output / "binding_manifest.json").read_text("utf-8"))
        route = next(
            row["official_english_same_state"]["authoritative_route"]
            for row in manifest["bindings"]
            if row["route_asset_id"] == "pf:rio000:0x00000001"
        )
        decoded = route["official_decoded_target_png"]
        self.assertEqual(decoded["status"], "official_decoded_png_absent")
        self.assertIsNone(decoded["logical_ref"])
        self.assertEqual(
            route["native_identity"]["target_asset_id"],
            "pf:rio000:0x00abcdef",
        )
        self.assertEqual(list(output.rglob("*.png")), [])

    def test_route_closure_fail_closed_invariants(self) -> None:
        mutations = {
            "source_set": lambda rows: rows[0].__setitem__(
                "source_asset_id", "pf:rio000:0x00fffffe"
            ),
            "translation_self_target": lambda rows: rows[0].__setitem__(
                "target_asset_id", rows[0]["source_asset_id"]
            ),
            "shared_target_differs": lambda rows: rows[1].__setitem__(
                "target_asset_id", "pf:rio000:0x00001001"
            ),
            "shared_proof_missing": lambda rows: rows[1][
                "route_authority"
            ].__setitem__("shared_across_locales_proven", False),
        }
        original = json.loads(json.dumps(self.route_document))
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                self.route_document = json.loads(json.dumps(original))
                mutate(self.route_document["rows"])
                self._write_route_closure()
                output = self.workspace / f"refused-{name}"
                with self.assertRaises(MODULE.BindingAuditError):
                    MODULE.export_audit(
                        workspace_root=self.workspace,
                        production_state_path=self.state_path,
                        classification_path=self.classification_path,
                        canonical_root=self.canonical_root,
                        candidate_snapshot_root=self.snapshot_root,
                        route_closure_path=self.route_path,
                        expected_route_count=2,
                        output_path=output,
                    )
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
