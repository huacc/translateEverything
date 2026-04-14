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
        description="Overlay placeholder English text on restored page backgrounds."
    )
    parser.add_argument("--blocks-jsonl", type=Path, required=True)
    parser.add_argument("--background-dir", type=Path, required=True)
    parser.add_argument(
        "--background-suffix",
        default="",
        help="Suffix after page number, e.g. '_image_only' for page_0003_image_only.png.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pages", type=str, required=True)
    parser.add_argument("--render-dpi", type=int, default=96)
    parser.add_argument("--font-path", type=Path)
    parser.add_argument(
        "--fill",
        default="255,255,255",
        help="Text RGB fill, e.g. '255,255,255' or '35,35,35'.",
    )
    return parser.parse_args()


def parse_page_numbers(selection: str) -> set[int]:
    selected: set[int] = set()
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
            selected.update(range(start, end + 1))
        else:
            selected.add(int(token))
    return selected


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


def fit_text(
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


def parse_fill(fill: str) -> tuple[int, int, int]:
    parts = [int(part.strip()) for part in fill.split(",")]
    if len(parts) != 3:
        raise ValueError("--fill must have three comma-separated integers")
    return parts[0], parts[1], parts[2]


def main() -> None:
    args = parse_args()
    page_numbers = parse_page_numbers(args.pages)
    records = load_page_records(args.blocks_jsonl, page_numbers)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fill = parse_fill(args.fill)
    scale = args.render_dpi / 72
    report: list[dict] = []

    for page_no in sorted(page_numbers):
        record = records[page_no]
        background_path = args.background_dir / f"page_{page_no:04d}{args.background_suffix}.png"
        image = Image.open(background_path).convert("RGB")
        draw = ImageDraw.Draw(image)
        for index, block in enumerate(record["blocks"]):
            text = PLACEHOLDER_SENTENCES[index % len(PLACEHOLDER_SENTENCES)]
            rect = pdf_bbox_to_image_bbox(block["bbox"], scale, image.width, image.height)
            max_size = max(8, int(round((block.get("font_size_avg") or 10) * scale)))
            font, lines, status = fit_text(draw, text, args.font_path, rect, max_size)
            left, top, right, bottom = rect
            line_height = max(10, int(getattr(font, "size", max_size) * 1.2))
            y = top
            for line in lines:
                if y + line_height > bottom:
                    status = "overflow"
                    break
                draw.text((left, y), line, fill=fill, font=font)
                y += line_height
            report.append(
                {
                    "page_no": page_no,
                    "block_id": block["block_id"],
                    "fit_status": status,
                    "background": str(background_path),
                }
            )
        output_path = args.output_dir / f"page_{page_no:04d}_placeholder_overlay.png"
        image.save(output_path, format="PNG")
        print(output_path)

    report_path = args.output_dir / "placeholder_overlay_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
