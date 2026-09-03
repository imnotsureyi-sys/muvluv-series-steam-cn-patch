"""Inventory every native CRsa text field without modifying games or reviews.

Inputs are the checksum-verified plaintext cache/census produced by
audit_crsa_display_gaps. Optional current-overlay plaintexts are audited as a
second layer. All decisions retain field ownership, hashes and both languages.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import itertools
import json
from pathlib import Path
import re

from rUGP.formats.rio.crsa_vm_fields import inventory_vm_pool
from rUGP.formats.rio import crsa_vm_stream
from rUGP.formats.rio.crsa_vm_pool import find_vm_message_commands
from rUGP.formats.rio.crsa_vm_stream import CrsaVmStream, NativeVmSchema, native_message_commands
from rUGP.formats.rio.crypto import decode_extent_offset


WEAPON_CALLEES = {
    "pf": {0xC634C9DC, 0xC634F69E},
    "pm": {0xF9367126, 0xF936A58F},
}
GAME_FOLDERS = {"pf": "photonflowers", "pm": "photonmelodies"}
CONTROLS = "".join(chr(i) for i in range(32))
CSV_COLUMNS = (
    "field_id", "game", "category", "rio_file", "block_offset", "stage",
    "command_order", "vm_message_order", "language", "role", "payload_offset",
    "source_payload_offset", "text", "source_text", "display_text", "field_sha256",
    "source_field_sha256", "native_index", "native_target_offset", "index_field_offset",
    "native_target_text", "native_reference_error", "binding", "keys_in_message", "reviewed_ids",
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def escaped(text: str, keep: str = "\t\r\n") -> str:
    return "".join(f"<{ord(c):02X}>" if ord(c) < 32 and c not in keep else c for c in text)


def source_hashes(text: str, *, counted: bool = False) -> set[str]:
    """Recognize historical control escaping, never cross a NUL to find text."""
    forms = {text}
    if counted:
        forms.add(text.rstrip(CONTROLS))
    if text.startswith("\x10"):
        forms.add(text[1:])
    keep_sets = ["".join(c for c, keep in zip("\t\r\n", flags) if keep)
                 for flags in itertools.product((False, True), repeat=3)]
    return ({sha(form.encode("utf-8")) for form in forms}
            | {sha(escaped(form, keep).encode("utf-8")) for form in forms for keep in keep_sets})


def visible(text: str) -> bool:
    return any(ord(c) >= 32 and not c.isspace() and c != "\u2060" for c in text)


def has_chinese_or_font_glyph(text: str) -> bool:
    return any("\u3400" <= c <= "\u9fff" or "\ue000" <= c <= "\uf8ff" for c in text)


def has_kana_letters(text: str) -> bool:
    return any("\u3041" <= c <= "\u3096" or "\u30a1" <= c <= "\u30fa" for c in text)


def latin_sentence(text: str) -> bool:
    body = re.sub(r"^【[^】]*】", "", text.lstrip(CONTROLS))
    return bool(re.search(r"[A-Za-z]{3}", body)) and not has_chinese_or_font_glyph(body)


def inline_category(field: dict, command: dict, game: str) -> str:
    text, role = field["text"], field["role"]
    if not text:
        return "empty_inline_field"
    if (role == "call.argument.2" and command.get("name") == "CVmCall"
            and command["fields"]["script"].get("key") in WEAPON_CALLEES[game]):
        return "excluded_weapon_parameter"
    if role == "generic.OM_SetFont.フェイス名":
        return "font_identifier"
    if "\\|" in text:
        display = text.split("\\|", 1)[1]
        if has_chinese_or_font_glyph(display):
            return "existing_bilingual_inline"
        if not visible(display.replace("\\", "")):
            return "formatting_inline"
        if display in ("No.$NO\\", "$TR", "%Y/%m/%d", "%H:%M:%S"):
            return "save_slot_template"
        return "unresolved_inline_display"
    if role.startswith(("generic.OM_Access", "generic.OM_ChangeSetting")):
        return "setting_key_or_value"
    if re.fullmatch(r"-?\d+|[A-Z][A-Z_\d]*|[A-Z_\d１２]+(?:_[^\\\s]+)+", text):
        return "script_identifier_or_number"
    if text in ("\\A", "\\|", "muvluv16_steam"):
        return "format_or_resource_identifier"
    if text in ("Muv-Luv photonflowers*", "マブラヴ photonmelodys"):
        return "game_title_metadata"
    if has_chinese_or_font_glyph(text) and not has_kana_letters(text):
        return "existing_chinese_inline"
    return "unresolved_inline_semantics"


def load_reviews(paths: list[Path]) -> tuple[dict, list[dict]]:
    lookup = defaultdict(lambda: defaultdict(list))
    files = []
    for path in paths:
        rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
        files.append(dict(path=str(path), sha256=sha(path.read_bytes()), rows=len(rows)))
        for row in rows:
            volume, offset = row["scene"].removeprefix("crsa:").rsplit("@", 1)
            block = f"{volume}.{int(offset):010d}"
            lookup[block][row["source_text_sha256"].upper()].append(row)
    return lookup, files


def review_matches(lookup: dict, block: str, text: str, *, counted: bool = False) -> list[dict]:
    matches = {}
    for digest in source_hashes(text, counted=counted):
        for row in lookup.get(block, {}).get(digest, ()):
            matches[row["stable_id"]] = row
    return list(matches.values())


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            values = dict(row)
            for key, value in values.items():
                if isinstance(value, str):
                    values[key] = escaped(value)
                elif isinstance(value, (list, tuple)):
                    values[key] = json.dumps(value, ensure_ascii=False)
            writer.writerow(values)


def audit(game: str, cache: Path, output: Path, reviewed: list[Path],
          overlay_cache: Path | None = None, overlay_manifest: Path | None = None) -> dict:
    schema = NativeVmSchema(game)
    census = json.loads((cache / "census.json").read_text(encoding="utf-8"))
    expected = {}
    global_blocks = {}
    start = 0
    for volume in census["volumes"]:
        for block in volume["blocks"]:
            name = f"{volume['name']}.{block['offset']:010d}"
            expected[name] = dict(block, rio_file=volume["name"])
            global_blocks[start + block["offset"]] = name
        start += volume["bytes"]
    actual = {p.stem: p for p in cache.glob("*.plain")}
    if set(actual) != set(expected):
        raise ValueError("plaintext cache and complete census have different block sets")
    overlay_rows = {}
    if overlay_cache is not None:
        if overlay_manifest is None:
            raise ValueError("overlay audit requires its current snapshot manifest")
        manifest = json.loads(overlay_manifest.read_text(encoding="utf-8"))[game]
        overlay_rows = {r["block"]: r for r in manifest["routes"] if r.get("payload_sha256")}
        for block in overlay_rows:
            if block not in expected:
                raise ValueError(f"current override has no census binding: {block}")
    reviews, review_files = load_reviews(reviewed)
    reviewed_ids = {r["stable_id"] for hashes in reviews.values() for rs in hashes.values() for r in rs}
    seen_reviews = set()
    all_annotations, all_inline, all_unclaimed = [], [], []
    missed_current, unreviewed_current, retained_english = [], [], []
    blocks, source_mismatches, graph_issues = [], [], []
    stats = Counter()
    output.mkdir(parents=True, exist_ok=True)
    # A failed refresh must not leave an older "complete" report next to a
    # partially refreshed ledger. Completion is published only after all blocks.
    (output / "audit.json").write_text(
        json.dumps(dict(audit_state="incomplete", game=game), indent=2)+"\n", encoding="utf-8")
    with (output / "all-native-text.jsonl").open("w", encoding="utf-8") as ledger:
        for block, path in sorted(actual.items()):
            volume = expected[block]["rio_file"]
            block_offset = expected[block]["offset"]
            stages = [("base", path, expected[block]["payload_sha256"])]
            if block in overlay_rows:
                stages.append(("overlay", overlay_cache / (block + ".plain"), overlay_rows[block]["payload_sha256"]))
            for stage, stage_path, digest in stages:
                data = stage_path.read_bytes()
                expected_length = (expected[block]["plaintext_bytes"] if stage == "base"
                                   else overlay_rows[block]["bytes"])
                if len(data) != expected_length:
                    raise ValueError(f"plaintext length mismatch: {stage_path}")
                if sha(data) != digest.upper():
                    raise ValueError(f"plaintext hash mismatch: {stage_path}")
                parser = CrsaVmStream(data, schema)
                parsed = parser.parse()
                native_messages = native_message_commands(parsed)
                heuristic = find_vm_message_commands(data)
                native_offsets = {c.body_offset for c in native_messages}
                heuristic_offsets = {c.body_offset for c in heuristic}
                if native_offsets != heuristic_offsets:
                    source_mismatches.append(dict(block=block, stage=stage,
                        native_only=sorted(native_offsets-heuristic_offsets),
                        heuristic_only=sorted(heuristic_offsets-native_offsets)))
                pool = inventory_vm_pool(data, native_messages, parsed["pool_base"])
                if any(r.error for r in pool.references if r.role == "message"):
                    raise ValueError(f"invalid primary message reference: {block}/{stage}")
                current = stage == "overlay" or block not in overlay_rows
                by_message = defaultdict(dict)
                for ref in pool.references:
                    if ref.role == "message":
                        by_message[ref.command_order][ref.language] = ref
                stream_messages = [c for c in parsed["commands"] if c["name"] == "CVmMsg3"]
                command_map = {c["order"]: c for c in parsed["commands"]}
                common = dict(game=game, rio_file=volume, block_offset=block_offset, stage=stage)

                def emit(row: dict) -> dict:
                    row = dict(common, **row)
                    row.setdefault("field_id", f"{game}:native:{volume}:{block_offset}:"
                                   f"{row.get('command_order', 0)}:{row.get('language', '')}:"
                                   f"{row.get('role', '')}:{row.get('payload_offset', '')}")
                    ledger.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                    return row

                for order, languages in by_message.items():
                    source = languages.get(0)
                    display = languages.get(1)
                    source_text = source.text or "" if source else ""
                    display_text = display.text or "" if display else ""
                    matches = review_matches(reviews, block, source_text)
                    ids = sorted(r["stable_id"] for r in matches)
                    if stage == "base":
                        seen_reviews.update(ids)
                    if ids:
                        category = "reviewed_message"
                    elif not visible(display_text):
                        category = "control_or_empty_message"
                    elif not visible(source_text) and latin_sentence(display_text):
                        category = "missed_control_source_display"
                    elif has_chinese_or_font_glyph(display_text):
                        category = "existing_chinese_unreviewed_message"
                    else:
                        category = "unresolved_message"
                    row = emit(dict(category=category, command_order=stream_messages[order-1]["order"],
                        vm_message_order=order, language=1, role="message",
                        payload_offset=display.offset if display else None,
                        source_payload_offset=source.offset if source else None,
                        source_field_sha256=sha(source_text.encode("utf-16le")),
                        index_field_offset=display.index_field_offset if display else None,
                        source_text=source_text, display_text=display_text, text=display_text,
                        field_sha256=sha(display_text.encode("utf-16le")), reviewed_ids=ids))
                    if current:
                        stats[category] += 1
                        if category.startswith(("missed_", "unresolved_")):
                            missed_current.append(row)
                        if not ids:
                            unreviewed_current.append(row)
                        if ids and latin_sentence(display_text):
                            retained_english.append(row)
                    # Retain languages beyond the normal source/display pair too.
                    for language, ref in languages.items():
                        if language > 1:
                            emit(dict(category="additional_language_message", command_order=stream_messages[order-1]["order"],
                                vm_message_order=order, language=language, role="message", payload_offset=ref.offset,
                                text=ref.text, field_sha256=sha((ref.text or "").encode("utf-16le"))))

                for annotation in pool.annotations:
                    text = annotation.cell.text
                    category = "source_language_annotation" if annotation.language == 0 else (
                        "display_annotation_format_marker" if all(v == "&" for _, v in annotation.entries)
                        else "missed_display_annotation")
                    primary = by_message[annotation.command_order][annotation.language]
                    actual_ref = next(r for r in pool.references if r.command_order == annotation.command_order
                                      and r.language == annotation.language and r.role == "annotation")
                    row = emit(dict(category=category,
                        command_order=stream_messages[annotation.command_order-1]["order"],
                        vm_message_order=annotation.command_order, language=annotation.language, role="annotation",
                        payload_offset=annotation.cell.offset, text=text, entries=annotation.entries,
                        source_text=primary.text if annotation.language == 0 else "",
                        display_text=primary.text if annotation.language == 1 else "",
                        field_sha256=sha(annotation.cell.raw[:-2]), native_index=annotation.native_index,
                        native_target_offset=annotation.native_offset, index_field_offset=annotation.index_field_offset,
                        native_target_text=actual_ref.text, native_reference_error=actual_ref.error,
                        binding=annotation.binding, keys_in_message=annotation.keys_in_message))
                    all_annotations.append(row)
                    if current:
                        stats[category] += 1
                        unreviewed_current.append(row)
                        if category == "missed_display_annotation":
                            missed_current.append(row)

                bound_annotations = {(a.command_order, a.language) for a in pool.annotations}
                for ref in pool.references:
                    unresolved = ref.role == "annotation" and (ref.command_order, ref.language) not in bound_annotations
                    if ref.role == "directive" or unresolved:
                        row = emit(dict(category="unresolved_annotation_reference" if unresolved else "directive_field",
                            command_order=stream_messages[ref.command_order-1]["order"],
                            vm_message_order=ref.command_order, language=ref.language, role=ref.role,
                            payload_offset=ref.offset, text=ref.text, native_index=ref.index,
                            index_field_offset=ref.index_field_offset, native_reference_error=ref.error))
                        if current and unresolved:
                            stats["unresolved_annotation_reference"] += 1
                            unreviewed_current.append(row)
                            missed_current.append(row)

                for field in parsed["strings"]:
                    match = re.match(r"command_(\d+):", field["context"])
                    order = int(match[1]) if match else 0
                    command = command_map.get(order, {})
                    text = field["text"]
                    source_text = text.split("\\|", 1)[0]
                    matches = review_matches(reviews, block, source_text, counted=True) if text else []
                    ids = sorted(r["stable_id"] for r in matches)
                    if stage == "base":
                        seen_reviews.update(ids)
                    category = inline_category(field, command, game)
                    row = emit(dict(category=category, command_order=order, language="inline", role=field["role"],
                        payload_offset=field["offset"], start=field["start"], end=field["end"], width=field["width"],
                        text=text, source_text=source_text, display_text=text.split("\\|", 1)[1] if "\\|" in text else "",
                        field_sha256=sha(data[field["offset"]:field["end"]]), reviewed_ids=ids))
                    all_inline.append(row)
                    if current:
                        stats[category] += 1
                        if not ids and text and category != "excluded_weapon_parameter":
                            unreviewed_current.append(row)
                        if category.startswith(("missed_", "unresolved_")):
                            missed_current.append(row)

                for cell in pool.unclaimed_cells:
                    row = emit(dict(category="unreferenced_pool_cell", language="unbound", role="pool_residue",
                        payload_offset=cell.offset, end=cell.end, text=cell.text, field_sha256=sha(cell.raw[:-2])))
                    all_unclaimed.append(row)
                    if current:
                        stats["unreferenced_pool_cell"] += 1
                for resource in parsed["resource_references"]:
                    target = decode_extent_offset(resource["key"], 4)
                    if target not in global_blocks:
                        graph_issues.append(dict(block=block, stage=stage, reference=resource, target=target))
                summary = dict(common, block=block, payload_sha256=sha(data), payload_bytes=len(data),
                    commands=parsed["command_count"], message_commands=len(native_messages),
                    command_classes=parsed["classes"], pool_base=pool.base, pool_end=pool.end,
                    pool_units=pool.declared_units, pool_cells=len(pool.cells),
                    nonempty_pool_cells=sum(bool(c.text) for c in pool.cells),
                    primary_references=len([r for r in pool.references if r.role == "message"]),
                    auxiliary_references=len([r for r in pool.references if r.role != "message"]),
                    annotations=len(pool.annotations), unreferenced_pool_cells=len(pool.unclaimed_cells),
                    cstrings=len(parsed["strings"]), nonempty_cstrings=sum(bool(f["text"]) for f in parsed["strings"]),
                    suffix_references=parsed["suffix_refs"], zero_padding=parsed["zero_padding"],
                    crsa_resource_references=len(parsed["resource_references"]), issues=list(pool.issues))
                blocks.append(summary)
            if len([b for b in blocks if b["stage"] == "base"]) % 50 == 0:
                print(f"{game}: {block}", flush=True)
    unmatched = sorted(reviewed_ids-seen_reviews)
    report = dict(audit_state="complete", game=game, validation_passed=not (unmatched or graph_issues),
        schema_executable={k:v for k,v in schema.metadata.items() if k != "types" and k != "descriptors"},
        schema_sha256=sha(Path(crsa_vm_stream.__file__).with_name('crsa_vm_schema.json').read_bytes()),
        base_blocks=len(expected), overlay_blocks=len(overlay_rows), complete_native_blocks=len(blocks),
        current_categories=dict(stats), reviewed_files=review_files, reviewed_rows=len(reviewed_ids),
        reviewed_source_hashes_matched=len(seen_reviews), unmatched_reviewed_ids=unmatched,
        heuristic_message_boundary_differences=source_mismatches, unmapped_crsa_references=graph_issues,
        blocks=blocks)
    (output / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")
    current_annotations = [r for r in all_annotations if r["stage"] == "overlay"
                           or f"{r['rio_file']}.{r['block_offset']:010d}" not in overlay_rows]
    write_csv(output / "all-annotations.csv", current_annotations)
    write_csv(output / "all-inline-fields.csv", [r for r in all_inline if r["stage"] == "overlay"
              or f"{r['rio_file']}.{r['block_offset']:010d}" not in overlay_rows])
    write_csv(output / "missing-current-text.csv", missed_current)
    write_csv(output / "unreviewed-fields.csv", unreviewed_current)
    write_csv(output / "unreferenced-pool-cells.csv", all_unclaimed)
    write_csv(output / "reviewed-foreign-language.csv", retained_english)
    for file in review_files:
        if sha(Path(file["path"]).read_bytes()) != file["sha256"]:
            raise ValueError("reviewed translations changed during audit")
    print(json.dumps({k:v for k,v in report.items() if k not in ("blocks", "reviewed_files", "schema_executable")},ensure_ascii=False),flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", choices=GAME_FOLDERS, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reviewed", type=Path, action="append")
    parser.add_argument("--overlay-cache", type=Path)
    parser.add_argument("--overlay-manifest", type=Path)
    args = parser.parse_args()
    reviewed = args.reviewed or sorted((Path(__file__).resolve().parents[2] / "games" /
                                      GAME_FOLDERS[args.game] / "translations/reviewed").rglob("*.csv"))
    report = audit(args.game, args.cache, args.output, reviewed, args.overlay_cache, args.overlay_manifest)
    if report["unmatched_reviewed_ids"] or report["unmapped_crsa_references"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
