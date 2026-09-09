"""Create a local categorized HTML review and optional streamed PNG atlas.

Inputs are a portable catalog and an explicit PRIVATE hash-to-path asset map.
Outputs contain derived game images and are local review artifacts, not Git or
release payloads. No game discovery, edits, installation or network access.
"""
from __future__ import annotations

import argparse
import binascii
import hashlib
import html
from io import BytesIO
import json
import math
from pathlib import Path
import struct
import zlib

from PIL import Image, ImageDraw, ImageFont
from rUGP.tools.provenance.export_static_review import SCHEMA, SHA, catalog_counts

BG = (25, 31, 41)
PANEL, GAP, CARD_W, CARD_H = 320, 8, 992, 324


class StreamPNG:
    """Bound memory to one horizontal card strip, independent of atlas height."""
    def __init__(self, path: Path, width: int, height: int):
        self.file = path.open("xb")
        self.file.write(b"\x89PNG\r\n\x1a\n")
        self.chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        self.compressor = zlib.compressobj(4)
        self.width, self.height, self.rows = width, height, 0

    def chunk(self, kind: bytes, data: bytes) -> None:
        self.file.write(struct.pack(">I", len(data)) + kind + data +
                        struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF))

    def append(self, image: Image.Image) -> None:
        if image.mode != "RGB" or image.width != self.width:
            raise ValueError("Atlas strip geometry mismatch")
        raw, stride = image.tobytes(), image.width * 3
        for y in range(image.height):
            data = self.compressor.compress(b"\0" + raw[y * stride:(y + 1) * stride])
            if data:
                self.chunk(b"IDAT", data)
        self.rows += image.height

    def close(self) -> None:
        try:
            if self.rows != self.height:
                raise ValueError("Incomplete atlas")
            self.chunk(b"IDAT", self.compressor.flush())
            self.chunk(b"IEND", b"")
        finally:
            self.file.close()


def panels(row: dict) -> list[tuple[str, dict | None]]:
    official = row["official"]
    if row["shared_native"]:
        native = [("官方日文／英文共用", official["jp"]), ("与左侧共用", None)]
    else:
        native = [("官方日文", official["jp"])] if "jp" in official else [("官图 · 语言待核", official["unknown"])] if "unknown" in official else [("官方日文 · 无已确认对应", None)]
        native.append(("官方英文", official["en"]) if "en" in official else ("官方英文 · 无已确认对应", None))
    if "jp" in official and "unknown" in official:
        native.append(("官图 · 语言待核", official["unknown"]))
    return native + [("汉化 · 当前审核稿", row["candidate"])]


def authenticated_image(path: Path, digest: str) -> Image.Image:
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest().upper() != digest:
        raise ValueError("Asset hash mismatch")
    with Image.open(BytesIO(data)) as source:
        return source.convert("RGBA")


def validate(catalog: dict, assets: dict, map_root: Path) -> dict[str, Path]:
    if catalog.get("schema") != SCHEMA:
        raise ValueError("Unsupported review catalog schema")
    categories = catalog["categories"]
    if not categories or len(categories) != len(set(categories)):
        raise ValueError("Invalid categories")
    if catalog.get("counts") != catalog_counts(catalog["rows"]):
        raise ValueError("Catalog counts mismatch; possible omitted or stale rows")
    paths, sizes, seen = {}, {}, set()
    for row in catalog["rows"]:
        gid = row["id"]
        if type(gid) is not int or gid <= 0 or gid in seen or row["category"] not in categories:
            raise ValueError("Invalid group identity or category")
        seen.add(gid)
        if type(row["placeholder"]) is not bool or type(row["shared_native"]) is not bool:
            raise ValueError("Invalid catalog state flag")
        if row["placeholder"]:
            if row["candidate"] is not None or row["official"]:
                raise ValueError("Status-only rows must not contain images")
            continue
        if not row["candidate"] or not row["official"] or set(row["official"]) - {"jp", "en", "unknown"}:
            raise ValueError("Invalid image or language selection")
        if row["shared_native"] and not {"jp", "en"} <= set(row["official"]):
            raise ValueError("Shared row requires both language identities")
        for item in [*row["official"].values(), row["candidate"]]:
            digest, size = item["sha256"], item["size"]
            if not SHA.fullmatch(digest) or len(size) != 2 or any(type(n) is not int or n <= 0 for n in size):
                raise ValueError("Invalid image identity")
            if digest in sizes and sizes[digest] != size:
                raise ValueError("One hash has conflicting dimensions")
            sizes[digest] = size
            if digest in paths:
                continue
            path = Path(assets[digest])
            path = (map_root / path).resolve() if not path.is_absolute() else path.resolve()
            with authenticated_image(path, digest) as image:
                if list(image.size) != size:
                    raise ValueError("Asset dimensions mismatch")
            paths[digest] = path
        if row["shared_native"]:
            jp, en = row["official"]["jp"]["sha256"], row["official"]["en"]["sha256"]
            with authenticated_image(paths[jp], jp) as a, authenticated_image(paths[en], en) as b:
                if a.size != b.size or a.convert("RGBA").tobytes() != b.convert("RGBA").tobytes():
                    raise ValueError("Claimed shared language images differ")
    return paths


