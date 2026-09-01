#!/usr/bin/env python3
"""Verify the 1,490-image Photon locale-route closure without game assets."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


SCHEMA = "photon-image-routes-1490/v1"
TRANSLATION = "translation_peer_native_range"
SHARED = "proven_shared_native_range"
SHA256_RE = re.compile(r"[0-9A-Fa-f]{64}\Z")


class RouteError(RuntimeError):
    """Route authority is incomplete, inconsistent or unauthenticated."""


def _sha(value: object) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def _asset_id(value: object) -> str:
    if not isinstance(value, str):
        raise RouteError(f"invalid asset identity: {value!r}")
    parts = value.split(":")
    if len(parts) < 3 or not all(parts[:3]):
        raise RouteError(f"invalid asset identity: {value!r}")
    return ":".join(parts[:3])


def _translation_proven(authority: Mapping[str, Any]) -> bool:
    # evidence_count is the number of authenticated structural observations,
    # not the number of unique external evidence files.  slot_map_sha256 binds
    # the observation set; evidence_sha256 is an optional de-duplicated list of
    # additional artifact hashes and may therefore be empty.
    evidence_count = authority.get("evidence_count")
    evidence_hashes = authority.get("evidence_sha256")
    slot_map = (
        _sha(authority.get("slot_map_sha256"))
        and isinstance(evidence_count, int)
        and not isinstance(evidence_count, bool)
        and evidence_count > 0
        and isinstance(evidence_hashes, list)
        and all(_sha(value) for value in evidence_hashes)
        and bool(authority.get("confidence"))
        and bool(authority.get("slot_form"))
    )
    handoff = (
        authority.get("semantic_peer_proven") is True
        and _sha(authority.get("route_handoff_v2_sha256"))
    )
    return bool(authority.get("authority")) and bool(slot_map or handoff)


def _shared_proven(authority: Mapping[str, Any]) -> bool:
    evidence = authority.get("evidence")
    return bool(
        authority.get("authority")
        and authority.get("shared_across_locales_proven") is True
        and _sha(authority.get("remaining42_manifest_sha256"))
        and _sha(authority.get("remaining42_parent_sha256"))
        and _sha(authority.get("family_shared_proof_sha256"))
        and _sha(authority.get("family_transports_sha256"))
        and isinstance(evidence, Mapping)
        and evidence.get("parent_evidence_id")
        and evidence.get("interpretation")
    )


def verify(
    routes: Mapping[str, Any],
    image_manifest: Mapping[str, Any],
    *,
    expected_total: int = 1490,
    expected_translation: int = 1448,
    expected_shared: int = 42,
) -> dict[str, object]:
    rows = routes.get("rows")
    if routes.get("schema") != SCHEMA or not isinstance(rows, list):
        raise RouteError("route closure schema/rows mismatch")
    if routes.get("count") != len(rows) or len(rows) != expected_total:
        raise RouteError("route closure count mismatch")
    entries = image_manifest.get("entries")
    if not isinstance(entries, list) or image_manifest.get("asset_count") != len(entries):
        raise RouteError("image authority count mismatch")

    seen: set[str] = set()
    targets: set[str] = set()
    ordinals: set[int] = set()
    counts: Counter[str] = Counter()
    for row in rows:
        if not isinstance(row, Mapping):
            raise RouteError("route closure contains a non-object row")
        source = _asset_id(row.get("source_asset_id"))
        target = _asset_id(row.get("target_asset_id"))
        if source in seen:
            raise RouteError(f"duplicate route source: {source}")
        seen.add(source)
        targets.add(target)
        ordinal = row.get("ordinal")
        if not isinstance(ordinal, int) or ordinal < 1 or ordinal in ordinals:
            raise RouteError(f"invalid route ordinal: {ordinal!r}")
        ordinals.add(ordinal)
        kind = row.get("route_kind")
        authority = row.get("route_authority")
        if not isinstance(authority, Mapping):
            raise RouteError(f"missing route authority: {source}")
        if kind == TRANSLATION:
            if source == target or not _translation_proven(authority):
                raise RouteError(f"unproven translation peer: {source}")
            counts[TRANSLATION] += 1
        elif kind == SHARED:
            if source != target or not _shared_proven(authority):
                raise RouteError(f"unproven shared endpoint: {source}")
            counts[SHARED] += 1
        else:
            raise RouteError(f"unsupported route kind: {kind!r}")
        if not row.get("source_codec") or not row.get("target_codec"):
            raise RouteError(f"missing codec identity: {source}")
        size = row.get("target_size")
        if not (
            isinstance(size, list)
            and len(size) == 2
            and all(isinstance(value, int) and value > 0 for value in size)
        ):
            raise RouteError(f"invalid target geometry: {source}")
        if not isinstance(row.get("target_kind"), int):
            raise RouteError(f"invalid target kind: {source}")
        if not _sha(row.get("encoder_record_sha256")):
            raise RouteError(f"invalid encoder record hash: {source}")

    if ordinals != set(range(1, expected_total + 1)):
        raise RouteError("route ordinals are not contiguous")
    if counts[TRANSLATION] != expected_translation or counts[SHARED] != expected_shared:
        raise RouteError(f"route kind census mismatch: {dict(counts)}")
    image_ids = {_asset_id(entry.get("asset_id")) for entry in entries if isinstance(entry, Mapping)}
    if image_ids != seen:
        raise RouteError(
            f"route/image source set mismatch: missing={len(image_ids-seen)} extra={len(seen-image_ids)}"
        )
    games = Counter(value.split(":", 1)[0].upper() for value in seen)
    return {
        "schema": "muvluv-photon-route-verification/v1",
        "status": "PASS",
        "routes": len(seen),
        "translation_peer_routes": counts[TRANSLATION],
        "proven_shared_routes": counts[SHARED],
        "games": dict(sorted(games.items())),
        "unique_targets": len(targets),
        "claim_boundary": (
            "semantic locale endpoint closure only; transport fit, runtime timing, "
            "visual output and release authorization are separate gates"
        ),
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("routes", type=Path)
    parser.add_argument("image_manifest", type=Path)
    parser.add_argument("--expect-routes-sha256")
    parser.add_argument("--expect-images-sha256")
    args = parser.parse_args(argv)
    try:
        for path, expected in (
            (args.routes, args.expect_routes_sha256),
            (args.image_manifest, args.expect_images_sha256),
        ):
            if expected and sha256_file(path) != expected.upper():
                raise RouteError(f"input SHA-256 mismatch: {path}")
        result = verify(
            json.loads(args.routes.read_text(encoding="utf-8-sig")),
            json.loads(args.image_manifest.read_text(encoding="utf-8-sig")),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
