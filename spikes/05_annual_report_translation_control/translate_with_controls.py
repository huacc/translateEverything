from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

import fitz
import requests
from PIL import Image, ImageDraw


DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent / "configs"
SYSTEM_FONT_DIR = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
MONTH_NAMES = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}
FONT_OBJECT_CACHE: dict[str, fitz.Font] = {}
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
    default_domain_spec = DEFAULT_CONFIG_DIR / "domain_spec.json"
    default_task_spec = DEFAULT_CONFIG_DIR / "task_spec.json"
    default_validation_spec = DEFAULT_CONFIG_DIR / "validation_spec.json"
    default_glossary = DEFAULT_CONFIG_DIR / "glossary_zh_en_seed.json"
    default_patterns = DEFAULT_CONFIG_DIR / "patterns_zh_en.json"
    parser = argparse.ArgumentParser(
        description="Translate PDF text blocks with a Claude-compatible API and overlay them back into the PDF."
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
    parser.add_argument("--source-language", default="Traditional Chinese")
    parser.add_argument("--target-language", default="English")
    parser.add_argument("--model", default=os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL))
    parser.add_argument("--render-dpi", type=int, default=96)
    parser.add_argument(
        "--compact-threshold",
        type=float,
        default=0.80,
        help="Retry compact rewrite if fitted font size falls below this ratio of the original font size.",
    )
    parser.add_argument("--max-output-tokens", type=int, default=2200)
    parser.add_argument("--domain-spec", type=Path, default=default_domain_spec)
    parser.add_argument("--task-spec", type=Path, default=default_task_spec)
    parser.add_argument("--validation-spec", type=Path, default=default_validation_spec)
    parser.add_argument("--glossary", type=Path, default=default_glossary)
    parser.add_argument("--patterns", type=Path, default=default_patterns)
    parser.add_argument(
        "--company-memory",
        type=Path,
        help="Optional company memory JSON generated from historical annual reports.",
    )
    parser.add_argument(
        "--document-context-pages",
        type=int,
        default=30,
        help="Build dynamic document context from the first N pages in blocks.jsonl.",
    )
    parser.add_argument(
        "--continue-on-page-error",
        action="store_true",
        help="Continue processing later pages if one page fails.",
    )
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


