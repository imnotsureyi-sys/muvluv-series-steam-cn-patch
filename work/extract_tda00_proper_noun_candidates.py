from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "outputs" / "tda_text" / "tda00_jp_audit"
CALLS_CSV = AUDIT_DIR / "tda00_jp_text_by_call_order.csv"
SPEAKERS_CSV = AUDIT_DIR / "tda00_speakers_jp.csv"
RUBY_CSV = AUDIT_DIR / "tda00_ruby_jp.csv"
GLOSSARY_CSV = ROOT / "outputs" / "glossary" / "muvluv_lunatranslator_full_glossary.csv"
PROPER_TSV = ROOT / "outputs" / "glossary" / "muvluv_lunatranslator_proper_nouns.tsv"
OUT_DIR = ROOT / "outputs" / "qa" / "name_review" / "tda00"

KATAKANA_RE = re.compile(r"[ァ-ヴー・][ァ-ヴー・Ａ-Ｚａ-ｚA-Za-z０-９0-9－―-]{1,}")
CJK_RUN_RE = re.compile(r"[一-龯々〆ヶ]{2,}")
ASCII_UPPER_RE = re.compile(r"\b[A-Z][A-Z0-9-]{1,}\b|[Ａ-Ｚ][Ａ-Ｚ０-９－]{1,}")

MIL_SUFFIXES = (
    "隊",
    "部隊",
    "小隊",
    "中隊",
    "大隊",
    "戦隊",
    "機隊",
    "艦隊",
    "軍",
    "海軍",
    "陸軍",
    "海兵隊",
    "司令部",
    "司令",
    "参謀会議",
    "政府",
    "帝国",
    "国連",
    "米国",
    "日本",
    "基地",
    "ハイヴ",
    "租借地",
)
PLACE_SUFFIXES = ("島", "海", "洋", "湾", "岸", "州", "国", "領", "地", "星", "月", "地球")
PERSON_SUFFIXES = ("少佐", "准将", "大将", "中尉", "少尉", "艦長", "軍医", "航海長")
KATA_HINTS = (
    "ナイヴス",
    "バスター",
    "ブラック",
    "マルドゥーク",
    "バビロン",
    "オールストン",
    "マクマナス",
    "リリア",
    "ウィル",
    "メルヴィナ",
    "ダリル",
    "テイラー",
    "スーパーホーネット",
    "ラプター",
    "ＪＦＫ",
)
DROP_TERMS = {
    "それ",
    "これ",
    "ここ",
    "あれ",
    "もの",
    "こと",
    "よう",
    "ため",
    "そう",
    "どこ",
    "誰か",
    "自分",
    "人間",
    "世界",
    "今日",
    "明日",
    "昨日",
    "アタシ",
    "アンタ",
    "ホント",
    "クソッ",
    "アイマム",
    "レベル",
    "タイミング",
    "ポイント",
    "アクセス",
    "スキャン",
    "ハーネス",
    "アンテナ",
    "システム",
    "ライン",
    "ポジション",
    "ヶ月",
    "大地",
    "着地",
}
PRIORITY_CATEGORIES = {
    "speaker_table_name",
    "katakana_callsign_or_unit",
    "katakana_ship_or_codename",
    "katakana_person",
    "latin_or_acronym",
    "ruby_term",
    "ruby_reading_katakana",
}
PRIORITY_KEYWORDS = (
    "作戦",
    "計画",
    "隊",
    "軍",
    "海兵",
    "海軍",
    "艦",
    "母艦",
    "司令",
    "基地",
    "ハイヴ",
    "合衆国",
    "国連",
    "帝国",
    "米国",
    "日本",
    "太平洋",
    "ヨコハマ",
    "シアトル",
    "ハワイ",
    "シドニー",
    "バビロン",
    "ブルーオーシャン",
    "フライング・ブーム",
    "ビッグ",
    "メモリアル",
)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def clean_for_scan(text: str) -> str:
    cleaned = text or ""
    for marker in ("\\w", "\\n", "…", "――", "―", "「", "」", "『", "』"):
        cleaned = cleaned.replace(marker, " ")
    return cleaned


