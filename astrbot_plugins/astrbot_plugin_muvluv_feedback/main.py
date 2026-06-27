from __future__ import annotations

import csv
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import astrbot.api.message_components as Comp
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import Provider
from astrbot.api.star import Context, Star, register
from astrbot.core.utils.astrbot_path import get_astrbot_plugin_data_path


DEFAULT_COMPARE_PATHS = [
    "C:/Users/Administrator/Desktop/TDA00_03_latest_compare_tables/TDA00_JP_CN_COMPARE_utf8bom_2026.6.23.csv",
    "C:/Users/Administrator/Desktop/TDA00_03_latest_compare_tables/TDA01_JP_CN_COMPARE_utf8bom_2026.6.23.csv",
    "C:/Users/Administrator/Desktop/TDA00_03_latest_compare_tables/TDA02_JP_CN_COMPARE_utf8bom_2026.6.23.csv",
    "C:/Users/Administrator/Desktop/TDA00_03_latest_compare_tables/TDA03_JP_CN_COMPARE_utf8bom_2026.6.23.csv",
]

DEFAULT_GLOSSARY_PATHS = [
    "C:/Users/Administrator/Desktop/TDA00_03_PARATRANZ_import_csv/muvluv_lunatranslator_full_glossary.csv",
    "C:/Users/Administrator/Documents/Muv-LuvSeries汉化/outputs/glossary/muvluv_jp_cn_terms.csv",
]

DEFAULT_PARATRANZ_BASE_IDS = {
    "TDA00": 990024132,
    "TDA01": 990027845,
    "TDA02": 990036410,
    "TDA03": 990042999,
}


@dataclass
class TranslationRow:
    source_file: str
    csv_line: int
    call_order: int
    key: str
    chapter: str
    egpack: str
    scene: str
    speaker_jp: str
    row_id: str
    jp_text: str
    cn_text: str
    review_status: str
    audit_flags: str
    paratranz_id: str
    jp_norm: str
    cn_norm: str


@dataclass
class MatchResult:
    row: TranslationRow
    score: int
    matched_text: str
    matched_field: str


class TranslationIndex:
    def __init__(
        self,
        csv_paths: list[str],
        glossary_paths: list[str],
        paratranz_base_ids: dict[str, int] | None = None,
    ) -> None:
        self.csv_paths = csv_paths
        self.glossary_paths = glossary_paths
        self.paratranz_base_ids = paratranz_base_ids or DEFAULT_PARATRANZ_BASE_IDS
        self.rows: list[TranslationRow] = []
        self.by_key: dict[str, TranslationRow] = {}
        self.by_id: dict[str, list[TranslationRow]] = {}
        self.row_positions: dict[str, int] = {}
        self.glossary: list[dict[str, str]] = []
        self.load()

    def load(self) -> None:
        self.rows.clear()
        self.by_key.clear()
        self.by_id.clear()
        self.row_positions.clear()
        for path in self.csv_paths:
            self._load_translation_csv(path)
        self._load_glossary()
        logger.info("[muvluv_feedback] loaded %s translation rows", len(self.rows))

    def search(self, text: str, limit: int = 5) -> list[MatchResult]:
        text = text or ""
        direct = self._search_direct_key(text)
        if direct:
            return direct[:limit]

        fragments = extract_search_fragments(text)
        results: dict[str, MatchResult] = {}
        for fragment in fragments:
            norm = normalize_text(fragment)
            if len(norm) < 4:
                continue
            for row in self.rows:
                field = ""
                if norm in row.cn_norm:
                    field = "CN"
                    score = len(norm) * 10 + (1000 if norm == row.cn_norm else 0)
                elif norm in row.jp_norm:
                    field = "JP"
                    score = len(norm) * 8 + (800 if norm == row.jp_norm else 0)
                else:
                    continue
                existing = results.get(row.key)
                if existing is None or score > existing.score:
                    results[row.key] = MatchResult(row, score, fragment, field)
        return sorted(results.values(), key=lambda item: item.score, reverse=True)[:limit]

    def search_short_exact(self, text: str, limit: int = 5) -> list[MatchResult]:
        results: dict[str, MatchResult] = {}
        for norm in extract_short_search_norms(text):
            if len(norm) < 2 or len(norm) > 8:
                continue
            for row in self.rows:
                field = ""
                if norm == row.cn_norm:
                    field = "CN_SHORT_EXACT"
                    score = 600000 + len(norm) * 10
                elif norm == row.jp_norm:
                    field = "JP_SHORT_EXACT"
                    score = 590000 + len(norm) * 10
                else:
                    continue
                existing = results.get(row.key)
                if existing is None or score > existing.score:
                    results[row.key] = MatchResult(row, score, text, field)
        return sorted(results.values(), key=lambda item: item.score, reverse=True)[:limit]

    def search_near(self, anchor: TranslationRow, text: str, window: int = 3) -> list[MatchResult]:
        position = self.row_positions.get(anchor.key)
        if position is None:
            return []
        norms = extract_short_search_norms(text)
        if not norms:
            return []

        offsets: list[int] = []
        for step in range(1, window + 1):
            offsets.extend([step, -step])

        results: list[MatchResult] = []
        for offset in offsets:
            target_index = position + offset
            if target_index < 0 or target_index >= len(self.rows):
                continue
            row = self.rows[target_index]
            if row.chapter != anchor.chapter or row.egpack != anchor.egpack:
                continue
            for norm in norms:
                if norm in row.cn_norm:
                    results.append(MatchResult(row, 700000 - abs(offset), text, "CN_NEAR"))
                    break
                if norm in row.jp_norm:
                    results.append(MatchResult(row, 690000 - abs(offset), text, "JP_NEAR"))
                    break
            if results:
                break
        return results

    def glossary_hits(self, row: TranslationRow, limit: int = 6) -> list[dict[str, str]]:
        haystack = f"{row.jp_text}\n{row.cn_text}"
        hits = []
        seen = set()
        for term in self.glossary:
            source = term.get("source", "").strip()
            target = term.get("target", "").strip()
            if not source and not target:
                continue
            key = (source, target)
            if key in seen:
                continue
            if (source and source in haystack) or (target and target in haystack):
                hits.append(term)
                seen.add(key)
            if len(hits) >= limit:
                break
        return hits

    def context_window(self, row: TranslationRow, before: int = 3, after: int = 3) -> list[TranslationRow]:
        position = self.row_positions.get(row.key)
        if position is None:
            return []
        start = max(0, position - before)
        end = min(len(self.rows), position + after + 1)
        return [
            item
            for item in self.rows[start:end]
            if item.chapter == row.chapter and item.egpack == row.egpack
        ]

    def _search_direct_key(self, text: str) -> list[MatchResult]:
        results: list[MatchResult] = []
        full_keys = re.findall(r"TDA\d{2}\|.+?\.egpack\|[A-Za-z0-9_]+", text)
        for key in full_keys:
            row = self.by_key.get(key)
            if row:
                results.append(MatchResult(row, 999999, key, "KEY"))
        if results:
            return results

        ids = set(re.findall(r"\b(?:game|tda\d{2})_t\d{5}\b", text, flags=re.IGNORECASE))
        chapters = set(re.findall(r"\bTDA\d{2}\b", text, flags=re.IGNORECASE))
        for row_id in ids:
            for row in self.by_id.get(row_id.lower(), []):
                if chapters and row.chapter.upper() not in {item.upper() for item in chapters}:
                    continue
                results.append(MatchResult(row, 900000, row_id, "ID"))
        return results

    def _load_translation_csv(self, path: str) -> None:
        csv_path = Path(path)
        if not csv_path.exists():
            logger.warning("[muvluv_feedback] missing CSV: %s", path)
            return
        try:
            with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                first_line = handle.readline()
                handle.seek(0)
                header = [item.strip() for item in next(csv.reader([first_line]))] if first_line else []
                if {"id", "jp_text", "cn_text"}.issubset(set(header)):
                    reader = csv.DictReader(handle)
                    for line_no, record in enumerate(reader, start=2):
                        item = self._row_from_compare_record(csv_path, line_no, record)
                        if item:
                            self._add_row(item)
                    return

                reader = csv.reader(handle)
                for line_no, row in enumerate(reader, start=1):
                    item = self._row_from_paratranz_record(csv_path, line_no, row)
                    if item:
                        self._add_row(item)
        except Exception as exc:
            logger.error("[muvluv_feedback] failed to load %s: %s", path, exc)

    def _row_from_compare_record(
        self,
        csv_path: Path,
        line_no: int,
        record: dict[str, str],
    ) -> TranslationRow | None:
        chapter = infer_chapter_from_path(csv_path)
        row_id = str(record.get("id", "")).strip()
        egpack = str(record.get("egpack", "")).strip()
        jp_text = str(record.get("jp_text", "")).strip()
        cn_text = str(record.get("cn_text", "")).strip()
        if not chapter or not row_id or not egpack:
            return None
        call_order = safe_int(record.get("call_order", ""), line_no - 1)
        key = f"{chapter}|{egpack}|{row_id}"
        return TranslationRow(
            source_file=str(csv_path),
            csv_line=line_no,
            call_order=call_order,
            key=key,
            chapter=chapter,
            egpack=egpack,
            scene=str(record.get("scene", "")).strip(),
            speaker_jp=str(record.get("speaker_jp", "")).strip(),
            row_id=row_id,
            jp_text=jp_text,
            cn_text=cn_text,
            review_status=str(record.get("review_status", "")).strip(),
            audit_flags=str(record.get("audit_flags", "")).strip(),
            paratranz_id=compute_paratranz_id(chapter, call_order, self.paratranz_base_ids),
            jp_norm=normalize_text(jp_text),
            cn_norm=normalize_text(cn_text),
        )

    def _row_from_paratranz_record(
        self,
        csv_path: Path,
        line_no: int,
        row: list[str],
    ) -> TranslationRow | None:
        if len(row) < 3:
            return None
        key, jp_text, cn_text = row[0].strip(), row[1].strip(), row[2].strip()
        parts = key.split("|", 2)
        if len(parts) != 3:
            return None
        chapter, egpack, row_id = parts
        return TranslationRow(
            source_file=str(csv_path),
            csv_line=line_no,
            call_order=line_no,
            key=key,
            chapter=chapter,
            egpack=egpack,
            scene="",
            speaker_jp="",
            row_id=row_id,
            jp_text=jp_text,
            cn_text=cn_text,
            review_status="",
            audit_flags="",
            paratranz_id=compute_paratranz_id(chapter, line_no, self.paratranz_base_ids),
            jp_norm=normalize_text(jp_text),
            cn_norm=normalize_text(cn_text),
        )

    def _add_row(self, item: TranslationRow) -> None:
        self.rows.append(item)
        self.by_key[item.key] = item
        self.by_id.setdefault(item.row_id.lower(), []).append(item)
        self.row_positions[item.key] = len(self.rows) - 1

    def _load_glossary(self) -> None:
        self.glossary.clear()
        seen = set()
        for path in self.glossary_paths:
            csv_path = Path(path)
            if not csv_path.exists():
                continue
            try:
                with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle)
                    for row in reader:
                        source = str(row.get("source", "")).strip()
                        target = str(row.get("target", "")).strip()
                        key = (source, target)
                        if key in seen:
                            continue
                        seen.add(key)
                        self.glossary.append(
                            {
                                "source": source,
                                "target": target,
                                "category": str(row.get("category", "")).strip(),
                                "note": str(row.get("note", "")).strip(),
                            }
                        )
            except Exception as exc:
                logger.warning("[muvluv_feedback] failed to load glossary %s: %s", path, exc)


