from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import fitz
from PIL import Image, ImageDraw


SHORT_PLACEHOLDERS = [
    "At a glance",
    "18 markets",
    "Claims paid",
    "Protection in force",
    "MDRT leadership",
]

MEDIUM_PLACEHOLDERS = [
    "Operating across 18 markets in Asia.",
    "Paid over US$16 billion in benefits and claims.",
    "Top-ranked globally in MDRT registered members.",
    "Serving individual and group customers across Asia.",
]

LONG_PLACEHOLDERS = [
    "The only international life insurer headquartered and listed in Hong Kong, fully focused on Asia.",
    "Serving more than 38 million individual policies and over 16 million group insurance members.",
    "Nearly US$2 trillion of in-force sum assured across Asia.",
    "Helping people live healthier, longer, better lives across the region.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove source PDF text natively and overlay placeholder translated text."
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


def int_to_rgb(value: int) -> tuple[int, int, int]:
    return ((value >> 16) & 255, (value >> 8) & 255, value & 255)


def rgb255_to_pdf(value: tuple[int, int, int]) -> tuple[float, float, float]:
    return tuple(channel / 255 for channel in value)


def render_page(page: fitz.Page, render_dpi: int) -> Image.Image:
    zoom = render_dpi / 72
    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)


def pick_placeholder(block: dict, index: int) -> str:
    line_count = block.get("line_count", 1)
    char_count = block.get("char_count", 0)
    width = max(1.0, block["bbox"][2] - block["bbox"][0])
    height = max(1.0, block["bbox"][3] - block["bbox"][1])
    area = width * height

    if line_count <= 1 and char_count <= 12:
        return SHORT_PLACEHOLDERS[index % len(SHORT_PLACEHOLDERS)]
    if line_count <= 2 or area < 12000:
        return MEDIUM_PLACEHOLDERS[index % len(MEDIUM_PLACEHOLDERS)]
    return LONG_PLACEHOLDERS[index % len(LONG_PLACEHOLDERS)]


def infer_block_style(page: fitz.Page, block: dict) -> dict:
    rect = fitz.Rect(block["bbox"])
    raw_dict = page.get_text("rawdict")
    colors: Counter[int] = Counter()
    sizes: list[float] = []

    for raw_block in raw_dict.get("blocks", []):
        if raw_block.get("type") != 0:
            continue
        raw_block_rect = fitz.Rect(raw_block["bbox"])
        if not rect.intersects(raw_block_rect):
            continue
        for line in raw_block.get("lines", []):
            for span in line.get("spans", []):
                span_rect = fitz.Rect(span["bbox"])
                if not rect.intersects(span_rect):
                    continue
                colors[span.get("color", 0)] += len(span.get("chars", [])) or 1
                sizes.append(float(span.get("size", block.get("font_size_avg") or 10)))

    color = int_to_rgb(colors.most_common(1)[0][0]) if colors else (0, 0, 0)
    font_size = max(sizes) if sizes else float(block.get("font_size_avg") or 10)
    return {
        "color_rgb255": color,
        "font_size": font_size,
    }


def insert_text_fit(
    page: fitz.Page,
    rect: fitz.Rect,
    text: str,
    color_rgb255: tuple[int, int, int],
    initial_font_size: float,
) -> tuple[float, str]:
    font_size = max(6.0, float(initial_font_size) * 0.9)
    color_pdf = rgb255_to_pdf(color_rgb255)

    while font_size >= 6.0:
        shape = page.new_shape()
        unused = shape.insert_textbox(
            rect,
            text,
            fontsize=font_size,
            fontname="helv",
            color=color_pdf,
            align=0,
            lineheight=1.1,
        )
        if unused >= 0:
            shape.commit()
            status = "ok" if font_size >= initial_font_size * 0.85 else "font_shrink"
            return font_size, status
        font_size -= 1.0

    shape = page.new_shape()
    unused = shape.insert_textbox(
        rect,
        text,
        fontsize=6.0,
        fontname="helv",
        color=color_pdf,
        align=0,
        lineheight=1.0,
    )
    if unused >= 0:
        shape.commit()
        return 6.0, "font_shrink"
    return 6.0, "overflow"


