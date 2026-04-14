from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import fitz


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_07 = ROOT / "spikes" / "07_translation_current_bundle" / "scripts" / "translate_with_controls.py"
SCRIPT_08 = ROOT / "spikes" / "08_semantic_group_reflow" / "semantic_group_reflow.py"
DEFAULT_INPUT = ROOT / "样本" / "中文" / "AIA_2021_Annual_Report_zh.pdf"
DEFAULT_BLOCKS = ROOT / "spikes" / "01_text_block_extraction" / "output" / "AIA_2021_Annual_Report_zh" / "blocks.jsonl"
DEFAULT_BACKGROUND = ROOT / "spikes" / "09_document_understanding_workflow" / "output" / "sample_2021_pages_10_13_19_20_run1" / "document_background.json"
DEFAULT_OUTPUT = ROOT / "spikes" / "10_background_context_translation" / "output" / "focus_pages_10_13_19_20_run1"
DEFAULT_MODEL = "claude-3-5-sonnet-20241022"


def load_module(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reuse07 = load_module(SCRIPT_07, "background_reuse07")
reuse08 = load_module(SCRIPT_08, "background_reuse08")

AnthropicGatewayClient = reuse07.AnthropicGatewayClient
apply_text_redactions = reuse07.apply_text_redactions
classify_block_type = reuse07.classify_block_type
extract_raw_line_segments = reuse07.extract_raw_line_segments
extract_response_text = reuse07.extract_response_text
fit_translation_block = reuse07.fit_translation_block
infer_block_style = reuse07.infer_block_style
load_page_records = reuse07.load_page_records
normalize_source_text = reuse07.normalize_source_text
parse_json_from_text = reuse07.parse_json_from_text
parse_page_numbers = reuse07.parse_page_numbers
render_page = reuse07.render_page
resolve_controlled_translation = reuse07.resolve_controlled_translation
save_comparison = reuse07.save_comparison
write_json_file = reuse07.write_json_file
collect_relevant_terms = reuse07.collect_relevant_terms

build_semantic_units = reuse08.build_semantic_units
clean_text = reuse08.clean_text
clean_translation = reuse08.clean_translation
collect_unit_slots = reuse08.collect_unit_slots
is_narrative_candidate = reuse08.is_narrative_candidate
is_better_result = reuse08.is_better_result
parse_unit_translation = reuse08.parse_unit_translation
render_unit = reuse08.render_unit
should_retry_compact = reuse08.should_retry_compact
write_text_file = reuse08.write_text_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Spike 10: semantic grouping with per-unit document background injection."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--blocks-jsonl", type=Path, default=DEFAULT_BLOCKS)
    parser.add_argument("--document-background", type=Path, default=DEFAULT_BACKGROUND)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pages", type=str, default="10,13,19,20")
    parser.add_argument("--source-language", default="Traditional Chinese")
    parser.add_argument("--target-language", default="English")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-output-tokens", type=int, default=1800)
    parser.add_argument("--render-dpi", type=int, default=110)
    parser.add_argument("--compact-threshold", type=float, default=0.84)
    parser.add_argument(
        "--glossary",
        type=Path,
        default=ROOT / "spikes" / "07_translation_current_bundle" / "configs" / "glossary_zh_en_seed.json",
    )
    parser.add_argument(
        "--patterns",
        type=Path,
        default=ROOT / "spikes" / "07_translation_current_bundle" / "configs" / "patterns_zh_en.json",
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def compact_rule_list(rule_items: list[dict[str, Any]], limit: int = 4) -> list[str]:
    rules: list[str] = []
    for item in rule_items[:limit]:
        rule = str(item.get("rule") or "").strip()
        if rule:
            rules.append(rule)
    return rules


def page_range_width(section: dict[str, Any]) -> int:
    page_range = section.get("page_range") or []
    if len(page_range) == 2:
        start, end = int(page_range[0]), int(page_range[1])
        return max(1, end - start + 1)
    if len(page_range) == 1:
        return 1
    return 9999


def select_page_sections(page_no: int, section_map: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for item in section_map:
        page_range = item.get("page_range") or []
        if len(page_range) == 1:
            start = end = int(page_range[0])
        elif len(page_range) >= 2:
            start, end = int(page_range[0]), int(page_range[1])
        else:
            continue
        if start <= page_no <= end:
            matches.append(item)
    matches.sort(key=lambda item: (page_range_width(item), str(item.get("target_section") or item.get("content_type") or "")))
    return matches[:3]


def unit_text(unit: dict[str, Any]) -> str:
    return clean_text(unit.get("source_text_joined", ""))


def unit_is_table_like(unit: dict[str, Any], page_sections: list[dict[str, Any]]) -> bool:
    text = unit_text(unit)
    if re.search(r"\d", text) and re.search(r"[%$]", text):
        return True
    if len(re.findall(r"\d", text)) >= 6:
        return True
    if any(str(item.get("content_type") or "") in {"financial_review", "business_metrics", "valuation_metrics"} for item in page_sections):
        if re.search(r"\d", text):
            return True
    return False


def unit_is_heading_like(unit: dict[str, Any]) -> bool:
    block_types = [str(item) for item in unit.get("block_types", [])]
    return len(block_types) == 1 and block_types[0] in {"heading", "label"}


def select_style_rules(document_background: dict[str, Any], unit: dict[str, Any], page_sections: list[dict[str, Any]]) -> list[str]:
    style_guide = document_background.get("style_guide", {})
    rules = compact_rule_list(style_guide.get("global_rules", []), limit=3)
    if unit_is_heading_like(unit):
        rules.extend(compact_rule_list(style_guide.get("title_rules", []), limit=3))
    elif unit_is_table_like(unit, page_sections):
        rules.extend(compact_rule_list(style_guide.get("table_rules", []), limit=4))
    else:
        rules.extend(compact_rule_list(style_guide.get("body_rules", []), limit=4))
    deduped: list[str] = []
    seen: set[str] = set()
    for rule in rules:
        if rule in seen:
            continue
        seen.add(rule)
        deduped.append(rule)
    return deduped[:7]


def normalize_term_entry(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": str(item.get("source_term") or item.get("source") or "").strip(),
        "target": str(item.get("target_term") or item.get("target") or "").strip(),
        "abbreviation": str(item.get("abbreviation") or "").strip(),
        "context": str(item.get("context") or "").strip(),
        "confidence": str(item.get("confidence") or "").strip(),
    }


def match_background_terms(document_background: dict[str, Any], unit: dict[str, Any]) -> list[dict[str, Any]]:
    text = unit_text(unit)
    matches: list[dict[str, Any]] = []
    term_entries = [normalize_term_entry(item) for item in document_background.get("termbase", [])]
    role_entries = document_background.get("role_map", [])

    for item in sorted(term_entries, key=lambda value: len(value["source"]), reverse=True):
        source = item["source"]
        if source and source in text:
            matches.append(item)
    for item in role_entries:
        source_title = str(item.get("source_title") or "").strip()
        if source_title and source_title in text:
            matches.append(
                {
                    "source": source_title,
                    "target": str(item.get("target_title") or "").strip(),
                    "abbreviation": "",
                    "context": str(item.get("role") or "").strip(),
                    "confidence": str(item.get("confidence") or "").strip(),
                }
            )

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in matches:
        key = (item["source"], item["target"])
        if not item["source"] or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:16]


def select_relevant_roles(document_background: dict[str, Any], unit: dict[str, Any], page_sections: list[dict[str, Any]]) -> list[dict[str, str]]:
    text = unit_text(unit)
    target_sections = {str(item.get("target_section") or "") for item in page_sections}
    source_sections = {str(item.get("source_section") or "") for item in page_sections}
    selected: list[dict[str, str]] = []
    for item in document_background.get("role_map", []):
        context = str(item.get("context") or "")
        source_title = str(item.get("source_title") or "")
        if source_title and source_title in text:
            selected.append(
                {
                    "source": source_title,
                    "target": str(item.get("target_title") or ""),
                    "role": str(item.get("role") or ""),
                }
            )
            continue
        if context and (context in target_sections or context in source_sections):
            selected.append(
                {
                    "source": source_title,
                    "target": str(item.get("target_title") or ""),
                    "role": str(item.get("role") or ""),
                }
            )
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in selected:
        key = (item["source"], item["target"], item["role"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:6]


def build_context_pack(document_background: dict[str, Any], unit: dict[str, Any]) -> dict[str, Any]:
    page_sections = select_page_sections(int(unit["page_no"]), document_background.get("section_map", []))
    profile = document_background.get("document_profile", {})
    context_pack = {
        "global_profile": {
            "company_name_target": str(profile.get("company_name_target") or ""),
            "industry": str(profile.get("industry") or ""),
            "report_type": str(profile.get("report_type") or ""),
            "report_year": profile.get("report_year"),
            "style_keywords": profile.get("style_keywords", [])[:4],
        },
        "page_sections": [
            {
                "target_section": str(item.get("target_section") or ""),
                "content_type": str(item.get("content_type") or ""),
                "page_range": item.get("page_range", []),
            }
            for item in page_sections
        ],
        "roles": select_relevant_roles(document_background, unit, page_sections),
        "terms": match_background_terms(document_background, unit),
        "style_rules": select_style_rules(document_background, unit, page_sections),
    }
    return context_pack


def merge_term_hits(glossary_hits: list[dict[str, str]], background_terms: list[dict[str, Any]]) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in glossary_hits:
        source = str(item.get("source") or "").strip()
        target = str(item.get("target") or "").strip()
        if source and target and (source, target) not in seen:
            seen.add((source, target))
            merged.append({"source": source, "target": target})
    for item in background_terms:
        source = str(item.get("source") or "").strip()
        target = str(item.get("target") or "").strip()
        if source and target and (source, target) not in seen:
            seen.add((source, target))
            merged.append({"source": source, "target": target})
    return merged[:20]


def build_translation_prompts(
    unit: dict[str, Any],
    source_language: str,
    target_language: str,
    context_pack: dict[str, Any],
    glossary_hits: list[dict[str, str]],
) -> tuple[str, str]:
    system_prompt = "\n".join(
        [
            "你是上市公司年报英文翻译器。",
            f"语言方向：{source_language} -> {target_language}。",
            "你只处理当前翻译单元。",
            "如果当前单元由多个连续文本块组成，只允许在当前组内恢复被换行打散的句子和段落；只做最小必要融合，不得引入组外信息。",
            "标题、栏目名、表头、图表标签要短、稳、标准；正文要保持正式披露语体。",
            "数字、百分比、货币、年份、专有名词、公司名、人名、地名、财务指标必须准确。",
            "不增删事实，不补充因果，不输出残句，不重复表达。",
            "输出必须是 JSON，且只能输出 JSON。",
        ]
    )
    blocks_payload = [
        {"block_id": block["block_id"], "source_text": clean_text(block.get("source_text", ""))}
        for block in unit["blocks"]
    ]
    user_payload = {
        "document_background": context_pack,
        "matched_terms": glossary_hits,
        "current_unit": {
            "page_no": unit["page_no"],
            "unit_id": unit["unit_id"],
            "unit_mode": unit["mode"],
            "block_types": unit["block_types"],
            "blocks": blocks_payload,
            "joined_source_text": unit["source_text_joined"],
        },
        "output_format": {
            "translations": [
                {
                    "unit_id": unit["unit_id"],
                    "translation": "<译文>",
                }
            ]
        },
    }
    user_prompt = "\n".join(
        [
            "文档场景：上市公司企业年报",
            "请优先使用背景中的标准叫法和术语。",
            json.dumps(user_payload, ensure_ascii=False, indent=2),
        ]
    )
    return system_prompt, user_prompt


def build_compact_prompts(
    unit: dict[str, Any],
    source_language: str,
    target_language: str,
    context_pack: dict[str, Any],
    current_translation: str,
) -> tuple[str, str]:
    system_prompt = "\n".join(
        [
            "你是年报英文压缩器，不是重译器。",
            f"语言方向：{source_language} -> {target_language}。",
            "你的任务只是对已有译文做最小必要压缩，以便回填原版面。",
            "禁止改变数字、单位、术语、专名、比较关系、主体和结论。",
            "标题不能改成正文，表头不能改成句子，不能输出口语化表达。",
            "输出必须是 JSON，且只能输出 JSON。",
        ]
    )
    user_payload = {
        "document_background": {
            "page_sections": context_pack.get("page_sections", []),
            "roles": context_pack.get("roles", []),
            "terms": context_pack.get("terms", []),
            "style_rules": context_pack.get("style_rules", []),
        },
        "current_unit": {
            "page_no": unit["page_no"],
            "unit_id": unit["unit_id"],
            "unit_mode": unit["mode"],
            "slot_count": len(unit["slots"]),
            "source_text": unit["source_text_joined"],
            "current_translation": clean_translation(current_translation),
        },
        "output_format": {
            "translations": [
                {
                    "unit_id": unit["unit_id"],
                    "translation": "<更紧凑译文>",
                }
            ]
        },
    }
    user_prompt = "\n".join(
        [
            "文档场景：上市公司企业年报",
            json.dumps(user_payload, ensure_ascii=False, indent=2),
        ]
    )
    return system_prompt, user_prompt


def export_prompt_bundle(
    prompt_dir: Path,
    stem: str,
    system_prompt: str,
    user_prompt: str,
    response_payload: dict[str, Any] | None = None,
) -> None:
    write_text_file(prompt_dir / f"{stem}.system.txt", system_prompt)
    write_text_file(prompt_dir / f"{stem}.user.txt", user_prompt)
    if response_payload is not None:
        write_text_file(prompt_dir / f"{stem}.response.txt", extract_response_text(response_payload))


def call_model_for_unit(
    client: Any,
    prompt_dir: Path,
    api_logs_dir: Path,
    stem: str,
    system_prompt: str,
    user_prompt: str,
    meta: dict[str, Any],
) -> dict[str, Any]:
    request_payload, response_payload = client._post_messages(system_prompt, user_prompt)
    export_prompt_bundle(prompt_dir, stem, system_prompt, user_prompt, response_payload=response_payload)
    write_json_file(
        api_logs_dir / f"{stem}.json",
        {
            "meta": meta,
            "request": request_payload,
            "response": response_payload,
        },
    )
    return response_payload


def main() -> None:
    args = parse_args()
    glossary = load_json(args.glossary)
    patterns = load_json(args.patterns)
    document_background = load_json(args.document_background)
    page_numbers = parse_page_numbers(args.pages)
    page_records = load_page_records(args.blocks_jsonl, set(page_numbers))
    client = AnthropicGatewayClient.from_env(model=args.model, max_output_tokens=args.max_output_tokens)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    original_dir = args.output_dir / "original"
    redacted_dir = args.output_dir / "redacted"
    translated_dir = args.output_dir / "translated"
    comparison_dir = args.output_dir / "comparison"
    prompt_dir = args.output_dir / "prompt_exports"
    api_logs_dir = args.output_dir / "api_logs"
    for directory in [original_dir, redacted_dir, translated_dir, comparison_dir, prompt_dir, api_logs_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    original_doc = fitz.open(args.input)
    redacted_doc = fitz.open(args.input)
    translated_doc = fitz.open(args.input)

    context_packs: list[dict[str, Any]] = []
    translations_payload: list[dict[str, Any]] = []
    page_reports: list[dict[str, Any]] = []

    for page_no in page_numbers:
        page_record = page_records[page_no]
        original_page = original_doc[page_no - 1]
        redacted_page = redacted_doc[page_no - 1]
        translated_page = translated_doc[page_no - 1]

        apply_text_redactions(redacted_page, page_record)
        apply_text_redactions(translated_page, page_record)

        blocks: list[dict[str, Any]] = []
        for block in sorted(page_record["blocks"], key=lambda item: item["reading_order"]):
            style = infer_block_style(original_page, block)
            segments = extract_raw_line_segments(original_page, block)
            block_type = classify_block_type(block)
            enriched = {
                **block,
                "_block_type": block_type,
                "_style": style,
                "_segments": segments,
            }
            enriched["_narrative_candidate"] = is_narrative_candidate(enriched, block_type)
            blocks.append(enriched)

        segment_map = {block["block_id"]: block["_segments"] for block in blocks}
        units = build_semantic_units(page_no=page_no, blocks=blocks)
        for unit in units:
            unit["slots"] = collect_unit_slots(unit, segment_map)

        page_unit_reports: list[dict[str, Any]] = []
        for unit in units:
            context_pack = build_context_pack(document_background, unit)
            context_packs.append(
                {
                    "page_no": page_no,
                    "unit_id": unit["unit_id"],
                    "context_pack": context_pack,
                }
            )

            controlled = None
            translation_source = "model_initial"
            if unit["mode"] == "single_block":
                block = unit["blocks"][0]
                controlled = resolve_controlled_translation(block, block["_block_type"], glossary, patterns)
            if controlled:
                initial_translation = clean_translation(controlled["translation"])
                translation_source = str(controlled["translation_source"])
                matched_terms = []
            else:
                glossary_hits = collect_relevant_terms(unit["blocks"], glossary, limit=12)
                matched_terms = merge_term_hits(glossary_hits, context_pack.get("terms", []))
                system_prompt, user_prompt = build_translation_prompts(
                    unit=unit,
                    source_language=args.source_language,
                    target_language=args.target_language,
                    context_pack=context_pack,
                    glossary_hits=matched_terms,
                )
                response = call_model_for_unit(
                    client=client,
                    prompt_dir=prompt_dir,
                    api_logs_dir=api_logs_dir,
                    stem=f"{unit['unit_id']}_translation",
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    meta={"stage": "translation", "page_no": page_no, "unit_id": unit["unit_id"]},
                )
                initial_translation = parse_unit_translation(response, unit["unit_id"])

            best_translation = initial_translation
            best_result = render_unit(
                page=translated_page,
                unit=unit,
                translation=best_translation,
                target_language=args.target_language,
                commit=False,
            )
            compact_translation = None
            compact_used = False

            if not controlled and should_retry_compact(best_result, args.compact_threshold):
                compact_system, compact_user = build_compact_prompts(
                    unit=unit,
                    source_language=args.source_language,
                    target_language=args.target_language,
                    context_pack=context_pack,
                    current_translation=best_translation,
                )
                compact_response = call_model_for_unit(
                    client=client,
                    prompt_dir=prompt_dir,
                    api_logs_dir=api_logs_dir,
                    stem=f"{unit['unit_id']}_compact",
                    system_prompt=compact_system,
                    user_prompt=compact_user,
                    meta={"stage": "compact", "page_no": page_no, "unit_id": unit["unit_id"]},
                )
                compact_translation = parse_unit_translation(compact_response, unit["unit_id"])
                compact_result = render_unit(
                    page=translated_page,
                    unit=unit,
                    translation=compact_translation,
                    target_language=args.target_language,
                    commit=False,
                )
                if is_better_result(compact_result, best_result):
                    best_translation = compact_translation
                    best_result = compact_result
                    compact_used = True

            committed_result = render_unit(
                page=translated_page,
                unit=unit,
                translation=best_translation,
                target_language=args.target_language,
                commit=True,
            )
            block_outputs = committed_result["rendered_by_block"] or {
                block["block_id"]: best_translation for block in unit["blocks"]
            }
            translations_payload.append(
                {
                    "page_no": page_no,
                    "unit_id": unit["unit_id"],
                    "mode": unit["mode"],
                    "block_ids": unit["block_ids"],
                    "source_text": unit["source_text_joined"],
                    "context_pack": context_pack,
                    "matched_terms": matched_terms if not controlled else [],
                    "initial_translation": initial_translation,
                    "compact_translation": compact_translation,
                    "final_translation": best_translation,
                    "translation_source": translation_source,
                    "compact_used": compact_used,
                    "render_result": committed_result,
                    "block_outputs": block_outputs,
                }
            )
            page_unit_reports.append(
                {
                    "unit_id": unit["unit_id"],
                    "mode": unit["mode"],
                    "block_ids": unit["block_ids"],
                    "translation_source": translation_source,
                    "compact_used": compact_used,
                    "fit_status": committed_result["fit_status"],
                    "font_ratio": committed_result["font_ratio"],
                    "layout_mode": committed_result["layout_mode"],
                }
            )

        original_image = render_page(original_page, args.render_dpi)
        redacted_image = render_page(redacted_page, args.render_dpi)
        translated_image = render_page(translated_page, args.render_dpi)
        original_image.save(original_dir / f"page_{page_no:04d}.png")
        redacted_image.save(redacted_dir / f"page_{page_no:04d}.png")
        translated_image.save(translated_dir / f"page_{page_no:04d}.png")
        save_comparison(
            original=original_image,
            redacted=redacted_image,
            translated=translated_image,
            output_path=comparison_dir / f"page_{page_no:04d}.png",
        )
        page_reports.append(
            {
                "page_no": page_no,
                "unit_count": len(units),
                "reports": page_unit_reports,
            }
        )

    write_json_file(args.output_dir / "selected_context_packs.json", context_packs)
    write_json_file(args.output_dir / "translations.json", translations_payload)
    write_json_file(args.output_dir / "report.json", {"pages": page_reports})
    redacted_doc.save(args.output_dir / "native_redacted.pdf")
    translated_doc.save(args.output_dir / "translated_en.pdf")


if __name__ == "__main__":
    main()
