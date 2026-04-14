from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz

SMALL_TITLE_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "in",
    "of",
    "on",
    "or",
    "per",
    "the",
    "to",
    "vs",
    "via",
}
FORCE_UPPER_TOKENS = {
    "AIA",
    "AGM",
    "CEO",
    "CFO",
    "ESG",
    "EV",
    "GWS",
    "HK",
    "IFRS",
    "LCSM",
    "NBV",
    "OPAT",
    "UFSG",
    "US",
    "VONB",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a reusable company memory pack from multi-year paired annual reports."
    )
    parser.add_argument("--zh-dir", type=Path, required=True)
    parser.add_argument("--en-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--exclude-year", type=int, default=0)
    parser.add_argument(
        "--max-pages",
        type=int,
        default=0,
        help="0 means all pages.",
    )
    parser.add_argument("--company-name", default="")
    parser.add_argument(
        "--min-mapping-count",
        type=int,
        default=2,
        help="Minimum repeated evidence before a mapping is promoted into the memory pack.",
    )
    return parser.parse_args()


def normalize_inline_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def clean_block_text(line_texts: list[str]) -> str:
    cleaned_lines = [normalize_inline_text(text) for text in line_texts]
    cleaned_lines = [text for text in cleaned_lines if text]
    return "\n".join(cleaned_lines).strip()


def normalize_multiline_text(text: str) -> str:
    return "\n".join(line for line in (normalize_inline_text(x) for x in str(text).splitlines()) if line)


def build_match_signature(text: str) -> str:
    normalized = normalize_inline_text(text).lower()
    normalized = normalized.replace("—", "-").replace("–", "-")
    normalized = re.sub(r"\d+", "#", normalized)
    normalized = re.sub(r"#+", "#", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def classify_region(bbox: list[float], page_height: float) -> str:
    y0, y1 = bbox[1], bbox[3]
    if y1 <= page_height * 0.12:
        return "top"
    if y0 >= page_height * 0.88:
        return "bottom"
    return "middle"


def iter_line_texts(line: dict[str, Any]) -> list[str]:
    text = "".join(span.get("text", "") for span in line.get("spans", []))
    text = normalize_inline_text(text)
    return [text] if text else []


def block_dimensions(block: dict[str, Any]) -> tuple[float, float]:
    x0, y0, x1, y1 = block["bbox"]
    return x1 - x0, y1 - y0


def is_numericish(text: str) -> bool:
    stripped = re.sub(r"[\s,.\-()%+/:$€£¥]", "", text)
    return bool(stripped) and stripped.isdigit()


def digit_ratio(text: str) -> float:
    compact = text.replace("\n", "")
    if not compact:
        return 0.0
    digits = sum(1 for char in compact if char.isdigit())
    return digits / len(compact)


def classify_block_role(block: dict[str, Any]) -> str:
    width, height = block_dimensions(block)
    text = normalize_multiline_text(block["source_text"])
    line_count = int(block["line_count"])
    char_count = int(block["char_count"])
    max_font = float(block.get("font_size_max") or block.get("font_size_avg") or 10)
    region = block["region"]
    ratio = digit_ratio(text)

    if region == "bottom" and height <= 18:
        return "footer"
    if width <= 30 and height >= 100 and line_count >= 3:
        return "sidebar_nav"
    if region == "top" and max_font >= 13 and char_count <= 80:
        return "heading"
    if line_count >= 4 and ratio >= 0.2 and width >= 150:
        return "table_row"
    if char_count <= 36 and line_count <= 2:
        return "label"
    return "body"


def classify_page_archetype(page_record: dict[str, Any]) -> str:
    role_counter: Counter[str] = Counter(block["role"] for block in page_record["blocks"])
    max_font = max((block.get("font_size_max") or block.get("font_size_avg") or 0) for block in page_record["blocks"]) if page_record["blocks"] else 0
    numeric_blocks = sum(1 for block in page_record["blocks"] if digit_ratio(block["source_text"]) >= 0.3)
    short_blocks = sum(1 for block in page_record["blocks"] if block["char_count"] <= 40)
    text_block_count = page_record["text_block_count"]
    image_count = page_record["image_count"]

    if page_record["page_no"] == 1 and max_font >= 30 and text_block_count <= 10:
        return "cover_like"
    if role_counter["table_row"] >= 4 or numeric_blocks >= 10:
        return "table_dense"
    if short_blocks >= 20 and role_counter["label"] >= 10:
        return "contents_like"
    if max_font >= 14 and image_count >= 1 and text_block_count <= 20:
        return "showcase_narrative"
    if role_counter["heading"] >= 1 and text_block_count <= 24:
        return "section_lead"
    return "dense_narrative"


def extract_page_blocks(page: fitz.Page) -> dict[str, Any]:
    text_dict = page.get_text("dict")
    unsorted_blocks: list[dict[str, Any]] = []

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
            float(span.get("size"))
            for line in lines
            for span in line.get("spans", [])
            if span.get("size") is not None
        ]
        font_names = [
            str(span.get("font"))
            for line in lines
            for span in line.get("spans", [])
            if span.get("font")
        ]

        unsorted_blocks.append(
            {
                "bbox": bbox,
                "source_text": text,
                "line_count": len(line_texts),
                "char_count": len(text.replace("\n", "")),
                "font_size_avg": round(statistics.mean(font_sizes), 2) if font_sizes else None,
                "font_size_max": round(max(font_sizes), 2) if font_sizes else None,
                "font_names": sorted(set(font_names)),
                "region": classify_region(bbox, page.rect.height),
                "match_signature": build_match_signature(text),
            }
        )

    sorted_blocks = sorted(unsorted_blocks, key=lambda item: (item["bbox"][1], item["bbox"][0]))
    blocks: list[dict[str, Any]] = []
    for reading_order, block in enumerate(sorted_blocks, start=1):
        role = classify_block_role(block)
        blocks.append(
            {
                "block_id": f"p{page.number + 1}_b{reading_order}",
                "reading_order": reading_order,
                **block,
                "role": role,
            }
        )

    page_record = {
        "page_no": page.number + 1,
        "width": round(page.rect.width, 2),
        "height": round(page.rect.height, 2),
        "text_block_count": len(blocks),
        "image_count": len(page.get_images(full=False)),
        "blocks": blocks,
    }
    page_record["archetype"] = classify_page_archetype(page_record)
    return page_record


