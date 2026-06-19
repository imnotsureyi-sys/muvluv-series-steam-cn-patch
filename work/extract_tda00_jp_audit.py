from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = (
    ROOT
    / "outputs"
    / "tda_fpd_extract"
    / "tda00"
    / "root"
    / "assets"
    / "data_spec"
    / "adv"
    / "game"
    / "scr"
    / "localized"
)
DEFAULT_OUT = ROOT / "outputs" / "tda_text" / "tda00_jp_audit"
ID_RE = re.compile(r"(game_[ts]\d+(?:_ruby)?)")


def is_surrogate(ch: str) -> bool:
    return 0xDC80 <= ord(ch) <= 0xDCFF


def is_boundary(ch: str) -> bool:
    return ch == "\x00" or is_surrogate(ch) or (ord(ch) < 32 and ch not in "\t\r\n")


def visible_runs(segment: str) -> list[str]:
    runs: list[str] = []
    start: int | None = None
    for index, ch in enumerate(segment):
        if is_boundary(ch):
            if start is not None:
                runs.append(segment[start:index])
                start = None
        elif start is None:
            start = index
    if start is not None:
        runs.append(segment[start:])
    return runs


def clean_text(text: str) -> str:
    return (text or "").replace("\r", "").replace("\n", "\\n").replace("\\p", "").replace("\\f", "").strip()


def useful_run(text: str) -> bool:
    if not text:
        return False
    if text in {"P", "U", ")", "}", "_", "4w", "Pg9", "\u038e", "*"}:
        return False
    if text in {"de", "en", "es", "fr", "id", "it", "jp", "pt", "pt_br", "zh_hans", "zh_hant"}:
        return False
    return True


def display_run(runs: list[str]) -> str:
    if "_" in runs:
        candidates = runs[: runs.index("_")]
    else:
        candidates = runs
    for item in reversed(candidates):
        text = clean_text(item)
        if useful_run(text):
            return text
    return ""


def extract_egpack(path: Path) -> list[dict[str, str]]:
    raw = path.read_bytes().decode("utf-8", "surrogateescape")
    matches = list(ID_RE.finditer(raw))
    if not matches:
        return []

    records: list[dict[str, str]] = []
    prefix_jp = display_run(visible_runs(raw[: matches[0].start()]))
    pending_jp = prefix_jp

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        segment_runs = visible_runs(raw[match.start() : end])
        current_id = match.group(1)
        next_jp = display_run(segment_runs)
        records.append(
            {
                "egpack": path.name,
                "id": current_id,
                "jp": pending_jp,
                "next_jp_carried_in_this_block": next_jp,
            }
        )
        pending_jp = next_jp
    return records