@register(
    "astrbot_plugin_muvluv_feedback",
    "Codex",
    "Locate Muv-Luv translation feedback against JP/CN compare table rows.",
    "0.1.0",
)
class MuvLuvFeedbackPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.context = context
        self.config = config or {}
        self.index = TranslationIndex(
            self._list("csv_paths", DEFAULT_COMPARE_PATHS),
            self._list("glossary_paths", DEFAULT_GLOSSARY_PATHS),
            self._dict_int("paratranz_base_ids", DEFAULT_PARATRANZ_BASE_IDS),
        )
        data_dir = Path(get_astrbot_plugin_data_path()) / "astrbot_plugin_muvluv_feedback"
        data_dir.mkdir(parents=True, exist_ok=True)
        self.queue_path = data_dir / self._str("queue_filename", "feedback_queue.csv")
        self.resolution_path = data_dir / self._str(
            "resolution_filename",
            "feedback_resolution_table.csv",
        )
        self.catalog_path = data_dir / self._str("line_catalog_filename", "line_catalog.csv")
        self.sync_task_path = data_dir / self._str("sync_task_filename", "paratranz_sync_tasks.csv")
        self.speaker_profile_path = data_dir / self._str(
            "speaker_profile_filename",
            "speaker_profiles.csv",
        )
        self.scene_context_path = data_dir / self._str(
            "scene_context_filename",
            "scene_contexts.csv",
        )
        self.relationship_path = data_dir / self._str(
            "speaker_relationship_filename",
            "speaker_relationships.csv",
        )
        self._ensure_queue_file()
        self._ensure_resolution_file()
        self._ensure_catalog_file()
        self._ensure_sync_task_file()
        self._ensure_speaker_profile_file()
        self._ensure_scene_context_file()
        self._ensure_relationship_file()
        logger.info("[muvluv_feedback] plugin initialized")

    @filter.command("反馈", alias={"翻译反馈", "查翻译", "定位翻译", "muvluv_feedback"})
    async def feedback(self, event: AstrMessageEvent):
        raw_text = strip_feedback_command(event.get_message_str())
        result = await self._process_feedback(event, raw_text)
        yield event.plain_result(result).stop_event()

    @filter.event_message_type(filter.EventMessageType.ALL, priority=45)
    async def auto_feedback(self, event: AstrMessageEvent):
        if not self._bool("auto_trigger_enabled", True):
            return
        has_image = event_has_image(event)
        is_addressed = is_event_addressed(event)
        explicit_trigger = should_auto_trigger(event)
        if has_image and not is_addressed:
            explicit_trigger = False
        image_probe = has_image and is_addressed and not explicit_trigger
        if not explicit_trigger and not image_probe:
            return
        result = await self._process_feedback(
            event,
            event.get_message_str(),
            silent_if_unmatched=image_probe,
        )
        if result:
            yield event.plain_result(result).stop_event()

    async def _process_feedback(
        self,
        event: AstrMessageEvent,
        raw_text: str,
        silent_if_unmatched: bool = False,
    ) -> str | None:
        image_refs = collect_event_image_refs(event)
        try:
            image_text = await self._extract_image_text(event, image_refs)
        except Exception as exc:
            logger.warning("[muvluv_feedback] image OCR failed: %s", exc)
            image_text = ""
        if image_refs and not image_text:
            if silent_if_unmatched:
                return None
            return (
                "这条消息里有图片，但 OCR 没提取到可用台词。\n"
                "请重发原图，或直接贴出截图里的中文台词。"
            )
        combined_text = "\n".join(part for part in [raw_text, image_text] if part.strip()).strip()
        if not combined_text:
            if silent_if_unmatched:
                return None
            return "请发截图或贴出当前中文台词。信息不足时我不会猜。"

        all_feedback_units = extract_feedback_units(raw_text, image_text)
        allow_short_exact = bool(image_text)
        context_matches = self._resolve_context_matches(
            all_feedback_units,
            allow_short_exact=allow_short_exact,
        )
        feedback_units = select_focused_units_by_rows(
            raw_text,
            all_feedback_units,
            context_matches,
        )
        resolved: list[tuple[str, MatchResult, str]] = []
        located: list[tuple[str, MatchResult]] = []
        missed: list[str] = []
        ambiguous: list[tuple[str, list[MatchResult]]] = []
        seen_keys: set[str] = set()
        last_match: MatchResult | None = None

        for unit in feedback_units:
            matches = self.index.search(unit, self._int("max_matches", 5))
            if not matches and allow_short_exact:
                matches = self.index.search_short_exact(unit, self._int("max_matches", 5))
            if not matches and last_match:
                matches = self.index.search_near(last_match.row, unit, window=3)
            if not matches and unit in context_matches:
                matches = [context_matches[unit]]
            if not matches:
                missed.append(unit)
                continue
            if len(matches) > 1 and matches[0].score == matches[1].score:
                ambiguous.append((unit, matches))
                continue

            match = matches[0]
            if match.row.key in seen_keys:
                continue
            seen_keys.add(match.row.key)
            located.append((unit, match))
            last_match = match

        reviews = await self._review_located_items(event, located)
        for unit, match in located:
            review = reviews.get(match.row.key, "")
            decision, suggested_cn, reason = parse_review_fields(review)
            side_effect_note = self._apply_review_result(
                event=event,
                raw_feedback=unit,
                image_text=image_text,
                match=match,
                decision=decision,
                suggested_cn=suggested_cn,
                reason=reason or review,
            )
            if side_effect_note:
                review = f"{review}\n{side_effect_note}" if review else side_effect_note
            self._append_queue(
                event=event,
                raw_feedback=unit,
                image_text=image_text,
                match=match,
                decision=decision or "已定位",
                suggested_cn=suggested_cn,
                reason=reason or review,
            )
            resolved.append((unit, match, review))

        if resolved:
            return self._format_feedback_results(
                resolved,
                image_text,
                missed,
                ambiguous,
                image_unit_count=len(all_feedback_units),
                focused_by_text=len(feedback_units) < len(all_feedback_units),
            )

        if ambiguous:
            if silent_if_unmatched:
                return None
            self._append_queue(
                event=event,
                raw_feedback=combined_text,
                image_text=image_text,
                match=None,
                decision="多候选",
                suggested_cn="",
                reason="找到多个同分候选，需要补充章节、上下文或更完整台词。",
            )
            return self._format_candidates(ambiguous[0][1], ambiguous[0][0])

        if silent_if_unmatched:
            return None
        self._append_queue(
            event=event,
            raw_feedback=combined_text,
            image_text=image_text,
            match=None,
            decision="定位不足",
            suggested_cn="",
            reason="未在 TDA00-03 JP/CN compare 表中找到精确匹配。",
        )
        return (
            "没有定位到精确 id。\n"
            "请补充更完整的当前中文台词、章节名，或直接提供 id。"
        )

    async def _review_located_items(
        self,
        event: AstrMessageEvent,
        located: list[tuple[str, MatchResult]],
    ) -> dict[str, str]:
        reviews: dict[str, str] = {}
        pending: list[tuple[str, MatchResult]] = []
        for unit, match in located:
            resolution = self._find_resolution_record(match.row)
            if resolution:
                reviews[match.row.key] = format_resolution_review(resolution)
            else:
                pending.append((unit, match))

        if not pending or not self._bool("enable_llm_review", True):
            return reviews
        if len(pending) == 1:
            unit, match = pending[0]
            reviews[match.row.key] = await self._review_with_llm(event, unit, match)
            return reviews

        batch_reviews = await self._review_many_with_llm(event, pending)
        reviews.update(batch_reviews)
        return reviews

    def _resolve_context_matches(
        self,
        units: list[str],
        allow_short_exact: bool = False,
    ) -> dict[str, MatchResult]:
        resolved: dict[str, MatchResult] = {}
        last_match: MatchResult | None = None
        for unit in units:
            matches = self.index.search(unit, self._int("max_matches", 5))
            if not matches and allow_short_exact:
                matches = self.index.search_short_exact(unit, self._int("max_matches", 5))
            if not matches and last_match:
                matches = self.index.search_near(last_match.row, unit, window=3)
            if not matches:
                continue
            if len(matches) > 1 and matches[0].score == matches[1].score:
                continue
            resolved[unit] = matches[0]
            last_match = matches[0]
        return resolved

    @filter.command("反馈队列", alias={"翻译反馈队列"})
    async def feedback_queue(self, event: AstrMessageEvent):
        count = 0
        if self.queue_path.exists():
            try:
                with self.queue_path.open("r", encoding="utf-8-sig", newline="") as handle:
                    count = max(0, sum(1 for _ in handle) - 1)
            except Exception:
                count = 0
        yield event.plain_result(
            f"当前反馈队列：{count} 条\n{self.queue_path}"
        ).stop_event()

    @filter.command("反馈重载", alias={"翻译反馈重载"})
    async def feedback_reload(self, event: AstrMessageEvent):
        if not event.is_admin():
            yield event.plain_result("只有管理员可以重载反馈索引。").stop_event()
            return
        self.index.load()
        self._ensure_catalog_file(refresh=True)
        self._ensure_speaker_profile_file(refresh=True)
        self._ensure_scene_context_file(refresh=True)
        yield event.plain_result(f"已重载索引：{len(self.index.rows)} 条。").stop_event()

    @filter.command("反馈处理表", alias={"反馈记录表", "翻译反馈处理表"})
    async def feedback_resolution_table(self, event: AstrMessageEvent):
        count = 0
        if self.resolution_path.exists():
            try:
                with self.resolution_path.open("r", encoding="utf-8-sig", newline="") as handle:
                    count = max(0, sum(1 for _ in handle) - 1)
            except Exception:
                count = 0
        yield event.plain_result(
            f"当前已处理反馈记录：{count} 条\n{self.resolution_path}"
        ).stop_event()

    @filter.command("反馈工作表", alias={"翻译反馈工作表", "反馈表格"})
    async def feedback_workbooks(self, event: AstrMessageEvent):
        yield event.plain_result(
            "反馈工作表：\n"
            f"台词主表：{self.catalog_path}\n"
            f"反馈队列：{self.queue_path}\n"
            f"已处理表：{self.resolution_path}\n"
            f"ParaTranz 同步任务：{self.sync_task_path}\n"
            f"人物资料：{self.speaker_profile_path}\n"
            f"场景资料：{self.scene_context_path}\n"
            f"人物关系：{self.relationship_path}"
        ).stop_event()

    async def _extract_image_text(
        self,
        event: AstrMessageEvent,
        image_refs: list[Any] | None = None,
    ) -> str:
        images = image_refs if image_refs is not None else collect_event_image_refs(event)
        if not images:
            return ""
        provider = self._get_vision_provider(event)
        prompt = (
            "你只负责 OCR。请提取图片中可见的游戏文本、说话人或文本标签。\n"
            "不要描述画面，不要解释，不要改写。\n"
            "按原顺序逐行输出；看不清的字用 [不确定] 标注；不要猜。"
        )
        outputs = []
        for index, image in enumerate(images, start=1):
            if isinstance(image, Comp.Image):
                image_ref = image.url or image.file or image.path
            else:
                image_ref = str(image or "")
            if not image_ref and isinstance(image, Comp.Image):
                image_ref = await image.convert_to_file_path()
            if not image_ref:
                continue
            response = await provider.text_chat(
                prompt=prompt,
                image_urls=[image_ref],
                session_id=uuid.uuid4().hex,
                persist=False,
            )
            text = clean_vision_text(str(response.completion_text or ""))
            if text:
                outputs.append(f"[图片{index} OCR]\n{text}")
        return "\n\n".join(outputs)

    def _get_vision_provider(self, event: AstrMessageEvent) -> Provider:
        provider_id = self._str("vision_provider_id", "").strip()
        if not provider_id:
            try:
                cfg = self.context.get_config(umo=event.unified_msg_origin)
                provider_settings = cfg.get("provider_settings", {})
                if isinstance(provider_settings, dict):
                    provider_id = str(
                        provider_settings.get("default_image_caption_provider_id")
                        or provider_settings.get("image_caption_provider_id")
                        or ""
                    ).strip()
            except Exception as exc:
                logger.warning("[muvluv_feedback] failed to read image provider config: %s", exc)
        provider = self.context.get_provider_by_id(provider_id) if provider_id else None
        if not isinstance(provider, Provider):
            raise RuntimeError(f"未找到可用图片识别模型：{provider_id or '<empty>'}")
        return provider

    def _get_review_provider_id(self, event: AstrMessageEvent) -> str:
        provider_id = self._str("review_provider_id", "deepseek/deepseek-v4-pro").strip()
        if provider_id:
            return provider_id
        provider = self.context.get_using_provider(umo=event.unified_msg_origin)
        return str(getattr(provider, "provider_config", {}).get("id") or "")

    async def _review_with_llm(
        self,
        event: AstrMessageEvent,
        raw_feedback: str,
        match: MatchResult,
    ) -> str:
        provider_id = self._get_review_provider_id(event)
        if not provider_id:
            return ""
        row = match.row
        glossary = self.index.glossary_hits(row)
        glossary_text = "\n".join(
            f"- {item.get('source')} => {item.get('target')} ({item.get('category')}) {item.get('note')}"
            for item in glossary
        ) or "无"
        context_text = self._format_row_context(row)
        prompt = (
            "你是 Muv-Luv 汉化翻译反馈判定助手。原始语义必须只基于 JP 原文和日文上下文判断，不使用英文兜底。\n"
            "你需要结合发言人性格、说话语气、人物关系、故事梗概、当前场景和前后文来判断当前 CN 是否合适。\n"
            "不要因为中文和 JP 字面不逐字对应就轻易判错；只有语义、语气、人物称谓、术语或上下文确实不合适时才建议修改。\n"
            "请输出简洁结论，格式必须包含以下四行：\n"
            "判定：需要修改/不需要修改/疑问/定位不足\n"
            "理由：...\n"
            "建议CN：如果不需要修改则写“无”\n"
            "交给：TDA00/TDA01/TDA02/TDA03/术语表/无需处理\n\n"
            f"群友反馈或截图 OCR：\n{raw_feedback}\n\n"
            f"定位：{row.key}\n"
            f"ParaTranz ID：{row.paratranz_id or '未知'}\n"
            f"发言人：{row.speaker_jp or '旁白/未知'}\n"
            f"场景：{row.scene or row.egpack}\n"
            f"JP：{row.jp_text}\n"
            f"当前CN：{row.cn_text}\n"
            f"上下文与人物资料：\n{context_text}\n"
            f"相关术语：\n{glossary_text}\n"
        )
        try:
            response = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=prompt,
                tools=None,
                contexts=[],
            )
            return clean_review_text(str(response.completion_text or ""))
        except Exception as exc:
            logger.warning("[muvluv_feedback] LLM review failed: %s", exc)
            return ""

    async def _review_many_with_llm(
        self,
        event: AstrMessageEvent,
        located: list[tuple[str, MatchResult]],
    ) -> dict[str, str]:
        provider_id = self._get_review_provider_id(event)
        if not provider_id:
            return {}

        item_blocks = []
        for index, (unit, match) in enumerate(located, start=1):
            row = match.row
            glossary = self.index.glossary_hits(row, limit=4)
            glossary_text = "; ".join(
                f"{item.get('source')}=>{item.get('target')}"
                for item in glossary
                if item.get("source") or item.get("target")
            ) or "无"
            item_blocks.append(
                "\n".join(
                    [
                        f"### ITEM {index}",
                        f"KEY：{row.key}",
                        f"ParaTranz ID：{row.paratranz_id or '未知'}",
                        f"反馈句：{unit}",
                        f"发言人：{row.speaker_jp or '旁白/未知'}",
                        f"场景：{row.scene or row.egpack}",
                        f"JP：{row.jp_text}",
                        f"当前CN：{row.cn_text}",
                        f"上下文与人物资料：{self._format_row_context(row, compact=True)}",
                        f"相关术语：{glossary_text}",
                    ]
                )
            )

        prompt = (
            "你是 Muv-Luv 汉化翻译反馈判定助手。原始语义必须只基于 JP 原文和日文上下文判断，不使用英文兜底。\n"
            "你需要结合发言人性格、说话语气、人物关系、故事梗概、当前场景和前后文来判断当前 CN 是否合适。\n"
            "下面有多条已定位台词，请逐条判定。每条必须严格按格式输出：\n"
            "### ITEM 序号\n"
            "判定：需要修改/不需要修改/疑问/定位不足\n"
            "理由：...\n"
            "建议CN：如果不需要修改则写“无”\n"
            "交给：TDA00/TDA01/TDA02/TDA03/术语表/无需处理\n\n"
            + "\n\n".join(item_blocks)
        )
        try:
            response = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=prompt,
                tools=None,
                contexts=[],
            )
            return parse_batch_reviews(
                str(response.completion_text or ""),
                [match.row.key for _, match in located],
            )
        except Exception as exc:
            logger.warning("[muvluv_feedback] batch LLM review failed: %s", exc)
            return {}

    def _find_resolution_record(self, row: TranslationRow) -> dict[str, str] | None:
        if not self.resolution_path.exists():
            return None
        try:
            with self.resolution_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                for record in reader:
                    if not resolution_record_matches(record, row):
                        continue
                    return {key: str(value or "") for key, value in record.items()}
        except Exception as exc:
            logger.warning("[muvluv_feedback] failed to read resolution table: %s", exc)
        return None

    def _format_single_result(
        self,
        match: MatchResult,
        raw_feedback: str,
        image_text: str,
        review: str,
        image_unit_count: int = 0,
        focused_by_text: bool = False,
    ) -> str:
        row = match.row
        parts = [
            "定位到了。",
            f"章节：{row.chapter}",
            f"id：{row.row_id}",
            f"ParaTranz ID：{row.paratranz_id or '未知'}",
            f"egpack：{row.egpack}",
            f"scene：{row.scene or '未知'}",
            f"speaker：{row.speaker_jp or '旁白/未知'}",
            f"CSV行：{row.csv_line}",
            "",
            f"JP：\n{clean_game_text(row.jp_text)}",
            "",
            f"当前CN：\n{clean_game_text(row.cn_text)}",
        ]
        if image_text:
            if image_unit_count:
                parts.extend(["", f"图片OCR：已识别 {image_unit_count} 条台词。"])
            else:
                parts.extend(["", "图片OCR：已识别文本。"])
            if focused_by_text:
                parts.append("本次聚焦：根据你的文字只处理这一句。")
        if review:
            parts.extend(["", review])
        parts.extend(["", "已记录到反馈队列。"])
        return "\n".join(parts)

    def _format_feedback_results(
        self,
        results: list[tuple[str, MatchResult, str]],
        image_text: str,
        missed: list[str],
        ambiguous: list[tuple[str, list[MatchResult]]],
        image_unit_count: int = 0,
        focused_by_text: bool = False,
    ) -> str:
        if len(results) == 1 and not missed and not ambiguous:
            unit, match, review = results[0]
            return self._format_single_result(
                match,
                unit,
                image_text,
                review,
                image_unit_count=image_unit_count,
                focused_by_text=focused_by_text,
            )

        lines = [
            f"识别到 {len(results)} 条可定位台词，已逐条记录到反馈队列。",
        ]
        if image_unit_count and focused_by_text:
            lines[0] = f"图片识别到 {image_unit_count} 条台词；根据你的文字聚焦到 {len(results)} 条，已记录到反馈队列。"
        for index, (unit, match, review) in enumerate(results, start=1):
            row = match.row
            lines.extend(
                [
                    "",
                    f"{index}. {row.chapter} / {row.row_id} / CSV行{row.csv_line}",
                    f"ParaTranz ID：{row.paratranz_id or '未知'}",
                    f"egpack：{row.egpack}",
                    f"scene：{row.scene or '未知'}",
                    f"speaker：{row.speaker_jp or '旁白/未知'}",
                    f"反馈句：{unit}",
                    f"JP：{clean_game_text(row.jp_text)}",
                    f"当前CN：{clean_game_text(row.cn_text)}",
                ]
            )
            if review:
                lines.append(review)

        if missed:
            lines.extend(["", f"另有 {len(missed)} 条未定位，已忽略为上下文或 OCR 噪声。"])
        if ambiguous:
            lines.extend(["", f"另有 {len(ambiguous)} 条出现多候选，需要补充上下文后再判定。"])
        return "\n".join(lines)

    def _format_candidates(self, matches: list[MatchResult], raw_feedback: str) -> str:
        lines = [
            "找到了多个同分候选，暂不判定。",
            "请补充章节、上下文或更完整台词。",
            "",
        ]
        for index, match in enumerate(matches, start=1):
            row = match.row
            lines.append(
                f"{index}. {row.chapter} {row.row_id} 行{row.csv_line}\n"
                f"ParaTranz ID：{row.paratranz_id or '未知'}\n"
                f"egpack：{row.egpack}\n"
                f"speaker：{row.speaker_jp or '旁白/未知'}\n"
                f"JP：{clean_game_text(row.jp_text)}\n"
                f"CN：{clean_game_text(row.cn_text)}"
            )
        return "\n\n".join(lines)

    def _format_row_context(self, row: TranslationRow, compact: bool = False) -> str:
        context_rows = self.index.context_window(row, before=3, after=3)
        context_lines = []
        for item in context_rows:
            marker = "=> " if item.key == row.key else "   "
            speaker = item.speaker_jp or "旁白/未知"
            context_lines.append(
                f"{marker}{item.call_order} [{speaker}] JP:{clean_game_text(item.jp_text)} CN:{clean_game_text(item.cn_text)}"
            )

        scene_info = self._lookup_scene_context(row)
        speaker_info = self._lookup_speaker_profile(row.speaker_jp)
        relationship_info = self._lookup_relationships(row.speaker_jp)
        blocks = []
        if scene_info:
            blocks.append(f"场景资料：{scene_info}")
        if speaker_info:
            blocks.append(f"人物资料：{speaker_info}")
        if relationship_info:
            blocks.append(f"人物关系：{relationship_info}")
        if context_lines:
            prefix = "前后文：" if not compact else "前后文："
            blocks.append(prefix + (" / ".join(context_lines) if compact else "\n" + "\n".join(context_lines)))
        return "\n".join(blocks) if blocks else "无"

    def _lookup_scene_context(self, row: TranslationRow) -> str:
        for record in read_csv_records(self.scene_context_path):
            if str(record.get("chapter", "")).strip() != row.chapter:
                continue
            if str(record.get("egpack", "")).strip() != row.egpack:
                continue
            start = safe_int(record.get("call_order_start", ""), 0)
            end = safe_int(record.get("call_order_end", ""), 0)
            if start and end and not (start <= row.call_order <= end):
                continue
            return compact_record(
                record,
                ["scene_label", "place", "story_summary", "mood", "context_note"],
            )
        return ""

    def _lookup_speaker_profile(self, speaker_jp: str) -> str:
        if not speaker_jp:
            return ""
        for record in read_csv_records(self.speaker_profile_path):
            if str(record.get("speaker_jp", "")).strip() == speaker_jp:
                return compact_record(
                    record,
                    ["speaker_cn", "personality", "tone", "relationship_notes", "speech_style", "translation_notes"],
                )
        return ""

    def _lookup_relationships(self, speaker_jp: str, limit: int = 4) -> str:
        if not speaker_jp:
            return ""
        hits = []
        for record in read_csv_records(self.relationship_path):
            left = str(record.get("speaker_a", "")).strip()
            right = str(record.get("speaker_b", "")).strip()
            if speaker_jp not in {left, right}:
                continue
            hits.append(compact_record(record, ["speaker_a", "speaker_b", "relationship", "chapter_scope", "notes"]))
            if len(hits) >= limit:
                break
        return "；".join(item for item in hits if item)

    def _apply_review_result(
        self,
        event: AstrMessageEvent,
        raw_feedback: str,
        image_text: str,
        match: MatchResult,
        decision: str,
        suggested_cn: str,
        reason: str,
    ) -> str:
        row = match.row
        self._mark_catalog_checked(row, qq_checked=True)
        if is_already_processed_decision(decision) or is_locate_insufficient_decision(decision):
            return ""

        if is_need_fix_decision(decision) and is_valid_suggested_cn(suggested_cn):
            updated = self._update_compare_row(
                row,
                new_cn=suggested_cn,
                review_status="FIXED_BY_FEEDBACK",
                audit_flag="QQ_FEEDBACK_FIXED",
            )
            self._append_resolution_record(
                row=row,
                status="modified",
                old_cn=row.cn_text,
                new_cn=suggested_cn,
                decision=decision,
                reason=reason,
                handoff_target=row.chapter,
                note=f"QQ反馈：{raw_feedback}",
            )
            self._append_sync_task(
                row=row,
                action="update_translation",
                old_cn=row.cn_text,
                new_cn=suggested_cn,
                decision=decision,
                reason=reason,
            )
            if updated:
                row.cn_text = suggested_cn
                row.cn_norm = normalize_text(suggested_cn)
                row.review_status = "FIXED_BY_FEEDBACK"
                row.audit_flags = append_flag(row.audit_flags, "QQ_FEEDBACK_FIXED")
                self._mark_catalog_checked(row, qq_checked=True, review_status="FIXED_BY_FEEDBACK")
                return "本地处理：已更新 compare 表；ParaTranz 修改任务已生成。"
            return "本地处理：生成了修改任务，但 compare 表写入失败，请看日志。"

        if is_question_decision(decision):
            updated = self._update_compare_row(
                row,
                review_status="QUESTION",
                audit_flag="QQ_FEEDBACK_QUESTION",
            )
            self._append_resolution_record(
                row=row,
                status="question",
                old_cn=row.cn_text,
                new_cn="",
                decision=decision,
                reason=reason,
                handoff_target=row.chapter,
                note=f"QQ反馈：{raw_feedback}",
            )
            self._append_sync_task(
                row=row,
                action="mark_question",
                old_cn=row.cn_text,
                new_cn="",
                decision=decision,
                reason=reason,
            )
            if updated:
                row.review_status = "QUESTION"
                row.audit_flags = append_flag(row.audit_flags, "QQ_FEEDBACK_QUESTION")
                self._mark_catalog_checked(row, qq_checked=True, review_status="QUESTION")
                return "本地处理：已在 compare 表标记 QUESTION；ParaTranz 疑问任务已生成。"
            return "本地处理：生成了疑问任务，但 compare 表写入失败，请看日志。"

        if is_no_change_decision(decision):
            self._append_resolution_record(
                row=row,
                status="无需处理",
                old_cn=row.cn_text,
                new_cn="",
                decision=decision,
                reason=reason,
                handoff_target="无需处理",
                note=f"QQ反馈：{raw_feedback}",
            )
            self._update_compare_row(row, audit_flag="QQ_FEEDBACK_CHECKED")
            row.audit_flags = append_flag(row.audit_flags, "QQ_FEEDBACK_CHECKED")
            self._mark_catalog_checked(row, qq_checked=True)
            return "本地处理：已记录检查结果。"

        return ""

    def _update_compare_row(
        self,
        row: TranslationRow,
        new_cn: str | None = None,
        review_status: str | None = None,
        audit_flag: str | None = None,
    ) -> bool:
        path = Path(row.source_file)
        if not path.exists():
            logger.warning("[muvluv_feedback] compare table missing: %s", path)
            return False
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = list(reader.fieldnames or [])
                records = list(reader)
            required = {"id", "egpack", "jp_text", "cn_text"}
            if not required.issubset(set(fieldnames)):
                logger.warning("[muvluv_feedback] skip non-compare CSV update: %s", path)
                return False
            for extra_field in ("review_status", "audit_flags"):
                if extra_field not in fieldnames:
                    fieldnames.append(extra_field)

            changed = False
            for record in records:
                if str(record.get("id", "")).strip() != row.row_id:
                    continue
                if str(record.get("egpack", "")).strip() != row.egpack:
                    continue
                if normalize_text(record.get("jp_text", "")) != row.jp_norm:
                    continue
                if new_cn is not None:
                    record["cn_text"] = new_cn
                if review_status:
                    record["review_status"] = review_status
                if audit_flag:
                    record["audit_flags"] = append_flag(record.get("audit_flags", ""), audit_flag)
                changed = True
                break
            if not changed:
                return False

            tmp_path = path.with_suffix(path.suffix + ".tmp")
            with tmp_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(records)
            os.replace(tmp_path, path)
            return True
        except Exception as exc:
            logger.error("[muvluv_feedback] failed to update compare row %s: %s", row.key, exc)
            return False

    def _ensure_queue_file(self) -> None:
        ensure_csv_file(self.queue_path, QUEUE_FIELDS)

    def _ensure_resolution_file(self) -> None:
        ensure_csv_file(self.resolution_path, RESOLUTION_FIELDS)

    def _ensure_catalog_file(self, refresh: bool = False) -> None:
        ensure_csv_file(self.catalog_path, CATALOG_FIELDS)
        if self.catalog_path.exists() and not refresh and count_csv_rows(self.catalog_path) > 0:
            return
        existing = {
            str(record.get("key", "")): record
            for record in read_csv_records(self.catalog_path)
            if str(record.get("key", "")).strip()
        }
        records = []
        for row in self.index.rows:
            old = existing.get(row.key, {})
            records.append(
                {
                    "chapter": row.chapter,
                    "call_order": row.call_order,
                    "id": row.row_id,
                    "egpack": row.egpack,
                    "scene": row.scene,
                    "speaker_jp": row.speaker_jp,
                    "jp_text": row.jp_text,
                    "cn_text": row.cn_text,
                    "review_status": row.review_status,
                    "audit_flags": row.audit_flags,
                    "paratranz_id": row.paratranz_id,
                    "qq_feedback_checked": old.get("qq_feedback_checked", ""),
                    "paratranz_question_checked": old.get("paratranz_question_checked", ""),
                    "last_local_update": old.get("last_local_update", ""),
                    "key": row.key,
                    "source_file": row.source_file,
                }
            )
        write_csv_records(self.catalog_path, CATALOG_FIELDS, records)

    def _ensure_sync_task_file(self) -> None:
        ensure_csv_file(self.sync_task_path, SYNC_TASK_FIELDS)

    def _ensure_speaker_profile_file(self, refresh: bool = False) -> None:
        ensure_csv_file(self.speaker_profile_path, SPEAKER_PROFILE_FIELDS)
        existing = {
            str(record.get("speaker_jp", "")): record
            for record in read_csv_records(self.speaker_profile_path)
            if str(record.get("speaker_jp", "")).strip()
        }
        speakers = sorted({row.speaker_jp for row in self.index.rows if row.speaker_jp})
        if not refresh and existing and all(speaker in existing for speaker in speakers):
            return
        records = []
        for speaker in speakers:
            old = existing.get(speaker, {})
            records.append(
                {
                    "speaker_jp": speaker,
                    "speaker_cn": old.get("speaker_cn", ""),
                    "personality": old.get("personality", ""),
                    "tone": old.get("tone", ""),
                    "relationship_notes": old.get("relationship_notes", ""),
                    "speech_style": old.get("speech_style", ""),
                    "translation_notes": old.get("translation_notes", ""),
                }
            )
        write_csv_records(self.speaker_profile_path, SPEAKER_PROFILE_FIELDS, records)

    def _ensure_scene_context_file(self, refresh: bool = False) -> None:
        ensure_csv_file(self.scene_context_path, SCENE_CONTEXT_FIELDS)
        existing = {
            (str(record.get("chapter", "")), str(record.get("egpack", ""))): record
            for record in read_csv_records(self.scene_context_path)
            if str(record.get("chapter", "")).strip() and str(record.get("egpack", "")).strip()
        }
        grouped: dict[tuple[str, str], list[TranslationRow]] = {}
        for row in self.index.rows:
            grouped.setdefault((row.chapter, row.egpack), []).append(row)
        if not refresh and existing and all(key in existing for key in grouped):
            return
        records = []
        for key, rows in sorted(grouped.items(), key=lambda item: (item[0][0], min(row.call_order for row in item[1]))):
            chapter, egpack = key
            old = existing.get(key, {})
            first = min(row.call_order for row in rows)
            last = max(row.call_order for row in rows)
            scene_label = old.get("scene_label", "") or rows[0].scene or egpack
            records.append(
                {
                    "chapter": chapter,
                    "egpack": egpack,
                    "call_order_start": old.get("call_order_start", "") or first,
                    "call_order_end": old.get("call_order_end", "") or last,
                    "scene_label": scene_label,
                    "place": old.get("place", ""),
                    "story_summary": old.get("story_summary", ""),
                    "mood": old.get("mood", ""),
                    "context_note": old.get("context_note", ""),
                }
            )
        write_csv_records(self.scene_context_path, SCENE_CONTEXT_FIELDS, records)

    def _ensure_relationship_file(self) -> None:
        ensure_csv_file(self.relationship_path, RELATIONSHIP_FIELDS)

    def _append_queue(
        self,
        event: AstrMessageEvent,
        raw_feedback: str,
        image_text: str,
        match: MatchResult | None,
        decision: str,
        suggested_cn: str,
        reason: str,
    ) -> None:
        row = match.row if match else None
        item = {
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "platform": event.get_platform_name(),
            "group_id": event.get_group_id(),
            "sender_id": event.get_sender_id(),
            "sender_name": event.get_sender_name() or "",
            "raw_feedback": raw_feedback,
            "image_ocr_text": image_text,
            "chapter": row.chapter if row else "",
            "egpack": row.egpack if row else "",
            "scene": row.scene if row else "",
            "speaker_jp": row.speaker_jp if row else "",
            "id": row.row_id if row else "",
            "key": row.key if row else "",
            "csv_line": row.csv_line if row else "",
            "call_order": row.call_order if row else "",
            "paratranz_id": row.paratranz_id if row else "",
            "jp_text": row.jp_text if row else "",
            "current_cn": row.cn_text if row else "",
            "decision": decision,
            "suggested_cn": suggested_cn,
            "reason": reason,
            "handoff_target": row.chapter if row else "",
            "status": "pending" if row else "needs_context",
        }
        try:
            with self.queue_path.open("a", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=QUEUE_FIELDS, extrasaction="ignore")
                writer.writerow(item)
        except Exception as exc:
            logger.error("[muvluv_feedback] failed to append queue: %s", exc)

    def _append_resolution_record(
        self,
        row: TranslationRow,
        status: str,
        old_cn: str,
        new_cn: str,
        decision: str,
        reason: str,
        handoff_target: str,
        note: str = "",
    ) -> None:
        ensure_csv_file(self.resolution_path, RESOLUTION_FIELDS)
        item = {
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": status,
            "key": row.key,
            "source_file": Path(row.source_file).name,
            "jp_text": row.jp_text,
            "old_cn": old_cn,
            "new_cn": new_cn,
            "decision": decision,
            "reason": reason,
            "handoff_target": handoff_target,
            "paratranz_id": row.paratranz_id,
            "note": note,
        }
        try:
            with self.resolution_path.open("a", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=RESOLUTION_FIELDS, extrasaction="ignore")
                writer.writerow(item)
        except Exception as exc:
            logger.error("[muvluv_feedback] failed to append resolution: %s", exc)

    def _append_sync_task(
        self,
        row: TranslationRow,
        action: str,
        old_cn: str,
        new_cn: str,
        decision: str,
        reason: str,
    ) -> None:
        ensure_csv_file(self.sync_task_path, SYNC_TASK_FIELDS)
        item = {
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "chapter": row.chapter,
            "id": row.row_id,
            "key": row.key,
            "egpack": row.egpack,
            "paratranz_id": row.paratranz_id,
            "jp_text": row.jp_text,
            "old_cn": old_cn,
            "new_cn": new_cn,
            "action": action,
            "decision": decision,
            "reason": reason,
            "sync_status": "pending",
            "paratranz_current_cn": "",
            "last_editor": "",
            "history_note": "",
            "synced_at": "",
        }
        try:
            with self.sync_task_path.open("a", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=SYNC_TASK_FIELDS, extrasaction="ignore")
                writer.writerow(item)
        except Exception as exc:
            logger.error("[muvluv_feedback] failed to append sync task: %s", exc)

    def _mark_catalog_checked(
        self,
        row: TranslationRow,
        qq_checked: bool = False,
        paratranz_question_checked: bool | None = None,
        review_status: str | None = None,
    ) -> None:
        ensure_csv_file(self.catalog_path, CATALOG_FIELDS)
        records = read_csv_records(self.catalog_path)
        if not records:
            return
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        changed = False
        for record in records:
            if str(record.get("key", "")).strip() != row.key:
                continue
            if qq_checked:
                record["qq_feedback_checked"] = now
            if paratranz_question_checked is not None:
                record["paratranz_question_checked"] = now if paratranz_question_checked else ""
            if review_status:
                record["review_status"] = review_status
            record["cn_text"] = row.cn_text
            record["audit_flags"] = row.audit_flags
            record["last_local_update"] = now
            changed = True
            break
        if changed:
            write_csv_records(self.catalog_path, CATALOG_FIELDS, records)

    def _str(self, key: str, default: str) -> str:
        value = self.config.get(key, default)
        return value if isinstance(value, str) else default

    def _int(self, key: str, default: int) -> int:
        try:
            return int(self.config.get(key, default))
        except (TypeError, ValueError):
            return default

    def _bool(self, key: str, default: bool) -> bool:
        value = self.config.get(key, default)
        return value if isinstance(value, bool) else default

    def _list(self, key: str, default: list[str]) -> list[str]:
        value = self.config.get(key, default)
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        return default

    def _dict_int(self, key: str, default: dict[str, int]) -> dict[str, int]:
        value = self.config.get(key, default)
        if not isinstance(value, dict):
            return default
        result: dict[str, int] = {}
        for item_key, item_value in value.items():
            try:
                result[str(item_key).upper()] = int(item_value)
            except (TypeError, ValueError):
                continue
        return result or default


