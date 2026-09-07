"""Generate private JP/EN/CN chapter views; import only validated Chinese edits.

Source: existing private consolidated JSONL extracted from the owner's game.
No source text is downloaded. This is not a native game-field writer.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

from .chapter_review import COLUMNS, decoded, read_chapters, visible

LOCAL_COLUMNS = ("binding_id", "jp_text", "en_text", "translated_text",
                 "cn_annotations", "kind", "review_scope", "jp_utf8_sha256",
                 "en_utf8_sha256", "base_edit_sha256")


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def edit_hash(row: dict) -> str:
    return sha(json.dumps([row["translated_text"], row["cn_annotations"]],
                          ensure_ascii=False, separators=(",", ":")))


def csv_bytes(columns, rows) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def read_csv(path: Path, columns) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != columns:
            raise ValueError("Unexpected CSV columns")
        rows = list(reader)
    if any(None in r or any(v is None for v in r.values()) for r in rows):
        raise ValueError("Malformed CSV row")
    return rows


def private_folder(folder: Path, local: Path) -> Path:
    # Only the ignored local-internal tree of this checkout may contain outputs.
    root = folder.resolve().parents[3]
    private = root / "local-internal"
    target = local.resolve()
    if target == private or not target.is_relative_to(private):
        raise ValueError("Local review must be below checkout/local-internal")
    return target


def export_plan(folder: Path, source: Path) -> dict[str, list[dict]]:
    originals = read_chapters(folder)
    wanted = {r["binding_id"]: r for r in originals}
    sources = {}
    with source.open(encoding="utf-8-sig") as stream:
        for line in stream:
            record = json.loads(line)
            identity = record["binding_id"]
            if identity not in wanted:
                continue
            if identity in sources:
                raise ValueError("Duplicate source binding")
            expected = wanted[identity]
            if record["game"] != expected["game"] or record["kind"] != expected["kind"]:
                raise ValueError("Source game/kind mismatch")
            for language in ("jp", "en"):
                value = record[language]
                if value is not None and not isinstance(value, str):
                    raise ValueError("Invalid source slot")
                if (None if value is None else sha(value)) != expected[language + "_utf8_sha256"]:
                    raise ValueError("Source text/control hash mismatch")
            sources[identity] = record
    if sources.keys() != wanted.keys():
        raise ValueError("Missing source bindings")
    manifest = json.loads((folder / "chapters.json").read_text(encoding="utf-8"))
    result = {}
    for entry in manifest["files"]:
        rows = read_csv(folder / entry["file"], COLUMNS)
        for row in rows:
            src = sources[row["binding_id"]]
            row["base_edit_sha256"] = edit_hash(row)
            row["jp_text"] = visible(src["jp"] or "")
            row["en_text"] = visible(src["en"] or "")
        result[entry["file"]] = rows
    return result


def export(folder: Path, source: Path, local: Path) -> dict:
    local = private_folder(folder, local)
    plan = export_plan(folder, source)
    products = {local / name: csv_bytes(LOCAL_COLUMNS, rows) for name, rows in plan.items()}
    if any(not path.resolve().is_relative_to(local) for path in products):
        raise ValueError("Review output escapes private session through a link")
    # Never overwrite a review session or its unimported edits.
    if any(path.exists() for path in products):
        raise ValueError("Review already exists; choose a new session directory")
    for path, data in products.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return {"files": len(plan), "rows": sum(map(len, plan.values()))}


def import_edits(folder: Path, local: Path, *, apply: bool = False) -> dict:
    local = private_folder(folder, local)
    read_chapters(folder)
    manifest = json.loads((folder / "chapters.json").read_text(encoding="utf-8"))
    listed = {e["file"] for e in manifest["files"]}
    if {p.relative_to(local).as_posix() for p in local.rglob("*.csv")} != listed:
        raise ValueError("Missing or unlisted local chapter")
    products, before, changed = {}, {}, 0
    for entry in manifest["files"]:
        name = entry["file"]
        before[name] = (folder / name).read_bytes()
        public = read_csv(folder / name, COLUMNS)
        rows = read_csv(local / name, LOCAL_COLUMNS)
        by_id = {r["binding_id"]: r for r in rows}
        if len(by_id) != len(rows) or by_id.keys() != {r["binding_id"] for r in public}:
            raise ValueError("Missing, duplicate, unknown or wrong-chapter binding")
        merged = []
        for current in public:
            incoming = by_id[current["binding_id"]]
            for key in COLUMNS:
                if key not in {"translated_text", "cn_annotations"} and incoming[key] != current[key]:
                    raise ValueError("Read-only metadata changed")
            for lang in ("jp", "en"):
                value = decoded(incoming[lang + "_text"])
                expected = current[lang + "_utf8_sha256"]
                if (sha(value) != expected if expected else value != ""):
                    raise ValueError("Read-only source text/control changed")
            updated = {key: incoming[key] for key in COLUMNS}
            if updated != current:
                if incoming["base_edit_sha256"] != edit_hash(current):
                    raise ValueError("Stale review conflicts with newer public Chinese; re-export")
                changed += 1
            merged.append(updated)
        products[name] = (csv_bytes(COLUMNS, merged) if merged != public else before[name])
    # Validate ALL chapters before writing ANY chapter. Preserve opaque metadata.
    read_chapters(folder, overrides=products)
    if apply:
        if any((folder / name).read_bytes() != data for name, data in before.items()):
            raise ValueError("Public files changed during validation")
        for name, data in products.items():
            if data != before[name]:
                (folder / name).write_bytes(data)
    return {"rows": manifest["rows"], "changed_rows": changed, "applied": apply}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("export", "import"))
    parser.add_argument("folder", type=Path, help="Public game translations directory")
    parser.add_argument("local", type=Path, help="Session below checkout/local-internal")
    parser.add_argument("--source", type=Path, help="Private full-three-language.jsonl for export")
    parser.add_argument("--apply", action="store_true", help="Import only: write Chinese changes after validation")
    args = parser.parse_args()
    if args.operation == "export":
        if args.source is None or args.apply:
            parser.error("export requires --source and does not accept --apply")
        result = export(args.folder, args.source, args.local)
    else:
        if args.source is not None:
            parser.error("import does not accept --source")
        result = import_edits(args.folder, args.local, apply=args.apply)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
