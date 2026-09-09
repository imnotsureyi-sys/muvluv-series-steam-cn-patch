"""Project a private Photon atlas manifest into a portable, image-free catalog."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re

from PIL import Image
from localization.tools.safe_output import write_new_files

SCHEMA = "photon-static-review-v1"
SHA = re.compile(r"[0-9A-F]{64}")
REF = re.compile(r"(?:pf|pm):rio\d{3}:0x[0-9a-f]+(?::cbg2d/cr6ti)?")


def text(value: object) -> str:
    if not isinstance(value, str) or len(value) > 2000:
        raise ValueError("Invalid review label")
    if re.search(r"(?i)(?:[a-z]:[\\/]|file:|https?://|\\\\)", value):
        raise ValueError("Review labels must not contain filesystem paths or URLs")
    return value


def image_identity(item: dict, assets: dict[str, str]) -> dict:
    digest = item["sha256"].upper()
    size = item["size"]
    if not SHA.fullmatch(digest) or len(size) != 2 or any(type(n) is not int or not 0 < n <= 100000 for n in size):
        raise ValueError("Invalid image identity")
    path = Path(item["path"]).resolve()
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest().upper() != digest:
        raise ValueError("Image hash drift")
    with Image.open(BytesIO(data)) as image:
        image.load()
        if list(image.size) != size:
            raise ValueError("Image dimensions drift")
    assets.setdefault(digest, str(path))
    return dict(sha256=digest, size=size)


def catalog_counts(rows: list[dict]) -> dict:
    return dict(entries=len(rows), pictured=sum(not r["placeholder"] for r in rows),
                status_only=sum(r["placeholder"] for r in rows),
                categories=dict(Counter(r["category"] for r in rows)))


def export(manifest: dict, resource_catalog: dict) -> tuple[dict, dict]:
    categories = [text(c) for c in manifest["categories"]]
    if len(set(categories)) != len(categories):
        raise ValueError("Duplicate categories")
    references = {}
    for asset in resource_catalog["assets"]:
        if asset["id"] in references:
            raise ValueError("Duplicate resource catalog ID")
        references[asset["id"]] = asset["refs"]
    rows, assets, seen = [], {}, set()
    for row in manifest["rows"]:
        gid = row["id"]
        if type(gid) is not int or gid <= 0 or gid in seen:
            raise ValueError("Invalid or duplicate group ID")
        seen.add(gid)
        category = text(row["category"])
        if category not in categories:
            raise ValueError("Unknown category")
        refs = references[gid]
        if not refs or any(not REF.fullmatch(ref) for ref in refs):
            raise ValueError("Invalid resource locator")
        placeholder = row["placeholder"]
        if type(placeholder) is not bool:
            raise ValueError("Invalid placeholder flag")
        shared = row.get("shared_native", False)
        if type(shared) is not bool:
            raise ValueError("Invalid shared_native flag")
        official = {}
        candidate = None
        if not placeholder:
            for language, item in row["official"].items():
                if language not in {"jp", "en", "unknown"}:
                    raise ValueError("Unknown language classification")
                official[language] = image_identity(item, assets)
            if not official:
                raise ValueError("Pictured row has no official reference")
            candidate = image_identity(row["candidate"], assets)
        rows.append(dict(id=gid, refs=refs, category=category,
                         title=text(row["title"]), collection=text(row["collection"]),
                         section=text(row["section"]), status=text(row["status"]),
                         placeholder=placeholder, shared_native=shared,
                         official=official, candidate=candidate))
    result = dict(schema=SCHEMA, categories=categories, rows=rows,
                  counts=catalog_counts(rows),
                  scope="Current reviewed selection; not all extracted assets, not a redistribution authorization, and not a complete in-game acceptance.")
    return result, assets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path, help="Private full-atlas manifest")
    parser.add_argument("--resource-catalog", required=True, type=Path, help="Private catalog with assets[].id/refs")
    parser.add_argument("--output", required=True, type=Path, help="New directory with public catalog and PRIVATE local asset map")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output directory already exists")
    manifest_bytes = args.manifest.read_bytes()
    resources_bytes = args.resource_catalog.read_bytes()
    manifest = json.loads(manifest_bytes)
    resources = json.loads(resources_bytes)
    result, assets = export(manifest, resources)
    result["source_manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest().upper()
    result["source_resource_catalog_sha256"] = hashlib.sha256(resources_bytes).hexdigest().upper()
    encode = lambda obj: (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    write_new_files({args.output / "catalog.json": encode(result),
                     args.output / "PRIVATE-asset-map.json": encode(assets)})
    print(json.dumps(result["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