def apply_text_redactions(page: fitz.Page, page_record: dict) -> None:
    for block in page_record["blocks"]:
        page.add_redact_annot(fitz.Rect(block["bbox"]), fill=None, cross_out=False)
    page.apply_redactions(images=0, graphics=0, text=0)


def save_comparison(
    original: Image.Image,
    redacted: Image.Image,
    translated: Image.Image,
    output_path: Path,
) -> None:
    width, height = original.size
    header_height = 34
    canvas = Image.new("RGB", (width * 3, height + header_height), "white")
    canvas.paste(original, (0, header_height))
    canvas.paste(redacted, (width, header_height))
    canvas.paste(translated, (width * 2, header_height))

    draw = ImageDraw.Draw(canvas)
    draw.text((10, 10), "original", fill="black")
    draw.text((width + 10, 10), "native redacted", fill="black")
    draw.text((width * 2 + 10, 10), "placeholder translated", fill="black")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG")


def main() -> None:
    args = parse_args()
    page_numbers = parse_page_numbers(args.pages)
    page_records = load_page_records(args.blocks_jsonl, set(page_numbers))

    original_dir = args.output_dir / "original"
    redacted_dir = args.output_dir / "redacted"
    translated_dir = args.output_dir / "translated"
    comparison_dir = args.output_dir / "comparison"
    for directory in [original_dir, redacted_dir, translated_dir, comparison_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    original_doc = fitz.open(args.input)
    redacted_doc = fitz.open(args.input)
    translated_doc = fitz.open(args.input)
    report: list[dict] = []

    try:
        for page_no in page_numbers:
            page_record = page_records.get(page_no)
            if not page_record:
                report.append({"page_no": page_no, "status": "missing_page_record"})
                continue

            original_page = original_doc.load_page(page_no - 1)
            original_image = render_page(original_page, args.render_dpi)

            redacted_page = redacted_doc.load_page(page_no - 1)
            translated_page = translated_doc.load_page(page_no - 1)

            styles = [infer_block_style(translated_page, block) for block in page_record["blocks"]]

            apply_text_redactions(redacted_page, page_record)
            apply_text_redactions(translated_page, page_record)

            block_reports: list[dict] = []
            for index, block in enumerate(page_record["blocks"]):
                placeholder = pick_placeholder(block, index)
                rect = fitz.Rect(block["bbox"])
                style = styles[index]
                font_size, fit_status = insert_text_fit(
                    page=translated_page,
                    rect=rect,
                    text=placeholder,
                    color_rgb255=style["color_rgb255"],
                    initial_font_size=style["font_size"],
                )
                block_reports.append(
                    {
                        "block_id": block["block_id"],
                        "placeholder": placeholder,
                        "fit_status": fit_status,
                        "font_size": round(font_size, 2),
                        "color_rgb255": list(style["color_rgb255"]),
                    }
                )

            redacted_image = render_page(redacted_page, args.render_dpi)
            translated_image = render_page(translated_page, args.render_dpi)

            original_path = original_dir / f"page_{page_no:04d}_original.png"
            redacted_path = redacted_dir / f"page_{page_no:04d}_redacted.png"
            translated_path = translated_dir / f"page_{page_no:04d}_translated.png"
            comparison_path = comparison_dir / f"page_{page_no:04d}_native_replace_comparison.png"

            original_image.save(original_path, format="PNG")
            redacted_image.save(redacted_path, format="PNG")
            translated_image.save(translated_path, format="PNG")
            save_comparison(original_image, redacted_image, translated_image, comparison_path)

            page_report = {
                "page_no": page_no,
                "text_block_count": page_record["text_block_count"],
                "original": str(original_path),
                "redacted": str(redacted_path),
                "translated": str(translated_path),
                "comparison": str(comparison_path),
                "blocks": block_reports,
                "status": "ok",
            }
            report.append(page_report)
            print(json.dumps(page_report, ensure_ascii=False))

        redacted_pdf_path = args.output_dir / "native_redacted.pdf"
        translated_pdf_path = args.output_dir / "native_translated_placeholder.pdf"
        redacted_doc.save(redacted_pdf_path)
        translated_doc.save(translated_pdf_path)

    finally:
        original_doc.close()
        redacted_doc.close()
        translated_doc.close()

    report_path = args.output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
