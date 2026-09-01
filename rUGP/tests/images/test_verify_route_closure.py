from __future__ import annotations

import json
from pathlib import Path
import unittest

from rUGP.tools.images.verify_route_closure import RouteError, SHARED, TRANSLATION, verify


HASH = "A" * 64


def route(ordinal: int, source: str, target: str, kind: str) -> dict[str, object]:
    if kind == TRANSLATION:
        authority = {
            "authority": "synthetic-peer-proof",
            "semantic_peer_proven": True,
            "route_handoff_v2_sha256": HASH,
        }
    else:
        authority = {
            "authority": "synthetic-common-proof",
            "shared_across_locales_proven": True,
            "remaining42_manifest_sha256": HASH,
            "remaining42_parent_sha256": HASH,
            "family_shared_proof_sha256": HASH,
            "family_transports_sha256": HASH,
            "evidence": {"parent_evidence_id": "parent", "interpretation": "shared"},
        }
    return {
        "ordinal": ordinal,
        "source_asset_id": source,
        "target_asset_id": target,
        "route_kind": kind,
        "route_authority": authority,
        "source_codec": "Cr6Ti",
        "target_codec": "Cr6Ti",
        "target_kind": 3,
        "target_size": [16, 16],
        "encoder_record_sha256": HASH,
    }


class RouteClosureTests(unittest.TestCase):
    def fixtures(self) -> tuple[dict[str, object], dict[str, object]]:
        rows = [
            route(1, "pf:rio000:0x10", "pf:rio000:0x20", TRANSLATION),
            route(2, "pm:rio001:0x30", "pm:rio001:0x30", SHARED),
        ]
        return (
            {"schema": "photon-image-routes-1490/v1", "count": 2, "rows": rows},
            {"asset_count": 2, "entries": [
                {"asset_id": "pf:rio000:0x10"},
                {"asset_id": "pm:rio001:0x30"},
            ]},
        )

    def test_proves_exact_translation_and_shared_census(self) -> None:
        routes, images = self.fixtures()
        result = verify(
            routes,
            images,
            expected_total=2,
            expected_translation=1,
            expected_shared=1,
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["games"], {"PF": 1, "PM": 1})

    def test_shared_route_cannot_point_at_a_different_endpoint(self) -> None:
        routes, images = self.fixtures()
        routes["rows"][1]["target_asset_id"] = "pm:rio001:0x40"
        with self.assertRaisesRegex(RouteError, "unproven shared endpoint"):
            verify(routes, images, expected_total=2, expected_translation=1, expected_shared=1)

    def test_slot_map_observation_count_is_not_an_artifact_hash_count(self) -> None:
        routes, images = self.fixtures()
        routes["rows"][0]["route_authority"] = {
            "authority": "synthetic-slot-map",
            "slot_map_sha256": HASH,
            "evidence_count": 3,
            "evidence_sha256": [],
            "confidence": "high",
            "slot_form": "translation",
        }
        result = verify(
            routes,
            images,
            expected_total=2,
            expected_translation=1,
            expected_shared=1,
        )
        self.assertEqual(result["status"], "PASS")
        routes["rows"][0]["route_authority"]["evidence_sha256"] = ["not-a-hash"]
        with self.assertRaisesRegex(RouteError, "unproven translation peer"):
            verify(
                routes,
                images,
                expected_total=2,
                expected_translation=1,
                expected_shared=1,
            )

    def test_public_authority_is_portable_and_still_closes_all_routes(self) -> None:
        root = Path(__file__).resolve().parents[3]
        routes = json.loads(
            (
                root
                / "rUGP"
                / "evidence"
                / "photon"
                / "routes"
                / "routes.json"
            ).read_text(encoding="utf-8")
        )
        images = json.loads(
            (
                root
                / "rUGP"
                / "evidence"
                / "photon"
                / "images"
                / "manifest.json"
            ).read_text(encoding="utf-8")
        )
        policy = routes["artifact_locator_policy"]
        self.assertFalse(policy["local_staging_paths_published"])
        self.assertEqual(policy["removed_locator_fields"], 1355)
        serialized = json.dumps(routes, ensure_ascii=False)
        self.assertNotIn("outputs/", serialized)
        self.assertNotIn("local-internal/", serialized)
        self.assertEqual(verify(routes, images)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