def iter_message_refs(xml_path: Path) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(xml_path.read_text(encoding="utf-8"))
    except ET.ParseError:
        # Fall back to a conservative regex scan if a script XML has nonstandard syntax.
        refs: list[dict[str, str]] = []
        text_attr_re = re.compile(r'\b(text\d*)="\$([^"]+)"')
        speaker_attr_re = re.compile(r'\b(name|speaker)="\$([^"]+)"')
        for line_no, line in enumerate(xml_path.read_text("utf-8", errors="replace").splitlines(), start=1):
            if "<message" not in line:
                continue
            text_ids = [m.group(2) for m in text_attr_re.finditer(line)]
            speaker_ids = [m.group(2) for m in speaker_attr_re.finditer(line)]
            for order_in_message, text_id in enumerate(text_ids, start=1):
                refs.append(
                    {
                        "xml": xml_path.name,
                        "xml_line": str(line_no),
                        "message_tag_index": "",
                        "order_in_message": str(order_in_message),
                        "text_id": text_id,
                        "speaker_id": speaker_ids[0] if speaker_ids else "",
                        "xml_attrs": line.strip(),
                    }
                )
        return refs

    refs = []
    message_index = 0
    for elem in root.iter():
        if elem.tag != "message":
            continue
        message_index += 1
        speaker_id = ""
        for key in ("name", "speaker"):
            value = elem.attrib.get(key, "")
            if value.startswith("$"):
                speaker_id = value[1:]
                break
        text_attrs = []
        for key, value in elem.attrib.items():
            if re.fullmatch(r"text\d*", key) and value.startswith("$"):
                text_attrs.append((key, value[1:]))
        text_attrs.sort(key=lambda kv: (0 if kv[0] == "text" else int(kv[0][4:] or 0), kv[0]))
        for order_in_message, (attr_name, text_id) in enumerate(text_attrs, start=1):
            refs.append(
                {
                    "xml": xml_path.name,
                    "xml_line": "",
                    "message_tag_index": str(message_index),
                    "order_in_message": str(order_in_message),
                    "text_attr": attr_name,
                    "text_id": text_id,
                    "speaker_id": speaker_id,
                    "xml_attrs": " ".join(f'{k}="{v}"' for k, v in sorted(elem.attrib.items())),
                }
            )
    return refs


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract and audit TDA00 JP slots against localized XML calls.")
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    src = args.src
    out = args.out
    all_records: list[dict[str, str]] = []
    by_file_id: dict[tuple[str, str], dict[str, str]] = {}
    by_id: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    speaker_rows: list[dict[str, str]] = []
    ruby_rows: list[dict[str, str]] = []

    for egpack in sorted(src.glob("*.egpack")):
        records = extract_egpack(egpack)
        if egpack.name == "__staffroll__.egpack":
            continue
        if egpack.name == "__speakers__.egpack":
            for order, rec in enumerate(records, start=1):
                speaker_rows.append(
                    {
                        "speaker_order": str(order),
                        "speaker_id": rec["id"],
                        "speaker_jp": rec["jp"],
                        "egpack": egpack.name,
                    }
                )
            continue
        for rec in records:
            if rec["id"].endswith("_ruby"):
                ruby_rows.append(
                    {
                        "egpack": egpack.name,
                        "ruby_id": rec["id"],
                        "ruby_jp": rec["jp"],
                    }
                )
                continue
            by_file_id[(egpack.name, rec["id"])] = rec
            by_id[rec["id"]].append(rec)
            all_records.append(rec)

    calls: list[dict[str, str]] = []
    global_order = 0
    speaker_by_id = {row["speaker_id"]: row["speaker_jp"] for row in speaker_rows}
    for xml in sorted(src.glob("*.xml")):
        if xml.name == "gallery.xml":
            continue
        egpack_name = xml.with_suffix(".egpack").name
        for ref in iter_message_refs(xml):
            if ref["text_id"].endswith("_ruby"):
                continue
            global_order += 1
            rec = by_file_id.get((egpack_name, ref["text_id"]))
            same_id_records = by_id.get(ref["text_id"], [])
            status = "ok" if rec else "missing_in_matching_egpack"
            if rec and not rec["jp"]:
                status = "called_but_jp_empty"
            calls.append(
                {
                    "call_order": str(global_order),
                    "egpack": egpack_name,
                    "xml": ref["xml"],
                    "message_tag_index": ref.get("message_tag_index", ""),
                    "order_in_message": ref["order_in_message"],
                    "text_attr": ref.get("text_attr", ""),
                    "id": ref["text_id"],
                    "jp": rec["jp"] if rec else "",
                    "speaker_id": ref.get("speaker_id", ""),
                    "speaker_jp": speaker_by_id.get(ref.get("speaker_id", ""), ""),
                    "status": status,
                    "same_id_total_egpacks": str(len(same_id_records)),
                    "xml_attrs": ref["xml_attrs"],
                }
            )

    called_keys = {(row["egpack"], row["id"]) for row in calls}
    uncalled = [
        {
            "egpack": row["egpack"],
            "id": row["id"],
            "jp": row["jp"],
            "reason": "present_in_egpack_not_called_by_localized_xml",
        }
        for row in all_records
        if (row["egpack"], row["id"]) not in called_keys
    ]
    issues = [row for row in calls if row["status"] != "ok"]
    duplicate_ids = [
        {"id": text_id, "egpack_count": str(len(rows)), "egpacks": " | ".join(r["egpack"] for r in rows)}
        for text_id, rows in sorted(by_id.items())
        if len(rows) > 1
    ]
    call_counter = Counter((row["egpack"], row["id"]) for row in calls)
    repeated_calls = [
        {"egpack": egpack, "id": text_id, "call_count": str(count)}
        for (egpack, text_id), count in sorted(call_counter.items())
        if count > 1
    ]

    write_csv(
        out / "tda00_jp_text_by_call_order.csv",
        calls,
        [
            "call_order",
            "egpack",
            "xml",
            "message_tag_index",
            "order_in_message",
            "text_attr",
            "id",
            "jp",
            "speaker_id",
            "speaker_jp",
            "status",
            "same_id_total_egpacks",
            "xml_attrs",
        ],
    )
    write_csv(
        out / "tda00_jp_text_by_egpack_id.csv",
        all_records,
        ["egpack", "id", "jp", "next_jp_carried_in_this_block"],
    )
    write_csv(out / "tda00_speakers_jp.csv", speaker_rows, ["speaker_order", "speaker_id", "speaker_jp", "egpack"])
    write_csv(out / "tda00_ruby_jp.csv", ruby_rows, ["egpack", "ruby_id", "ruby_jp"])
    write_csv(out / "tda00_jp_call_issues.csv", issues, list(calls[0].keys()) if calls else [])
    write_csv(out / "tda00_jp_uncalled_egpack_rows.csv", uncalled, ["egpack", "id", "jp", "reason"])
    write_csv(out / "tda00_duplicate_ids_across_egpacks.csv", duplicate_ids, ["id", "egpack_count", "egpacks"])
    write_csv(out / "tda00_repeated_xml_calls.csv", repeated_calls, ["egpack", "id", "call_count"])

    print(f"src={src}")
    print(f"text_records={len(all_records)} called_text_refs={len(calls)} speakers={len(speaker_rows)} ruby={len(ruby_rows)}")
    print(f"issues={len(issues)} uncalled={len(uncalled)} duplicate_ids={len(duplicate_ids)} repeated_calls={len(repeated_calls)}")
    print(f"out={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
