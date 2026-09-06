from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import unittest


RUGP_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = (
    RUGP_ROOT
    / "evidence"
    / "photon"
    / "images"
    / "pm-watermelon-timer-runtime-routes-20260904.json"
)
ROUTE_AUTHORITY = RUGP_ROOT / "evidence" / "photon" / "routes" / "routes.json"
PM_EXACT = (
    RUGP_ROOT / "runtime" / "generated" / "photon_v6_pm_exact_rgba_table.generated.h"
)
PM_TARGETS = (
    RUGP_ROOT / "runtime" / "generated" / "photon_v6_pm_special40_table.generated.h"
)
SPECIAL_SIDECARS = (
    RUGP_ROOT / "runtime" / "generated" / "photon_v6_special57_table.generated.h"
)
PM_SELECTOR = RUGP_ROOT / "runtime" / "src" / "photon_v6_pm_selector_adapter.c"
PM_NATIVE = RUGP_ROOT / "runtime" / "src" / "photon_v6_pm_native_runtime.c"

SEALED_PM_TARGET_PREFIX_SHA256 = (
    "3345E0C73D10690BA769D6F006FCF0A4027B385A1AD0CD042D0E8A1740431372"
)
SEALED_SPECIAL_SIDECAR_PREFIX_SHA256 = (
    "DF8C9AB54F5404FFEC30A2547AF5B3D490EBA7B998C57CA62BE0A9C0FD826E5F"
)


def _hex_array(value: str) -> str:
    return "".join(re.findall(r"0x([0-9A-Fa-f]{2})", value)).upper()


