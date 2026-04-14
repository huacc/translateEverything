from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import fitz
from PIL import Image, ImageDraw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild translated PDF pages from cached block translations."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--blocks-jsonl", type=Path, required=True)
    parser.add_argument("--translations-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--pages",
        type=str,
        required=True,
        help="Page selection such as '1-20' or '3,294'. Uses 1-based page numbers.",
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


def load_translation_map(translations_json: Path, page_numbers: set[int]) -> dict[int, dict[str, dict]]:
    items = json.loads(translations_json.read_text(encoding="utf-8"))
    mapping: dict[int, dict[str, dict]] = {}
    for item in items:
        page_no = item["page_no"]
        if page_no not in page_numbers:
            continue
        mapping.setdefault(page_no, {})[item["block_id"]] = item
    return mapping


def int_to_rgb(value: int) -> tuple[int, int, int]:
    return ((value >> 16) & 255, (value >> 8) & 255, value & 255)


def rgb255_to_pdf(value: tuple[int, int, int]) -> tuple[float, float, float]:
    return tuple(channel / 255 for channel in value)


def render_page(page: fitz.Page, render_dpi: int) -> Image.Image:
    zoom = render_dpi / 72
    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)


def choose_font_name(font_names: list[str]) -> str:
    text = " ".join(font_names).lower()
    if any(token in text for token in ["bold", "xbold", "black", "heavy", "medi"]):
        return "Helvetica-Bold"
    return "Helvetica"


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
        "font_name": choose_font_name(block.get("font_names", [])),
    }


def extract_raw_line_segments(page: fitz.Page, block: dict) -> list[dict[str, Any]]:
    rect = fitz.Rect(block["bbox"])
    raw_dict = page.get_text("rawdict")
    segments: list[dict[str, Any]] = []
    for raw_block in raw_dict.get("blocks", []):
        if raw_block.get("type") != 0:
            continue
        raw_block_rect = fitz.Rect(raw_block["bbox"])
        if not rect.intersects(raw_block_rect):
            continue
        for line in raw_block.get("lines", []):
            texts: list[str] = []
            size = None
            line_bbox = None
            for span in line.get("spans", []):
                span_text = "".join(char["c"] for char in span.get("chars", []))
                if not span_text.strip():
                    continue
                texts.append(span_text)
                size = float(span.get("size", size or block.get("font_size_avg") or 10))
                span_rect = fitz.Rect(span["bbox"])
                line_bbox = span_rect if line_bbox is None else line_bbox | span_rect
            if texts and line_bbox is not None:
                segments.append(
                    {
                        "text": "".join(texts).strip(),
                        "bbox": [line_bbox.x0, line_bbox.y0, line_bbox.x1, line_bbox.y1],
                        "font_size": size or float(block.get("font_size_avg") or 10),
                    }
                )
    segments.sort(key=lambda item: (round(item["bbox"][1], 2), item["bbox"][0]))
    return segments


def is_numericish(text: str) -> bool:
    normalized = re.sub(r"[\s,.\-()%+/]", "", text)
    return bool(normalized) and normalized.isdigit()


def is_tiny_numeric_block(block: dict, text: str) -> bool:
    x0, y0, x1, y1 = block["bbox"]
    width = x1 - x0
    height = y1 - y0
    return block.get("line_count", 1) == 1 and is_numericish(text) and width <= 18 and height <= 9


def is_segment_overlay_candidate(block: dict, translation: str, segments: list[dict[str, Any]]) -> bool:
    x0, y0, x1, y1 = block["bbox"]
    width = x1 - x0
    height = y1 - y0
    translation_lines = [line.strip() for line in translation.splitlines() if line.strip()]
    if len(translation_lines) < 2 or len(translation_lines) != len(segments):
        return False
    if width < 150:
        return False
    if height > 36:
        return False
    return True


def insert_single_line_best_fit(
    page: fitz.Page,
    rect: fitz.Rect,
    text: str,
    color_rgb255: tuple[int, int, int],
    preferred_font_size: float,
    preferred_fonts: list[str] | None = None,
    min_font_size: float = 2.5,
    commit: bool = False,
) -> tuple[float, str]:
    fonts = preferred_fonts or ["Helvetica", "Times-Roman"]
    color_pdf = rgb255_to_pdf(color_rgb255)
    best: tuple[float, str, str] | None = None

    for font_name in fonts:
        width_at_one = fitz.get_text_length(text, fontname=font_name, fontsize=1)
        if width_at_one <= 0:
            continue
        size_by_width = rect.width / width_at_one
        size_by_height = rect.height * 0.95
        start_size = min(max(preferred_font_size * 0.9, min_font_size), size_by_width, size_by_height)
        size = max(start_size, min_font_size)
        while size >= min_font_size:
            shape = page.new_shape()
            unused = shape.insert_textbox(
                rect,
                text,
                fontsize=size,
                fontname=font_name,
                color=color_pdf,
                align=0,
                lineheight=1.0,
            )
            if unused >= 0:
                if commit:
                    shape.commit()
                status = "ok" if size >= preferred_font_size * 0.85 else "font_shrink"
                return size, status
            if best is None or size > best[0]:
                best = (size, font_name, "overflow")
            size -= 0.25

    return (best[0], best[2]) if best else (min_font_size, "overflow")


