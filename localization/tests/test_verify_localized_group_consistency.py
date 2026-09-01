from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


from localization.tools.images import verify_localized_group_consistency as MODULE


REFERENCE = {
    "text_height_ratio": 0.55,
    "center_x_ratio": 0.5,
    "center_y_ratio": 0.5,
    "outline_to_fill_ratio": 0.6,
    "fill_red": 254.0,
    "fill_green": 254.0,
    "fill_blue": 254.0,
    "outline_red": 148.0,
    "outline_green": 4.0,
    "outline_blue": 44.0,
}
TOLERANCES = {
    "text_height_ratio": 0.04,
    "center_x_ratio": 0.04,
    "center_y_ratio": 0.04,
    "outline_to_fill_ratio": 0.15,
    "fill_red": 3.0,
    "fill_green": 3.0,
    "fill_blue": 3.0,
    "outline_red": 8.0,
    "outline_green": 8.0,
    "outline_blue": 8.0,
}


def entry(asset_id: str, metrics: dict) -> dict:
    return {
        "id": asset_id,
        "state": "normal",
        "single_image_qa_status": "pass",
        "semantic_text_status": "confirmed",
        "typography_review_status": "pass",
        "metrics": metrics,
    }


class VerifyLocalizedGroupConsistencyTest(unittest.TestCase):
    def spec(self, entries: list[dict]) -> dict:
        return {
            "group_id": "fixture",
            "family_id": "family",
            "template_id": "template",
            "representative_id": entries[0]["id"],
            "representative_approval": "user_approved",
            "approved_reference_metrics": REFERENCE,
            "tolerances": TOLERANCES,
            "entries": entries,
        }

    def run_spec(self, directory: Path, spec: dict) -> dict:
        path = directory / "spec.json"
        path.write_text(json.dumps(spec), encoding="utf-8")
        return MODULE.validate_group(path, directory / "report.json")

    def test_consistent_group_passes_but_still_requires_contact_sheet(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            metrics = REFERENCE | {"center_x_ratio": 0.52}
            report = self.run_spec(directory, self.spec([entry("a", REFERENCE), entry("b", metrics)]))
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["failure_count"], 0)
            self.assertTrue(report["requires_group_contact_sheet_user_review"])
            self.assertEqual(report["group_contact_sheet_review_status"], "pending")

    def test_deep_purple_outlier_fails_outline_color(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            outlier = REFERENCE | {"outline_red": 95.0, "outline_blue": 90.0}
            report = self.run_spec(directory, self.spec([entry("a", REFERENCE), entry("bad", outlier)]))
            self.assertEqual(report["status"], "fail")
            self.assertEqual(report["failure_count"], 1)
            self.assertEqual(report["entries"][1]["status"], "fail")
            self.assertIn("outline_red", report["failure_reasons"])
            self.assertIn("outline_blue", report["failure_reasons"])

    def test_unapproved_representative_blocks_group_qa(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            spec = self.spec([entry("a", REFERENCE)])
            spec["representative_approval"] = "pending"
            with self.assertRaisesRegex(PermissionError, "not user approved"):
                self.run_spec(directory, spec)

    def test_rejects_missing_representative_and_nonfinite_or_negative_limits(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            spec = self.spec([entry("a", REFERENCE)])
            spec["representative_id"] = "missing"
            with self.assertRaisesRegex(ValueError, "representative_id"):
                self.run_spec(directory, spec)

            spec = self.spec([entry("a", REFERENCE)])
            spec["approved_reference_metrics"] = REFERENCE | {"center_x_ratio": float("inf")}
            with self.assertRaisesRegex(ValueError, "non-finite approved reference"):
                self.run_spec(directory, spec)

            spec = self.spec([entry("a", REFERENCE)])
            spec["tolerances"] = TOLERANCES | {"center_x_ratio": -1.0}
            with self.assertRaisesRegex(ValueError, "finite and non-negative"):
                self.run_spec(directory, spec)

    def test_reference_metrics_must_belong_to_the_named_representative(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            representative = entry("a", REFERENCE | {"center_x_ratio": 0.51})
            with self.assertRaisesRegex(ValueError, "does not match representative"):
                self.run_spec(directory, self.spec([representative]))

    def test_rejects_invalid_metric_on_an_ordinary_member_before_summarizing(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            invalid = entry("bad", REFERENCE | {"center_x_ratio": float("nan")})
            with self.assertRaisesRegex(ValueError, "bad.*non-finite metric"):
                self.run_spec(
                    directory,
                    self.spec([entry("representative", REFERENCE), invalid]),
                )

    def test_refuses_to_overwrite_spec_or_existing_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            spec = self.spec([entry("a", REFERENCE)])
            spec_path = directory / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "aliases an input"):
                MODULE.validate_group(spec_path, spec_path)
            report_path = directory / "report.json"
            report_path.write_text("reviewed", encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "already exists"):
                MODULE.validate_group(spec_path, report_path)
            self.assertEqual(report_path.read_text(encoding="utf-8"), "reviewed")


if __name__ == "__main__":
    unittest.main()
