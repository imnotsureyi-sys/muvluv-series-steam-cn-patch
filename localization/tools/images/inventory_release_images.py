"""Build a deterministic image inventory from a historical patch ZIP.

The tool never extracts files.  It reads image members in memory, validates
their decodability with Pillow, and records stable metadata that can be kept in
Git while the binary release payload remains attached to GitHub Releases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from collections import Counter
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from PIL import Image

from localization.tools.safe_output import write_new_files


IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".webp"}
LOCALE_SUFFIX_RE = re.compile(r"_(ja|zh|en)(?=\.[^.]+$)", re.IGNORECASE)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def normalize_archive_path(name: str) -> tuple[str, str]:
    """Return slash-normalized archive path and path relative to payload/."""

    archive_path = name.replace("\\", "/")
    if (
        not archive_path
        or archive_path.startswith("/")
        or re.match(r"^[A-Za-z]:/", archive_path)
        or "\x00" in archive_path
    ):
        raise ValueError(f"unsafe archive member: {name!r}")

    parts = archive_path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError(f"unsafe archive member: {name!r}")

    lowered = [part.lower() for part in parts]
    if "payload" in lowered:
        payload_index = lowered.index("payload")
        relative_parts = parts[payload_index + 1 :]
    else:
        relative_parts = parts

    if not relative_parts:
        raise ValueError(f"archive member has no payload-relative path: {name!r}")
    return "/".join(parts), "/".join(relative_parts)


def locale_hint(path: str) -> str | None:
    match = LOCALE_SUFFIX_RE.search(PurePosixPath(path).name)
    return match.group(1).lower() if match else None


def build_inventory(
    zip_path: Path,
    *,
    game_id: str,
    engine: str,
    release_tag: str,
    source_url: str,
    expected_zip_sha256: str | None = None,
) -> dict[str, Any]:
    zip_sha256 = sha256_file(zip_path)
    if expected_zip_sha256 and zip_sha256 != expected_zip_sha256.upper():
        raise ValueError(
            f"ZIP SHA-256 mismatch: expected {expected_zip_sha256.upper()}, got {zip_sha256}"
        )

    entries: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    with zipfile.ZipFile(zip_path, "r") as archive:
        members: list[tuple[str, str, str, zipfile.ZipInfo]] = []
        for info in archive.infolist():
            if info.is_dir():
                continue
            archive_path, payload_path = normalize_archive_path(info.filename)
            if PurePosixPath(payload_path).suffix.lower() not in IMAGE_SUFFIXES:
                continue
            members.append(
                (payload_path.casefold(), payload_path, archive_path, info)
            )

        for path_key, payload_path, archive_path, info in sorted(
            members, key=lambda member: member[:3]
        ):
            if path_key in seen_paths:
                raise ValueError(
                    "duplicate case-insensitive normalized image path: "
                    f"{payload_path}"
                )
            seen_paths.add(path_key)

            data = archive.read(info)
            with Image.open(BytesIO(data)) as image:
                image.load()
                image_format = image.format or PurePosixPath(payload_path).suffix[1:]
                width, height = image.size
                mode = image.mode

            entries.append(
                {
                    "path": payload_path,
                    "archive_path": archive_path,
                    "format": image_format.upper(),
                    "width": width,
                    "height": height,
                    "mode": mode,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest().upper(),
                    "filename_locale_hint": locale_hint(payload_path),
                }
            )

    format_counts = Counter(entry["format"] for entry in entries)
    locale_counts = Counter(entry["filename_locale_hint"] or "none" for entry in entries)
    unique_content_count = len({entry["sha256"] for entry in entries})

    return {
        "schema": "muvluv-release-image-inventory/v1",
        "game_id": game_id,
        "engine": engine,
        "release_tag": release_tag,
        "release_asset": zip_path.name,
        "release_asset_url": source_url,
        "release_asset_sha256": zip_sha256,
        "image_count": len(entries),
        "unique_content_count": unique_content_count,
        "duplicate_content_reference_count": len(entries) - unique_content_count,
        "format_counts": dict(sorted(format_counts.items())),
        "filename_locale_hint_counts": dict(sorted(locale_counts.items())),
        "scope_note": (
            "Inventory of image members present in the historical patch release. "
            "Presence does not prove that every member was newly translated or is "
            "independently redistributable outside that release."
        ),
        "entries": entries,
    }


def write_inventory(
    path: Path, inventory: dict[str, Any], *, inputs: Iterable[Path] = ()
) -> None:
    payload = (json.dumps(inventory, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )
    write_new_files({path: payload}, inputs=inputs)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inventory image members in a historical patch ZIP without extracting them."
    )
    parser.add_argument("zip", type=Path, help="Historical patch ZIP")
    parser.add_argument("output", type=Path, help="Output JSON manifest")
    parser.add_argument("--game-id", required=True)
    parser.add_argument("--engine", required=True)
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--expect-zip-sha256")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    inventory = build_inventory(
        args.zip,
        game_id=args.game_id,
        engine=args.engine,
        release_tag=args.release_tag,
        source_url=args.source_url,
        expected_zip_sha256=args.expect_zip_sha256,
    )
    write_inventory(args.output, inventory, inputs=[args.zip])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