def short(draw: ImageDraw.ImageDraw, value: str, font: ImageFont.FreeTypeFont, width: int) -> str:
    value = " ".join(value.split())
    if draw.textlength(value, font=font) <= width:
        return value
    while value and draw.textlength(value + "…", font=font) > width:
        value = value[:-1]
    return value + "…"


def card(row: dict, paths: dict[str, Path], fonts: dict[int, ImageFont.FreeTypeFont]) -> Image.Image:
    result = Image.new("RGB", (CARD_W, CARD_H), BG)
    draw = ImageDraw.Draw(result)
    draw.rounded_rectangle((3, 3, CARD_W - 4, CARD_H - 4), radius=10, fill=(38, 46, 59))
    for y, value, size in [(7, f"G{row['id']} {row['title']}", 22),
                            (36, row["collection"] + " / " + row["section"], 16),
                            (295, row["status"], 18)]:
        draw.text((12, y), short(draw, value, fonts[size], CARD_W - 28), font=fonts[size], fill=(226, 236, 246))
    if row["placeholder"]:
        draw.text((24, 150), "人工完成登记 · 仅列状态", font=fonts[34], fill=(160, 210, 190))
        return result
    views = panels(row)
    panel_width = (CARD_W - GAP * (len(views) + 1)) // len(views)
    sizes = [item["size"] for _, item in views if item]
    scale = min(panel_width / max(s[0] for s in sizes), 200 / max(s[1] for s in sizes), 2)
    for column, (label, item) in enumerate(views):
        x = GAP + column * (panel_width + GAP)
        draw.text((x + 3, 61), short(draw, label, fonts[18], panel_width - 6), font=fonts[18], fill=(130, 215, 210))
        draw.rectangle((x, 87, x + panel_width - 1, 286), fill=(71, 78, 88))
        if item:
            with authenticated_image(paths[item["sha256"]], item["sha256"]) as source:
                tile = source.convert("RGBA")
                tile = tile.resize((max(1, round(tile.width * scale)), max(1, round(tile.height * scale))), Image.Resampling.LANCZOS)
                result.paste(tile, (x + (panel_width - tile.width) // 2, 87 + (200 - tile.height) // 2), tile)
    return result


def build(catalog: dict, assets: dict, map_root: Path, output: Path, font: Path,
          atlas: bool = False, columns: int = 10) -> dict:
    if not 1 <= columns <= 10:
        raise ValueError("Columns must be between 1 and 10")
    if output.exists():
        raise ValueError("Output already exists")
    paths = validate(catalog, assets, map_root)
    fonts = {size: ImageFont.truetype(str(font), size) for size in [16, 18, 22, 34, 42]}
    output.mkdir(parents=True)
    (output / "cards").mkdir()
    groups = [(c, [r for r in catalog["rows"] if r["category"] == c]) for c in catalog["categories"]]
    height = 180 + sum(80 + CARD_H * math.ceil(len(rows) / columns) for _, rows in groups)
    png = StreamPNG(output / "atlas.png", CARD_W * columns, height) if atlas else None
    escaped, sections, y, locations = html.escape, [], 180, []
    if png:
        head = Image.new("RGB", (CARD_W * columns, 180), BG)
        d = ImageDraw.Draw(head)
        d.text((20, 25), "PF / PM 素材全量审核", font=fonts[42], fill="white")
        d.text((20, 95), f"{len(catalog['rows'])} 项 · 日文 / 英文 / 汉化 · 状态与实机验证分别记录", font=fonts[22], fill="white")
        png.append(head)
    try:
        for category_index, (category, rows) in enumerate(groups):
            sections.append(f'<section><h2>{escaped(category)} · {len(rows)}</h2>')
            if png:
                band = Image.new("RGB", (CARD_W * columns, 80), (29, 72, 91))
                ImageDraw.Draw(band).text((20, 18), category, font=fonts[34], fill="white")
                png.append(band)
            y += 80
            for start in range(0, len(rows), columns):
                strip = Image.new("RGB", (CARD_W * columns, CARD_H), BG) if png else None
                for column, row in enumerate(rows[start:start + columns]):
                    image = card(row, paths, fonts)
                    filename = f"cards/G{row['id']}.png"
                    image.save(output / filename)
                    if png:
                        strip.paste(image, (column * CARD_W, 0))
                        locations.append(dict(id=row["id"], x=column * CARD_W, y=y))
                    search = escaped(f"G{row['id']} {row['title']} {row['collection']} {row['section']} {row['status']}", quote=True)
                    sections.append(f'<article data-category="{category_index}" data-search="{search}"><a href="{filename}"><img loading="lazy" src="{filename}" alt="{search}"></a></article>')
                if png:
                    png.append(strip)
                y += CARD_H
            sections.append("</section>")
        if png:
            png.close()
    except BaseException:
        if png and not png.file.closed:
            png.file.close()
        raise
    options = ''.join(f'<option value="{i}">{escaped(c)}</option>' for i, c in enumerate(catalog["categories"]))
    document = '''<!doctype html><html lang="zh-Hans"><meta charset="utf-8"><title>PF / PM 素材审核</title>
<style>body{background:#191f29;color:#e7edf6;font:16px system-ui;margin:24px}header{position:sticky;top:0;background:#191f29;padding:12px}input,select{font:inherit;padding:8px}article{display:inline-block;width:min(100%,992px);vertical-align:top}img{width:100%}a{color:#80daca}[hidden]{display:none!important}</style>
<header><h1>PF / PM 素材审核</h1><p>官方日文 / 官方英文 / 汉化。缺少已确认配对不等于不存在另一语言；登记、安装及实机验收分别记录。</p>
<label>分类 <select id="category"><option value="">全部</option>''' + options + '''</select></label>
<label>搜索 <input id="query" placeholder="编号、用途、分组或状态"></label><span id="count"></span></header>''' + ''.join(sections) + '''
<script>const category=document.querySelector('#category'),query=document.querySelector('#query');function filter(){let n=0;for(const a of document.querySelectorAll('article')){a.hidden=!!((category.value&&a.dataset.category!==category.value)||!a.dataset.search.toLowerCase().includes(query.value.toLowerCase()));if(!a.hidden)n++}for(const s of document.querySelectorAll('section'))s.hidden=![...s.querySelectorAll('article')].some(a=>!a.hidden);document.querySelector('#count').textContent=` ${n} 项`}category.onchange=query.oninput=filter;filter();</script></html>'''
    (output / "index.html").write_text(document, "utf-8")
    report = dict(schema="photon-static-review-build-v1", entries=len(catalog["rows"]),
                  image_identities_verified=len(paths), atlas=atlas,
                  font_sha256=hashlib.sha256(font.read_bytes()).hexdigest().upper(),
                  game_started=False, game_files_modified=False)
    if png:
        report["atlas_geometry"] = [CARD_W * columns, height]
        report["locations"] = locations
        with (output / "atlas.png").open("rb") as stream:
            report["atlas_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest().upper()
    (output / "verification.json").write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--asset-map", required=True, type=Path, help="Private digest-to-local-path JSON")
    parser.add_argument("--font", required=True, type=Path, help="Local font supporting the catalog language")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--atlas", action="store_true")
    parser.add_argument("--columns", type=int, default=10)
    args = parser.parse_args()
    report = build(json.loads(args.catalog.read_text("utf-8")), json.loads(args.asset_map.read_text("utf-8")),
                   args.asset_map.resolve().parent, args.output, args.font, args.atlas, args.columns)
    print(json.dumps({k: v for k, v in report.items() if k != "locations"}))


if __name__ == "__main__":
    main()