def load_context_page_records(blocks_jsonl: Path, max_pages: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with blocks_jsonl.open("r", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record["page_no"] <= max_pages:
                records.append(record)
    return records


def load_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_optional_json_file(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    return load_json_file(path)


def dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        items.append(value)
    return items


def build_memory_signature(text: str) -> str:
    normalized = normalize_source_text(text).lower()
    normalized = normalized.replace("—", "-").replace("–", "-")
    normalized = re.sub(r"\d+", "#", normalized)
    normalized = re.sub(r"#+", "#", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def normalize_source_text(text: str) -> str:
    lines = [" ".join(line.split()) for line in str(text).splitlines()]
    return "\n".join(line for line in lines if line).strip()


def detect_memory_target_display_style(text: str) -> str:
    compact = normalize_source_text(text).replace("\n", " ")
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


def smart_memory_title_segment(segment: str, lowercase_small_words: bool) -> str:
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
        return smart_memory_title_segment(base_text, lowercase_small_words=False) + suffix

    return lowered[:1].upper() + lowered[1:]


def normalize_memory_prompt_target(text: str) -> tuple[str, str]:
    normalized = normalize_source_text(text)
    normalized = re.sub(r"\s*\n\s*", " ", normalized)
    normalized = re.sub(r"\s{2,}", " ", normalized).strip()
    display_style = detect_memory_target_display_style(normalized)
    if display_style in {"all_caps", "mostly_caps"}:
        tokens = [token for token in re.split(r"\s+", normalized) if token]
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
                rendered_parts.append(smart_memory_title_segment(part, lowercase_small_words))
            rendered_tokens.append("-".join(rendered_parts))
        normalized = " ".join(rendered_tokens)
    return normalized, display_style


def iter_company_memory_title_entries(company_memory: dict[str, Any]) -> list[dict[str, str]]:
    prompt_entries = company_memory.get("prompt_title_entries")
    if isinstance(prompt_entries, list) and prompt_entries:
        entries: list[dict[str, str]] = []
        for item in prompt_entries:
            if not isinstance(item, dict):
                continue
            source = normalize_source_text(item.get("source", ""))
            target = normalize_source_text(item.get("target", ""))
            raw_target = normalize_source_text(item.get("raw_target", "")) or target
            if not source or not target:
                continue
            entries.append(
                {
                    "source": source,
                    "target": target,
                    "raw_target": raw_target,
                    "display_style": str(item.get("display_style") or ""),
                    "source_kind": str(item.get("source_kind") or ""),
                }
            )
        return entries

    chosen_entries: dict[str, dict[str, str]] = {}
    for source_kind in ["line_map", "exact_map"]:
        source_map = company_memory.get(source_kind, {})
        if not isinstance(source_map, dict):
            continue
        for source_text, target_text in source_map.items():
            source = normalize_source_text(source_text)
            raw_target = normalize_source_text(target_text)
            if not source or not raw_target:
                continue
            if len(source.splitlines()) > 1 or len(raw_target.splitlines()) > 2:
                continue
            if len(source.replace("\n", "")) > 60:
                continue
            target, display_style = normalize_memory_prompt_target(raw_target)
            if not target:
                continue
            if source not in chosen_entries:
                chosen_entries[source] = {
                    "source": source,
                    "target": target,
                    "raw_target": raw_target,
                    "display_style": display_style,
                    "source_kind": source_kind,
                }
    return [entry for _, entry in sorted(chosen_entries.items(), key=lambda item: item[0])]


def block_dimensions(block: dict) -> tuple[float, float]:
    x0, y0, x1, y1 = block["bbox"]
    return x1 - x0, y1 - y0


def classify_block_type(block: dict) -> str:
    width, height = block_dimensions(block)
    text = normalize_source_text(block.get("source_text", ""))
    line_count = int(block.get("line_count") or max(1, text.count("\n") + 1))
    char_count = int(block.get("char_count") or len(text.replace("\n", "")))
    region = block.get("region")

    if region == "bottom" and height <= 18:
        return "footer"
    if width <= 24 and height >= 100 and line_count >= 3:
        return "sidebar_nav"
    if re.fullmatch(r"[\d\s,.\-()%+/–—]+", text):
        return "chart_label"
    if region == "top" and char_count <= 60 and height <= 40:
        return "heading"
    if char_count <= 28 and line_count <= 2:
        return "label"
    return "body"


def month_name(month_text: str) -> str:
    month = int(month_text)
    return MONTH_NAMES.get(month, month_text)


def render_regex_template(template: str, match: re.Match[str]) -> str:
    groups = {key: value for key, value in match.groupdict().items() if value is not None}
    if "month" in groups:
        groups["month_name"] = month_name(groups["month"])
        groups["month"] = str(int(groups["month"]))
    if "day" in groups:
        groups["day"] = str(int(groups["day"]))
    return template.format(**groups)


def apply_regex_templates(text: str, regex_templates: list[dict[str, Any]]) -> tuple[str, str] | None:
    for item in regex_templates:
        pattern = item.get("pattern")
        template = item.get("template")
        if not isinstance(pattern, str) or not isinstance(template, str):
            continue
        match = re.fullmatch(pattern, text)
        if match:
            return render_regex_template(template, match), str(item.get("name") or pattern)
    return None


def resolve_line_control(
    line: str,
    glossary: dict[str, Any],
    patterns: dict[str, Any],
) -> tuple[str, str, str] | None:
    exact_map = glossary.get("exact_map", {})
    line_map = glossary.get("line_map", {})
    if line in exact_map:
        return str(exact_map[line]), "glossary_exact", line
    if line in line_map:
        return str(line_map[line]), "glossary_line", line

    for pattern in patterns.get("preserve_fullmatch_patterns", []):
        if re.fullmatch(pattern, line):
            return line, "pattern_preserve", pattern

    rendered = apply_regex_templates(line, patterns.get("regex_templates", []))
    if rendered:
        translation, rule_name = rendered
        return translation, "pattern_template", rule_name
    return None


def resolve_controlled_translation(
    block: dict,
    block_type: str,
    glossary: dict[str, Any],
    patterns: dict[str, Any],
) -> dict[str, str] | None:
    text = normalize_source_text(block.get("source_text", ""))
    exact_map = glossary.get("exact_map", {})
    if text in exact_map:
        return {
            "translation": str(exact_map[text]),
            "translation_source": "glossary_exact",
            "control_rule": text,
        }

    for pattern in patterns.get("preserve_fullmatch_patterns", []):
        if re.fullmatch(pattern, text):
            return {
                "translation": text,
                "translation_source": "pattern_preserve",
                "control_rule": pattern,
            }

    rendered = apply_regex_templates(text, patterns.get("regex_templates", []))
    if rendered:
        translation, rule_name = rendered
        return {
            "translation": translation,
            "translation_source": "pattern_template",
            "control_rule": rule_name,
        }

    lines = [normalize_source_text(line) for line in str(block.get("source_text", "")).splitlines() if line.strip()]
    if len(lines) >= 2:
        translated_lines: list[str] = []
        rule_names: list[str] = []
        source_kinds: list[str] = []
        for line in lines:
            line_result = resolve_line_control(line, glossary, patterns)
            if not line_result:
                translated_lines = []
                break
            translation, source_kind, rule_name = line_result
            translated_lines.append(translation)
            source_kinds.append(source_kind)
            rule_names.append(rule_name)
        if translated_lines:
            source_kind = "glossary_linewise" if any(kind.startswith("glossary") for kind in source_kinds) else "pattern_linewise"
            return {
                "translation": "\n".join(translated_lines),
                "translation_source": source_kind,
                "control_rule": " | ".join(rule_names),
            }

    if block_type == "chart_label" and all(resolve_line_control(line, glossary, patterns) for line in [text]):
        line_result = resolve_line_control(text, glossary, patterns)
        if line_result:
            translation, source_kind, rule_name = line_result
            return {
                "translation": translation,
                "translation_source": source_kind,
                "control_rule": rule_name,
            }
    return None


def collect_relevant_terms(blocks: list[dict], glossary: dict[str, Any], limit: int = 24) -> list[dict[str, str]]:
    block_text = "\n".join(normalize_source_text(block.get("source_text", "")) for block in blocks)
    candidates: list[dict[str, str]] = []
    term_map = glossary.get("term_map", {})
    for source_text, target_text in term_map.items():
        if source_text and source_text in block_text:
            candidates.append({"source": str(source_text), "target": str(target_text)})
        if len(candidates) >= limit:
            break
    return candidates


def build_dynamic_document_context(
    context_records: list[dict[str, Any]],
    glossary: dict[str, Any],
) -> dict[str, Any]:
    headings: list[str] = []
    sidebar_items: list[str] = []
    all_blocks: list[dict[str, Any]] = []
    numeric_dense_blocks = 0

    for record in context_records:
        for block in record.get("blocks", []):
            text = normalize_source_text(block.get("source_text", ""))
            if not text:
                continue
            all_blocks.append(block)
            block_type = classify_block_type(block)
            if block_type == "heading":
                headings.append(text)
            elif block_type == "sidebar_nav":
                sidebar_items.extend(line.strip() for line in text.splitlines() if line.strip())
            if block_type == "chart_label" or (block.get("line_count", 1) >= 5 and re.search(r"\d", text)):
                numeric_dense_blocks += 1

    heading_candidates = dedupe_keep_order(headings)[:16]
    sidebar_candidates = dedupe_keep_order(sidebar_items)[:16]
    term_hits = collect_relevant_terms(all_blocks, glossary, limit=24)

    style_hints = [
        "这是上市公司年度报告语境，译文要保持年报/财报正式书面表达，不使用口语化或营销化措辞。",
    ]
    if numeric_dense_blocks:
        style_hints.append("文档包含财务表格、比率和金额，数字、百分比、币种、年份及缩写必须严格保留。")
    if sidebar_candidates:
        style_hints.append("文档包含目录或侧边导航，导航项宜使用固定、稳定、可复用的正式译法。")
    if heading_candidates:
        style_hints.append("文档存在大量章节标题，标题应优先贴近正式已发布年报的写法，并尽量避免不必要换行。")

    return {
        "sampled_page_count": len(context_records),
        "heading_candidates": heading_candidates,
        "sidebar_candidates": sidebar_candidates,
        "term_hits": term_hits,
        "style_hints": style_hints,
    }


def merge_company_memory_glossary(
    glossary: dict[str, Any],
    company_memory: dict[str, Any],
) -> dict[str, Any]:
    if not company_memory:
        return glossary

    merged = json.loads(json.dumps(glossary, ensure_ascii=False))
    return merged


def classify_runtime_page_archetype(
    page_record: dict[str, Any],
    block_type_map: dict[str, str],
) -> str:
    text_block_count = page_record["text_block_count"]
    headings = sum(1 for block in page_record["blocks"] if block_type_map[block["block_id"]] == "heading")
    sidebars = sum(1 for block in page_record["blocks"] if block_type_map[block["block_id"]] == "sidebar_nav")
    numeric_dense = sum(
        1
        for block in page_record["blocks"]
        if (block.get("line_count", 1) >= 4 and re.search(r"\d", block["source_text"]))
        or block_type_map[block["block_id"]] == "chart_label"
    )
    max_font = max((block.get("font_size_max") or block.get("font_size_avg") or 0) for block in page_record["blocks"]) if page_record["blocks"] else 0

    if page_record["page_no"] == 1 and max_font >= 30 and text_block_count <= 10:
        return "cover_like"
    if numeric_dense >= 8:
        return "table_dense"
    if sidebars >= 1 and text_block_count <= 24:
        return "showcase_narrative"
    if headings >= 1 and text_block_count <= 24:
        return "section_lead"
    if text_block_count >= 30:
        return "dense_narrative"
    return "contents_like"


def retrieve_company_page_examples(
    page_record: dict[str, Any],
    block_type_map: dict[str, str],
    company_memory: dict[str, Any],
    limit: int = 3,
) -> list[dict[str, Any]]:
    if not company_memory:
        return []

    current_heading_signatures: set[str] = set()
    current_signatures: set[str] = set()
    for block in page_record["blocks"]:
        block_id = block["block_id"]
        block_type = block_type_map[block_id]
        signature = build_memory_signature(block["source_text"])
        if not signature:
            continue
        if block_type == "heading":
            current_heading_signatures.add(signature)
            current_signatures.add(signature)
            continue
        if block_type in {"sidebar_nav", "footer"}:
            current_signatures.add(signature)
            continue
        if block_type == "label" and block.get("char_count", 0) <= 30 and block.get("region") == "top":
            current_signatures.add(signature)

    current_archetype = classify_runtime_page_archetype(page_record, block_type_map)
    ranked: list[tuple[int, dict[str, Any]]] = []
    for example in company_memory.get("page_examples", []):
        score = 0
        example_heading = build_memory_signature(example.get("heading", ""))
        example_signatures = set(example.get("signatures", []))
        if example.get("archetype") == current_archetype:
            score += 3
        if example_heading and example_heading in current_heading_signatures:
            score += 8
        score += 2 * len(current_signatures & example_signatures)
        if score > 0:
            ranked.append((score, example))

    ranked.sort(key=lambda item: (-item[0], item[1].get("year", 0), item[1].get("page_no", 0)))
    return [example for _, example in ranked[:limit]]


def select_relevant_company_memory_titles(
    company_memory: dict[str, Any],
    page_record: dict[str, Any] | None,
    limit: int = 8,
) -> list[dict[str, str]]:
    title_entries = iter_company_memory_title_entries(company_memory)
    if not title_entries:
        return []

    if page_record is None:
        return title_entries[:limit]

    page_block_texts: set[str] = set()
    page_lines: set[str] = set()
    for block in page_record["blocks"]:
        normalized = normalize_source_text(block["source_text"])
        if not normalized:
            continue
        page_block_texts.add(normalized)
        page_lines.update(line for line in normalized.splitlines() if line)

    ranked: list[tuple[int, int, int, dict[str, str]]] = []
    for entry in title_entries:
        source = entry["source"]
        source_lines = [line for line in source.splitlines() if line]
        exact_block_match = source in page_block_texts
        line_match_count = sum(1 for line in source_lines if line in page_lines)
        if not exact_block_match and line_match_count != len(source_lines):
            continue
        score = 10 if exact_block_match else 0
        score += line_match_count
        ranked.append((score, len(source_lines), len(source.replace("\n", "")), entry))

    ranked.sort(key=lambda item: (-item[0], item[1], item[2], item[3]["source"]))
    return [entry for _, _, _, entry in ranked[:limit]]


def augment_document_context_with_company_memory(
    document_context: dict[str, Any],
    company_memory: dict[str, Any],
    page_record: dict[str, Any] | None = None,
    block_type_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    if not company_memory:
        return document_context

    merged = dict(document_context)
    merged["company_name"] = company_memory.get("company_name", "")
    merged["company_style_hints"] = company_memory.get("style_hints", [])
    merged["historical_fixed_titles"] = select_relevant_company_memory_titles(
        company_memory=company_memory,
        page_record=page_record,
        limit=10,
    )
    if page_record is not None and block_type_map is not None:
        merged["page_history_examples"] = retrieve_company_page_examples(
            page_record=page_record,
            block_type_map=block_type_map,
            company_memory=company_memory,
        )
    return merged


def render_document_context(document_context: dict[str, Any]) -> str:
    if not document_context:
        return "- 无"

    lines: list[str] = []
    headings = document_context.get("heading_candidates") or []
    sidebar = document_context.get("sidebar_candidates") or []
    term_hits = document_context.get("term_hits") or []
    style_hints = document_context.get("style_hints") or []
    company_name = document_context.get("company_name") or ""
    company_style_hints = document_context.get("company_style_hints") or []
    historical_titles = document_context.get("historical_fixed_titles") or []
    page_history_examples = document_context.get("page_history_examples") or []

    if headings:
        lines.append("章节线索：" + " | ".join(headings[:10]))
    if sidebar:
        lines.append("导航线索：" + " | ".join(sidebar[:10]))
    if term_hits:
        term_line = " | ".join(f"{item['source']} -> {item['target']}" for item in term_hits[:12])
        lines.append("高频术语：" + term_line)
    for hint in style_hints[:4]:
        lines.append(hint)
    if company_name:
        lines.append(f"公司历史语料：{company_name}")
    if historical_titles:
        title_line = " | ".join(
            f"{item['source']} -> {item['target']}" for item in historical_titles[:8]
        )
        lines.append("历史固定标题参考（只复用译法语义，不强制大小写和换行）：" + title_line)
    for hint in company_style_hints[:3]:
        lines.append(hint)
    if page_history_examples:
        lines.append("历史近似页面：")
        for item in page_history_examples[:3]:
            lines.append(
                f"  {item['year']} p{item['page_no']} [{item['archetype']}] {item['heading'] or '(无标题)'}"
            )

    return "\n".join(f"- {line}" for line in lines) if lines else "- 无"


def summarize_block_type_rules(task_spec: dict[str, Any]) -> str:
    policies = task_spec.get("block_type_policies", {})
    lines: list[str] = []
    for block_type, policy in policies.items():
        summary = policy.get("summary")
        if summary:
            lines.append(f"- {block_type}: {summary}")
    return "\n".join(lines)


def build_translation_prompts(
    page_no: int,
    blocks: list[dict],
    source_language: str,
    target_language: str,
    domain_spec: dict[str, Any],
    task_spec: dict[str, Any],
    validation_spec: dict[str, Any],
    glossary: dict[str, Any],
    document_context: dict[str, Any],
) -> tuple[str, str]:
    priorities = "\n".join(f"- {item}" for item in task_spec.get("priorities", []))
    forbidden_actions = "\n".join(f"- {item}" for item in task_spec.get("forbidden_actions", []))
    protected_tokens = "\n".join(f"- {item}" for item in validation_spec.get("protected_token_categories", []))
    block_rules = summarize_block_type_rules(task_spec)
    relevant_terms = collect_relevant_terms(blocks, glossary)
    dynamic_context = render_document_context(document_context)

    system_prompt = (
        "你是一个用于 PDF 原位回填的专业翻译助手。\n"
        "你的任务不是总结，不是改写，不是润色，而是生成适合放回原始版面的高保真译文。\n"
        "只返回 JSON，不要输出任何解释。\n\n"
        f"文档场景：{domain_spec.get('scenario')}\n"
        f"文档类型：{domain_spec.get('document_type')}\n"
        f"文档特征：{domain_spec.get('document_characteristics')}\n"
        f"目标风格：{domain_spec.get('target_register')}\n"
        f"目标读者：{domain_spec.get('target_audience')}\n\n"
        "动态文档背景：\n"
        f"{dynamic_context}\n\n"
        "任务优先级：\n"
        f"{priorities}\n\n"
        "禁止项：\n"
        f"{forbidden_actions}\n\n"
        "受保护信息：\n"
        f"{protected_tokens}\n\n"
        "块类型规则：\n"
        f"{block_rules}\n\n"
        "硬约束：\n"
        "- 不要摘要，不要口语化，不要投研笔记化，不要营销化。\n"
        "- 不要把正式标题随意缩写成 CEO、NBV、YoY、H2 等写法，除非原文本身就是这种写法。\n"
        "- 标题、栏目名、导航项、图表标签、页眉页脚必须保持正式、稳定、可出版。\n"
        "- 数字、百分比、货币、年份、专有名词、公司名、人名、地名必须准确。\n"
        "- 如果译文用于上市公司年报，要优先贴近年报/财报正式表达，不使用聊天式表达。\n"
        "- block_id 必须原样保留。\n"
        "- 返回格式：{\"translations\": [{\"block_id\": \"...\", \"translation\": \"...\"}]}\n"
    )

    payload = {
        "page_no": page_no,
        "source_language": source_language,
        "target_language": target_language,
        "relevant_terms": relevant_terms,
        "blocks": [
            {
                "block_id": block["block_id"],
                "block_type": block.get("block_type"),
                "source_text": block["source_text"],
                "line_count": block.get("line_count"),
                "char_count": block.get("char_count"),
                "region": block.get("region"),
                "font_size_avg": block.get("font_size_avg"),
            }
            for block in blocks
        ],
    }
    user_prompt = (
        "请将以下文本块从源语言翻译为目标语言，用于上市公司年报 PDF 的原位回填。\n"
        "要求高保真、正式、可出版，不要摘要，不要解释。\n"
        "术语表和动态文档背景优先于自由翻译。\n"
        "只输出严格 JSON。\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    return system_prompt, user_prompt


def build_compact_prompts(
    page_no: int,
    blocks: list[dict],
    source_language: str,
    target_language: str,
    domain_spec: dict[str, Any],
    validation_spec: dict[str, Any],
    document_context: dict[str, Any],
) -> tuple[str, str]:
    protected_tokens = "\n".join(f"- {item}" for item in validation_spec.get("protected_token_categories", []))
    dynamic_context = render_document_context(document_context)
    system_prompt = (
        "你是一个用于 PDF 原位回填的精修助手。\n"
        "你处理的是已经翻译过、但版面过紧的文本块。\n"
        "你的目标不是重写内容，而是在尽量不损失信息和正式风格的前提下，做最小必要压缩。\n"
        "只返回 JSON，不要输出任何解释。\n\n"
        f"文档场景：{domain_spec.get('scenario')}\n"
        f"目标风格：{domain_spec.get('target_register')}\n\n"
        "动态文档背景：\n"
        f"{dynamic_context}\n\n"
        "受保护信息：\n"
        f"{protected_tokens}\n\n"
        "硬约束：\n"
        "- 只做最小幅度缩短，不要摘要化，不要改成分析师速记风格。\n"
        "- 不要随意缩写正式标题、栏目名、导航项、图表标签、页眉页脚。\n"
        "- 如果原文是完整句，优先保持完整句。\n"
        "- block_id 必须原样保留。\n"
        "- 返回格式：{\"translations\": [{\"block_id\": \"...\", \"translation\": \"...\"}]}\n"
    )
    payload = {
        "page_no": page_no,
        "source_language": source_language,
        "target_language": target_language,
        "problem_blocks": blocks,
    }
    user_prompt = (
        "以下文本块版面过紧。请在不改变核心含义和正式风格的前提下，仅做最小必要压缩。\n"
        "不要摘要，不要解释，只输出严格 JSON。\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    return system_prompt, user_prompt


def build_language_repair_prompts(
    page_no: int,
    blocks: list[dict[str, Any]],
    source_language: str,
    target_language: str,
) -> tuple[str, str]:
    system_prompt = (
        "你是一个用于 PDF 原位回填的翻译修复助手。\n"
        "上一轮输出中，部分文本块没有严格使用目标语言，或者出现了乱码/源语言残留。\n"
        "你的任务是只修复这些异常块。\n"
        "只返回 JSON，不要输出任何解释。\n\n"
        "硬约束：\n"
        f"- 目标语言必须是 {target_language}。\n"
        "- 不允许保留中文、乱码或源语言残留，除非是受保护的数字、百分比、年份、货币或标准缩写。\n"
        "- 不要摘要，不要改写成另一种风格。\n"
        "- 保留 block_id。\n"
        "- 返回格式：{\"translations\": [{\"block_id\": \"...\", \"translation\": \"...\"}]}\n"
    )
    payload = {
        "page_no": page_no,
        "source_language": source_language,
        "target_language": target_language,
        "problem_blocks": blocks,
    }
    user_prompt = (
        "以下文本块的上一轮译文不符合目标语言要求，请重新给出目标语言译文。\n"
        "只输出严格 JSON。\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    return system_prompt, user_prompt


def render_page(page: fitz.Page, render_dpi: int) -> Image.Image:
    zoom = render_dpi / 72
    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)


def int_to_rgb(value: int) -> tuple[int, int, int]:
    return ((value >> 16) & 255, (value >> 8) & 255, value & 255)


def rgb255_to_pdf(value: tuple[int, int, int]) -> tuple[float, float, float]:
    return tuple(channel / 255 for channel in value)


def make_builtin_font_spec(fontname: str) -> dict[str, Any]:
    return {
        "fontname": fontname,
        "fontfile": None,
    }


def make_system_font_spec(alias: str, filename: str) -> dict[str, Any] | None:
    path = SYSTEM_FONT_DIR / filename
    if not path.exists():
        return None
    return {
        "fontname": alias,
        "fontfile": str(path),
    }


def dedupe_font_specs(specs: list[dict[str, Any] | None]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    resolved: list[dict[str, Any]] = []
    for spec in specs:
        if not spec:
            continue
        key = (str(spec["fontname"]), str(spec.get("fontfile") or ""))
        if key in seen:
            continue
        seen.add(key)
        resolved.append(spec)
    return resolved


def resolve_font_candidates(font_names: list[str]) -> list[dict[str, Any]]:
    text = " ".join(font_names).lower()
    is_bold = any(token in text for token in ["bold", "xbold", "black", "heavy", "medi", "demi"])
    is_condensed = any(token in text for token in ["condensed", "narrow", "cn", "compressed", "everest"])
    is_din = "din" in text
    is_serif = any(token in text for token in ["times", "serif", "garamond", "georgia", "minion"])

    specs: list[dict[str, Any] | None] = []
    if is_serif:
        specs.extend(
            [
                make_builtin_font_spec("Times-Bold" if is_bold else "Times-Roman"),
                make_builtin_font_spec("Helvetica-Bold" if is_bold else "Helvetica"),
            ]
        )
        return dedupe_font_specs(specs)

    if is_condensed or is_din or "mhei" in text:
        if is_bold:
            specs.extend(
                [
                    make_system_font_spec("F_ARIALNB", "ARIALNB.TTF"),
                    make_system_font_spec("F_FRAMDCN", "FRAMDCN.TTF"),
                    make_system_font_spec("F_ARIALN", "ARIALN.TTF"),
                    make_builtin_font_spec("Helvetica-Bold"),
                    make_builtin_font_spec("Helvetica"),
                ]
            )
        else:
            specs.extend(
                [
                    make_system_font_spec("F_ARIALN", "ARIALN.TTF"),
                    make_system_font_spec("F_BAHN", "bahnschrift.ttf"),
                    make_builtin_font_spec("Helvetica"),
                ]
            )
    else:
        if is_bold:
            specs.extend(
                [
                    make_system_font_spec("F_ARIALNB", "ARIALNB.TTF"),
                    make_system_font_spec("F_ARIALN", "ARIALN.TTF"),
                    make_builtin_font_spec("Helvetica-Bold"),
                    make_system_font_spec("F_CALIBRIB", "calibrib.ttf"),
                    make_builtin_font_spec("Helvetica"),
                ]
            )
        else:
            specs.extend(
                [
                    make_system_font_spec("F_ARIALN", "ARIALN.TTF"),
                    make_builtin_font_spec("Helvetica"),
                    make_system_font_spec("F_CALIBRI", "calibri.ttf"),
                ]
            )

    specs.append(make_builtin_font_spec("Times-Roman"))
    return dedupe_font_specs(specs)


def normalize_font_specs(preferred_fonts: list[Any] | None) -> list[dict[str, Any]]:
    if not preferred_fonts:
        return [make_builtin_font_spec("Helvetica"), make_builtin_font_spec("Times-Roman")]

    specs: list[dict[str, Any] | None] = []
    for item in preferred_fonts:
        if isinstance(item, dict):
            specs.append(item)
        elif isinstance(item, str):
            specs.append(make_builtin_font_spec(item))
    return dedupe_font_specs(specs)


def get_font_object(fontfile: str) -> fitz.Font:
    cached = FONT_OBJECT_CACHE.get(fontfile)
    if cached is None:
        cached = fitz.Font(fontfile=fontfile)
        FONT_OBJECT_CACHE[fontfile] = cached
    return cached


def measure_text_width(text: str, font_spec: dict[str, Any], fontsize: float = 1.0) -> float:
    fontfile = font_spec.get("fontfile")
    if fontfile:
        return get_font_object(str(fontfile)).text_length(text, fontsize=fontsize)
    return fitz.get_text_length(text, fontname=str(font_spec["fontname"]), fontsize=fontsize)


def ensure_page_font(page: fitz.Page, font_spec: dict[str, Any]) -> str:
    fontname = str(font_spec["fontname"])
    fontfile = font_spec.get("fontfile")
    if fontfile:
        try:
            page.insert_font(fontname=fontname, fontfile=str(fontfile))
        except RuntimeError:
            pass
    return fontname


def infer_block_style(page: fitz.Page, block: dict) -> dict:
    rect = fitz.Rect(block["bbox"])
    raw_dict = page.get_text("rawdict")
    colors: Counter[int] = Counter()
    sizes: list[float] = []
    font_names: list[str] = list(block.get("font_names", []))

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
                if span.get("font"):
                    font_names.append(str(span.get("font")))

    color = int_to_rgb(colors.most_common(1)[0][0]) if colors else (0, 0, 0)
    font_size = max(sizes) if sizes else float(block.get("font_size_avg") or 10)
    font_specs = resolve_font_candidates(font_names)
    return {
        "color_rgb255": color,
        "font_size": font_size,
        "font_name": str(font_specs[0]["fontname"]),
        "font_specs": font_specs,
        "font_names": dedupe_keep_order(font_names),
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
            font_names: list[str] = []
            colors: Counter[int] = Counter()
            for span in line.get("spans", []):
                span_text = "".join(char["c"] for char in span.get("chars", []))
                if not span_text.strip():
                    continue
                texts.append(span_text)
                size = float(span.get("size", size or block.get("font_size_avg") or 10))
                span_rect = fitz.Rect(span["bbox"])
                line_bbox = span_rect if line_bbox is None else line_bbox | span_rect
                if span.get("font"):
                    font_names.append(str(span.get("font")))
                colors[span.get("color", 0)] += len(span_text)
            if texts and line_bbox is not None:
                color = int_to_rgb(colors.most_common(1)[0][0]) if colors else (0, 0, 0)
                font_specs = resolve_font_candidates(font_names or list(block.get("font_names", [])))
                segments.append(
                    {
                        "text": "".join(texts).strip(),
                        "bbox": [line_bbox.x0, line_bbox.y0, line_bbox.x1, line_bbox.y1],
                        "font_size": size or float(block.get("font_size_avg") or 10),
                        "font_names": dedupe_keep_order(font_names),
                        "font_specs": font_specs,
                        "color_rgb255": color,
                    }
                )
    segments.sort(key=lambda item: (round(item["bbox"][1], 2), item["bbox"][0]))
    segments = expand_segments_to_inferred_columns(block, segments)
    return segments


def expand_segments_to_inferred_columns(
    block: dict,
    segments: list[dict[str, Any]],
    merge_tolerance: float = 6.0,
) -> list[dict[str, Any]]:
    if len(segments) < 4:
        return segments

    block_rect = fitz.Rect(block["bbox"])
    if block_rect.width < 250:
        return segments

    columns: list[dict[str, float]] = []
    for segment in sorted(segments, key=lambda item: item["bbox"][0]):
        x0, _, x1, _ = segment["bbox"]
        if columns and x0 <= columns[-1]["x1"] + merge_tolerance:
            columns[-1]["x0"] = min(columns[-1]["x0"], x0)
            columns[-1]["x1"] = max(columns[-1]["x1"], x1)
        else:
            columns.append({"x0": x0, "x1": x1})

    if len(columns) < 4:
        return segments

    column_bounds: list[tuple[float, float]] = []
    for index, column in enumerate(columns):
        if index == 0:
            left = block_rect.x0
        else:
            left = (columns[index - 1]["x1"] + column["x0"]) / 2
        if index == len(columns) - 1:
            right = block_rect.x1
        else:
            right = (column["x1"] + columns[index + 1]["x0"]) / 2
        column_bounds.append((left, right))

    expanded_segments: list[dict[str, Any]] = []
    for segment in segments:
        x0, y0, x1, y1 = segment["bbox"]
        center = (x0 + x1) / 2
        column_index = min(
            range(len(columns)),
            key=lambda idx: abs(center - ((columns[idx]["x0"] + columns[idx]["x1"]) / 2)),
        )
        left, right = column_bounds[column_index]
        expanded_segments.append(
            {
                **segment,
                "bbox": [
                    max(block_rect.x0, left - 0.5),
                    y0,
                    min(block_rect.x1, right + 0.5),
                    y1,
                ],
                "column_index": column_index,
            }
        )
    return expanded_segments


def is_numericish(text: str) -> bool:
    normalized = re.sub(r"[\s,.\-()%+/]", "", text)
    return bool(normalized) and normalized.isdigit()


def is_tiny_numeric_block(block: dict, text: str) -> bool:
    x0, y0, x1, y1 = block["bbox"]
    width = x1 - x0
    height = y1 - y0
    return block.get("line_count", 1) == 1 and is_numericish(text) and width <= 18 and height <= 9


def is_single_line_block(block: dict, translation: str) -> bool:
    x0, y0, x1, y1 = block["bbox"]
    width = x1 - x0
    height = y1 - y0
    return (
        int(block.get("line_count") or 1) == 1
        and "\n" not in translation.strip()
        and width >= 40
        and height <= 32
    )


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
    preferred_fonts: list[Any] | None = None,
    min_font_size: float = 2.5,
    commit: bool = False,
) -> tuple[float, str]:
    font_specs = normalize_font_specs(preferred_fonts)
    color_pdf = rgb255_to_pdf(color_rgb255)
    best_fit: tuple[float, dict[str, Any], str] | None = None
    best_success: tuple[float, dict[str, Any], str] | None = None

    for font_spec in font_specs:
        width_at_one = measure_text_width(text, font_spec, fontsize=1)
        if width_at_one <= 0:
            continue
        size_by_width = rect.width / width_at_one
        size_by_height = rect.height * 0.95
        start_size = min(
            max(preferred_font_size, min_font_size),
            size_by_width,
            size_by_height,
        )
        size = max(start_size, min_font_size)
        while size >= min_font_size:
            font_name = ensure_page_font(page, font_spec)
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
                status = "ok" if size >= preferred_font_size * 0.85 else "font_shrink"
                if best_success is None or size > best_success[0]:
                    best_success = (size, font_spec, status)
                break
            if best_fit is None or size > best_fit[0]:
                best_fit = (size, font_spec, "overflow")
            size -= 0.25

    selected = best_success or best_fit
    if selected and commit:
        size, font_spec, status = selected
        font_name = ensure_page_font(page, font_spec)
        shape = page.new_shape()
        shape.insert_textbox(
            rect,
            text,
            fontsize=size,
            fontname=font_name,
            color=color_pdf,
            align=0,
            lineheight=1.0,
        )
        shape.commit()
        return size, status

    if selected:
        return selected[0], selected[2]
    return min_font_size, "overflow"


def textbox_fit(
    page: fitz.Page,
    rect: fitz.Rect,
    text: str,
    style: dict,
    min_font_size: float = 5.0,
    commit: bool = False,
) -> tuple[float, str]:
    color_pdf = rgb255_to_pdf(style["color_rgb255"])
    font_specs = normalize_font_specs(style.get("font_specs"))
    start_size = max(min_font_size, float(style["font_size"]))
    best_fit: tuple[float, dict[str, Any], float, str] | None = None
    best_success: tuple[float, dict[str, Any], float, str] | None = None

    for font_spec in font_specs:
        font_name = ensure_page_font(page, font_spec)
        for lineheight in [1.0, 0.95, 0.9, 0.86]:
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
                    status = "ok" if font_size >= style["font_size"] * 0.85 else "font_shrink"
                    if best_success is None or font_size > best_success[0]:
                        best_success = (font_size, font_spec, lineheight, status)
                    break
                if best_fit is None or font_size > best_fit[0]:
                    best_fit = (font_size, font_spec, lineheight, "overflow")
                font_size -= 0.5

    selected = best_success or best_fit
    if selected and commit:
        font_size, font_spec, lineheight, status = selected
        font_name = ensure_page_font(page, font_spec)
        shape = page.new_shape()
        shape.insert_textbox(
            rect,
            text,
            fontsize=font_size,
            fontname=font_name,
            color=color_pdf,
            align=0,
            lineheight=lineheight,
        )
        shape.commit()
        return font_size, status

    if selected:
        return selected[0], selected[3]
    return min_font_size, "overflow"


def overlay_segmented_translation(
    page: fitz.Page,
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
            "color_rgb255": segment.get("color_rgb255", base_style["color_rgb255"]),
            "font_size": segment.get("font_size", base_style["font_size"]),
            "font_name": base_style["font_name"],
            "font_specs": segment.get("font_specs") or base_style.get("font_specs"),
        }
        if is_numericish(line_text):
            fitted_size, seg_status = insert_single_line_best_fit(
                page=page,
                rect=seg_rect,
                text=line_text,
                color_rgb255=segment_style["color_rgb255"],
                preferred_font_size=segment_style["font_size"],
                preferred_fonts=segment_style.get("font_specs") or ["Times-Roman", "Helvetica"],
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
                preferred_fonts=segment_style.get("font_specs") or ["Helvetica-Bold", "Helvetica", "Times-Roman"],
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


def fit_translation_block(
    page: fitz.Page,
    block: dict,
    translation: str,
    style: dict,
    raw_segments: list[dict[str, Any]] | None = None,
    commit: bool = False,
) -> tuple[float, str, str]:
    raw_segments = raw_segments if raw_segments is not None else extract_raw_line_segments(page, block)
    if is_segment_overlay_candidate(block, translation, raw_segments):
        font_ratio, fit_status = overlay_segmented_translation(
            page=page,
            translation=translation,
            base_style=style,
            segments=raw_segments,
            commit=commit,
        )
        return font_ratio * max(1.0, style["font_size"]), fit_status, "segmented"
    if is_tiny_numeric_block(block, translation):
        font_size, fit_status = insert_single_line_best_fit(
            page=page,
            rect=fitz.Rect(block["bbox"]),
            text=translation,
            color_rgb255=style["color_rgb255"],
            preferred_font_size=style["font_size"],
            preferred_fonts=style.get("font_specs") or ["Times-Roman", "Helvetica"],
            min_font_size=2.5,
            commit=commit,
        )
        return font_size, fit_status, "tiny_numeric"
    if is_single_line_block(block, translation):
        font_size, fit_status = insert_single_line_best_fit(
            page=page,
            rect=fitz.Rect(block["bbox"]),
            text=translation,
            color_rgb255=style["color_rgb255"],
            preferred_font_size=style["font_size"],
            preferred_fonts=style.get("font_specs")
            or [style["font_name"], "Helvetica-Bold", "Helvetica", "Times-Roman"],
            min_font_size=4.0,
            commit=commit,
        )
        return font_size, fit_status, "single_line"
    font_size, fit_status = textbox_fit(
        page=page,
        rect=fitz.Rect(block["bbox"]),
        text=translation,
        style=style,
        commit=commit,
    )
    return font_size, fit_status, "textbox"


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


class AnthropicGatewayClient:
    def __init__(self, base_url: str, api_key: str, model: str, max_output_tokens: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_output_tokens = max_output_tokens

    @classmethod
    def from_env(cls, model: str, max_output_tokens: int) -> "AnthropicGatewayClient":
        base_url = os.environ.get("ANTHROPIC_BASE_URL")
        api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN")
        if not base_url or not api_key:
            raise RuntimeError(
                "Missing ANTHROPIC_BASE_URL or ANTHROPIC_AUTH_TOKEN in the environment."
            )
        return cls(
            base_url=base_url,
            api_key=api_key,
            model=model,
            max_output_tokens=max_output_tokens,
        )

    def _post_messages(self, system_prompt: str, user_prompt: str) -> tuple[dict[str, Any], dict[str, Any]]:
        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": self.max_output_tokens,
            "temperature": 0,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        return payload, response.json()

    def _write_api_exchange(
        self,
        api_log_path: Path,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any],
        meta: dict[str, Any] | None = None,
    ) -> None:
        write_json_file(
            api_log_path,
            {
                "meta": meta or {},
                "request": request_payload,
                "response": response_payload,
            },
        )

    def translate_blocks(
        self,
        page_no: int,
        blocks: list[dict],
        source_language: str,
        target_language: str,
        api_log_path: Path,
        domain_spec: dict[str, Any],
        task_spec: dict[str, Any],
        validation_spec: dict[str, Any],
        glossary: dict[str, Any],
        document_context: dict[str, Any],
    ) -> dict[str, str]:
        system_prompt, user_prompt = build_translation_prompts(
            page_no=page_no,
            blocks=blocks,
            source_language=source_language,
            target_language=target_language,
            domain_spec=domain_spec,
            task_spec=task_spec,
            validation_spec=validation_spec,
            glossary=glossary,
            document_context=document_context,
        )
        request_payload, response = self._post_messages(system_prompt, user_prompt)
        self._write_api_exchange(
            api_log_path,
            request_payload=request_payload,
            response_payload=response,
            meta={"stage": "initial_translation", "page_no": page_no},
        )
        return parse_translation_map(response, expected_block_ids=[block["block_id"] for block in blocks])

    def compact_blocks(
        self,
        page_no: int,
        blocks: list[dict],
        source_language: str,
        target_language: str,
        api_log_path: Path,
        domain_spec: dict[str, Any],
        validation_spec: dict[str, Any],
        document_context: dict[str, Any],
    ) -> dict[str, str]:
        system_prompt, user_prompt = build_compact_prompts(
            page_no=page_no,
            blocks=blocks,
            source_language=source_language,
            target_language=target_language,
            domain_spec=domain_spec,
            validation_spec=validation_spec,
            document_context=document_context,
        )
        request_payload, response = self._post_messages(system_prompt, user_prompt)
        self._write_api_exchange(
            api_log_path,
            request_payload=request_payload,
            response_payload=response,
            meta={"stage": "compact_translation", "page_no": page_no},
        )
        return parse_translation_map(
            response,
            expected_block_ids=[block["block_id"] for block in blocks],
            strict=False,
        )

    def repair_invalid_blocks(
        self,
        page_no: int,
        blocks: list[dict[str, Any]],
        source_language: str,
        target_language: str,
        api_log_path: Path,
    ) -> dict[str, str]:
        system_prompt, user_prompt = build_language_repair_prompts(
            page_no=page_no,
            blocks=blocks,
            source_language=source_language,
            target_language=target_language,
        )
        request_payload, response = self._post_messages(system_prompt, user_prompt)
        self._write_api_exchange(
            api_log_path,
            request_payload=request_payload,
            response_payload=response,
            meta={"stage": "language_repair", "page_no": page_no},
        )
        return parse_translation_map(
            response,
            expected_block_ids=[block["block_id"] for block in blocks],
            strict=False,
        )


def extract_response_text(response_json: dict[str, Any]) -> str:
    content = response_json.get("content", [])
    text_parts = [item.get("text", "") for item in content if item.get("type") == "text"]
    return "\n".join(text_parts).strip()


def strip_code_fence(text: str) -> str:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 3:
            candidate = "\n".join(lines[1:-1]).strip()
    return candidate


def decode_model_string(value: str) -> str:
    return (
        value.replace("\\r", "\r")
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
    )


def parse_translation_pairs_from_text(text: str) -> dict[str, str]:
    candidate = strip_code_fence(text)
    pair_pattern = re.compile(
        r'"block_id"\s*:\s*"(?P<block_id>[^"]+)"\s*,\s*"translation"\s*:\s*"(?P<translation>.*?)"\s*(?=\}\s*,?\s*(?:\{|\]))',
        re.S,
    )
    translation_map: dict[str, str] = {}
    for match in pair_pattern.finditer(candidate):
        block_id = match.group("block_id").strip()
        translation = decode_model_string(match.group("translation").strip())
        if block_id:
            translation_map[block_id] = translation
    return translation_map


def parse_translation_map(
    response_json: dict[str, Any],
    expected_block_ids: list[str],
    strict: bool = True,
) -> dict[str, str]:
    text = extract_response_text(response_json)
    translation_map: dict[str, str] = {}
    try:
        payload = parse_json_from_text(text)
        translations = payload.get("translations", [])
        for item in translations:
            block_id = item.get("block_id")
            translation = item.get("translation")
            if isinstance(block_id, str) and isinstance(translation, str):
                translation_map[block_id] = translation.strip()
    except Exception:
        translation_map = parse_translation_pairs_from_text(text)

    missing = [block_id for block_id in expected_block_ids if block_id not in translation_map]
    if strict and missing:
        raise ValueError(f"Missing translations for block ids: {missing}")
    return translation_map


def parse_json_from_text(text: str) -> dict[str, Any]:
    candidate = strip_code_fence(text)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(candidate[start : end + 1])


def normalize_translation_text(block: dict, translation: str, target_language: str) -> str:
    lines = [" ".join(line.split()) for line in translation.strip().splitlines()]
    text = "\n".join(line for line in lines if line)
    if block.get("region") == "bottom" and block.get("line_count", 1) == 1:
        text = text.replace("\n", " ")
    return text


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text))


def is_translation_valid_for_target(text: str, target_language: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    target = target_language.lower()
    if target == "english":
        return not contains_cjk(cleaned)
    return True


def build_invalid_language_request_blocks(
    blocks: list[dict[str, Any]],
    translations: dict[str, str],
    target_language: str,
    translation_sources: dict[str, str],
) -> list[dict[str, Any]]:
    invalid_blocks: list[dict[str, Any]] = []
    for block in blocks:
        block_id = block["block_id"]
        source_kind = translation_sources.get(block_id, "")
        if not source_kind.startswith("model"):
            continue
        translation = translations.get(block_id, "")
        if is_translation_valid_for_target(translation, target_language):
            continue
        invalid_blocks.append(
            {
                "block_id": block_id,
                "source_text": block["source_text"],
                "current_translation": translation,
                "block_type": block.get("block_type"),
                "line_count": block.get("line_count"),
                "char_count": block.get("char_count"),
            }
        )
    return invalid_blocks


def evaluate_translations(
    page: fitz.Page,
    blocks: list[dict],
    styles: dict[str, dict],
    translations: dict[str, str],
    segment_map: dict[str, list[dict[str, Any]]],
) -> list[dict]:
    evaluations: list[dict] = []
    for block in blocks:
        block_id = block["block_id"]
        style = styles[block_id]
        font_size, fit_status, layout_mode = fit_translation_block(
            page=page,
            block=block,
            translation=translations[block_id],
            style=style,
            raw_segments=segment_map.get(block_id),
            commit=False,
        )
        evaluations.append(
            {
                "block_id": block_id,
                "translation": translations[block_id],
                "fit_status": fit_status,
                "font_size": round(font_size, 2),
                "font_ratio": round(font_size / max(1.0, style["font_size"]), 3),
                "layout_mode": layout_mode,
            }
        )
    return evaluations


def index_evaluations(evaluations: list[dict]) -> dict[str, dict]:
    return {item["block_id"]: item for item in evaluations}


def build_compact_request_blocks(
    blocks: list[dict],
    evaluations: list[dict],
    styles: dict[str, dict],
    compact_threshold: float,
    translation_sources: dict[str, str],
    block_type_map: dict[str, str],
    validation_spec: dict[str, Any],
) -> list[dict]:
    evaluation_map = index_evaluations(evaluations)
    problem_blocks: list[dict] = []
    allowed_block_types = set(validation_spec.get("compact_retry_allowed_block_types", []))
    for block in blocks:
        block_id = block["block_id"]
        evaluation = evaluation_map[block["block_id"]]
        translation_source = translation_sources.get(block_id, "")
        if not translation_source.startswith("model"):
            continue
        if allowed_block_types and block_type_map.get(block_id) not in allowed_block_types:
            continue
        if (
            evaluation["fit_status"] == "overflow"
            or evaluation["font_ratio"] < compact_threshold
        ):
            problem_blocks.append(
                {
                    "block_id": block_id,
                    "block_type": block_type_map.get(block_id),
                    "source_text": block["source_text"],
                    "current_translation": evaluation["translation"],
                    "translation_source": translation_source,
                    "fit_status": evaluation["fit_status"],
                    "current_font_ratio": evaluation["font_ratio"],
                    "line_count": block.get("line_count"),
                    "char_count": block.get("char_count"),
                    "bbox": block["bbox"],
                    "font_size_avg": block.get("font_size_avg"),
                    "suggested_font": styles[block_id]["font_name"],
                }
            )
    return problem_blocks


def chunk_translation_blocks(
    blocks: list[dict[str, Any]],
    max_blocks: int = 8,
    max_chars: int = 320,
) -> list[list[dict[str, Any]]]:
    batches: list[list[dict[str, Any]]] = []
    current_batch: list[dict[str, Any]] = []
    current_chars = 0

    for block in blocks:
        block_chars = int(block.get("char_count") or len(normalize_source_text(block.get("source_text", "")).replace("\n", "")))
        if current_batch and (len(current_batch) >= max_blocks or current_chars + block_chars > max_chars):
            batches.append(current_batch)
            current_batch = []
            current_chars = 0
        current_batch.append(block)
        current_chars += block_chars

    if current_batch:
        batches.append(current_batch)
    return batches


def write_json_file(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    page_numbers = parse_page_numbers(args.pages)
    page_records = load_page_records(args.blocks_jsonl, set(page_numbers))
    context_records = load_context_page_records(args.blocks_jsonl, args.document_context_pages)
    domain_spec = load_json_file(args.domain_spec)
    task_spec = load_json_file(args.task_spec)
    validation_spec = load_json_file(args.validation_spec)
    glossary = load_json_file(args.glossary)
    company_memory = load_optional_json_file(args.company_memory)
    glossary = merge_company_memory_glossary(glossary, company_memory)
    patterns = load_json_file(args.patterns)
    document_context = build_dynamic_document_context(context_records, glossary)
    document_context = augment_document_context_with_company_memory(document_context, company_memory)
    client: AnthropicGatewayClient | None = None

    original_dir = args.output_dir / "original"
    redacted_dir = args.output_dir / "redacted"
    translated_dir = args.output_dir / "translated"
    comparison_dir = args.output_dir / "comparison"
    api_logs_dir = args.output_dir / "api_logs"
    for directory in [original_dir, redacted_dir, translated_dir, comparison_dir, api_logs_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    original_doc = fitz.open(args.input)
    redacted_doc = fitz.open(args.input)
    translated_doc = fitz.open(args.input)
    translations_report: list[dict[str, Any]] = []
    page_report: list[dict[str, Any]] = []
    translations_path = args.output_dir / "translations.json"
    report_path = args.output_dir / "report.json"
    document_context_path = args.output_dir / "document_context.json"
    write_json_file(document_context_path, document_context)

    try:
        for page_no in page_numbers:
            try:
                page_record = page_records.get(page_no)
                if not page_record:
                    page_report.append({"page_no": page_no, "status": "missing_page_record"})
                    continue

                original_page = original_doc.load_page(page_no - 1)
                original_image = render_page(original_page, args.render_dpi)
                styles = {
                    block["block_id"]: infer_block_style(original_page, block)
                    for block in page_record["blocks"]
                }
                segment_map = {
                    block["block_id"]: extract_raw_line_segments(original_page, block)
                    for block in page_record["blocks"]
                }
                block_type_map = {
                    block["block_id"]: classify_block_type(block)
                    for block in page_record["blocks"]
                }
                page_document_context = augment_document_context_with_company_memory(
                    document_context=document_context,
                    company_memory=company_memory,
                    page_record=page_record,
                    block_type_map=block_type_map,
                )
                seeded_translations: dict[str, str] = {}
                translation_sources: dict[str, str] = {}
                control_rules: dict[str, str] = {}
                model_blocks: list[dict[str, Any]] = []
                for block in page_record["blocks"]:
                    block_id = block["block_id"]
                    block_type = block_type_map[block_id]
                    controlled = resolve_controlled_translation(
                        block=block,
                        block_type=block_type,
                        glossary=glossary,
                        patterns=patterns,
                    )
                    if controlled:
                        seeded_translations[block_id] = normalize_translation_text(
                            block, controlled["translation"], args.target_language
                        )
                        translation_sources[block_id] = controlled["translation_source"]
                        control_rules[block_id] = controlled["control_rule"]
                    else:
                        model_blocks.append(
                            {
                                **block,
                                "block_type": block_type,
                            }
                        )

                translations = dict(seeded_translations)
                if model_blocks:
                    if client is None:
                        client = AnthropicGatewayClient.from_env(args.model, args.max_output_tokens)
                    model_batches = chunk_translation_blocks(model_blocks)
                    for batch_index, model_batch in enumerate(model_batches, start=1):
                        initial_log_path = api_logs_dir / f"page_{page_no:04d}_initial_translation_batch_{batch_index:02d}.json"
                        model_translations = client.translate_blocks(
                            page_no=page_no,
                            blocks=model_batch,
                            source_language=args.source_language,
                            target_language=args.target_language,
                            api_log_path=initial_log_path,
                            domain_spec=domain_spec,
                            task_spec=task_spec,
                            validation_spec=validation_spec,
                            glossary=glossary,
                            document_context=page_document_context,
                        )
                        for block in model_batch:
                            block_id = block["block_id"]
                            translations[block_id] = normalize_translation_text(
                                block, model_translations[block_id], args.target_language
                            )
                            translation_sources[block_id] = "model_initial"
                            control_rules[block_id] = ""

                    invalid_language_blocks = build_invalid_language_request_blocks(
                        blocks=model_blocks,
                        translations=translations,
                        target_language=args.target_language,
                        translation_sources=translation_sources,
                    )
                    if invalid_language_blocks:
                        repair_log_path = api_logs_dir / f"page_{page_no:04d}_language_repair_initial.json"
                        repaired_map = client.repair_invalid_blocks(
                            page_no=page_no,
                            blocks=invalid_language_blocks,
                            source_language=args.source_language,
                            target_language=args.target_language,
                            api_log_path=repair_log_path,
                        )
                        for block in model_blocks:
                            block_id = block["block_id"]
                            if block_id not in repaired_map:
                                continue
                            repaired_text = normalize_translation_text(
                                block, repaired_map[block_id], args.target_language
                            )
                            if is_translation_valid_for_target(repaired_text, args.target_language):
                                translations[block_id] = repaired_text
                                translation_sources[block_id] = "model_repair_initial"

                initial_eval = evaluate_translations(
                    page=original_page,
                    blocks=page_record["blocks"],
                    styles=styles,
                    translations=translations,
                    segment_map=segment_map,
                )

                compact_requests = build_compact_request_blocks(
                    blocks=page_record["blocks"],
                    evaluations=initial_eval,
                    styles=styles,
                    compact_threshold=args.compact_threshold,
                    translation_sources=translation_sources,
                    block_type_map=block_type_map,
                    validation_spec=validation_spec,
                )

                compact_map: dict[str, str] = {}
                if compact_requests:
                    if client is None:
                        client = AnthropicGatewayClient.from_env(args.model, args.max_output_tokens)
                    compact_log_path = api_logs_dir / f"page_{page_no:04d}_compact_translation.json"
                    compact_map = client.compact_blocks(
                        page_no=page_no,
                        blocks=compact_requests,
                        source_language=args.source_language,
                        target_language=args.target_language,
                        api_log_path=compact_log_path,
                        domain_spec=domain_spec,
                        validation_spec=validation_spec,
                        document_context=page_document_context,
                    )
                    compact_map = {
                        block["block_id"]: normalize_translation_text(
                            block, compact_map[block["block_id"]], args.target_language
                        )
                        for block in page_record["blocks"]
                        if block["block_id"] in compact_map
                    }
                    translations.update(compact_map)
                    translation_sources.update({block_id: "model_compact" for block_id in compact_map})

                    compact_blocks_full = [
                        {**block, "block_type": block_type_map[block["block_id"]]}
                        for block in page_record["blocks"]
                        if block["block_id"] in compact_map
                    ]
                    invalid_language_blocks = build_invalid_language_request_blocks(
                        blocks=compact_blocks_full,
                        translations=translations,
                        target_language=args.target_language,
                        translation_sources=translation_sources,
                    )
                    if invalid_language_blocks:
                        repair_log_path = api_logs_dir / f"page_{page_no:04d}_language_repair_compact.json"
                        repaired_map = client.repair_invalid_blocks(
                            page_no=page_no,
                            blocks=invalid_language_blocks,
                            source_language=args.source_language,
                            target_language=args.target_language,
                            api_log_path=repair_log_path,
                        )
                        for block in compact_blocks_full:
                            block_id = block["block_id"]
                            if block_id not in repaired_map:
                                continue
                            repaired_text = normalize_translation_text(
                                block, repaired_map[block_id], args.target_language
                            )
                            if is_translation_valid_for_target(repaired_text, args.target_language):
                                translations[block_id] = repaired_text
                                translation_sources[block_id] = "model_repair_compact"

                final_eval = evaluate_translations(
                    page=original_page,
                    blocks=page_record["blocks"],
                    styles=styles,
                    translations=translations,
                    segment_map=segment_map,
                )

                redacted_page = redacted_doc.load_page(page_no - 1)
                translated_page = translated_doc.load_page(page_no - 1)
                apply_text_redactions(redacted_page, page_record)
                apply_text_redactions(translated_page, page_record)

                initial_eval_map = index_evaluations(initial_eval)
                block_reports: list[dict[str, Any]] = []
                for block in page_record["blocks"]:
                    block_id = block["block_id"]
                    style = styles[block_id]
                    final_font_size, fit_status, layout_mode = fit_translation_block(
                        page=translated_page,
                        block=block,
                        translation=translations[block_id],
                        style=style,
                        raw_segments=segment_map.get(block_id),
                        commit=True,
                    )
                    block_report = {
                        "block_id": block_id,
                        "block_type": block_type_map[block_id],
                        "source_text": block["source_text"],
                        "translation": translations[block_id],
                        "translation_source": translation_sources.get(block_id, "unknown"),
                        "control_rule": control_rules.get(block_id, ""),
                        "used_compact_retry": block_id in compact_map,
                        "fit_status_initial": initial_eval_map[block_id]["fit_status"],
                        "fit_status_final": fit_status,
                        "font_ratio_initial": initial_eval_map[block_id]["font_ratio"],
                        "font_ratio_final": round(final_font_size / max(1.0, style["font_size"]), 3),
                        "font_size_final": round(final_font_size, 2),
                        "layout_mode_initial": initial_eval_map[block_id]["layout_mode"],
                        "layout_mode_final": layout_mode,
                    }
                    block_reports.append(block_report)
                    translations_report.append(
                        {
                            "page_no": page_no,
                            **block_report,
                        }
                    )

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

                summary_counter = Counter(item["fit_status_final"] for item in block_reports)
                source_counter = Counter(item["translation_source"] for item in block_reports)
                page_summary = {
                    "page_no": page_no,
                    "text_block_count": page_record["text_block_count"],
                    "rule_resolved_count": sum(
                        1 for value in translation_sources.values() if not value.startswith("model")
                    ),
                    "model_resolved_count": sum(
                        1 for value in translation_sources.values() if value.startswith("model")
                    ),
                    "compact_retry_count": len(compact_map),
                    "fit_summary": dict(summary_counter),
                    "translation_source_summary": dict(source_counter),
                    "original": str(original_path),
                    "redacted": str(redacted_path),
                    "translated": str(translated_path),
                    "comparison": str(comparison_path),
                    "document_context": str(document_context_path),
                    "company_memory": str(args.company_memory) if args.company_memory else "",
                    "status": "ok",
                }
                page_report.append(page_summary)
                print(json.dumps(page_summary, ensure_ascii=False))
            except Exception as exc:
                page_summary = {
                    "page_no": page_no,
                    "status": "error",
                    "error": str(exc),
                }
                page_report.append(page_summary)
                print(json.dumps(page_summary, ensure_ascii=False))
                if not args.continue_on_page_error:
                    raise
            finally:
                write_json_file(translations_path, translations_report)
                write_json_file(report_path, page_report)

        redacted_pdf_path = args.output_dir / "native_redacted.pdf"
        translated_pdf_path = args.output_dir / "translated_en.pdf"
        redacted_doc.save(redacted_pdf_path)
        translated_doc.save(translated_pdf_path)

    finally:
        original_doc.close()
        redacted_doc.close()
        translated_doc.close()

    write_json_file(translations_path, translations_report)
    write_json_file(report_path, page_report)
    print(f"translations={translations_path}")
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
