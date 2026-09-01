from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from localization.tools.safe_output import write_new_files


METRIC_KEYS = (
    "text_height_ratio",
    "center_x_ratio",
    "center_y_ratio",
    "outline_to_fill_ratio",
    "fill_red",
    "fill_green",
    "fill_blue",
    "outline_red",
    "outline_green",
    "outline_blue",
)


def robust_center(values: list[float]) -> float:
    return float(statistics.median(values))


def deviation(value: float, center: float) -> float:
    return abs(value - center)


def validate_group(spec_path: Path, output_path: Path) -> dict:
    spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
    entries = spec.get("entries", [])
    if not isinstance(entries, list) or not entries:
        raise ValueError("group specification contains no entries")
    if any(not isinstance(entry, dict) for entry in entries):
        raise ValueError("group entries must be objects")
    ids = [entry.get("id") for entry in entries]
    if any(not isinstance(asset_id, str) or not asset_id for asset_id in ids):
        raise ValueError("every group entry needs a non-empty string ID")
    if len(ids) != len(set(ids)):
        raise ValueError("group specification contains duplicate IDs")
    if spec.get("representative_approval") != "user_approved":
        raise PermissionError("representative is not user approved")
    representative_id = spec.get("representative_id")
    if representative_id not in ids:
        raise ValueError("representative_id does not name a group entry")

    reference = spec.get("approved_reference_metrics")
    if not isinstance(reference, dict):
        raise ValueError("approved_reference_metrics is required")
    tolerances = spec.get("tolerances", {})
    if not isinstance(tolerances, dict):
        raise ValueError("tolerances must be an object")
    missing_reference = [key for key in METRIC_KEYS if key not in reference]
    missing_tolerances = [key for key in METRIC_KEYS if key not in tolerances]
    if missing_reference or missing_tolerances:
        raise ValueError(
            f"missing metrics: reference={missing_reference}, tolerance={missing_tolerances}"
        )
    normalized_reference: dict[str, float] = {}
    normalized_tolerances: dict[str, float] = {}
    for key in METRIC_KEYS:
        try:
            expected = float(reference[key])
            tolerance = float(tolerances[key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"non-numeric reference/tolerance for {key}") from exc
        if not math.isfinite(expected):
            raise ValueError(f"non-finite approved reference metric: {key}")
        if not math.isfinite(tolerance) or tolerance < 0:
            raise ValueError(f"tolerance must be finite and non-negative: {key}")
        normalized_reference[key] = expected
        normalized_tolerances[key] = tolerance
    reference = normalized_reference
    tolerances = normalized_tolerances

    representative = next(entry for entry in entries if entry["id"] == representative_id)
    representative_metrics = representative.get("metrics")
    if not isinstance(representative_metrics, dict):
        raise ValueError("representative entry has no metrics object")
    for key in METRIC_KEYS:
        try:
            measured = float(representative_metrics[key])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"representative entry has invalid metric: {key}") from exc
        if not math.isfinite(measured) or measured != reference[key]:
            raise ValueError(
                f"approved reference metric does not match representative {representative_id}: {key}"
            )

    state_groups: dict[str, list[dict]] = {}
    for entry in entries:
        if entry.get("single_image_qa_status") != "pass":
            raise AssertionError(f"single-image QA is not pass for {entry['id']}")
        if entry.get("semantic_text_status") != "confirmed":
            raise AssertionError(f"target-language text is not confirmed for {entry['id']}")
        if entry.get("typography_review_status") != "pass":
            raise AssertionError(f"typography review is not pass for {entry['id']}")
        if not isinstance(entry.get("metrics"), dict):
            raise ValueError(f"metrics are not an object for {entry['id']}")
        normalized_metrics: dict[str, float] = {}
        for key in METRIC_KEYS:
            try:
                value = float(entry["metrics"][key])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"entry {entry['id']} has an invalid metric: {key}"
                ) from exc
            if not math.isfinite(value):
                raise ValueError(
                    f"entry {entry['id']} has a non-finite metric: {key}"
                )
            normalized_metrics[key] = value
        entry["metrics"] = normalized_metrics
        state_groups.setdefault(entry.get("state", "default"), []).append(entry)

    failures: list[dict] = []
    entry_reports: list[dict] = []
    for entry in entries:
        metrics = entry.get("metrics", {})
        metric_failures = []
        for key in METRIC_KEYS:
            value = float(metrics[key])
            expected = reference[key]
            tolerance = tolerances[key]
            observed_deviation = deviation(value, expected)
            if observed_deviation > tolerance:
                metric_failures.append(
                    {
                        "metric": key,
                        "value": value,
                        "expected": expected,
                        "tolerance": tolerance,
                        "deviation": observed_deviation,
                    }
                )
        if metric_failures:
            failures.append({"id": entry["id"], "failures": metric_failures})
        entry_reports.append(
            {
                "id": entry["id"],
                "state": entry.get("state", "default"),
                "status": "fail" if metric_failures else "pass",
                "metric_failures": metric_failures,
            }
        )

    state_summaries = []
    for state, members in sorted(state_groups.items()):
        state_summaries.append(
            {
                "state": state,
                "member_count": len(members),
                "metric_medians": {
                    key: robust_center([float(member["metrics"][key]) for member in members])
                    for key in METRIC_KEYS
                },
                "fill_rgb_variants": len(
                    {
                        tuple(round(float(member["metrics"][key]), 3) for key in METRIC_KEYS[4:7])
                        for member in members
                    }
                ),
                "outline_rgb_variants": len(
                    {
                        tuple(round(float(member["metrics"][key]), 3) for key in METRIC_KEYS[7:10])
                        for member in members
                    }
                ),
            }
        )

    report = {
        "schema": "photon-localized-group-consistency/v1",
        "group_id": spec.get("group_id"),
        "family_id": spec.get("family_id"),
        "template_id": spec.get("template_id"),
        "representative_id": spec.get("representative_id"),
        "representative_approval": spec.get("representative_approval"),
        "member_count": len(entries),
        "status": "fail" if failures else "pass",
        "failure_count": len(failures),
        "failure_reasons": Counter(
            failure["metric"]
            for entry_failure in failures
            for failure in entry_failure["failures"]
        ),
        "approved_reference_metrics": reference,
        "tolerances": tolerances,
        "state_summaries": state_summaries,
        "entries": entry_reports,
        "failures": failures,
        "requires_group_contact_sheet_user_review": True,
        "group_contact_sheet_review_status": "pending",
    }
    report["failure_reasons"] = dict(sorted(report["failure_reasons"].items()))
    write_new_files(
        {
            output_path: (
                json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8")
        },
        inputs=(spec_path,),
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = validate_group(args.spec, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
