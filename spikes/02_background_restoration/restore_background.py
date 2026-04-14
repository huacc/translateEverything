from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import cv2
import fitz
import numpy as np
from PIL import Image, ImageDraw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Try background restoration strategies for PDF pages."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--blocks-jsonl", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--pages",
        type=str,
        required=True,
        help="Page selection such as '3' or '3,294'. Uses 1-based page numbers.",
    )
    parser.add_argument("--render-dpi", type=int, default=96)
    parser.add_argument("--mask-padding-px", type=int, default=3)
    parser.add_argument("--inpaint-radius", type=int, default=5)
    return parser.parse_args()


def parse_page_numbers(selection: str) -> list[int]:
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
    return sorted(selected)


def load_page_records(blocks_jsonl: Path, page_numbers: set[int]) -> dict[int, dict]:
    records: dict[int, dict] = {}
    with blocks_jsonl.open("r", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record["page_no"] in page_numbers:
                records[record["page_no"]] = record
    return records


def render_page(page: fitz.Page, render_dpi: int) -> Image.Image:
    zoom = render_dpi / 72
    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)


def pdf_bbox_to_image_bbox(
    bbox: list[float],
    scale: float,
    image_width: int,
    image_height: int,
    padding_px: int = 0,
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = bbox
    left = max(0, int(round(x0 * scale)) - padding_px)
    top = max(0, int(round(y0 * scale)) - padding_px)
    right = min(image_width, int(round(x1 * scale)) + padding_px)
    bottom = min(image_height, int(round(y1 * scale)) + padding_px)
    return left, top, right, bottom


def build_text_mask(
    page_record: dict,
    image_size: tuple[int, int],
    render_dpi: int,
    padding_px: int,
) -> Image.Image:
    width, height = image_size
    scale = render_dpi / 72
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    for block in page_record["blocks"]:
        rect = pdf_bbox_to_image_bbox(
            bbox=block["bbox"],
            scale=scale,
            image_width=width,
            image_height=height,
            padding_px=padding_px,
        )
        draw.rectangle(rect, fill=255)
    return mask


def render_image_only_page(page: fitz.Page, render_dpi: int) -> Image.Image:
    zoom = render_dpi / 72
    page_width = int(round(page.rect.width * zoom))
    page_height = int(round(page.rect.height * zoom))
    canvas = Image.new("RGB", (page_width, page_height), "white")

    text_dict = page.get_text("dict")
    for block in text_dict.get("blocks", []):
        if block.get("type") != 1:
            continue
        image_bytes = block.get("image")
        if not image_bytes:
            continue
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        rect = pdf_bbox_to_image_bbox(
            bbox=[round(value, 2) for value in block.get("bbox", ())],
            scale=zoom,
            image_width=page_width,
            image_height=page_height,
        )
        left, top, right, bottom = rect
        if right <= left or bottom <= top:
            continue
        image = image.resize((right - left, bottom - top), Image.Resampling.LANCZOS)
        canvas.paste(image, (left, top))

    return canvas


def opencv_inpaint(original: Image.Image, mask: Image.Image, radius: int) -> Image.Image:
    original_array = cv2.cvtColor(np.array(original), cv2.COLOR_RGB2BGR)
    mask_array = np.array(mask)
    inpainted = cv2.inpaint(original_array, mask_array, radius, cv2.INPAINT_TELEA)
    return Image.fromarray(cv2.cvtColor(inpainted, cv2.COLOR_BGR2RGB))


def save_comparison(
    original: Image.Image,
    mask: Image.Image,
    image_only: Image.Image,
    inpainted: Image.Image,
    output_path: Path,
) -> None:
    width, height = original.size
    header_height = 34
    canvas = Image.new("RGB", (width * 4, height + header_height), "white")
    canvas.paste(original, (0, header_height))
    canvas.paste(mask.convert("RGB"), (width, header_height))
    canvas.paste(image_only, (width * 2, header_height))
    canvas.paste(inpainted, (width * 3, header_height))

    draw = ImageDraw.Draw(canvas)
    draw.text((10, 10), "original", fill="black")
    draw.text((width + 10, 10), "text mask", fill="black")
    draw.text((width * 2 + 10, 10), "image only", fill="black")
    draw.text((width * 3 + 10, 10), "opencv inpaint", fill="black")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG")


def main() -> None:
    args = parse_args()
    page_numbers = parse_page_numbers(args.pages)
    page_records = load_page_records(args.blocks_jsonl, set(page_numbers))

    original_dir = args.output_dir / "original"
    mask_dir = args.output_dir / "mask"
    image_only_dir = args.output_dir / "image_only"
    inpaint_dir = args.output_dir / "inpaint"
    comparison_dir = args.output_dir / "comparison"
    for directory in [original_dir, mask_dir, image_only_dir, inpaint_dir, comparison_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    report: list[dict] = []
    document = fitz.open(args.input)
    try:
        for page_no in page_numbers:
            page_record = page_records.get(page_no)
            if not page_record:
                report.append({"page_no": page_no, "status": "missing_page_record"})
                continue

            page = document.load_page(page_no - 1)
            original = render_page(page, args.render_dpi)
            mask = build_text_mask(
                page_record=page_record,
                image_size=original.size,
                render_dpi=args.render_dpi,
                padding_px=args.mask_padding_px,
            )
            image_only = render_image_only_page(page, args.render_dpi)
            inpainted = opencv_inpaint(original, mask, args.inpaint_radius)

            original_path = original_dir / f"page_{page_no:04d}.png"
            mask_path = mask_dir / f"page_{page_no:04d}_mask.png"
            image_only_path = image_only_dir / f"page_{page_no:04d}_image_only.png"
            inpaint_path = inpaint_dir / f"page_{page_no:04d}_inpaint.png"
            comparison_path = comparison_dir / f"page_{page_no:04d}_background_restoration_comparison.png"

            original.save(original_path, format="PNG")
            mask.save(mask_path, format="PNG")
            image_only.save(image_only_path, format="PNG")
            inpainted.save(inpaint_path, format="PNG")
            save_comparison(original, mask, image_only, inpainted, comparison_path)

            record = {
                "page_no": page_no,
                "text_block_count": page_record["text_block_count"],
                "image_block_count": len(
                    [
                        block
                        for block in page.get_text("dict").get("blocks", [])
                        if block.get("type") == 1
                    ]
                ),
                "original": str(original_path),
                "mask": str(mask_path),
                "image_only": str(image_only_path),
                "inpaint": str(inpaint_path),
                "comparison": str(comparison_path),
                "status": "ok",
            }
            report.append(record)
            print(json.dumps(record, ensure_ascii=False))
    finally:
        document.close()

    report_path = args.output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