def extract_document(pdf_path: Path, max_pages: int) -> dict[str, Any]:
    doc = fitz.open(pdf_path)
    try:
        total_pages = doc.page_count if max_pages <= 0 else min(doc.page_count, max_pages)
        page_records = [extract_page_blocks(doc.load_page(index)) for index in range(total_pages)]
    finally:
        doc.close()
    return {
        "pdf": str(pdf_path),
        "page_count": total_pages,
        "pages": page_records,
    }


def parse_year_from_filename(path: Path) -> int | None:
    match = re.search(r"(20\d{2})", path.name)
    return int(match.group(1)) if match else None


def load_year_pairs(zh_dir: Path, en_dir: Path, exclude_year: int) -> list[tuple[int, Path, Path]]:
    zh_map = {
        year: path
        for path in zh_dir.glob("*.pdf")
        if (year := parse_year_from_filename(path)) is not None and year != exclude_year
    }
    en_map = {
        year: path
        for path in en_dir.glob("*.pdf")
        if (year := parse_year_from_filename(path)) is not None and year != exclude_year
    }
    years = sorted(set(zh_map) & set(en_map))
    return [(year, zh_map[year], en_map[year]) for year in years]


def is_candidate_block(block: dict[str, Any]) -> bool:
    text = normalize_multiline_text(block["source_text"])
    if not text or is_numericish(text):
        return False
    if block["role"] in {"heading", "sidebar_nav", "footer"}:
        return True
    if block["role"] == "label" and block["char_count"] <= 40:
        return True
    if block["region"] == "top" and block["char_count"] <= 60 and block["line_count"] <= 3:
        return True
    return False


def filtered_blocks(page_record: dict[str, Any], role: str) -> list[dict[str, Any]]:
    items = [block for block in page_record["blocks"] if block["role"] == role and is_candidate_block(block)]
    items.sort(key=lambda item: (item["bbox"][1], item["bbox"][0]))
    return items