def load_glossary_terms() -> dict[str, set[str]]:
    covered: dict[str, set[str]] = defaultdict(set)
    if GLOSSARY_CSV.exists():
        for row in read_rows(GLOSSARY_CSV):
            src = (row.get("source") or "").strip()
            tgt = (row.get("target") or "").strip()
            if src:
                covered[src].add(tgt)
    if PROPER_TSV.exists():
        with PROPER_TSV.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            for row in reader:
                src = (row.get("source") or row.get("jp") or row.get("term") or "").strip()
                tgt = (row.get("target") or row.get("cn") or row.get("translation") or "").strip()
                if src:
                    covered[src].add(tgt)
    return covered


def categorize_katakana(term: str, context: str) -> str:
    if any(hint in term for hint in ("ナイヴス", "バスター", "ブラック", "カロネード", "イーグル")):
        return "katakana_callsign_or_unit"
    if any(hint in term for hint in ("マルドゥーク", "ＪＦＫ", "ケネディ")):
        return "katakana_ship_or_codename"
    if any(hint in term for hint in ("ウィル", "リリア", "ダリル", "メルヴィナ", "オールストン", "マクマナス", "テイラー")):
        return "katakana_person"
    if any(word in context for word in ("隊", "母艦", "艦", "作戦", "戦術機", "海兵隊")):
        return "katakana_military_or_foreign"
    return "katakana_foreign_word"


def cjk_candidates(text: str) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    compact = clean_for_scan(text)
    for match in CJK_RUN_RE.finditer(compact):
        term = match.group(0)
        if term in DROP_TERMS or len(term) < 2:
            continue
        if any(suffix in term for suffix in MIL_SUFFIXES):
            found.add(("kanji_place_or_military_org", term))
        elif any(term.endswith(suffix) for suffix in PERSON_SUFFIXES):
            found.add(("kanji_person_or_rank_name", term))
        elif any(term.endswith(suffix) for suffix in PLACE_SUFFIXES):
            found.add(("kanji_place_or_region", term))
    phrase_patterns = [
        r"(?:国連|米国|日本帝国|帝国|北米)[一-龯々〆ヶァ-ヴー・Ａ-Ｚ０-９A-Z0-9]{2,}(?:司令部|参謀会議|海兵隊|海軍|陸軍|艦隊|政府|軍)",
        r"第[０-９0-9一二三四五六七八九十百]+[一-龯々〆ヶァ-ヴー・Ａ-Ｚ０-９A-Z0-9]{1,}(?:隊|大隊|戦隊|機隊|艦隊)",
        r"[一-龯々〆ヶァ-ヴー・Ａ-Ｚ０-９A-Z0-9]{2,}(?:作戦|計画|号作戦)",
    ]
    for pattern in phrase_patterns:
        for match in re.finditer(pattern, compact):
            found.add(("kanji_place_or_military_org", match.group(0)))
    return found


def add_candidate(
    buckets: dict[tuple[str, str], Counter],
    mentions: list[dict[str, str]],
    category: str,
    term: str,
    row: dict[str, str],
) -> None:
    term = term.strip("、。，．・！？!?（）()[]［］「」『』:：;； 　―-ッ")
    if len(term) < 2 or term in DROP_TERMS:
        return
    key = (category, term)
    buckets[key]["count"] += 1
    mentions.append(
        {
            "category": category,
            "term": term,
            "call_order": row.get("call_order", ""),
            "egpack": row.get("egpack", ""),
            "id": row.get("id", ""),
            "speaker_jp": row.get("speaker_jp", ""),
            "jp": row.get("jp", ""),
        }
    )


