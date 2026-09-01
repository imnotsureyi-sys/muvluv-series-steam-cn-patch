from __future__ import annotations

import unittest

from rUGP.tools.images.sanitize_route_closure import SanitizeError, sanitize


class SanitizeRouteClosureTests(unittest.TestCase):
    def test_removes_only_nonportable_locator_fields_and_keeps_authority(self) -> None:
        source = {
            "schema": "fixture",
            "rows": [
                {
                    "native_range": {
                        "candidate": {
                            "path": "outputs/staging/candidate.bin",
                            "bytes": 3,
                            "sha256": "A" * 64,
                        },
                        "rollback": {
                            "official_span_path": "local-internal/official.bin",
                            "official_span_sha256": "B" * 64,
                        },
                    }
                }
            ],
        }
        clean = sanitize(source, expected_removed=2)
        candidate = clean["rows"][0]["native_range"]["candidate"]
        self.assertNotIn("path", candidate)
        self.assertEqual(candidate["bytes"], 3)
        self.assertEqual(candidate["sha256"], "A" * 64)
        self.assertEqual(
            clean["artifact_locator_policy"]["removed_locator_fields"], 2
        )

    def test_fails_when_scope_or_unknown_local_locator_drifts(self) -> None:
        with self.assertRaisesRegex(SanitizeError, "count mismatch"):
            sanitize({"path": "outputs/a"}, expected_removed=2)
        with self.assertRaisesRegex(SanitizeError, "non-portable locator"):
            sanitize({"source_file": "OuTpUtS\\not-an-approved-path-field"})

    def test_removes_casefolded_windows_staging_locator_in_approved_fields(self) -> None:
        clean = sanitize(
            {
                "path": "OuTpUtS\\staging\\candidate.bin",
                "official_span_path": "LOCAL-INTERNAL\\official.bin",
                "portable_path": "native-records/PF/candidate.record",
            },
            expected_removed=2,
        )
        self.assertNotIn("path", clean)
        self.assertNotIn("official_span_path", clean)
        self.assertEqual(clean["portable_path"], "native-records/PF/candidate.record")

    def test_rejects_absolute_unc_parent_and_retained_backslash_locators(self) -> None:
        cases = {
            "windows drive": {"path": r"Q:\outside\secret.bin"},
            "UNC": {"path": r"\\server\share\secret.bin"},
            "POSIX absolute": {"path": "/home/alice/secret.bin"},
            "parent traversal": {"path": "../outputs/secret.bin"},
            "parent after staging root": {"path": "outputs/../secret.bin"},
            "retained backslash": {"portable_path": r"native-records\PF\secret.bin"},
        }
        for name, document in cases.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(
                    SanitizeError, "(?:non-portable|ambiguous private) locator"
                ):
                    sanitize(document)


if __name__ == "__main__":
    unittest.main()
