"""Write a tiny, entirely synthetic 113/114-shaped exporter fixture to a new directory."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from PIL import Image

from rUGP.formats.images.crmti_decode import CRMT_CHILD_WRAPPER, decode_crmt
from rUGP.formats.images.crmti_encode import encode_crmt


def digest(data):
    return hashlib.sha256(data).hexdigest().upper()


def synthetic_record(sizes, color):
    parent = bytearray(0x41)
    parent[:4] = bytes.fromhex("80 04 02 05")
    parent[0x40] = len(sizes)
    children = bytearray()
    for width, height in sizes:
        header = (width.to_bytes(2, "little") + height.to_bytes(2, "little")
                  + (0x0707070F).to_bytes(4, "little") + (2).to_bytes(4, "little")
                  + (width * height * 4).to_bytes(4, "little") + b"\0\0")
        children.extend(CRMT_CHILD_WRAPPER + header + b"\0\0")
    raw, _, _ = encode_crmt(bytes(parent) + bytes(children) + b"SYNTHETIC",
                            [bytes(color) * (w * h) for w, h in sizes])
    return raw


def write_fixture(destination):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    review = {"rows": []}
    expanded = {"items": []}
    catalog = {"objects": [], "assets": [], "language_pairs": []}
    volumes = [{"volume": "synthetic.rio"}]
    pictures = {}
    records = {}
    sizes = {"ja": [(5, 3), (3, 2)], "en": [(5, 3)], "zh": [(5, 3), (3, 2)]}
    for name, color in (("ja", (80, 100, 120, 255)), ("en", (160, 100, 120, 255)), ("zh", (40, 180, 120, 255))):
        raw = synthetic_record(sizes[name], color)
        record = destination / (name + ".crmt")
        record.write_bytes(raw)
        layers, _ = decode_crmt(raw)
        pictures[name] = []
        for d in layers:
            path = destination / f"{name}-{d.level.index}.png"
            Image.frombytes("RGBA", (d.level.width, d.level.height), d.rgba).save(path)
            pictures[name].append({"path": str(path), "image_id": f"{name}-{d.level.index}",
                                   "level": d.level.index, "width": d.level.width, "height": d.level.height,
                                   "sha256": digest(path.read_bytes()), "rgba_sha256": digest(d.rgba)})
        records[name] = {"record": str(record), "record_sha256": digest(raw)}
    for number, (paired, kept, games) in enumerate(((True, False, ["PF", "PM"]),
                                                   (False, False, ["PF"]), (False, True, ["PM"])), 1):
        logical_id = f"SYN{number:03}"
        treatment = "保留官方日文" if kept else "中文改图"
        row = {"id": logical_id, "category": "synthetic", "category_label": "合成样本（非游戏素材）",
               "games": games, "relationship": "有英文本地化" if paired else "无英文本地化",
               "treatment": treatment, "text": "Synthetic fixture; not a real review approval"}
        item = {k: row[k] for k in ("id", "category", "category_label", "treatment")}
        item["branches"] = []
        for role, name in (("japanese", "ja"), ("english", "en")):
            if name == "en" and not paired:
                row["official_english"] = None
                continue
            picture = deepcopy(pictures[name][0])
            picture["image_id"] = f"{logical_id}-{name}"
            row["official_" + role] = picture
            catalog["assets"].append({"image_id": picture["image_id"], "width": picture["width"],
                                      "height": picture["height"], "png_sha256": picture["sha256"],
                                      "physical_uses": [{"game": g, "crmt_id": f"{logical_id}-{name}",
                                                         "role": "inline_top"} for g in games]})
        row["chinese"] = deepcopy(row["official_japanese"] if kept else pictures["zh"][0])
        for game in games:
            branch = {"game": game, "english": None}
            for role, name in (("japanese", "ja"), ("english", "en")):
                if name == "en" and not paired:
                    continue
                object_id = f"{logical_id}-{name}"
                branch[role] = {"game": game, "object_id": object_id, "levels": deepcopy(pictures[name])}
                catalog["objects"].append({"game": game, "crmt_id": object_id, "volume_index": 0,
                    "offset": number * 4096 + (256 if name == "en" else 0),
                    "extent": Path(records[name]["record"]).stat().st_size,
                    "record_sha256": records[name]["record_sha256"], "image_mp": None,
                    "external_image": None, "related_crmt_ids": [],
                    "inline_levels": [{"level": p["level"], "width": p["width"], "height": p["height"],
                                       "png_sha256": p["sha256"], "rgba_sha256": p["rgba_sha256"]}
                                      for p in pictures[name]]})
            target = branch["english"] or branch["japanese"]
            zh = {"game": game, "object_id": target["object_id"],
                  "levels": deepcopy(pictures["ja" if kept else "zh"])}
            if not kept:
                zh.update(records["zh"], approved_png_sha256=row["chinese"]["sha256"])
            branch["chinese"] = zh
            item["branches"].append(branch)
            if paired:
                catalog["language_pairs"].append({"pair_id": f"{game}-{logical_id}", "game": game,
                    "legacy_asset_id": logical_id, "japanese_crmt_id": branch["japanese"]["object_id"],
                    "english_crmt_id": branch["english"]["object_id"],
                    "japanese_image_ids": [row["official_japanese"]["image_id"]],
                    "english_image_ids": [row["official_english"]["image_id"]],
                    "relation": "confirmed_static_ja_en"})
        review["rows"].append(row)
        expanded["items"].append(item)
    for name, data in (("review", review), ("expanded", expanded), ("catalog", catalog),
                       ("volume-index", {"volumes": volumes})):
        (destination / (name + ".json")).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return review, expanded, catalog, volumes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    write_fixture(args.output_dir)


if __name__ == "__main__":
    main()