QUEUE_FIELDS = [
    "created_at",
    "platform",
    "group_id",
    "sender_id",
    "sender_name",
    "raw_feedback",
    "image_ocr_text",
    "chapter",
    "egpack",
    "scene",
    "speaker_jp",
    "id",
    "key",
    "csv_line",
    "call_order",
    "paratranz_id",
    "jp_text",
    "current_cn",
    "decision",
    "suggested_cn",
    "reason",
    "handoff_target",
    "status",
]

RESOLUTION_FIELDS = [
    "updated_at",
    "status",
    "key",
    "source_file",
    "jp_text",
    "old_cn",
    "new_cn",
    "decision",
    "reason",
    "handoff_target",
    "paratranz_id",
    "note",
]

CATALOG_FIELDS = [
    "chapter",
    "call_order",
    "id",
    "egpack",
    "scene",
    "speaker_jp",
    "jp_text",
    "cn_text",
    "review_status",
    "audit_flags",
    "paratranz_id",
    "qq_feedback_checked",
    "paratranz_question_checked",
    "last_local_update",
    "key",
    "source_file",
]

SYNC_TASK_FIELDS = [
    "created_at",
    "chapter",
    "id",
    "key",
    "egpack",
    "paratranz_id",
    "jp_text",
    "old_cn",
    "new_cn",
    "action",
    "decision",
    "reason",
    "sync_status",
    "paratranz_current_cn",
    "last_editor",
    "history_note",
    "synced_at",
]

