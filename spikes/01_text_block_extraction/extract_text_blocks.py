from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import fitz
from PIL import Image, ImageDraw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract page-level text blocks and bounding boxes from a PDF."
    )
    parser.add_argument("--input", type=Path, required=True, help="Source PDF path.")
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        required=True,
        help="Output JSONL file with one page record per line.",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        required=True,
        help="Output summary JSON file.",
    )
    parser.add_argument(
        "--pages",
        type=str,
        help="Optional page selection such as '1-20,55,60-62'. Uses 1-based indexing.",
    )
    parser.add_argument(
        "--render-pages-dir",
        type=Path,
        help="Optional output directory for rendered page PNG files.",
    )
    parser.add_argument(
        "--masked-pages-dir",
        type=Path,
        help="Optional output directory for text-masked page PNG files.",
    )
    parser.add_argument(
        "--render-dpi",
        type=int,
        default=144,
        help="PNG render DPI when --render-pages-dir is provided.",
    )
    parser.add_argument(
        "--header-footer-min-repeat-pages",
        type=int,
        default=3,
        help="Minimum repeated pages before a top/bottom block is classified as header/footer.",
    )
    parser.add_argument(
        "--header-footer-top-ratio",
        type=float,
        default=0.12,
        help="Top page ratio used to mark blocks as header candidates.",
    )
    parser.add_argument(
        "--header-footer-bottom-ratio",
        type=float,
        default=0.12,
        help="Bottom page ratio used to mark blocks as footer candidates.",
    )
    parser.add_argument(
        "--mask-padding-px",
        type=int,
        default=2,
        help="Extra pixel padding applied around each text block when masking.",
    )
    parser.add_argument(
        "--mask-sample-margin-px",
        type=int,
        default=4,
        help="Margin used to sample surrounding background colors for masked pages.",
    )
    return parser.parse_args()


def parse_page_selection(selection: str | None, total_pages: int) -> list[int]:
    if not selection:
        return list(range(total_pages))

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
            for page_no in range(start, end + 1):
                if 1 <= page_no <= total_pages:
                    selected.add(page_no - 1)
        else:
            page_no = int(token)
            if 1 <= page_no <= total_pages:
                selected.add(page_no - 1)

    return sorted(selected)


def normalize_inline_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def clean_block_text(line_texts: list[str]) -> str:
    cleaned_lines = [normalize_inline_text(text) for text in line_texts]
    cleaned_lines = [text for text in cleaned_lines if text]
    return "\n".join(cleaned_lines).strip()