def _canonical_sha256(rows: list[dict[str, object]]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest().upper()


def _parse_exact_table() -> list[dict[str, object]]:
    text = PM_EXACT.read_text(encoding="utf-8")
    pattern = re.compile(
        r"\{\s*UINT32_C\((?P<payload_bytes>\d+)\),\s*"
        r"UINT64_C\(0x(?P<fnv>[0-9A-Fa-f]+)\),\s*"
        r"UINT32_C\((?P<width>\d+)\),\s*"
        r"UINT32_C\((?P<height>\d+)\),\s*"
        r"\{(?P<png_sha>[^}]*)\},\s*"
        r"\{(?P<rgba_sha>[^}]*)\},\s*\}",
        re.DOTALL,
    )
    return [
        {
            "payload_bytes": int(match.group("payload_bytes")),
            "payload_fnv1a64": match.group("fnv").upper().zfill(16),
            "width": int(match.group("width")),
            "height": int(match.group("height")),
            "png_sha256": _hex_array(match.group("png_sha")),
            "rgba_sha256": _hex_array(match.group("rgba_sha")),
        }
        for match in pattern.finditer(text)
    ]


def _parse_pm_targets() -> list[dict[str, object]]:
    text = PM_TARGETS.read_text(encoding="utf-8")
    pattern = re.compile(
        r"\{\s*"
        r"(?P<payload_bytes>\d+)U,\s*UINT64_C\(0x(?P<fnv>[0-9A-Fa-f]+)\),\s*"
        r"\{(?P<sha>[^}]*)\},\s*"
        r'"(?P<source>[^"]+)",\s*"(?P<context>[^"]*)",\s*'
        r"(?P<stable_id>\d+)U\s*\},",
        re.DOTALL,
    )
    return [
        {
            "payload_bytes": int(match.group("payload_bytes")),
            "payload_fnv1a64": match.group("fnv").upper().zfill(16),
            "payload_sha256": _hex_array(match.group("sha")),
            "source_asset_id": match.group("source"),
            "context_identity_key": match.group("context"),
            "stable_id": int(match.group("stable_id")),
        }
        for match in pattern.finditer(text)
    ]


def _parse_special_sidecars() -> list[dict[str, object]]:
    text = SPECIAL_SIDECARS.read_text(encoding="utf-8")
    pattern = re.compile(
        r"\{\s*"
        r'"(?P<source>[^"]+)",\s*'
        r'"(?P<context>[^"]*)",\s*'
        r'L"(?P<path>[^"]+)",\s*'
        r"(?P<game>\d+)U,\s*(?P<payload_bytes>\d+)U,\s*"
        r"UINT64_C\(0x(?P<fnv>[0-9A-Fa-f]+)\),\s*"
        r"(?P<width>\d+)U,\s*(?P<height>\d+)U,\s*"
        r"\{(?P<png_sha>[^}]*)\},\s*"
        r"\{(?P<rgba_sha>[^}]*)\},\s*"
        r"(?P<owner>\d+)U,\s*(?P<context_route>\d+)U,\s*"
        r"(?P<offline_exact_owner>\d+)U\s*\},",
        re.DOTALL,
    )
    return [
        {
            "source_asset_id": match.group("source"),
            "context_identity_key": match.group("context"),
            "relative_path": match.group("path").replace("\\\\", "/"),
            "game": int(match.group("game")),
            "payload_bytes": int(match.group("payload_bytes")),
            "payload_fnv1a64": match.group("fnv").upper().zfill(16),
            "width": int(match.group("width")),
            "height": int(match.group("height")),
            "png_sha256": _hex_array(match.group("png_sha")),
            "rgba_sha256": _hex_array(match.group("rgba_sha")),
            "owner_route": int(match.group("owner")),
            "context_route": int(match.group("context_route")),
            "offline_exact_owner_route": int(match.group("offline_exact_owner")),
        }
        for match in pattern.finditer(text)
    ]


class PmWatermelonTimerRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        cls.routes = cls.evidence["routes"]
        cls.dynamic = [
            route for route in cls.routes if route["kind"] == "dynamic_timer_layer"
        ]
        cls.embedded = [
            route
            for route in cls.routes
            if route["kind"] == "embedded_tutorial_frame"
        ]
        cls.pm_exact = _parse_exact_table()
        cls.pm_targets = _parse_pm_targets()
        cls.special_sidecars = _parse_special_sidecars()
        cls.route_authority = json.loads(
            ROUTE_AUTHORITY.read_text(encoding="utf-8")
        )["rows"]

    def test_evidence_accounts_for_every_logical_and_physical_route(self) -> None:
        scope = self.evidence["scope"]
        physical = {
            (
                route["payload_bytes"],
                route["payload_fnv1a64"],
                route["payload_sha256"],
            )
            for route in self.routes
        }
        self.assertEqual(
            self.evidence["schema"],
            "photon-pm-watermelon-timer-runtime-routes/v2",
        )
        self.assertEqual(len(self.routes), scope["logical_routes"])
        self.assertEqual(len(physical), scope["unique_physical_routes"])
        self.assertEqual(len(self.dynamic), scope["dynamic_timer_layers"])
        self.assertEqual(len(self.embedded), scope["embedded_tutorial_frames"])
        self.assertEqual(
            len(
                {
                    (
                        route["payload_bytes"],
                        route["payload_fnv1a64"],
                        route["payload_sha256"],
                    )
                    for route in self.embedded
                }
            ),
            scope["unique_embedded_tutorial_payloads"],
        )
        self.assertEqual(scope["repointed_existing_special_targets"], 0)
        self.assertEqual(scope["appended_special_targets"], 11)

        duplicate = next(
            route for route in self.embedded if "duplicate_physical_identity_of" in route
        )
        original = next(
            route
            for route in self.embedded
            if route["source_asset_id"] == duplicate["duplicate_physical_identity_of"]
        )
        for key in (
            "payload_bytes",
            "payload_fnv1a64",
            "payload_sha256",
            "sidecar",
            "sidecar_png_bytes",
            "sidecar_png_sha256",
            "sidecar_rgba_sha256",
            "size",
            "context_identity_key",
        ):
            self.assertEqual(duplicate[key], original[key], key)

    def test_all_dynamic_routes_keep_the_official_translation_mapping(self) -> None:
        authority_by_source = {
            route["source_asset_id"]: route for route in self.route_authority
        }
        self.assertEqual(
            [route["timer"] for route in self.dynamic],
            ["300", "270", "240", "210", "180", "150", "120", "90", "60", "30", "0"],
        )
        for route in self.dynamic:
            with self.subTest(timer=route["timer"]):
                authority = authority_by_source[route["source_asset_id"]]
                self.assertEqual(authority["target_asset_id"], route["target_asset_id"])
                self.assertEqual(
                    authority["route_authority"]["authority"],
                    "official_pm_raw_locale_table_source_then_translation_field",
                )
                self.assertTrue(authority["route_authority"]["semantic_peer_proven"])

                self.assertEqual(len(route["ordinary_table_indices"]), 1)
                table = self.pm_exact[route["ordinary_table_indices"][0]]
                expected = {
                    "payload_bytes": route["payload_bytes"],
                    "payload_fnv1a64": route["payload_fnv1a64"],
                    "width": route["size"][0],
                    "height": route["size"][1],
                    "png_sha256": route["sidecar_png_sha256"],
                    "rgba_sha256": route["sidecar_rgba_sha256"],
                }
                for key, value in expected.items():
                    self.assertEqual(table[key], value, key)
                expected_name = (
                    f"{route['payload_bytes']:010d}_{route['payload_fnv1a64']}.png"
                )
                self.assertEqual(route["sidecar"], f"sidecars/PM/{expected_name}")

    def test_only_existing_dynamic_exceptions_remain_special(self) -> None:
        by_stable_id = {target["stable_id"]: target for target in self.pm_targets}
        for timer, stable_id in (("30", 4), ("0", 5)):
            route = next(value for value in self.dynamic if value["timer"] == timer)
            target = by_stable_id[stable_id]
            self.assertEqual(route["existing_special_target_stable_id"], stable_id)
            for key in (
                "source_asset_id",
                "payload_bytes",
                "payload_fnv1a64",
                "payload_sha256",
                "context_identity_key",
            ):
                self.assertEqual(target[key], route[key], key)

        self.assertTrue(
            all(
                "existing_special_target_stable_id" not in route
                for route in self.dynamic[:-2]
            )
        )

    def test_pm_target_addendum_preserves_the_sealed_first_39(self) -> None:
        scope = self.evidence["scope"]
        self.assertEqual(len(self.pm_targets), scope["pm_special_target_count_after"])
        self.assertEqual(
            [target["stable_id"] for target in self.pm_targets], list(range(1, 51))
        )
        self.assertEqual(
            _canonical_sha256(self.pm_targets[:39]), SEALED_PM_TARGET_PREFIX_SHA256
        )

        unique_embedded = [
            route
            for route in self.embedded
            if "duplicate_physical_identity_of" not in route
        ]
        for stable_id, route in zip(range(40, 51), unique_embedded, strict=True):
            target = self.pm_targets[stable_id - 1]
            self.assertEqual(route["appended_special_target_stable_id"], stable_id)
            for key in (
                "source_asset_id",
                "payload_bytes",
                "payload_fnv1a64",
                "payload_sha256",
                "context_identity_key",
            ):
                self.assertEqual(target[key], route[key], key)

        duplicate_source = next(
            route["source_asset_id"]
            for route in self.embedded
            if "duplicate_physical_identity_of" in route
        )
        self.assertNotIn(
            duplicate_source,
            {target["source_asset_id"] for target in self.pm_targets},
        )

        header = PM_TARGETS.read_text(encoding="utf-8")
        self.assertRegex(
            header,
            r"PHOTON_V6_PM_TRANSLATION_WITNESS_FIRST_INDEX\s+UINT32_C\(39\)",
        )
        self.assertRegex(
            header, r"PHOTON_V6_PM_TRANSLATION_WITNESS_COUNT\s+UINT32_C\(11\)"
        )

    def test_combined_sidecar_addendum_matches_the_reviewed_images(self) -> None:
        scope = self.evidence["scope"]
        self.assertEqual(
            len(self.special_sidecars), scope["combined_special_sidecar_count_after"]
        )
        self.assertEqual(
            _canonical_sha256(self.special_sidecars[:57]),
            SEALED_SPECIAL_SIDECAR_PREFIX_SHA256,
        )
        appended = self.special_sidecars[57:]
        header = SPECIAL_SIDECARS.read_text(encoding="utf-8")
        guard = header.index("#if defined(PHOTON_BUILD_PM)")
        first_append = header.index(f'"{appended[0]["source_asset_id"]}"')
        guard_end = header.index("#endif", first_append)
        self.assertLess(guard, first_append)
        self.assertLess(first_append, guard_end)
        unique_embedded = [
            route
            for route in self.embedded
            if "duplicate_physical_identity_of" not in route
        ]
        self.assertEqual(len(appended), len(unique_embedded))
        for sidecar, route in zip(appended, unique_embedded, strict=True):
            with self.subTest(source=route["source_asset_id"]):
                expected = {
                    "source_asset_id": route["source_asset_id"],
                    "context_identity_key": route["context_identity_key"],
                    "relative_path": route["sidecar"],
                    "game": 2,
                    "payload_bytes": route["payload_bytes"],
                    "payload_fnv1a64": route["payload_fnv1a64"],
                    "width": route["size"][0],
                    "height": route["size"][1],
                    "png_sha256": route["sidecar_png_sha256"],
                    "rgba_sha256": route["sidecar_rgba_sha256"],
                    "owner_route": 1,
                    "context_route": 1,
                    "offline_exact_owner_route": 1,
                }
                for key, value in expected.items():
                    self.assertEqual(sidecar[key], value, key)

    def test_selector_uses_the_observed_action_stack_and_cold_save_witness(self) -> None:
        selector = PM_SELECTOR.read_text(encoding="utf-8")
        native = PM_NATIVE.read_text(encoding="utf-8")
        action_stack = re.search(
            r"static int exact_action_stack\(void\) \{(?P<body>.*?)\n\}",
            selector,
            re.DOTALL,
        )
        self.assertIsNotNone(action_stack)
        assert action_stack is not None
        self.assertEqual(
            re.findall(r"0x[0-9A-Fa-f]{8}", action_stack.group("body")),
            ["0x00043132", "0x00042409", "0x00122EB8", "0x0012D327"],
        )
        self.assertIn("bootstrap_translation_from_witness", selector)
        self.assertIn("target_is_translation_witness", selector)
        self.assertIn("action_bind_candidate", selector)
        self.assertIn("action_same_value", selector)
        self.assertIsNotNone(
            re.search(
                r"target_is_translation_witness\(\(uint32_t\)exact\).*?"
                r"bootstrap_translation_from_witness\(\(uint32_t\)exact\)",
                selector,
                re.DOTALL,
            )
        )
        self.assertRegex(
            native, r"PHOTON_NATIVE_SPECIAL_TARGET_COUNT\s+UINT32_C\(50\)"
        )
        self.assertRegex(
            native,
            r"PHOTON_NATIVE_SPECIAL_VALID_TARGET_COUNT\s+UINT32_C\(50\)",
        )

    def test_runtime_artifact_ledger_is_portable_and_hash_complete(self) -> None:
        runtime = self.evidence["runtime_evidence"]
        for key in (
            "options_japanese_image_chinese_text",
            "options_translation_selected",
            "translation_target_without_overlay",
            "setter_trace",
            "all_calls_control",
        ):
            artifact = runtime[key]
            self.assertEqual(Path(artifact["file"]).name, artifact["file"])
            self.assertGreater(artifact["bytes"], 0)
            self.assertRegex(artifact["sha256"], r"^[0-9A-F]{64}$")
        self.assertEqual(runtime["setter_trace"]["old_stack_matches"], 0)
        self.assertEqual(
            runtime["fresh_saved_position"]["setter_events_before_options"], 0
        )
        self.assertIn("no 831/8311 observed", runtime["status"])
        samples = runtime["after_fix_samples"]
        self.assertEqual(
            [sample["file"] for sample in samples],
            [
                "pm-watermelon-timer-300-live-20260905.png",
                "pm-watermelon-timer-0-closed-ring-live-20260905.png",
                "pm-watermelon-tutorial-choice-live-20260905.png",
                "pm-watermelon-gameplay-300-live-20260905.png",
            ],
        )
        for sample in samples:
            with self.subTest(file=sample["file"]):
                self.assertEqual(Path(sample["file"]).name, sample["file"])
                self.assertGreater(sample["bytes"], 0)
                self.assertRegex(sample["sha256"], r"^[0-9A-F]{64}$")


if __name__ == "__main__":
    unittest.main()
