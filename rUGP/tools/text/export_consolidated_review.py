"""Publish Chinese audit rows; full official language slots stay private.

This exports review data, not native write contracts or a game patch.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


TITLES = {"pf": "photonflowers", "pm": "photonmelodies"}
FIELDS = (
    "game", "kind", "binding_id", "stable_id", "rio_file", "block_offset",
    "command_offset", "command_order", "native_command_order", "marker_offset",
    "text_offset", "source_kind", "review_scope", "non_layout_characters_equal",
    "decision_reason", "changes", "cn_annotations", "speaker_repair_id",
    "alias_mapping_sha256",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def public_rows(rows: list[dict]) -> list[dict]:
    result, seen = [], set()
    for row in rows:
        identity = row["binding_id"]
        if not isinstance(identity, str) or identity in seen:
            raise ValueError("Missing or duplicate binding identity")
        seen.add(identity)
        if row["game"] not in TITLES or row["kind"] not in {
            "cvm", "cstring", "recovered_message"
        }:
            raise ValueError("Unknown game or row kind")
        if not identity.startswith(row["game"] + ":"):
            raise ValueError("Binding/game mismatch")
        cn = row["cn"]
        if not isinstance(cn, str):
            raise ValueError("Chinese field must be a string")
        if row["kind"] != "cstring" and "\x03" in cn:
            raise ValueError("Body still contains U+0003")
        if any("\u2060" in name for name in re.findall(r"【([^】]*)】", cn)):
            raise ValueError("Speaker name still contains U+2060")
        public = {key: row[key] for key in FIELDS if key in row}
        public["translated_text"] = cn
        public["representation"] = (
            "reviewed_display_not_serialized_field" if row["kind"] == "cstring"
            else "decoded_message_with_actual_controls"
        )
        for language in ("jp", "en"):
            value = row[language]
            if value is not None and not isinstance(value, str):
                raise ValueError("Source slot must be a string or null")
            public[language + "_utf8_sha256"] = (
                digest(value.encode("utf-8")) if value is not None else None
            )
        result.append(public)
    if not result:
        raise ValueError("No review rows")
    return result


def export(source: Path, games_root: Path) -> dict:
    raw = source.read_bytes()
    rows = public_rows([json.loads(line) for line in raw.decode("utf-8").splitlines()])
    products = {}
    for game, title in TITLES.items():
        selected = [r for r in rows if r["game"] == game]
        if not selected:
            continue
        folder = games_root / title / "translations" / "layout-20260906"
        shards = []
        for start in range(0, len(selected), 1000):
            batch = selected[start:start + 1000]
            name = f"rows-{start + 1:05d}-{start + len(batch):05d}.json"
            data = ("[\n" + ",\n".join(json.dumps(r, ensure_ascii=False) for r in batch)
                    + "\n]\n").encode("utf-8")
            products[folder / name] = data
            shards.append({"file": name, "rows": len(batch), "sha256": digest(data)})
        manifest = {
            "schema": "photon-consolidated-chinese-review/v1",
            "status": "draft_audit_snapshot_not_native_write_contract",
            "game": game,
            "source_private_jsonl_sha256": digest(raw),
            "source_hash_encoding": "Exact parsed JP/EN slot encoded as UTF-8, actual control characters; no normalization. Null means no English slot.",
            "official_source_text_included": False,
            "identity_policy": "binding_id is unique; stable_id is a historical alias and may repeat",
            "counts": dict(Counter(r["kind"] for r in selected)),
            "rows": len(selected),
            "shards": shards,
        }
        products[folder / "manifest.json"] = (
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
    # Refuse overwriting different existing work, before writing any file.
    for path, data in products.items():
        if path.exists() and path.read_bytes() != data:
            raise ValueError(f"Existing snapshot differs: {path.name}")
    for path, data in products.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(data)
    return {game: sum(r["game"] == game for r in rows) for game in TITLES}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Private full-three-language.jsonl")
    parser.add_argument("--games-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.source, args.games_root)))


if __name__ == "__main__":
    main()