def textbox_fit(
    page: fitz.Page,
    rect: fitz.Rect,
    text: str,
    style: dict,
    min_font_size: float = 5.0,
    commit: bool = False,
) -> tuple[float, str]:
    color_pdf = rgb255_to_pdf(style["color_rgb255"])
    font_name = style["font_name"]
    start_size = max(min_font_size, float(style["font_size"]) * 0.9)

    for lineheight in [1.1, 1.0, 0.95]:
        font_size = start_size
        while font_size >= min_font_size:
            shape = page.new_shape()
            unused = shape.insert_textbox(
                rect,
                text,
                fontsize=font_size,
                fontname=font_name,
                color=color_pdf,
                align=0,
                lineheight=lineheight,
            )
            if unused >= 0:
                if commit:
                    shape.commit()
                status = "ok" if font_size >= style["font_size"] * 0.85 else "font_shrink"
                return font_size, status
            font_size -= 0.5
    return min_font_size, "overflow"


def overlay_segmented_translation(
    page: fitz.Page,
    block: dict,
    translation: str,
    base_style: dict,
    segments: list[dict[str, Any]],
    commit: bool = False,
) -> tuple[float, str]:
    translation_lines = [line.strip() for line in translation.splitlines() if line.strip()]
    fit_statuses: list[str] = []
    min_ratio = 1.0
    for line_text, segment in zip(translation_lines, segments):
        seg_rect = fitz.Rect(segment["bbox"])
        seg_rect.x0 = max(seg_rect.x0 - 0.5, 0)
        seg_rect.x1 += 0.5
        segment_style = {
            "color_rgb255": base_style["color_rgb255"],
            "font_size": segment.get("font_size", base_style["font_size"]),
            "font_name": base_style["font_name"],
        }
        if is_numericish(line_text):
            fitted_size, seg_status = insert_single_line_best_fit(
                page=page,
                rect=seg_rect,
                text=line_text,
                color_rgb255=segment_style["color_rgb255"],
                preferred_font_size=segment_style["font_size"],
                preferred_fonts=["Times-Roman", "Helvetica"],
                min_font_size=2.5,
                commit=commit,
            )
        else:
            fitted_size, seg_status = insert_single_line_best_fit(
                page=page,
                rect=seg_rect,
                text=line_text,
                color_rgb255=segment_style["color_rgb255"],
                preferred_font_size=segment_style["font_size"],
                preferred_fonts=["Helvetica-Bold", "Helvetica", "Times-Roman"],
                min_font_size=3.0,
                commit=commit,
            )
            if seg_status == "overflow":
                fitted_size, seg_status = textbox_fit(
                    page=page,
                    rect=seg_rect,
                    text=line_text,
                    style=segment_style,
                    min_font_size=3.0,
                    commit=commit,
                )
        fit_statuses.append(seg_status)
        min_ratio = min(min_ratio, fitted_size / max(1.0, segment_style["font_size"]))

    if any(status == "overflow" for status in fit_statuses):
        return min_ratio, "overflow"
    if any(status == "font_shrink" for status in fit_statuses):
        return min_ratio, "font_shrink"
    return min_ratio, "ok"


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
    draw.text((width * 2 + 10, 10), "translated", fill="black")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG")


