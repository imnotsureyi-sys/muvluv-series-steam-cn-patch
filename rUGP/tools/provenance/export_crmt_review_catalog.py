"""Project an expanded CRmt review into public identities, not artwork or workstation paths.

Input adapters are deliberately limited to the reviewed 113/114 ledger shapes.
This is a publication adapter, not a fresh census, language detector or game installer.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

from PIL import Image

from rUGP.formats.images.crmti_decode import decode_crmt
from rUGP.tools.provenance.export_crmt_localization_evidence import assert_portable_document


def load(path):
    with (gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else path.open(encoding="utf-8")) as stream:
        return json.load(stream)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest().upper()


def checked_file(value):
    if sha(Path(value["path"])) != value["sha256"]:
        raise ValueError("artifact SHA-256 mismatch")


def checked_pixels(value):
    checked_file(value)
    with Image.open(value["path"]) as im:
        if im.size != (value["width"], value["height"]):
            raise ValueError("PNG dimensions mismatch")
        return im.convert("RGBA").tobytes()


def unique_index(rows, key, label):
    result = {key(r): r for r in rows}
    if len(result) != len(rows):
        raise ValueError("duplicate " + label)
    return result


def expected_branches(parent, catalog, assets):
    """Bind frozen review images to the census, not to expanded display labels."""
    uses = {}
    image_ids = {}
    for role in ("japanese", "english"):
        picture = parent["official_" + role]
        if picture is None:
            uses[role] = set()
            image_ids[role] = None
            continue
        asset = assets[picture["image_id"]]
        if (picture["width"], picture["height"], picture["sha256"]) != (
                asset["width"], asset["height"], asset["png_sha256"]):
            raise ValueError("review image identity mismatch")
        checked_pixels(picture)
        image_ids[role] = picture["image_id"]
        uses[role] = {(p["game"], p["crmt_id"]) for p in asset["physical_uses"] if p["role"] == "inline_top"}
    pairs = [p for p in catalog["language_pairs"] if p["legacy_asset_id"] == parent["id"]
             or uses["japanese"] & {(p["game"], p["japanese_crmt_id"]), (p["game"], p["english_crmt_id"])}
             or uses["english"] & {(p["game"], p["japanese_crmt_id"]), (p["game"], p["english_crmt_id"])}]
    expected = set()
    if image_ids["english"] is not None:
        if parent["relationship"] != "有英文本地化":
            raise ValueError("review language relationship mismatch")
        for p in pairs:
            if (p["legacy_asset_id"] != parent["id"] or p["relation"] != "confirmed_static_ja_en"
                    or image_ids["japanese"] not in p["japanese_image_ids"]
                    or image_ids["english"] not in p["english_image_ids"]):
                raise ValueError("canonical language pair mismatch")
            identity = (p["game"], p["japanese_crmt_id"], p["english_crmt_id"])
            if identity in expected:
                raise ValueError("duplicate canonical language pair")
            expected.add(identity)
        if ({(g, j) for g, j, e in expected} != uses["japanese"]
                or {(g, e) for g, j, e in expected} != uses["english"]):
            raise ValueError("language pairs do not cover physical uses")
    else:
        if pairs or parent["relationship"] != "无英文本地化":
            raise ValueError("shared image conflicts with canonical language pairs")
        expected = {(g, j, None) for g, j in uses["japanese"]}
    if not expected or {g for g, j, e in expected} != set(parent["games"]):
        raise ValueError("incomplete review game coverage")
    return expected


def chinese_layers(zh, parent, japanese, kept):
    """Read actual encoded bytes; a self-consistent PNG ledger is insufficient."""
    checked_pixels(parent["chinese"])
    if kept:
        if zh.get("record") or zh.get("record_sha256"):
            raise ValueError("retained official image must not claim an encoded replacement")
        if parent["chinese"]["sha256"] != parent["official_japanese"]["sha256"]:
            raise ValueError("retained artwork differs from official Japanese")
        expected = [(p["level"], p["width"], p["height"], checked_pixels(p)) for p in japanese["levels"]]
    else:
        raw = Path(zh["record"]).read_bytes()
        if (hashlib.sha256(raw).hexdigest().upper() != zh["record_sha256"]
                or zh["approved_png_sha256"] != parent["chinese"]["sha256"]):
            raise ValueError("stale Chinese record or artwork")
        decoded, _ = decode_crmt(raw)
        expected = [(d.level.index, d.level.width, d.level.height, d.rgba) for d in decoded]
    if len(zh["levels"]) != len(expected) or not expected:
        raise ValueError("incomplete Chinese layer list")
    result = []
    for index, (p, (level, width, height, rgba)) in enumerate(zip(zh["levels"], expected, strict=True)):
        if (p["level"], p["width"], p["height"]) != (level, width, height) or level != index:
            raise ValueError("Chinese layer order or dimensions mismatch")
        if checked_pixels(p) != rgba:
            raise ValueError("Chinese layer pixels differ from decoded record or retained official")
        result.append({"level": level, "width": width, "height": height,
                       "png_sha256": p["sha256"], "rgba_sha256": hashlib.sha256(rgba).hexdigest().upper()})
    return result


def project(review, expanded, catalog, volumes, runtime_reports=()):
    originals = unique_index(catalog["objects"], lambda o: (o["game"], o["crmt_id"]), "official objects")
    logical = {r["id"]: r for r in review["rows"]}
    if len(logical) != len(review["rows"]) or len(logical) != len(expanded["items"]) or set(logical) != {r["id"] for r in expanded["items"]}:
        raise ValueError("duplicate or mismatched logical IDs")
    runtime = {}
    for report in runtime_reports:
        if report["status"] != "ALL_PENDING_BATCH_NATIVE_CONTROLLED_DISPLAY_PASSED":
            raise ValueError("unsupported runtime report profile")
        for r in report["results"]:
            if r["status"] != "PASS_NATIVE_OWN_KEY_DISPLAY_AND_ALL_MIP_PAYLOADS":
                raise ValueError("runtime row is not an own-key display pass")
            for field in ("candidate", "encoded_record", "screenshot", "payload_probe"):
                checked_file(r[field])
            key = (r["asset_id"], r["game"], r["object_id"])
            if key in runtime:
                raise ValueError("duplicate runtime target")
            runtime[key] = r
    assets = unique_index(catalog["assets"], lambda a: a["image_id"], "image IDs")
    public_objects = {}
    items = []
    used_targets = set()
    used_runtime = set()
    for row in expanded["items"]:
        parent = logical[row["id"]]
        for field in ("treatment", "category", "category_label"):
            if row[field] != parent[field]:
                raise ValueError("expanded review decision mismatch")
        expected = expected_branches(parent, catalog, assets)
        actual = [(b["game"], b["japanese"]["object_id"], b["english"]["object_id"] if b["english"] else None)
                  for b in row["branches"]]
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise ValueError("expanded branches differ from canonical language pairs/physical uses")
        branches = []
        for branch in row["branches"]:
            roles = {}
            for role in ("japanese", "english"):
                obj = branch[role]
                if obj is None:
                    roles[role] = None
                    continue
                key = (branch["game"], obj["object_id"])
                if obj["game"] != branch["game"]:
                    raise ValueError("official object game mismatch")
                original = originals[key]
                if original["external_image"] or original["related_crmt_ids"]:
                    raise ValueError("this projection requires separate handling of external/dependent images")
                if len(obj["levels"]) != len(original["inline_levels"]):
                    raise ValueError("incomplete inline layer list")
                v = volumes[original["volume_index"]]
                levels = []
                for p, q in zip(obj["levels"], original["inline_levels"], strict=True):
                    if (p["level"], p["width"], p["height"], p["sha256"]) != (q["level"], q["width"], q["height"], q["png_sha256"]):
                        raise ValueError("original layer identity mismatch")
                    if hashlib.sha256(checked_pixels(p)).hexdigest().upper() != q["rgba_sha256"]:
                        raise ValueError("original layer RGBA mismatch")
                    levels.append({"level": p["level"], "width": p["width"], "height": p["height"],
                                   "png_sha256": p["sha256"], "rgba_sha256": q["rgba_sha256"]})
                identity = {"game": branch["game"], "object_id": obj["object_id"], "volume": v["volume"],
                            "offset": original["offset"], "extent": original["extent"],
                            "record_sha256": original["record_sha256"], "image_mp": original["image_mp"],
                            "external_image": None, "levels": levels}
                public_objects[key] = identity
                roles[role] = obj["object_id"]
            zh = branch["chinese"]
            target = roles["english"] or roles["japanese"]
            if (zh["game"], zh["object_id"]) != (branch["game"], target):
                raise ValueError("Chinese target identity mismatch")
            if (branch["game"], target) in used_targets:
                raise ValueError("duplicate physical target")
            used_targets.add((branch["game"], target))
            kept = row["treatment"] == "保留官方日文"
            zhlevels = chinese_layers(zh, parent, branch["japanese"], kept)
            evidence = {"controlled_display": "not_imported_in_this_snapshot", "original_story": "not_certified_by_this_snapshot"}
            rk = (row["id"], branch["game"], target)
            if rk in runtime:
                hit = runtime[rk]
                if hit["encoded_record"]["sha256"] != zh.get("record_sha256") or hit["candidate"]["sha256"] != parent["chinese"]["sha256"]:
                    raise ValueError("runtime evidence belongs to different artwork/record")
                used_runtime.add(rk)
                evidence.update(controlled_display="passed_diagnostic_original_key", matched_mip_payloads=hit["mips_verified"],
                                screenshot_sha256=hit["screenshot"]["sha256"], payload_probe_sha256=hit["payload_probe"]["sha256"])
            branches.append({"game": branch["game"], "official_japanese": roles["japanese"], "official_english": roles["english"],
                             "english_localization": "separate" if roles["english"] else "none_uses_official_japanese",
                             "target_object": target, "chinese": {"record_sha256": zh.get("record_sha256"),
                             "source_png_sha256": parent["chinese"]["sha256"], "levels": zhlevels,
                             "encoding": "not_required_official_retained" if kept else "all_layers_decoded_and_hash_bound"},
                             "evidence": evidence})
        items.append({"id": row["id"], "category": row["category"], "category_label": row["category_label"],
                      "treatment": row["treatment"], "chinese_copy": parent["text"],
                      "visual_review": "user_approved_or_explicit_official_retention", "branches": branches})
    if set(runtime) != used_runtime:
        raise ValueError("runtime records outside current review")
    objects = sorted(public_objects.values(), key=lambda x: (x["game"], x["object_id"]))
    summary = {"logical_groups": len(items), "physical_targets": len(used_targets), "official_objects": len(objects),
               "official_inline_layers": sum(len(o["levels"]) for o in objects),
               "chinese_or_retained_layers": sum(len(b["chinese"]["levels"]) for r in items for b in r["branches"]),
               "separate_english_groups": sum(any(b["official_english"] for b in r["branches"]) for r in items),
               "treatments": dict(Counter(r["treatment"] for r in items)), "imported_controlled_display_records": len(runtime)}
    result = {"schema": "photon-crmt-review-catalog/1", "scope": "Current reviewed localization groups, not the whole-game image census",
              "summary": summary, "objects": objects, "items": items,
              "limits": ["No official or localized image bytes are distributed by this catalog.",
                         "Official Japanese identifies the Japanese-version source, which may itself contain English.",
                         "A null official_english means no separate English localization; not an unidentified English peer.",
                         "Mips are not animation frames. Equal layer numbers need not have equal dimensions across locales.",
                         "Not-imported evidence is not a failed or never-tested claim. This is not release certification.",
                         "Matching loaded mip payloads does not prove that every mip was separately drawn."]}
    assert_portable_document(result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("review", "expanded", "catalog", "volume-index", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--runtime", action="append", type=Path, default=[])
    args = parser.parse_args(argv)
    paths = {k: getattr(args, k) for k in ("review", "expanded", "catalog", "volume_index")}
    bindings = {k: sha(p) for k, p in paths.items()}
    bindings["runtime"] = [sha(p) for p in args.runtime]
    result = project(load(args.review), load(args.expanded), load(args.catalog), load(args.volume_index)["volumes"], [load(p) for p in args.runtime])
    if any(sha(p) != bindings[k] for k, p in paths.items()) or [sha(p) for p in args.runtime] != bindings["runtime"]:
        raise ValueError("input changed during export")
    result["input_sha256"] = bindings
    assert_portable_document(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    # Keep redirected Windows consoles (e.g. cp1252) from failing after publication.
    # The artifact above remains readable UTF-8; stdout is ASCII-safe JSON.
    print(json.dumps(result["summary"], ensure_ascii=True))


if __name__ == "__main__":
    main()
