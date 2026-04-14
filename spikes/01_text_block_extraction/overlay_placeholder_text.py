from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PLACEHOLDER_SENTENCES = [
    "AIA at a glance",
    "The only international life insurer headquartered and listed in Hong Kong, fully focused on Asia.",
    "Serving more than 38 million individual policies and over 16 million group insurance members.",
    "Business coverage across 18 markets.",
    "Delivering healthier, longer, better lives.",
    "Over US$16 billion paid in benefits and claims.",
    "Nearly US$2 trillion of protection across Asia.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Overlay placeholder English text into extracted PDF text blocks."
    )
    parser.add_argument("--blocks-jsonl", type=Path, required=True)
    parser.add_argument("--masked-pages-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--pages",
        type=str,
        required=True,
        help="Page selection such as '3' or '1,3,8'. Uses 1-based page numbers.",
    )
    parser.add_argument("--render-dpi", type=int, default=96)
    parser.add_argument("--font-path", type=Path)
    return parser.parse_args()


def parse_page_numbers(selection: str) -> set[int]:
    page_numbers: set[int] = set()
    for part in selection.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if start > end:
                start, end = end, start
            page_numbers.update(range(start, end + 1))
        else:
            page_numbers.add(int(token))
    return page_numbers


def load_page_records(blocks_jsonl: Path, page_numbers: set[int]) -> dict[int, dict]:
    records: dict[int, dict] = {}
    with blocks_jsonl.open("r", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record["page_no"] in page_numbers:
                records[record["page_no"]] = record
    return records


def load_font(font_path: Path | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if font_path and font_path.exists():
        return ImageFont.truetype(str(font_path), size=size)
    for candidate in [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/msyh.ttc",
    ]:
        candidate_path = Path(candidate)
        if candidate_path.exists():
            return ImageFont.truetype(str(candidate_path), size=size)
    return ImageFont.load_default()


def pdf_bbox_to_image_bbox(
    bbox: list[float], scale: float, image_width: int, image_height: int
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = bbox
    left = max(0, int(round(x0 * scale)))
    top = max(0, int(round(y0 * scale)))
    right = min(image_width, int(round(x1 * scale)))
    bottom = min(image_height, int(round(y1 * scale)))
    return left, top, right, bottom


def fit_font_size(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: Path | None,
    rect: tuple[int, int, int, int],
    max_size: int,
    min_size: int = 7,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], str]:
    left, top, right, bottom = rect
    width = max(1, right - left)
    height = max(1, bottom - top)

    for size in range(max_size, min_size - 1, -1):
        font = load_font(font_path, size)
        avg_char_width = max(1, draw.textlength("abcdefghijklmnopqrstuvwxyz", font=font) / 26)
        wrap_width = max(1, int(width / avg_char_width))
        lines = textwrap.wrap(text, width=wrap_width) or [text]
        line_height = int(size * 1.2)
        if len(lines) * line_height <= height:
            return font, lines, "ok" if size == max_size else "font_shrink"

    font = load_font(font_path, min_size)
    avg_char_width = max(1, draw.textlength("abcdefghijklmnopqrstuvwxyz", font=font) / 26)
    wrap_width = max(1, int(width / avg_char_width))
    lines = textwrap.wrap(text, width=wrap_width) or [text]
    return font, lines, "overflow"


def draw_block_text(
    image: Image.Image,
    block: dict,
    placeholder_text: str,
    font_path: Path | None,
    render_dpi: int,
) -> str:
    scale = render_dpi / 72
    rect = pdf_bbox_to_image_bbox(block["bbox"], scale, image.width, image.height)
    left, top, right, bottom = rect
    if right <= left or bottom <= top:
        return "invalid_bbox"

    draw = ImageDraw.Draw(image)
    max_size = max(8, int(round((block.get("font_size_avg") or 10) * scale)))
    font, lines, status = fit_font_size(
        draw=draw,
        text=placeholder_text,
        font_path=font_path,
        rect=rect,
        max_size=max_size,
    )

    line_height = max(10, int(getattr(font, "size", max_size) * 1.2))
    y = top
    for line in lines:
        if y + line_height > bottom:
            status = "overflow"
            break
        draw.text((left, y), line, fill=(35, 35, 35), font=font)
        y += line_height
    return status


def main() -> None:
    args = parse_args()
    page_numbers = parse_page_numbers(args.pages)
    page_records = load_page_records(args.blocks_jsonl, page_numbers)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    report: list[dict] = []
    for page_no in sorted(page_numbers):
        record = page_records.get(page_no)
        if not record:
            continue
        masked_page_path = args.masked_pages_dir / f"page_{page_no:04d}.png"
        image = Image.open(masked_page_path).convert("RGB")

        for index, block in enumerate(record["blocks"]):
            placeholder_text = PLACEHOLDER_SENTENCES[index % len(PLACEHOLDER_SENTENCES)]
            fit_status = draw_block_text(
                image=image,
                block=block,
                placeholder_text=placeholder_text,
                font_path=args.font_path,
                render_dpi=args.render_dpi,
            )
            report.append(
                {
                    "page_no": page_no,
                    "block_id": block["block_id"],
                    "placeholder_text": placeholder_text,
                    "fit_status": fit_status,
                }
            )

        output_path = args.output_dir / f"page_{page_no:04d}_placeholder_overlay.png"
        image.save(output_path, format="PNG")
        print(output_path)

    report_path = args.output_dir / "placeholder_overlay_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