def write_json_file(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    page_numbers = parse_page_numbers(args.pages)
    page_number_set = set(page_numbers)
    page_records = load_page_records(args.blocks_jsonl, page_number_set)
    translation_map = load_translation_map(args.translations_json, page_number_set)

    original_dir = args.output_dir / "original"
    redacted_dir = args.output_dir / "redacted"
    translated_dir = args.output_dir / "translated"
    comparison_dir = args.output_dir / "comparison"
    for directory in [original_dir, redacted_dir, translated_dir, comparison_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    original_doc = fitz.open(args.input)
    redacted_doc = fitz.open(args.input)
    translated_doc = fitz.open(args.input)
    sample_only_doc = fitz.open()
    report: list[dict[str, Any]] = []
    translations_out: list[dict[str, Any]] = []

    try:
        for page_no in page_numbers:
            page_record = page_records.get(page_no)
            page_translations = translation_map.get(page_no, {})
            if not page_record:
                report.append({"page_no": page_no, "status": "missing_page_record"})
                continue

            original_page = original_doc.load_page(page_no - 1)
            original_image = render_page(original_page, args.render_dpi)
            styles = {
                block["block_id"]: infer_block_style(original_page, block)
                for block in page_record["blocks"]
            }

            redacted_page = redacted_doc.load_page(page_no - 1)
            translated_page = translated_doc.load_page(page_no - 1)
            apply_text_redactions(redacted_page, page_record)
            apply_text_redactions(translated_page, page_record)

            block_reports: list[dict[str, Any]] = []
            for block in page_record["blocks"]:
                block_id = block["block_id"]
                cached = page_translations.get(block_id)
                if not cached:
                    block_report = {
                        "block_id": block_id,
                        "status": "missing_cached_translation",
                    }
                    block_reports.append(block_report)
                    continue

                style = styles[block_id]
                raw_segments = extract_raw_line_segments(original_page, block)
                if is_segment_overlay_candidate(block, cached["translation"], raw_segments):
                    font_metric, fit_status = overlay_segmented_translation(
                        page=translated_page,
                        block=block,
                        translation=cached["translation"],
                        base_style=style,
                        segments=raw_segments,
                        commit=True,
                    )
                    final_font_size = round(font_metric * max(1.0, style["font_size"]), 2)
                elif is_tiny_numeric_block(block, cached["translation"]):
                    final_font_size, fit_status = insert_single_line_best_fit(
                        page=translated_page,
                        rect=fitz.Rect(block["bbox"]),
                        text=cached["translation"],
                        color_rgb255=style["color_rgb255"],
                        preferred_font_size=style["font_size"],
                        preferred_fonts=["Times-Roman", "Helvetica"],
                        min_font_size=2.5,
                        commit=True,
                    )
                else:
                    final_font_size, fit_status = textbox_fit(
                        page=translated_page,
                        rect=fitz.Rect(block["bbox"]),
                        text=cached["translation"],
                        style=style,
                        commit=True,
                    )
                block_report = {
                    "block_id": block_id,
                    "source_text": cached.get("source_text", block["source_text"]),
                    "translation": cached["translation"],
                    "fit_status_final": fit_status,
                    "font_size_final": round(final_font_size, 2),
                }
                block_reports.append(block_report)
                translations_out.append({"page_no": page_no, **block_report})

            redacted_image = render_page(redacted_page, args.render_dpi)
            translated_image = render_page(translated_page, args.render_dpi)

            original_path = original_dir / f"page_{page_no:04d}_original.png"
            redacted_path = redacted_dir / f"page_{page_no:04d}_redacted.png"
            translated_path = translated_dir / f"page_{page_no:04d}_translated.png"
            comparison_path = comparison_dir / f"page_{page_no:04d}_translation_comparison.png"
            original_image.save(original_path, format="PNG")
            redacted_image.save(redacted_path, format="PNG")
            translated_image.save(translated_path, format="PNG")
            save_comparison(original_image, redacted_image, translated_image, comparison_path)

            summary_counter = Counter(
                item["fit_status_final"] for item in block_reports if "fit_status_final" in item
            )
            page_summary = {
                "page_no": page_no,
                "text_block_count": page_record["text_block_count"],
                "fit_summary": dict(summary_counter),
                "original": str(original_path),
                "redacted": str(redacted_path),
                "translated": str(translated_path),
                "comparison": str(comparison_path),
                "status": "ok",
            }
            report.append(page_summary)
            print(json.dumps(page_summary, ensure_ascii=False))

        translated_pdf_path = args.output_dir / "translated_en_first20_full.pdf"
        redacted_pdf_path = args.output_dir / "native_redacted_first20_full.pdf"
        translated_doc.save(translated_pdf_path)
        redacted_doc.save(redacted_pdf_path)

        sample_only_doc.insert_pdf(translated_doc, from_page=page_numbers[0] - 1, to_page=page_numbers[-1] - 1)
        sample_only_pdf_path = args.output_dir / "translated_en_first20_only.pdf"
        sample_only_doc.save(sample_only_pdf_path)
    finally:
        original_doc.close()
        redacted_doc.close()
        translated_doc.close()
        sample_only_doc.close()

    write_json_file(args.output_dir / "report.json", report)
    write_json_file(args.output_dir / "translations.json", translations_out)


if __name__ == "__main__":
    main()