def main() -> int:
    calls = read_rows(CALLS_CSV)
    speakers = read_rows(SPEAKERS_CSV)
    ruby_rows = read_rows(RUBY_CSV)
    covered = load_glossary_terms()
    buckets: dict[tuple[str, str], Counter] = defaultdict(Counter)
    mentions: list[dict[str, str]] = []

    for speaker in speakers:
        add_candidate(
            buckets,
            mentions,
            "speaker_table_name",
            speaker["speaker_jp"],
            {"egpack": speaker["egpack"], "id": speaker["speaker_id"], "jp": speaker["speaker_jp"]},
        )

    for row in calls:
        jp = row["jp"]
        scan = clean_for_scan(jp)
        for match in KATAKANA_RE.finditer(scan):
            term = match.group(0)
            if len(term.replace("・", "").replace("ー", "")) < 3 and not any(ch.isdigit() for ch in term):
                continue
            add_candidate(buckets, mentions, categorize_katakana(term, scan), term, row)
        for match in ASCII_UPPER_RE.finditer(scan):
            term = match.group(0)
            if term in {"GS", "BETA", "JFK", "NORAD", "UAF"} or len(term) >= 3:
                add_candidate(buckets, mentions, "latin_or_acronym", term, row)
        for category, term in cjk_candidates(jp):
            add_candidate(buckets, mentions, category, term, row)

    for row in ruby_rows:
        ruby = row["ruby_jp"]
        if ":" in ruby:
            base, reading = ruby.split(":", 1)
            add_candidate(
                buckets,
                mentions,
                "ruby_term",
                base,
                {"egpack": row["egpack"], "id": row["ruby_id"], "jp": ruby},
            )
            if KATAKANA_RE.fullmatch(reading):
                add_candidate(
                    buckets,
                    mentions,
                    "ruby_reading_katakana",
                    reading,
                    {"egpack": row["egpack"], "id": row["ruby_id"], "jp": ruby},
                )

    first_seen: dict[tuple[str, str], dict[str, str]] = {}
    mention_counts = Counter((m["category"], m["term"]) for m in mentions)
    for mention in mentions:
        first_seen.setdefault((mention["category"], mention["term"]), mention)

    candidate_rows: list[dict[str, str]] = []
    singleton_keep_terms = {"コード８１１", "レベル４"}
    for (category, term), counter in sorted(
        buckets.items(), key=lambda item: (-item[1]["count"], item[0][0], item[0][1])
    ):
        keep_singleton = (
            "・" in term
            or term in singleton_keep_terms
            or term.endswith(("ベース", "ステーション", "作戦", "基地", "隊"))
        )
        if (
            counter["count"] < 2
            and category not in {"speaker_table_name", "ruby_term", "ruby_reading_katakana"}
            and not keep_singleton
        ):
            continue
        existing = covered.get(term, set())
        first = first_seen[(category, term)]
        candidate_rows.append(
            {
                "category": category,
                "term": term,
                "count": str(mention_counts[(category, term)]),
                "covered_by_existing_glossary": "yes" if existing else "no",
                "existing_targets": " | ".join(sorted(t for t in existing if t)),
                "first_call_order": first["call_order"],
                "first_egpack": first["egpack"],
                "first_id": first["id"],
                "first_speaker_jp": first["speaker_jp"],
                "first_context_jp": first["jp"],
                "decision": "",
                "confirmed_translation": "",
                "note": "",
            }
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "tda00_proper_noun_candidates_for_decision.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        fields = [
            "category",
            "term",
            "count",
            "covered_by_existing_glossary",
            "existing_targets",
            "first_call_order",
            "first_egpack",
            "first_id",
            "first_speaker_jp",
            "first_context_jp",
            "decision",
            "confirmed_translation",
            "note",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(candidate_rows)

    with (OUT_DIR / "tda00_proper_noun_candidate_mentions.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["category", "term", "call_order", "egpack", "id", "speaker_jp", "jp"]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(mentions)

    uncovered = [row for row in candidate_rows if row["covered_by_existing_glossary"] == "no"]
    with (OUT_DIR / "tda00_uncovered_candidates_for_manual_decision.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        fields = list(candidate_rows[0].keys()) if candidate_rows else []
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(uncovered)

    priority_rows = []
    for row in candidate_rows:
        term = row["term"]
        context = row["first_context_jp"]
        if term in DROP_TERMS:
            continue
        is_priority = row["category"] in PRIORITY_CATEGORIES or any(
            keyword in term or keyword in context for keyword in PRIORITY_KEYWORDS
        )
        if is_priority:
            priority_rows.append(row)
    with (OUT_DIR / "tda00_priority_terms_for_user_decision.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        fields = list(candidate_rows[0].keys()) if candidate_rows else []
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(priority_rows)

    print(
        f"candidates={len(candidate_rows)} uncovered={len(uncovered)} "
        f"priority={len(priority_rows)} mentions={len(mentions)} out={OUT_DIR}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
