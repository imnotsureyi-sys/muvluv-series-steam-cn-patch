#!/usr/bin/env python3
"""Read back and independently verify the published V6 image bundle."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import zipfile
from collections import Counter
from pathlib import Path
import tempfile

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
PUBLIC_MANIFEST = ROOT / "rugp/evidence/photon-images-v6/manifest.json"
EXPECTED_ZIP_SHA256 = "B11D0D322CF3081D0788BA60BB3D94C2014BD57B32852DC053B0D158128E97D8"
EXPECTED_AUTHORITY_SHA256 = "19009AFB9C38822FB9057D8FAEEF2C9370CED2EFA1E090199A081682EF89447D"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def write_new_report(
    output: Path, report: dict[str, object], *, inputs: tuple[Path, ...]
) -> None:
    identity = output.resolve(strict=False)
    if identity in {path.resolve(strict=False) for path in inputs}:
        raise FileExistsError("verification report must not alias an input")
    payload = (
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, output)
        except FileExistsError as exc:
            raise FileExistsError(
                f"refusing to overwrite existing verification report: {output}"
            ) from exc
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def verify(
    archive_path: Path,
    public_manifest: Path,
    expected_zip_sha256: str = EXPECTED_ZIP_SHA256,
    expected_authority_sha256: str = EXPECTED_AUTHORITY_SHA256,
) -> dict[str, object]:
    require(
        archive_path.is_file() and sha256(archive_path) == expected_zip_sha256,
        "ZIP SHA drift",
    )
    require(public_manifest.is_file(), f"public manifest is missing: {public_manifest}")
    with zipfile.ZipFile(archive_path, "r") as archive:
        require(archive.testzip() is None, "ZIP CRC failure")
        names = archive.namelist()
        require(len(names) == len(set(names)), "duplicate ZIP member")
        manifest_candidates = [name for name in names if name.count("/") == 1 and name.endswith("/manifest.json")]
        require(len(manifest_candidates) == 1, "ZIP must contain one top-level manifest.json")
        manifest_name = manifest_candidates[0]
        prefix = manifest_name[: -len("manifest.json")]
        manifest = json.loads(archive.read(manifest_name).decode("utf-8"))
        require(manifest["asset_count"] == manifest["unique_asset_count"] == 1490, "manifest count drift")
        require(manifest["formal_authority_sha256"] == expected_authority_sha256, "authority binding drift")
        require(len(manifest["entries"]) == len({entry["asset_id"] for entry in manifest["entries"]}) == 1490, "manifest IDs are not unique")
        png_count = sum(name.startswith(prefix + "localized-png/") and name.endswith(".png") for name in names)
        record_count = sum(name.startswith(prefix + "native-records/") and name.endswith(".record") for name in names)
        require(png_count == 1490 and record_count == 243, "ZIP payload count drift")
        counts = Counter()
        exact_authority_sha_matches = 0
        for entry in manifest["entries"]:
            png_name = prefix + entry["backup_png"]
            payload = archive.read(png_name)
            require(sha256_bytes(payload) == entry["backup_png_sha256"], f"PNG SHA mismatch: {entry['asset_id']}")
            with Image.open(io.BytesIO(payload)) as image:
                rgba = image.convert("RGBA")
                require(list(rgba.size) == entry["size"] and rgba.mode == "RGBA", f"PNG geometry mismatch: {entry['asset_id']}")
                require(sha256_bytes(rgba.tobytes()) == entry["backup_decoded_rgba_sha256"], f"RGBA SHA mismatch: {entry['asset_id']}")
            counts[entry["materialization"]] += 1
            if entry["materialization"] == "exact_formal_png":
                require(entry["backup_png_sha256"] == entry["authority_candidate_png_sha256"], f"exact authority PNG mismatch: {entry['asset_id']}")
                require(entry["native_record"] is None, f"unexpected record on exact PNG: {entry['asset_id']}")
                exact_authority_sha_matches += 1
            else:
                record = entry["native_record"]
                require(record and record["packaging_authority"] and record["do_not_reencode_from_preview_png"], f"record policy missing: {entry['asset_id']}")
                record_payload = archive.read(prefix + record["path"])
                require(sha256_bytes(record_payload) == record["sha256"], f"record SHA mismatch: {entry['asset_id']}")
                require(entry["backup_decoded_rgba_sha256"] == record["runtime_decoded_rgba_sha256"], f"record RGBA binding mismatch: {entry['asset_id']}")
        require(counts == Counter({"exact_formal_png": 1247, "sealed_native_record_runtime_decode": 243}), f"materialization count drift: {counts}")
        sums = archive.read(prefix + "SHA256SUMS.txt").decode("utf-8").splitlines()
        require(len(sums) == 1490 + 243 + 2, "SHA256SUMS line count drift")
        require(
            sha256(public_manifest) == sha256_bytes(archive.read(manifest_name)),
            "public manifest differs from ZIP",
        )
    return {
        "schema": "muvluv-photon-image-github-backup-independent-verification/v1",
        "status": "PASS",
        "zip_sha256": sha256(archive_path),
        "zip_bytes": archive_path.stat().st_size,
        "zip_member_count": len(names),
        "localized_png_count": 1490,
        "native_record_count": 243,
        "exact_formal_png_sha_matches": exact_authority_sha_matches,
        "runtime_decoded_rgba_matches": 243,
        "formal_authority_sha256": expected_authority_sha256,
        "review_jpeg_used_as_source": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="downloaded V6 ZIP")
    parser.add_argument("--manifest", type=Path, default=PUBLIC_MANIFEST)
    parser.add_argument("--expected-zip-sha256", default=EXPECTED_ZIP_SHA256)
    parser.add_argument("--expected-authority-sha256", default=EXPECTED_AUTHORITY_SHA256)
    parser.add_argument("--output", type=Path, help="optional JSON verification report")
    args = parser.parse_args()
    report = verify(
        args.archive,
        args.manifest,
        args.expected_zip_sha256.upper(),
        args.expected_authority_sha256.upper(),
    )
    if args.output:
        write_new_report(
            args.output,
            report,
            inputs=(args.archive, args.manifest),
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
