#!/usr/bin/env python3
"""Create paged JP/CN side-by-side QA sheets for Imperial event cards."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path, PurePosixPath

from PIL import Image, ImageDraw, ImageFont


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def create_sheets(
    manifest: Path,
    jp_root: Path,
    cn_root: Path,
    font_path: Path,
    output: Path,
) -> list[Path]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite comparison directory: {output}")
    output.mkdir(parents=True)

    rows = read_rows(manifest)
    if len(rows) != 61:
        raise ValueError(f"expected 61 event cards, got {len(rows)}")

    title_font = ImageFont.truetype(str(font_path), 22)
    tag_font = ImageFont.truetype(str(font_path), 18)
    thumb_size = (640, 360)
    pair_width = 1280
    item_height = 430
    per_page = 16
    columns = 2
    pages: list[Path] = []

    for page_number, start in enumerate(range(0, len(rows), per_page), 1):
        chunk = rows[start : start + per_page]
        grid_rows = math.ceil(len(chunk) / columns)
        sheet = Image.new(
            "RGB",
            (pair_width * columns, item_height * grid_rows),
            (32, 36, 43),
        )
        draw = ImageDraw.Draw(sheet)

        for local_index, row in enumerate(chunk):
            index = start + local_index + 1
            grid_y, grid_x = divmod(local_index, columns)
            origin_x = grid_x * pair_width
            origin_y = grid_y * item_height
            relative = Path(*PurePosixPath(row["source_relative"]).parts)

            with Image.open(jp_root / relative) as source:
                jp_image = source.convert("RGB").resize(
                    thumb_size, Image.Resampling.LANCZOS
                )
            with Image.open(cn_root / relative) as source:
                cn_image = source.convert("RGB").resize(
                    thumb_size, Image.Resampling.LANCZOS
                )

            draw.rectangle(
                (
                    origin_x,
                    origin_y,
                    origin_x + pair_width - 1,
                    origin_y + item_height - 1,
                ),
                outline=(92, 100, 112),
                width=2,
            )
            title = f"{index:02d}  {row['kind']}  {row['zh_cn'].replace('|', ' / ')}"
            draw.text(
                (origin_x + 12, origin_y + 7),
                title,
                font=title_font,
                fill="white",
            )
            draw.text(
                (origin_x + 12, origin_y + 36),
                "JP 原图",
                font=tag_font,
                fill=(255, 190, 80),
            )
            draw.text(
                (origin_x + 652, origin_y + 36),
                "CN 补丁",
                font=tag_font,
                fill=(80, 210, 255),
            )
            sheet.paste(jp_image, (origin_x, origin_y + 68))
            sheet.paste(cn_image, (origin_x + 640, origin_y + 68))
            draw.line(
                (
                    origin_x + 640,
                    origin_y + 62,
                    origin_x + 640,
                    origin_y + 428,
                ),
                fill="white",
                width=2,
            )

        page = output / f"location-date-comparison-{page_number:02d}.png"
        sheet.save(page, optimize=True)
        pages.append(page)

    with (output / "comparison-index.tsv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow(
            ("index", "kind", "source_relative", "jp_text", "zh_cn", "page")
        )
        for index, row in enumerate(rows, 1):
            writer.writerow(
                (
                    index,
                    row["kind"],
                    row["source_relative"],
                    row["jp_text"],
                    row["zh_cn"],
                    f"location-date-comparison-{(index - 1) // per_page + 1:02d}.png",
                )
            )
    return pages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--jp-root", required=True, type=Path)
    parser.add_argument("--cn-root", required=True, type=Path)
    parser.add_argument("--font", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    pages = create_sheets(
        args.manifest, args.jp_root, args.cn_root, args.font, args.output
    )
    print(f"cards=61 pages={len(pages)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
