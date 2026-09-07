"""Read the chapter CSV editing surface without losing sealed native metadata.

This is review data, not a native-field writer or a player patch. JP/EN full
slots remain private. The committed layout snapshot is the migration baseline.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import unicodedata


COLUMNS = ("binding_id", "kind", "translated_text", "cn_annotations",
           "review_scope", "jp_utf8_sha256", "en_utf8_sha256")
TOKEN = re.compile(r"<([0-9A-F]{2,6})>")


def visible(text: str) -> str:
    """Escape literal '<' too, so a literal '<0A>' cannot become a newline."""
    return "".join(f"<{ord(c):02X}>" if c == "<" or
                   unicodedata.category(c) in {"Cc", "Cf"} else c for c in text)


def decoded(text: str) -> str:
    value = TOKEN.sub(lambda m: chr(int(m[1], 16)), text)
    if visible(value) != text:
        raise ValueError("Noncanonical control escape; use uppercase <0A>, <01>, <2060>")
    return value


def cells(row: dict) -> list[str]:
    return [row["binding_id"], row["kind"], visible(row["translated_text"]),
            json.dumps(row.get("cn_annotations", []), ensure_ascii=False),
            row.get("review_scope", ""), row["jp_utf8_sha256"] or "",
            row["en_utf8_sha256"] or ""]


def snapshot(folder: Path) -> list[dict]:
    source = folder.parent / "text-data" / "layout-baseline"
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    result = []
    for shard in manifest["shards"]:
        data = (source / shard["file"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != shard["sha256"]:
            raise ValueError("Sealed snapshot hash changed")
        rows = json.loads(data)
        if len(rows) != shard["rows"]:
            raise ValueError("Snapshot shard row count changed")
        result.extend(rows)
    if len(result) != manifest["rows"]:
        raise ValueError("Snapshot row count changed")
    return result


def read_chapters(folder: Path, *, unchanged: bool = False,
                  overrides: dict[str, bytes] | None = None) -> list[dict]:
    """Overlay editable text/annotations on exact original binding metadata."""
    originals = snapshot(folder)
    by_id = {r["binding_id"]: r for r in originals}
    if len(by_id) != len(originals):
        raise ValueError("Duplicate snapshot identity")
    manifest = json.loads((folder / "chapters.json").read_text(encoding="utf-8"))
    if manifest["schema"] != "photon-chapter-review/v1":
        raise ValueError("Unsupported chapter schema")
    seen, result, listed = set(), {}, set()
    assignments = {}
    for entry in manifest["files"]:
        relative = Path(entry["file"])
        if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".csv":
            raise ValueError("Unsafe chapter path")
        if relative.as_posix() in listed:
            raise ValueError("Duplicate chapter file")
        listed.add(relative.as_posix())
        for scene in entry["scenes"]:
            key = (scene["rio_file"], scene["block_offset"])
            if key in assignments:
                raise ValueError("Duplicate scene assignment")
            assignments[key] = entry["file"]
    # Exact inventory: chapter files are top-level CSVs other than the legacy
    # runtime table, plus the explicitly named long-story directory.
    actual = {p.relative_to(folder).as_posix() for p in folder.glob("*.csv")
              if p.name != "zh-Hans.csv"}
    actual.update(p.relative_to(folder).as_posix()
                  for p in (folder / "时空的欠片").glob("*.csv"))
    if actual != listed:
        raise ValueError("Missing or unlisted chapter CSV")
    for entry in manifest["files"]:
        count = 0
        data = (overrides[entry["file"]] if overrides is not None
                else (folder / entry["file"]).read_bytes())
        with io.StringIO(data.decode("utf-8-sig"), newline="") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != COLUMNS:
                raise ValueError("Unexpected chapter CSV columns")
            for item in reader:
                identity = item["binding_id"]
                if None in item or any(v is None for v in item.values()):
                    raise ValueError("Malformed CSV row")
                if identity in seen or identity not in by_id:
                    raise ValueError("Duplicate or unknown binding")
                seen.add(identity)
                original = by_id[identity]
                scene = (original["rio_file"], original["block_offset"])
                if assignments.get(scene) != entry["file"]:
                    raise ValueError("Binding is in the wrong chapter")
                expected = dict(zip(COLUMNS, cells(original)))
                for key in ("kind", "review_scope", "jp_utf8_sha256", "en_utf8_sha256"):
                    if item[key] != expected[key]:
                        raise ValueError("Read-only binding/source metadata changed")
                updated = dict(original)
                updated["translated_text"] = decoded(item["translated_text"])
                annotations = json.loads(item["cn_annotations"])
                if not isinstance(annotations, list) or not all(isinstance(a, str) for a in annotations):
                    raise ValueError("Annotations must be a JSON string list")
                if "cn_annotations" in original or annotations:
                    updated["cn_annotations"] = annotations
                if original["kind"] != "cstring" and "\x03" in updated["translated_text"]:
                    raise ValueError("Body contains U+0003")
                if any("\u2060" in n for n in re.findall(r"【([^】]*)】", updated["translated_text"])):
                    raise ValueError("Speaker contains U+2060")
                if unchanged and updated != original:
                    raise ValueError(f"Migration changed content: {identity}")
                result[identity] = updated
                count += 1
        if count != entry["rows"]:
            raise ValueError("Chapter row count changed")
    if seen != set(by_id) or len(seen) != manifest["rows"]:
        raise ValueError("Missing bindings")
    return [result[r["binding_id"]] for r in originals]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Game translations directory")
    parser.add_argument("--unchanged", action="store_true", help="Prove lossless migration against the sealed snapshot")
    args = parser.parse_args()
    rows = read_chapters(args.folder, unchanged=args.unchanged)
    print(json.dumps({"rows": len(rows), "all_bindings_present": True,
                      "unchanged_from_snapshot": args.unchanged}))


if __name__ == "__main__":
    main()