SPEAKER_PROFILE_FIELDS = [
    "speaker_jp",
    "speaker_cn",
    "personality",
    "tone",
    "relationship_notes",
    "speech_style",
    "translation_notes",
]

SCENE_CONTEXT_FIELDS = [
    "chapter",
    "egpack",
    "call_order_start",
    "call_order_end",
    "scene_label",
    "place",
    "story_summary",
    "mood",
    "context_note",
]

RELATIONSHIP_FIELDS = [
    "speaker_a",
    "speaker_b",
    "relationship",
    "chapter_scope",
    "notes",
]


def infer_chapter_from_path(path: Path) -> str:
    match = re.search(r"TDA\d{2}", path.name, flags=re.I)
    return match.group(0).upper() if match else ""


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def compute_paratranz_id(chapter: str, call_order: int, bases: dict[str, int]) -> str:
    base = bases.get(str(chapter).upper())
    if not base or call_order <= 0:
        return ""
    return str(base + call_order - 1)


def read_csv_records(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [
                {str(key): str(value or "") for key, value in record.items()}
                for record in csv.DictReader(handle)
            ]
    except Exception as exc:
        logger.warning("[muvluv_feedback] failed to read CSV %s: %s", path, exc)
        return []


def write_csv_records(path: Path, fieldnames: list[str], records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow(record)
    os.replace(tmp_path, path)


def ensure_csv_file(path: Path, fieldnames: list[str]) -> None:
    if not path.exists():
        write_csv_records(path, fieldnames, [])
        return
    records = read_csv_records(path)
    existing_fields: list[str] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            existing_fields = list(reader.fieldnames or [])
    except Exception:
        existing_fields = []
    merged_fields = list(fieldnames)
    for field in existing_fields:
        if field not in merged_fields:
            merged_fields.append(field)
    if merged_fields != existing_fields:
        write_csv_records(path, merged_fields, records)


def count_csv_rows(path: Path) -> int:
    return len(read_csv_records(path))


def append_flag(current: str, flag: str) -> str:
    parts = [item.strip() for item in re.split(r"[;；,，|]+", str(current or "")) if item.strip()]
    if flag and flag not in parts:
        parts.append(flag)
    return ";".join(parts)


def compact_record(record: dict[str, str], fields: list[str]) -> str:
    parts = []
    for field in fields:
        value = str(record.get(field, "")).strip()
        if value:
            parts.append(f"{field}={value}")
    return "；".join(parts)


def is_valid_suggested_cn(text: str) -> bool:
    value = str(text or "").strip()
    return bool(value and value not in {"无", "なし", "不需要", "无需", "-"})


def is_need_fix_decision(decision: str) -> bool:
    norm = normalize_text(decision)
    if "不需要修改" in norm or "无需修改" in norm or "无需处理" in norm:
        return False
    return "需要修改" in norm or "建议修改" in norm or "应修改" in norm


def is_no_change_decision(decision: str) -> bool:
    norm = normalize_text(decision)
    return "不需要修改" in norm or "无需修改" in norm or "无需处理" in norm


def is_question_decision(decision: str) -> bool:
    norm = normalize_text(decision)
    return "疑问" in norm or "不确定" in norm or "人工确认" in norm or "需确认" in norm


def is_locate_insufficient_decision(decision: str) -> bool:
    return "定位不足" in normalize_text(decision)


def is_already_processed_decision(decision: str) -> bool:
    norm = normalize_text(decision)
    return "已处理过" in norm or "已处理" in norm or "已修改" in norm


FOCUS_STOP_WORDS = (
    "这里是不是有问题",
    "这里好像有问题",
    "这里有问题",
    "这句是不是有问题",
    "这句好像有问题",
    "这句有问题",
    "这个是不是有问题",
    "这个好像有问题",
    "这个有问题",
    "是不是",
    "好像",
    "感觉",
    "应该",
    "是否",
    "翻译",
    "台词",
    "字幕",
    "文本",
    "问题",
    "错误",
    "错字",
    "不对",
    "不太对",
    "有误",
    "疑似",
    "改成",
    "这里",
    "这句",
    "这段",
    "这个",
    "位置",
)

FOCUS_STOP_NORMS: set[str] = set()


def strip_feedback_command(text: Any) -> str:
    value = str(text or "").strip()
    for prefix in (
        "/翻译反馈",
        "翻译反馈",
        "/反馈",
        "反馈",
        "/查翻译",
        "查翻译",
        "/定位翻译",
        "定位翻译",
        "/muvluv_feedback",
        "muvluv_feedback",
    ):
        if value.lower().startswith(prefix.lower()):
            return value[len(prefix) :].strip()
    return value


IMAGE_FILE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")


def event_has_image(event: AstrMessageEvent) -> bool:
    return bool(collect_event_image_refs(event))


def collect_event_image_refs(event: AstrMessageEvent) -> list[Any]:
    refs: list[Any] = []
    seen: set[str] = set()

    def add_ref(ref: Any) -> None:
        if not ref:
            return
        key = image_ref_key(ref)
        if key in seen:
            return
        seen.add(key)
        refs.append(ref)

    for component in walk_message_components(event.get_messages()):
        if isinstance(component, Comp.Image):
            add_ref(component)
            continue
        if is_image_file_component(component):
            ref = getattr(component, "url", None) or getattr(component, "file_", None)
            if not ref and isinstance(component, (Comp.Image, Comp.Video, Comp.Record)):
                ref = getattr(component, "file", None)
            add_ref(ref)

    raw_message = getattr(getattr(event, "message_obj", None), "raw_message", None)
    for attachment in getattr(raw_message, "attachments", None) or []:
        if not is_image_attachment(attachment):
            continue
        url = normalize_attachment_url(getattr(attachment, "url", None))
        if url:
            add_ref(url)

    return refs


def walk_message_components(components: Any):
    for component in components or []:
        yield component
        reply_chain = getattr(component, "chain", None)
        if reply_chain:
            yield from walk_message_components(reply_chain)


def image_ref_key(ref: Any) -> str:
    if isinstance(ref, Comp.Image):
        return str(ref.url or ref.file or ref.path or id(ref))
    return str(ref)


def is_image_file_component(component: Any) -> bool:
    name = str(getattr(component, "name", "") or "").lower()
    url = str(getattr(component, "url", "") or "").lower()
    file_path = str(getattr(component, "file_", "") or "").lower()
    if not file_path and isinstance(component, (Comp.Image, Comp.Video, Comp.Record)):
        file_path = str(getattr(component, "file", "") or "").lower()
    return (
        name.endswith(IMAGE_FILE_EXTS)
        or url_path_looks_like_image(url)
        or file_path.endswith(IMAGE_FILE_EXTS)
    )


def is_image_attachment(attachment: Any) -> bool:
    content_type = str(getattr(attachment, "content_type", "") or "").lower()
    filename = str(
        getattr(attachment, "filename", None)
        or getattr(attachment, "name", None)
        or ""
    ).lower()
    url = str(getattr(attachment, "url", "") or "").lower()
    if content_type.startswith("image"):
        return True
    if filename.endswith(IMAGE_FILE_EXTS) or url_path_looks_like_image(url):
        return True
    return bool(url and not content_type and not filename)


def normalize_attachment_url(url: Any) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    if text.startswith(("http://", "https://", "file://", "base64://")):
        return text
    return f"https://{text}"


def url_path_looks_like_image(url: str) -> bool:
    path = str(url or "").split("?", 1)[0].split("#", 1)[0].lower()
    return path.endswith(IMAGE_FILE_EXTS)


def is_event_addressed(event: AstrMessageEvent) -> bool:
    return bool(getattr(event, "is_at_or_wake_command", False))


def should_auto_trigger(event: AstrMessageEvent) -> bool:
    text = str(event.get_message_str() or "").strip()
    if not text:
        return False
    if text.startswith("/"):
        return False

    has_image = event_has_image(event)
    if re.search(r"\b(?:game|tda\d{2})_t\d{5}\b", text, flags=re.IGNORECASE):
        return True
    if re.search(r"TDA\d{2}\|.+?\.egpack\|[A-Za-z0-9_]+", text):
        return True

    feedback_words = (
        "翻译",
        "台词",
        "文本",
        "字幕",
        "错",
        "错误",
        "错字",
        "不对",
        "有问题",
        "问题",
        "疑似",
        "改成",
        "应该是",
        "是不是",
        "术语",
        "不统一",
        "怪",
        "别扭",
        "这里",
        "这句",
        "这段",
        "这个位置",
    )
    has_feedback_word = any(word in text for word in feedback_words)
    if has_image and has_feedback_word:
        return True

    short_image_followup = re.fullmatch(
        r"\s*(?:这个|这张|这图|这处|这边|这句|这段|这个呢|这张呢|这个也|这个也看下|还有这个|同上|再看下这个|帮看下这个)[吗嘛呢呀啊呗吧？?！!。\s]*",
        text,
    )
    if has_image and short_image_followup:
        return True

    quote_like = re.search(r"[「『“\"]([^」』”\"]{4,80})[」』”\"]", text)
    if quote_like and has_feedback_word:
        return True

    cn_run = re.search(r"[\u3400-\u9fff]{8,}", text)
    return bool(cn_run and any(word in text for word in ("翻译", "不对", "有问题", "错", "术语")))


def extract_search_fragments(text: str) -> list[str]:
    cleaned = clean_vision_text(text)
    fragments: list[str] = []

    quoted = re.findall(r"[「『“\"]([^」』”\"]{2,80})[」』”\"]", cleaned)
    fragments.extend(quoted)

    for line in re.split(r"[\r\n]+", cleaned):
        line = re.sub(r"^\s*(?:\[[^\]]+\]|【[^】]+】|（[^）]+）|\([^)]*\))\s*", "", line)
        line = re.sub(r"^(?:JP|CN|OCR|图片\d*|识别文本|群友反馈)[:：]\s*", "", line, flags=re.I)
        line = line.strip(" \t-:：，。；;")
        if len(normalize_text(line)) >= 4:
            fragments.append(line)

    cjk_runs = re.findall(r"[\u3040-\u30ff\u3400-\u9fffA-Za-z0-9ー・\w\\]{4,80}", cleaned)
    fragments.extend(cjk_runs)

    unique: list[str] = []
    seen = set()
    for fragment in sorted(fragments, key=lambda item: len(normalize_text(item)), reverse=True):
        norm = normalize_text(fragment)
        if len(norm) < 4 or norm in seen:
            continue
        seen.add(norm)
        unique.append(fragment.strip())
    return unique[:40]


def extract_feedback_units(raw_text: str, image_text: str) -> list[str]:
    image_units = extract_dialogue_units(image_text, include_plain=True)
    if image_units:
        return image_units[:20]

    text_units = extract_dialogue_units(raw_text)
    if text_units:
        return text_units[:20]

    combined = "\n".join(part for part in [raw_text, image_text] if str(part or "").strip()).strip()
    return [combined] if combined else []


def select_focused_feedback_units(raw_text: str, units: list[str]) -> list[str]:
    if len(units) <= 1:
        return units
    focus_norms = extract_focus_norms(raw_text)
    if not focus_norms:
        return units

    scored: list[tuple[int, str]] = []
    for unit in units:
        unit_norm = normalize_text(unit)
        best = 0
        for focus in focus_norms:
            if focus in unit_norm:
                best = max(best, 1000 + len(focus))
                continue
            if len(focus) >= 4 and unit_norm in focus:
                best = max(best, 900 + len(unit_norm))
                continue
            overlap = len(set(focus) & set(unit_norm))
            if len(focus) >= 3 and overlap >= min(3, len(set(focus))):
                best = max(best, overlap)
        if best:
            scored.append((best, unit))

    if not scored:
        return units

    scored.sort(key=lambda item: item[0], reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return units
    if scored[0][0] < 3:
        return units
    return [scored[0][1]]


def select_focused_units_by_rows(
    raw_text: str,
    units: list[str],
    context_matches: dict[str, MatchResult],
) -> list[str]:
    if len(units) <= 1:
        return units
    focus_norms = extract_focus_norms(raw_text)
    if not focus_norms:
        return units

    scored: list[tuple[int, str]] = []
    for unit in units:
        match = context_matches.get(unit)
        row = match.row if match else None
        haystacks = [normalize_text(unit)]
        if row:
            haystacks.extend([row.cn_norm, row.jp_norm, normalize_text(clean_game_text(row.cn_text))])

        best = 0
        for focus in focus_norms:
            if len(focus) < 2:
                continue
            for haystack in haystacks:
                if not haystack:
                    continue
                if focus in haystack:
                    best = max(best, 2000 + len(focus))
                    continue
                if len(focus) >= 4 and haystack in focus:
                    best = max(best, 1500 + len(haystack))
                    continue
                overlap = len(set(focus) & set(haystack))
                if len(focus) >= 3 and overlap >= min(3, len(set(focus))):
                    best = max(best, overlap)
        if best:
            scored.append((best, unit))

    if not scored:
        return select_focused_feedback_units(raw_text, units)

    scored.sort(key=lambda item: item[0], reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return units
    if scored[0][0] < 3:
        return units
    return [scored[0][1]]


def extract_focus_norms(raw_text: str) -> list[str]:
    text = strip_feedback_command(raw_text)
    text = re.sub(r"@\S+", " ", text)
    quoted = re.findall(r"[「『“\"]([^」』”\"]{2,120})[」』”\"]", text)

    cleaned = text
    for word in FOCUS_STOP_WORDS:
        cleaned = cleaned.replace(word, " ")
    cleaned = re.sub(
        r"(对吗|對嗎|对不对|對不對|是不是|是否|吗|嘛|呢|啊|吧|呀|么|嗎|嘛|呢|啊|吧|呀|麼)+",
        " ",
        cleaned,
    )
    cleaned = re.sub(r"[，。！？!?、:：;；（）()\[\]【】「」『』“”\"'\s]+", " ", cleaned)
    runs = re.findall(r"[\u3040-\u30ff\u3400-\u9fffA-Za-z0-9ー\\w]{2,80}", cleaned)

    norms: list[str] = []
    seen = set()
    for fragment in quoted + runs:
        norm = normalize_text(fragment)
        if len(norm) < 2 or norm in seen:
            continue
        if norm in FOCUS_STOP_NORMS:
            continue
        seen.add(norm)
        norms.append(norm)
    return sorted(norms, key=len, reverse=True)


def extract_dialogue_units(text: str, include_plain: bool = False) -> list[str]:
    cleaned = clean_vision_text(text)
    if not cleaned:
        return []

    units: list[str] = []
    for line in re.split(r"[\r\n]+", cleaned):
        line = re.sub(r"^\s*\[图片\d+\s*OCR\]\s*$", "", line, flags=re.I).strip()
        if not line:
            continue
        if "「" in line or "『" in line or "“" in line or '"' in line:
            found = False
            for item in re.findall(
                r"(?:[【\[][^\]】]{1,30}[】\]]\s*)?[「『“\"]([^」』”\"]{2,180})[」』”\"]",
                line,
            ):
                speaker = ""
                speaker_match = re.search(r"([【\[][^\]】]{1,30}[】\]])", line)
                if speaker_match:
                    speaker = speaker_match.group(1)
                units.append(f"{speaker}「{item.strip()}」".strip())
                found = True
            if not found:
                units.append(line)
        elif include_plain and looks_like_ocr_dialogue_line(line):
            units.append(line)

    if not units:
        for item in re.findall(
            r"(?:[【\[][^\]】]{1,30}[】\]]\s*)?[「『“\"]([^」』”\"]{2,180})[」』”\"]",
            cleaned,
        ):
            units.append(f"「{item.strip()}」")

    unique: list[str] = []
    seen = set()
    for unit in units:
        unit = re.sub(r"^(?:Image\s*\d+|OCR|图片\d*)[:：]\s*", "", unit, flags=re.I).strip()
        norm = normalize_text(unit)
        min_len = 2 if include_plain else 4
        if len(norm) < min_len or norm in seen:
            continue
        seen.add(norm)
        unique.append(unit)
    return unique


def looks_like_ocr_dialogue_line(line: str) -> bool:
    value = re.sub(r"^(?:Image\s*\d+|OCR|图片\d*)[:：]\s*", "", str(line or ""), flags=re.I)
    value = value.strip(" \t-:：")
    norm = normalize_text(value)
    if len(norm) < 2:
        return False
    if len(norm) <= 40 and re.search(r"[\u3040-\u30ff\u3400-\u9fff]", value):
        return True
    return False


def extract_short_search_norms(text: str) -> list[str]:
    cleaned = clean_vision_text(text)
    fragments = re.findall(r"[「『“\"]([^」』”\"]{1,80})[」』”\"]", cleaned)
    fragments.append(cleaned)

    norms: list[str] = []
    seen = set()
    for fragment in fragments:
        norm = normalize_text(fragment)
        if len(norm) < 2 or norm in seen:
            continue
        seen.add(norm)
        norms.append(norm)
    return sorted(norms, key=len)


def normalize_text(text: str) -> str:
    text = str(text or "")
    text = text.replace("\\w", "")
    text = re.sub(r"[「」『』“”\"'’‘【】\[\]（）()〈〉《》]", "", text)
    text = re.sub(r"[\s　,，.。!！?？:：;；、~～…—\-・/／\\]+", "", text)
    return text.lower()


def clean_game_text(text: str) -> str:
    return str(text or "").replace("\\w", "")


def clean_vision_text(text: str) -> str:
    text = str(text or "").strip()
    text = re.sub(r"```(?:text|markdown|json)?", "", text, flags=re.I)
    text = text.replace("```", "")
    return text.strip()


def clean_review_text(text: str) -> str:
    text = clean_vision_text(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def parse_batch_reviews(text: str, keys: list[str]) -> dict[str, str]:
    text = clean_review_text(text)
    if not text:
        return {}
    blocks = re.split(r"(?=^###\s*ITEM\s*\d+)", text, flags=re.M | re.I)
    reviews: dict[str, str] = {}
    for block in blocks:
        match = re.search(r"^###\s*ITEM\s*(\d+)", block, flags=re.M | re.I)
        if not match:
            continue
        index = int(match.group(1)) - 1
        if index < 0 or index >= len(keys):
            continue
        reviews[keys[index]] = clean_review_text(block)
    return reviews


def parse_review_fields(review: str) -> tuple[str, str, str]:
    decision = ""
    suggested_cn = ""
    reason = ""
    for line in (review or "").splitlines():
        if line.startswith("判定：") or line.startswith("判定:"):
            decision = line.split(":", 1)[-1] if ":" in line else line.split("：", 1)[-1]
        elif line.startswith("建议CN：") or line.startswith("建议CN:"):
            suggested_cn = line.split(":", 1)[-1] if ":" in line else line.split("：", 1)[-1]
        elif line.startswith("理由：") or line.startswith("理由:"):
            reason = line.split(":", 1)[-1] if ":" in line else line.split("：", 1)[-1]
    return decision.strip() or "已定位", suggested_cn.strip(), reason.strip()


def resolution_record_matches(record: dict[str, str], row: TranslationRow) -> bool:
    if str(record.get("key", "")).strip() != row.key:
        return False

    source_file = str(record.get("source_file", "")).strip()
    if source_file:
        if Path(source_file).name.lower() != Path(row.source_file).name.lower():
            return False

    jp_text = str(record.get("jp_text", "")).strip()
    if jp_text and normalize_text(jp_text) != row.jp_norm:
        return False

    old_cn = normalize_text(record.get("old_cn", ""))
    new_cn = normalize_text(record.get("new_cn", ""))
    current_cn = row.cn_norm
    cn_candidates = [value for value in (old_cn, new_cn) if value]
    if cn_candidates and current_cn not in cn_candidates:
        return False

    status = str(record.get("status", "")).strip().lower()
    if status and status not in {
        "done",
        "applied",
        "modified",
        "resolved",
        "已处理",
        "已修改",
        "已应用",
        "无需处理",
        "question",
        "疑问",
        "待确认",
        "需确认",
    }:
        return False
    return True


def format_resolution_review(record: dict[str, str]) -> str:
    new_cn = str(record.get("new_cn", "")).strip() or "无"
    reason = str(record.get("reason", "")).strip() or "反馈记录表已有对应处理记录。"
    handoff = str(record.get("handoff_target", "")).strip() or "无需处理"
    status = str(record.get("status", "")).strip().lower()
    decision = "疑问" if status in {"question", "疑问", "待确认", "需确认"} else "已处理过"
    note = str(record.get("note", "")).strip()
    paratranz_id = str(record.get("paratranz_id", "")).strip()
    extra = []
    if paratranz_id:
        extra.append(f"ParaTranz：{paratranz_id}")
    if note:
        extra.append(f"备注：{note}")
    suffix = "\n" + "\n".join(extra) if extra else ""
    return (
        f"判定：{decision}\n"
        f"理由：{reason}\n"
        f"建议CN：{new_cn}\n"
        f"交给：{handoff}"
        f"{suffix}"
    )