def build_match_signature(text: str) -> str:
    normalized = normalize_inline_text(text).lower()
    normalized = normalized.replace("—", "-").replace("–", "-")
    normalized = re.sub(r"\d+", "#", normalized)
    normalized = re.sub(r"#+", "#", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def iter_line_texts(line: dict) -> Iterable[str]:
    spans = line.get("spans", [])
    text = "".join(span.get("text", "") for span in spans)
    text = normalize_inline_text(text)
    if text:
        yield text


def classify_region(
    bbox: list[float], page_height: float, top_ratio: float, bottom_ratio: float
) -> str:
    y0 = bbox[1]
    y1 = bbox[3]
    if y1 <= page_height * top_ratio:
        return "top"
    if y0 >= page_height * (1 - bottom_ratio):
        return "bottom"
    return "middle"


def render_page_png(
    page: fitz.Page, render_pages_dir: Path, render_dpi: int
) -> str:
    render_pages_dir.mkdir(parents=True, exist_ok=True)
    zoom = render_dpi / 72
    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    output_path = render_pages_dir / f"page_{page.number + 1:04d}.png"
    pixmap.save(output_path)
    return str(output_path)


def pdf_bbox_to_image_bbox(
    bbox: list[float],
    scale: float,
    image_width: int,
    image_height: int,
    padding_px: int,
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = bbox
    left = max(0, int(round(x0 * scale)) - padding_px)
    top = max(0, int(round(y0 * scale)) - padding_px)
    right = min(image_width, int(round(x1 * scale)) + padding_px)
    bottom = min(image_height, int(round(y1 * scale)) + padding_px)
    return left, top, right, bottom


def estimate_background_color(
    image: Image.Image,
    rect: tuple[int, int, int, int],
    sample_margin_px: int,
) -> tuple[int, int, int]:
    left, top, right, bottom = rect
    width, height = image.size
    samples: list[tuple[int, int, int]] = []

    outer_left = max(0, left - sample_margin_px)
    outer_top = max(0, top - sample_margin_px)
    outer_right = min(width, right + sample_margin_px)
    outer_bottom = min(height, bottom + sample_margin_px)

    for y in range(outer_top, outer_bottom):
        for x in range(outer_left, outer_right):
            inside = left <= x < right and top <= y < bottom
            if inside:
                continue
            samples.append(image.getpixel((x, y)))

    if not samples:
        return (255, 255, 255)

    red = int(round(sum(pixel[0] for pixel in samples) / len(samples)))
    green = int(round(sum(pixel[1] for pixel in samples) / len(samples)))
    blue = int(round(sum(pixel[2] for pixel in samples) / len(samples)))
    return red, green, blue


def save_masked_page_png(
    page: fitz.Page,
    blocks: list[dict],
    masked_pages_dir: Path,
    render_dpi: int,
    padding_px: int,
    sample_margin_px: int,
) -> str:
    masked_pages_dir.mkdir(parents=True, exist_ok=True)
    zoom = render_dpi / 72
    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
    draw = ImageDraw.Draw(image)

    for block in blocks:
        rect = pdf_bbox_to_image_bbox(
            bbox=block["bbox"],
            scale=zoom,
            image_width=image.width,
            image_height=image.height,
            padding_px=padding_px,
        )
        fill_color = estimate_background_color(
            image=image,
            rect=rect,
            sample_margin_px=sample_margin_px,
        )
        draw.rectangle(rect, fill=fill_color)

    output_path = masked_pages_dir / f"page_{page.number + 1:04d}.png"
    image.save(output_path, format="PNG")
    return str(output_path)


def extract_page_blocks(
    page: fitz.Page,
    top_ratio: float,
    bottom_ratio: float,
    page_image_path: str | None = None,
) -> dict:
    text_dict = page.get_text("dict")
    unsorted_blocks: list[dict] = []

    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue

        lines = block.get("lines", [])
        line_texts = [line_text for line in lines for line_text in iter_line_texts(line)]
        text = clean_block_text(line_texts)
        if not text:
            continue

        bbox = [round(value, 2) for value in block.get("bbox", ())]
        font_sizes = [
            span.get("size")
            for line in lines
            for span in line.get("spans", [])
            if span.get("size") is not None
        ]
        font_names = [
            span.get("font")
            for line in lines
            for span in line.get("spans", [])
            if span.get("font")
        ]
        region = classify_region(
            bbox=bbox,
            page_height=page.rect.height,
            top_ratio=top_ratio,
            bottom_ratio=bottom_ratio,
        )

        unsorted_blocks.append(
            {
                "bbox": bbox,
                "source_text": text,
                "line_count": len(line_texts),
                "char_count": len(text),
                "font_size_avg": round(statistics.mean(font_sizes), 2)
                if font_sizes
                else None,
                "font_size_max": round(max(font_sizes), 2) if font_sizes else None,
                "font_names": sorted(set(font_names)),
                "region": region,
                "match_signature": build_match_signature(text),
            }
        )

    sorted_blocks = sorted(
        unsorted_blocks, key=lambda block: (block["bbox"][1], block["bbox"][0])
    )
    blocks: list[dict] = []
    for reading_order, block in enumerate(sorted_blocks, start=1):
        blocks.append(
            {
                "block_id": f"p{page.number + 1}_b{reading_order}",
                "reading_order": reading_order,
                **block,
                "role": "body",
            }
        )

    page_record = {
        "page_no": page.number + 1,
        "width": round(page.rect.width, 2),
        "height": round(page.rect.height, 2),
        "text_block_count": len(blocks),
        "blocks": blocks,
    }
    if page_image_path:
        page_record["page_image"] = page_image_path
    return page_record


def detect_headers_and_footers(
    page_records: list[dict],
    min_repeat_pages: int,
) -> dict[str, int]:
    signature_to_pages: dict[tuple[str, str], set[int]] = defaultdict(set)

    for page_record in page_records:
        page_no = page_record["page_no"]
        for block in page_record["blocks"]:
            if block["region"] not in {"top", "bottom"}:
                continue
            if block["char_count"] > 200:
                continue
            signature = block["match_signature"]
            if not signature:
                continue
            signature_to_pages[(block["region"], signature)].add(page_no)

    repeated_signatures = {
        (region, signature)
        for (region, signature), page_numbers in signature_to_pages.items()
        if len(page_numbers) >= min_repeat_pages
    }

    header_count = 0
    footer_count = 0
    for page_record in page_records:
        for block in page_record["blocks"]:
            signature_key = (block["region"], block["match_signature"])
            if signature_key not in repeated_signatures:
                continue
            if block["region"] == "top":
                block["role"] = "header"
                header_count += 1
            elif block["region"] == "bottom":
                block["role"] = "footer"
                footer_count += 1

    return {
        "header_blocks": header_count,
        "footer_blocks": footer_count,
        "repeated_header_footer_signatures": len(repeated_signatures),
    }


def main() -> None:
    args = parse_args()
    source_pdf = args.input.resolve()
    output_jsonl = args.output_jsonl.resolve()
    summary_json = args.summary_json.resolve()
    render_pages_dir = args.render_pages_dir.resolve() if args.render_pages_dir else None
    masked_pages_dir = args.masked_pages_dir.resolve() if args.masked_pages_dir else None

    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    if render_pages_dir:
        render_pages_dir.mkdir(parents=True, exist_ok=True)
    if masked_pages_dir:
        masked_pages_dir.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    document = fitz.open(source_pdf)
    try:
        selected_pages = parse_page_selection(args.pages, document.page_count)
        page_records: list[dict] = []
        total_blocks = 0
        pages_with_zero_blocks = 0
        zero_block_pages: list[int] = []
        max_blocks_page_no: int | None = None
        max_blocks_count = -1
        rendered_page_count = 0
        masked_page_count = 0

        for page_index in selected_pages:
            page = document.load_page(page_index)
            page_image_path = None
            if render_pages_dir:
                page_image_path = render_page_png(page, render_pages_dir, args.render_dpi)
                rendered_page_count += 1

            page_record = extract_page_blocks(
                page=page,
                top_ratio=args.header_footer_top_ratio,
                bottom_ratio=args.header_footer_bottom_ratio,
                page_image_path=page_image_path,
            )
            page_record["source_pdf"] = str(source_pdf)

            if masked_pages_dir:
                masked_page_path = save_masked_page_png(
                    page=page,
                    blocks=page_record["blocks"],
                    masked_pages_dir=masked_pages_dir,
                    render_dpi=args.render_dpi,
                    padding_px=args.mask_padding_px,
                    sample_margin_px=args.mask_sample_margin_px,
                )
                page_record["masked_page_image"] = masked_page_path
                masked_page_count += 1

            page_records.append(page_record)

            total_blocks += page_record["text_block_count"]
            if page_record["text_block_count"] == 0:
                pages_with_zero_blocks += 1
                zero_block_pages.append(page_record["page_no"])
            if page_record["text_block_count"] > max_blocks_count:
                max_blocks_count = page_record["text_block_count"]
                max_blocks_page_no = page_record["page_no"]

        role_summary = detect_headers_and_footers(
            page_records=page_records,
            min_repeat_pages=args.header_footer_min_repeat_pages,
        )

        with output_jsonl.open("w", encoding="utf-8") as handle:
            for page_record in page_records:
                handle.write(json.dumps(page_record, ensure_ascii=False) + "\n")

        duration_sec = round(time.time() - start_time, 2)
        summary = {
            "source_pdf": str(source_pdf),
            "page_count_total": document.page_count,
            "page_count_processed": len(page_records),
            "selected_pages_1_based": [page_index + 1 for page_index in selected_pages],
            "total_text_blocks": total_blocks,
            "avg_text_blocks_per_page": round(total_blocks / len(page_records), 2)
            if page_records
            else 0,
            "pages_with_zero_blocks": pages_with_zero_blocks,
            "zero_block_pages_1_based": zero_block_pages,
            "max_blocks_page_1_based": max_blocks_page_no,
            "max_blocks_count": max_blocks_count if max_blocks_count >= 0 else 0,
            "rendered_page_count": rendered_page_count,
            "render_pages_dir": str(render_pages_dir) if render_pages_dir else None,
            "masked_page_count": masked_page_count,
            "masked_pages_dir": str(masked_pages_dir) if masked_pages_dir else None,
            **role_summary,
            "output_jsonl": str(output_jsonl),
            "duration_sec": duration_sec,
            "status": "ok",
        }
        summary_json.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False))
    finally:
        document.close()


if __name__ == "__main__":
    main()