def pair_page_blocks(zh_page: dict[str, Any], en_page: dict[str, Any]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for role in ["heading", "sidebar_nav", "footer", "label"]:
        zh_blocks = filtered_blocks(zh_page, role)
        en_blocks = filtered_blocks(en_page, role)
        if not zh_blocks or not en_blocks:
            continue
        pair_count = min(len(zh_blocks), len(en_blocks))
        for index in range(pair_count):
            zh_block = zh_blocks[index]
            en_block = en_blocks[index]
            y_delta = abs(zh_block["bbox"][1] - en_block["bbox"][1]) / max(1.0, zh_page["height"])
            if role != "footer" and y_delta > 0.18:
                continue
            pairs.append(
                {
                    "role": role,
                    "y_delta": round(y_delta, 4),
                    "zh_text": normalize_multiline_text(zh_block["source_text"]),
                    "en_text": normalize_multiline_text(en_block["source_text"]),
                    "zh_page_no": zh_page["page_no"],
                    "en_page_no": en_page["page_no"],
                    "zh_block_id": zh_block["block_id"],
                    "en_block_id": en_block["block_id"],
                }
            )
    return pairs


def safe_word_count(text: str) -> int:
    return len([token for token in re.split(r"\s+", text.strip()) if token])


def detect_target_display_style(text: str) -> str:
    compact = normalize_multiline_text(text)
    letters = [char for char in compact if char.isalpha()]
    if not letters:
        return "mixed"
    upper_count = sum(1 for char in letters if char.isupper())
    lower_count = sum(1 for char in letters if char.islower())
    if upper_count and not lower_count:
        return "all_caps"
    if upper_count >= max(4, int(len(letters) * 0.85)) and lower_count <= max(1, int(len(letters) * 0.1)):
        return "mostly_caps"
    return "mixed"


def smart_title_segment(segment: str, lowercase_small_words: bool) -> str:
    token = segment.strip()
    if not token:
        return token
    upper_token = token.upper()
    if upper_token in FORCE_UPPER_TOKENS:
        return upper_token

    lowered = token.lower()
    if lowercase_small_words and lowered in SMALL_TITLE_WORDS:
        return lowered

    possessive_match = re.fullmatch(r"(.+?)([’']s)", lowered)
    if possessive_match:
        base_text, suffix = possessive_match.groups()
        return smart_title_segment(base_text, lowercase_small_words=False) + suffix

    return lowered[:1].upper() + lowered[1:]


def smart_title_case(text: str) -> str:
    tokens = [token for token in re.split(r"\s+", text.replace("\n", " ").strip()) if token]
    rendered_tokens: list[str] = []
    for token_index, token in enumerate(tokens):
        hyphen_parts = token.split("-")
        rendered_parts: list[str] = []
        for part_index, part in enumerate(hyphen_parts):
            lowercase_small_words = (
                token_index > 0
                and token_index < len(tokens) - 1
                and part_index == 0
                and len(hyphen_parts) == 1
            )
            rendered_parts.append(smart_title_segment(part, lowercase_small_words))
        rendered_tokens.append("-".join(rendered_parts))
    return " ".join(rendered_tokens)


def normalize_prompt_target_text(text: str) -> tuple[str, str]:
    normalized = normalize_multiline_text(text)
    normalized = re.sub(r"\s*\n\s*", " ", normalized)
    normalized = re.sub(r"\s{2,}", " ", normalized).strip()
    display_style = detect_target_display_style(normalized)
    if display_style in {"all_caps", "mostly_caps"}:
        normalized = smart_title_case(normalized)
    return normalized, display_style


def is_bad_mapping_text(text: str) -> bool:
    compact = normalize_multiline_text(text)
    if not compact:
        return True
    if re.fullmatch(r"[\d\s./()-]+", compact):
        return True
    if digit_ratio(compact) >= 0.3:
        return True
    if len(compact) <= 1:
        return True
    return False


def should_keep_pair_for_exact(pair: dict[str, Any]) -> bool:
    zh_text = pair["zh_text"]
    en_text = pair["en_text"]
    role = pair["role"]
    if is_bad_mapping_text(zh_text) or is_bad_mapping_text(en_text):
        return False
    return role in {"heading", "sidebar_nav"}


def should_keep_pair_for_line(pair: dict[str, Any]) -> bool:
    if not should_keep_pair_for_exact(pair):
        return False
    return pair["role"] in {"heading", "sidebar_nav"}


def should_keep_pair_for_term(pair: dict[str, Any], zh_line: str, en_line: str) -> bool:
    if is_bad_mapping_text(zh_line) or is_bad_mapping_text(en_line):
        return False
    if len(zh_line) > 24:
        return False
    if safe_word_count(en_line) > 6:
        return False
    return pair["role"] in {"heading", "sidebar_nav"}


def add_mapping_counter(
    counter_map: dict[str, Counter[str]],
    source_text: str,
    target_text: str,
) -> None:
    if not source_text or not target_text:
        return
    counter_map[source_text][target_text] += 1


def choose_consensus_map(
    counter_map: dict[str, Counter[str]],
    min_count: int,
) -> tuple[dict[str, str], dict[str, list[dict[str, Any]]]]:
    chosen: dict[str, str] = {}
    debug: dict[str, list[dict[str, Any]]] = {}
    for source_text, target_counter in sorted(counter_map.items()):
        ranked = [
            {"target": target, "count": count}
            for target, count in target_counter.most_common()
        ]
        debug[source_text] = ranked
        if not ranked:
            continue
        top = ranked[0]
        if top["count"] >= min_count:
            chosen[source_text] = str(top["target"])
    return chosen, debug


def is_prompt_title_candidate(source_text: str, target_text: str) -> bool:
    source = normalize_multiline_text(source_text)
    target = normalize_multiline_text(target_text)
    if is_bad_mapping_text(source) or is_bad_mapping_text(target):
        return False
    if len(source.splitlines()) > 1 or len(target.splitlines()) > 2:
        return False
    if len(source.replace("\n", "")) > 60:
        return False
    if safe_word_count(target.replace("\n", " ")) > 12:
        return False
    if digit_ratio(source) >= 0.2 or digit_ratio(target) >= 0.2:
        return False
    return True


def build_prompt_title_entries(
    line_map: dict[str, str],
    exact_map: dict[str, str],
) -> list[dict[str, Any]]:
    chosen_entries: dict[str, dict[str, Any]] = {}

    def upsert_entry(source_text: str, target_text: str, source_kind: str, priority: int) -> None:
        if not is_prompt_title_candidate(source_text, target_text):
            return
        source = normalize_multiline_text(source_text)
        raw_target = normalize_multiline_text(target_text)
        prompt_target, display_style = normalize_prompt_target_text(raw_target)
        entry = {
            "source": source,
            "target": prompt_target,
            "raw_target": raw_target,
            "display_style": display_style,
            "source_kind": source_kind,
            "source_line_count": len(source.splitlines()),
            "target_line_count": len(raw_target.splitlines()),
        }
        existing = chosen_entries.get(source)
        if existing is None or priority < int(existing.get("priority", 99)):
            chosen_entries[source] = {"priority": priority, **entry}

    for source, target in sorted(line_map.items()):
        upsert_entry(source, target, "line_map", 0)
    for source, target in sorted(exact_map.items()):
        upsert_entry(source, target, "exact_map", 1)

    return [
        {key: value for key, value in entry.items() if key != "priority"}
        for _, entry in sorted(chosen_entries.items(), key=lambda item: item[0])
    ]


def first_heading_text(page_record: dict[str, Any]) -> str:
    for block in page_record["blocks"]:
        if block["role"] == "heading":
            return normalize_multiline_text(block["source_text"])
    return ""


def page_short_signatures(page_record: dict[str, Any], limit: int = 8) -> list[str]:
    items: list[str] = []
    for block in page_record["blocks"]:
        if not is_candidate_block(block):
            continue
        signature = block["match_signature"]
        if not signature or signature in items:
            continue
        items.append(signature)
        if len(items) >= limit:
            break
    return items


def build_memory_pack(
    year_pairs: list[tuple[int, Path, Path]],
    company_name: str,
    max_pages: int,
    min_mapping_count: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    exact_counter: dict[str, Counter[str]] = defaultdict(Counter)
    line_counter: dict[str, Counter[str]] = defaultdict(Counter)
    term_counter: dict[str, Counter[str]] = defaultdict(Counter)
    archetype_counter: Counter[str] = Counter()
    archetype_examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    layout_priors: dict[str, list[float]] = defaultdict(list)
    mapping_pairs: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    page_examples: list[dict[str, Any]] = []

    for year, zh_path, en_path in year_pairs:
        zh_doc = extract_document(zh_path, max_pages)
        en_doc = extract_document(en_path, max_pages)
        page_count = min(len(zh_doc["pages"]), len(en_doc["pages"]))
        sources.append(
            {
                "year": year,
                "zh_pdf": str(zh_path),
                "en_pdf": str(en_path),
                "page_count_used": page_count,
            }
        )

        for zh_page in zh_doc["pages"][:page_count]:
            archetype = zh_page["archetype"]
            archetype_counter[archetype] += 1
            page_examples.append(
                {
                    "year": year,
                    "page_no": zh_page["page_no"],
                    "archetype": archetype,
                    "heading": first_heading_text(zh_page),
                    "signatures": page_short_signatures(zh_page),
                }
            )
            if len(archetype_examples[archetype]) < 6:
                archetype_examples[archetype].append(
                    {
                        "year": year,
                        "page_no": zh_page["page_no"],
                        "heading": first_heading_text(zh_page),
                        "text_block_count": zh_page["text_block_count"],
                        "image_count": zh_page["image_count"],
                    }
                )
            for block in zh_page["blocks"]:
                font_size = block.get("font_size_avg")
                if font_size:
                    layout_priors[block["role"]].append(float(font_size))

        for index in range(page_count):
            zh_page = zh_doc["pages"][index]
            en_page = en_doc["pages"][index]
            page_pairs = pair_page_blocks(zh_page, en_page)
            for pair in page_pairs:
                mapping_pairs.append({"year": year, **pair})
                zh_text = pair["zh_text"]
                en_text = pair["en_text"]
                if not zh_text or not en_text:
                    continue
                if should_keep_pair_for_exact(pair):
                    add_mapping_counter(exact_counter, zh_text, en_text)

                zh_lines = [line for line in zh_text.splitlines() if line]
                en_lines = [line for line in en_text.splitlines() if line]
                if should_keep_pair_for_line(pair) and 1 <= len(zh_lines) <= 4 and len(zh_lines) == len(en_lines):
                    for zh_line, en_line in zip(zh_lines, en_lines):
                        add_mapping_counter(line_counter, zh_line, en_line)
                        if should_keep_pair_for_term(pair, zh_line, en_line):
                            add_mapping_counter(term_counter, zh_line, en_line)
                elif len(zh_lines) == 1 and len(en_lines) == 1 and should_keep_pair_for_term(pair, zh_text, en_text):
                        add_mapping_counter(term_counter, zh_text, en_text)

    exact_map, exact_debug = choose_consensus_map(exact_counter, min_mapping_count)
    line_map, line_debug = choose_consensus_map(line_counter, min_mapping_count)
    term_map, term_debug = choose_consensus_map(term_counter, min_mapping_count)
    prompt_title_entries = build_prompt_title_entries(line_map, exact_map)

    priors = {
        role: {
            "count": len(values),
            "font_size_avg": round(statistics.mean(values), 2),
            "font_size_median": round(statistics.median(values), 2),
            "font_size_max": round(max(values), 2),
        }
        for role, values in sorted(layout_priors.items())
        if values
    }

    memory_pack = {
        "schema_id": "annual_report_company_memory_v1",
        "company_name": company_name or "",
        "document_family": "annual_report",
        "years": [year for year, _, _ in year_pairs],
        "exact_map": exact_map,
        "line_map": line_map,
        "term_map": term_map,
        "prompt_title_entries": prompt_title_entries,
        "style_hints": [
            "优先沿用该公司历史年报中已经稳定出现的栏目标题、导航名和管理层头衔译法。",
            "若当前页面与历史年报中的页面形态接近，应优先参考该公司惯用的标题长度、表格标签写法和正式披露语气。",
            "若历史英文标题采用全大写或特殊分行展示，仅借鉴其正式措辞，不强制沿用大小写和换行样式。",
            "公司历史记忆仅作为软约束，不能覆盖当前 PDF 中真实抽取到的数字、页内结构和文本边界。",
        ],
        "page_archetypes": {
            archetype: {
                "count": count,
                "examples": archetype_examples.get(archetype, []),
            }
            for archetype, count in archetype_counter.most_common()
        },
        "layout_priors": priors,
        "page_examples": page_examples,
        "sources": sources,
    }

    debug_payload = {
        "mapping_pairs": mapping_pairs,
        "exact_map_candidates": exact_debug,
        "line_map_candidates": line_debug,
        "term_map_candidates": term_debug,
    }
    return memory_pack, debug_payload


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    year_pairs = load_year_pairs(args.zh_dir, args.en_dir, args.exclude_year)
    if not year_pairs:
        raise RuntimeError("No matching Chinese / English year pairs found.")

    company_name = args.company_name
    if not company_name:
        company_name = " / ".join(sorted({path.stem.split("_")[0] for _, path, _ in year_pairs}))

    memory_pack, debug_payload = build_memory_pack(
        year_pairs=year_pairs,
        company_name=company_name,
        max_pages=args.max_pages,
        min_mapping_count=args.min_mapping_count,
    )

    memory_path = args.output_dir / "company_memory.json"
    debug_path = args.output_dir / "mapping_debug.json"
    write_json(memory_path, memory_pack)
    write_json(debug_path, debug_payload)
    print(f"company_memory={memory_path}")
    print(f"mapping_debug={debug_path}")


if __name__ == "__main__":
    main()
