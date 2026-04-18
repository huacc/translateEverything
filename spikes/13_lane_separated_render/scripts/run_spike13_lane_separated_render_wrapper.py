from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import fitz


ROOT = Path(__file__).resolve().parents[3]
SPIKE05_SCRIPT = ROOT / "spikes" / "05_annual_report_translation_control" / "translate_with_controls.py"
SPIKE12_SCRIPT = ROOT / "spikes" / "12_anchor_group_render" / "scripts" / "run_spike12_anchor_group_render.py"
DEFAULT_OUTPUT = ROOT / "spikes" / "13_lane_separated_render" / "output" / "first20_run1"
DEFAULT_BASELINE_DIR = ROOT / "spikes" / "07_translation_current_bundle" / "outputs" / "first20_current"


def load_module(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


sp05 = load_module(SPIKE05_SCRIPT, "spike13_sp05")
sp12 = load_module(SPIKE12_SCRIPT, "spike13_sp12")

ORIGINAL_WRITE_JSON = sp12.write_json_file
ORIGINAL_RENDER_UNIT = sp12.render_unit
ORIGINAL_BUILD_FACT_LOCK_RECORDS = sp12.build_fact_lock_records
ORIGINAL_BUILD_MAPPING_HITS = sp12.build_mapping_hit_records
ORIGINAL_BUILD_COMPACT_PROMPTS = sp12.build_compact_prompts
ORIGINAL_POST_NORMALIZE = sp12.post_normalize_translation
ORIGINAL_PARSE_UNIT_TRANSLATION = sp12.parse_unit_translation

GROUP_STORE: dict[str, dict[str, Any]] = {}
GROUP_CONTEXT_STORE: dict[str, dict[str, Any]] = {}
PROMPT_AUDIT: list[dict[str, Any]] = []
MODEL_REQUEST_OPTIONS: dict[str, Any] = {
    "thinking_mode": "none",
    "thinking_budget": 0,
    "effort": "",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Spike 13: lane-separated translation + anchor reconstruction experiment.")
    parser.add_argument("--input", type=Path, default=sp12.DEFAULT_INPUT)
    parser.add_argument("--reference-pdf", type=Path, default=sp12.DEFAULT_REFERENCE)
    parser.add_argument("--blocks-jsonl", type=Path, default=sp12.DEFAULT_BLOCKS)
    parser.add_argument("--document-background", type=Path, default=sp12.DEFAULT_DOCUMENT_BACKGROUND)
    parser.add_argument("--company-memory", type=Path, default=sp12.DEFAULT_COMPANY_MEMORY)
    parser.add_argument("--glossary", type=Path, default=sp12.DEFAULT_GLOSSARY)
    parser.add_argument("--patterns", type=Path, default=sp12.DEFAULT_PATTERNS)
    parser.add_argument("--v11-baseline-dir", type=Path, default=DEFAULT_BASELINE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pages", type=str, default="1-20")
    parser.add_argument("--source-language", default="Traditional Chinese")
    parser.add_argument("--target-language", default="English")
    parser.add_argument("--model", default=sp12.DEFAULT_MODEL)
    parser.add_argument("--max-output-tokens", type=int, default=1800)
    parser.add_argument("--thinking-mode", choices=["none", "adaptive", "manual"], default="none")
    parser.add_argument("--thinking-budget", type=int, default=0)
    parser.add_argument("--effort", choices=["", "low", "medium", "high", "max"], default="")
    parser.add_argument("--render-dpi", type=int, default=110)
    parser.add_argument("--compact-threshold", type=float, default=0.84)
    parser.add_argument("--stop-after-stage", type=int, default=6)
    args = parser.parse_args()
    MODEL_REQUEST_OPTIONS["thinking_mode"] = args.thinking_mode
    MODEL_REQUEST_OPTIONS["thinking_budget"] = max(0, int(args.thinking_budget or 0))
    MODEL_REQUEST_OPTIONS["effort"] = str(args.effort or "").strip()
    return args


class AnthropicGatewayClientWithThinking(sp12.AnthropicGatewayClient):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        max_output_tokens: int,
        thinking_mode: str = "none",
        thinking_budget: int = 0,
        effort: str = "",
    ) -> None:
        super().__init__(base_url=base_url, api_key=api_key, model=model, max_output_tokens=max_output_tokens)
        self.thinking_mode = thinking_mode
        self.thinking_budget = max(0, int(thinking_budget or 0))
        self.effort = str(effort or "").strip()

    @classmethod
    def from_env(cls, model: str, max_output_tokens: int) -> "AnthropicGatewayClientWithThinking":
        base_url = os.environ.get("ANTHROPIC_BASE_URL")
        api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN")
        if not base_url or not api_key:
            raise RuntimeError("Missing ANTHROPIC_BASE_URL or ANTHROPIC_AUTH_TOKEN in the environment.")
        thinking_mode = str(MODEL_REQUEST_OPTIONS.get("thinking_mode") or "none")
        thinking_budget = int(MODEL_REQUEST_OPTIONS.get("thinking_budget") or 0)
        effort = str(MODEL_REQUEST_OPTIONS.get("effort") or "").strip()
        return cls(
            base_url=base_url,
            api_key=api_key,
            model=model,
            max_output_tokens=max_output_tokens,
            thinking_mode=thinking_mode,
            thinking_budget=thinking_budget,
            effort=effort,
        )

    def _post_messages(self, system_prompt: str, user_prompt: str) -> tuple[dict[str, Any], dict[str, Any]]:
        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_output_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        thinking_mode = self.thinking_mode
        if thinking_mode == "adaptive":
            payload["thinking"] = {"type": "adaptive"}
        elif thinking_mode == "manual":
            payload["thinking"] = {
                "type": "enabled",
                "budget_tokens": max(1024, self.thinking_budget or 1024),
            }
        else:
            payload["temperature"] = 0
        if self.effort:
            payload["output_config"] = {"effort": self.effort}
        response = sp05.requests.post(url, headers=headers, json=payload, timeout=180)
        response.raise_for_status()
        return payload, response.json()


def nonempty_lines(text: str) -> list[str]:
    return [line.strip() for line in str(text or "").splitlines() if line.strip()]


def clean_multiline_translation(text: str) -> str:
    lines = [" ".join(line.split()) for line in str(text or "").splitlines()]
    return "\n".join(line for line in lines if line).strip()


def normalize_table_translation(text: str) -> str:
    normalized = clean_multiline_translation(text)
    for source in ["Not meaningful", "not meaningful", "NOT MEANINGFUL"]:
        normalized = normalized.replace(source, "N/M")
    return normalized.strip()


def bbox_union(blocks: list[dict[str, Any]]) -> list[float]:
    x0 = min(float(block["bbox"][0]) for block in blocks)
    y0 = min(float(block["bbox"][1]) for block in blocks)
    x1 = max(float(block["bbox"][2]) for block in blocks)
    y1 = max(float(block["bbox"][3]) for block in blocks)
    return [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)]


def table_signal_details(block: dict[str, Any], block_type: str) -> tuple[bool, list[str]]:
    text = str(block.get("source_text") or "")
    lines = nonempty_lines(text)
    width = sp12.block_width(block)
    font_size = sp12.block_font_size(block)
    dense = sp12.likely_numeric_dense(block)
    numeric_lines = sum(
        1 for line in lines if re.search(r"\d|%|\(|\)|無意義|n/m", line, flags=re.IGNORECASE)
    )
    keyword_lines = sum(
        1
        for line in lines
        if re.search(
            r"(新業務|價值|利潤率|年化|按年變動|固定匯率|實質匯率|百萬美元|除另有說明外|小計|總計|非控股權益|資本要求|總部開支)",
            line,
        )
    )
    reasons: list[str] = []
    if dense:
        reasons.append("numeric_dense")
    if width >= 180:
        reasons.append("wide_block")
    if font_size <= 9.5:
        reasons.append("small_font")
    if len(lines) >= 3:
        reasons.append("multi_line")
    if numeric_lines >= 2:
        reasons.append("numeric_lines")
    if keyword_lines >= 1:
        reasons.append("table_keywords")
    is_table = False
    if block_type != "chart_label":
        if width >= 180 and font_size <= 9.5 and len(lines) >= 3 and (numeric_lines >= 2 or keyword_lines >= 2):
            is_table = True
        elif width >= 240 and dense and len(lines) >= 2:
            is_table = True
        elif block_type == "body" and width >= 200 and len(lines) >= 4 and numeric_lines >= max(2, len(lines) // 2):
            is_table = True
        elif block_type == "body" and font_size <= 9.5 and len(lines) >= 3 and keyword_lines >= 2:
            is_table = True
        elif block_type == "body" and font_size <= 9.5 and re.search(r"(百萬美元|除另有說明外)", text):
            is_table = True
    return is_table, reasons if is_table else []


def classify_lane(block: dict[str, Any], block_type: str, sidebar_flag: bool, exclude_reason: str | None) -> tuple[str, str, list[str]]:
    text = sp12.clean_text(block.get("source_text", ""))
    lines = nonempty_lines(block.get("source_text", ""))
    width = sp12.block_width(block)
    font_size = sp12.block_font_size(block)
    if sidebar_flag:
        return "sidebar_excluded", exclude_reason or "sidebar_excluded", ["sidebar_boundary"]
    is_table, table_signals = table_signal_details(block, block_type)
    if is_table:
        return "table", "table_layout_signals", table_signals
    if block_type == "label" and re.search(r"\d", text) and re.search(r"(億美元|港仙|股息|自由盈餘|利潤|權益|比率|覆蓋率|%|美元)", text):
        return "body", "financial_tail_clause", ["label_like_body", "financial_tail_clause"]
    if block_type in {"chart_label", "heading", "footer"}:
        return "caption_label", block_type, [block_type]
    if block_type == "label":
        return "caption_label", "label_block", ["label_block"]
    if width <= 60:
        return "caption_label", "narrow_short_text", ["narrow_block"]
    if len(lines) <= 2 and len(text) <= 36 and font_size >= 11.0:
        return "caption_label", "short_display_text", ["short_text", "display_font"]
    return "body", "default_body", ["body_fallback"]


def build_anchor_block_records(page_no: int, page_record: dict[str, Any], page: fitz.Page) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    for block in sorted(page_record["blocks"], key=lambda item: item["reading_order"]):
        style = sp12.infer_block_style(page, block)
        segments = sp12.extract_raw_line_segments(page, block)
        block_type = sp12.classify_block_type(block)
        sidebar_flag, exclude_reason = sp12.is_sidebar_excluded(block, block_type)
        enriched = {
            **block,
            "_style": style,
            "_segments": segments,
            "_block_type": block_type,
            "is_sidebar_excluded": sidebar_flag,
            "exclude_reason": exclude_reason,
        }
        lane, lane_reason, lane_signals = classify_lane(enriched, block_type, sidebar_flag, exclude_reason)
        narrative_candidate = lane == "body" and sp12.is_primary_narrative_candidate(enriched, block_type)
        anchors.append(
            {
                "page_no": page_no,
                "block_id": enriched["block_id"],
                "reading_order": enriched["reading_order"],
                "bbox": list(enriched["bbox"]),
                "region": enriched.get("region"),
                "role": enriched.get("role"),
                "char_count": int(enriched.get("char_count") or len(sp12.clean_text(enriched.get("source_text", "")))),
                "source_text": str(enriched.get("source_text") or ""),
                "block_type": block_type,
                "style": style,
                "slots": sp12.collect_unit_slots({"blocks": [enriched]}, {enriched["block_id"]: segments}),
                "font_size_avg": enriched.get("font_size_avg"),
                "font_size_max": enriched.get("font_size_max"),
                "segment_count": len(segments),
                "is_sidebar_excluded": sidebar_flag,
                "exclude_reason": exclude_reason,
                "translation_target": lane != "sidebar_excluded",
                "narrative_candidate": narrative_candidate,
                "lane": lane,
                "lane_reason": lane_reason,
                "lane_signals": lane_signals,
                "_runtime": enriched,
            }
        )
    return anchors


def make_group_record(page_no: int, block_group: list[dict[str, Any]], mode: str, group_id: str, reason_records: list[dict[str, Any]]) -> dict[str, Any]:
    runtime_blocks = [block["_runtime"] for block in block_group]
    record = {
        "group_id": group_id,
        "unit_id": group_id,
        "page_no": page_no,
        "mode": mode,
        "lane": block_group[0]["lane"],
        "block_ids": [block["block_id"] for block in block_group],
        "block_types": [block["block_type"] for block in block_group],
        "source_text_joined": "\n".join(
            sp12.clean_text(block["source_text"]) for block in block_group if sp12.clean_text(block["source_text"])
        ),
        "translation_target": all(block["translation_target"] for block in block_group),
        "is_sidebar_group": any(block["is_sidebar_excluded"] for block in block_group),
        "group_reason": reason_records,
        "group_bbox": bbox_union(runtime_blocks),
        "slots": sp12.collect_unit_slots({"blocks": runtime_blocks}, {block["block_id"]: block["_segments"] for block in runtime_blocks}),
        "blocks": runtime_blocks,
    }
    GROUP_STORE[group_id] = record
    return record


def detect_table_role(block_group: list[dict[str, Any]]) -> str:
    text = "\n".join(sp12.clean_text(block["source_text"]) for block in block_group)
    if re.search(r"(百萬美元|除另有說明外)", text):
        return "note"
    if re.search(r"(按年變動|固定匯率|實質匯率|利潤率|年化|新保費|新業務價值)", text):
        return "header"
    return "row"


def build_semantic_group_records(page_no: int, anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pending_body_group: list[dict[str, Any]] = []
    raw_units: list[list[dict[str, Any]]] = []

    def flush_pending() -> None:
        nonlocal pending_body_group
        if pending_body_group:
            raw_units.append(pending_body_group)
            pending_body_group = []

    for anchor in anchors:
        lane = anchor["lane"]
        runtime_block = anchor["_runtime"]
        if lane != "body":
            flush_pending()
            raw_units.append([anchor])
            continue
        if not anchor["narrative_candidate"]:
            if pending_body_group and sp12.is_tail_clause_candidate([item["_runtime"] for item in pending_body_group], runtime_block):
                pending_body_group.append(anchor)
                continue
            flush_pending()
            raw_units.append([anchor])
            continue
        if not pending_body_group:
            pending_body_group = [anchor]
            continue
        if sp12.can_merge_primary_group([item["_runtime"] for item in pending_body_group], runtime_block):
            pending_body_group.append(anchor)
        else:
            flush_pending()
            pending_body_group = [anchor]
    flush_pending()

    group_records: list[dict[str, Any]] = []
    body_group_index = 1
    for block_group in raw_units:
        lane = block_group[0]["lane"]
        if lane == "sidebar_excluded":
            group_records.append(
                make_group_record(
                    page_no,
                    block_group,
                    mode="single_block",
                    group_id=str(block_group[0]["block_id"]),
                    reason_records=[{"kind": "excluded_single", "reason": block_group[0]["exclude_reason"] or "sidebar_excluded"}],
                )
            )
            continue
        if lane == "body" and len(block_group) > 1:
            reasons = []
            for previous, current in zip(block_group, block_group[1:]):
                merge_kind = "tail_numeric_clause" if not current["narrative_candidate"] else "adjacent_narrative"
                reasons.append({"kind": merge_kind, "from": previous["block_id"], "to": current["block_id"]})
            group_records.append(
                make_group_record(
                    page_no,
                    block_group,
                    mode="semantic_group",
                    group_id=f"p{page_no}_g{body_group_index:02d}",
                    reason_records=reasons,
                )
            )
            body_group_index += 1
            continue
        if lane == "table":
            role = detect_table_role(block_group)
            group_records.append(
                make_group_record(
                    page_no,
                    block_group,
                    mode="single_block",
                    group_id=str(block_group[0]["block_id"]),
                    reason_records=[{"kind": "table_unit", "table_role": role, "reason": block_group[0]["lane_reason"]}],
                )
            )
            GROUP_STORE[str(block_group[0]["block_id"])]["table_role"] = role
            continue
        group_records.append(
            make_group_record(
                page_no,
                block_group,
                mode="single_block",
                group_id=str(block_group[0]["block_id"]),
                reason_records=[{"kind": "single_non_narrative", "reason": block_group[0]["block_type"]}],
            )
        )
    return group_records


def build_group_context_record(
    group_record: dict[str, Any],
    context_pack: dict[str, Any],
    mapping_hits: list[dict[str, Any]],
    fact_locks: list[dict[str, Any]],
    neighbor_context: dict[str, str],
) -> dict[str, Any]:
    record = {
        "group_id": group_record["group_id"],
        "page_no": group_record["page_no"],
        "mode": group_record["mode"],
        "lane": group_record["lane"],
        "block_ids": group_record["block_ids"],
        "group_text": group_record["source_text_joined"],
        "group_bbox": group_record["group_bbox"],
        "page_sections": context_pack.get("page_sections", []),
        "global_profile": context_pack.get("global_profile", {}),
        "term_usage_mode": context_pack.get("term_usage_mode"),
        "roles": context_pack.get("roles", []),
        "style_rules": context_pack.get("style_rules", []),
        "mapping_hits": mapping_hits,
        "fact_locks": fact_locks,
        "neighbor_context": neighbor_context,
    }
    GROUP_CONTEXT_STORE[group_record["group_id"]] = record
    return record


def build_fact_lock_records(group_record: dict[str, Any]) -> list[dict[str, Any]]:
    if group_record.get("lane") != "body":
        return []
    return ORIGINAL_BUILD_FACT_LOCK_RECORDS(group_record)


def build_mapping_hit_records(group_record: dict[str, Any], context_pack: dict[str, Any], glossary: dict[str, Any]) -> list[dict[str, Any]]:
    if group_record.get("lane") == "sidebar_excluded":
        return []
    return ORIGINAL_BUILD_MAPPING_HITS(group_record, context_pack, glossary)


def build_translation_prompts(
    group_record: dict[str, Any],
    source_language: str,
    target_language: str,
    group_context_record: dict[str, Any],
) -> tuple[str, str]:
    profile = group_context_record.get("global_profile", {})
    lane = group_context_record.get("lane", group_record.get("lane", "body"))
    common_payload = {
        "task": {
            "scenario": "listed_company_annual_report",
            "industry": profile.get("industry", ""),
            "report_type": profile.get("report_type", ""),
            "company_name_target": profile.get("company_name_target", ""),
            "direction": f"{source_language} -> {target_language}",
        },
        "page_context": {
            "page_no": group_record["page_no"],
            "page_sections": group_context_record.get("page_sections", []),
            "term_usage_mode": group_context_record.get("term_usage_mode", ""),
            "neighbor_context": group_context_record.get("neighbor_context", {}),
        },
        "mapping_hits": [
            {"source": item["source"], "target": item["target"], "hit_type": item["hit_type"]}
            for item in group_context_record.get("mapping_hits", [])
        ],
        "fact_locks": [
            {
                "label": item["label"],
                "fact_type": item["fact_type"],
                "source_value": item["source_value"],
                "expected_forms": item["expected_forms"],
            }
            for item in group_context_record.get("fact_locks", [])
        ],
    }
    if lane == "table":
        system_prompt = "\n".join(
            [
                "你是上市保险公司年报中的表格翻译器。",
                f"语言方向：{source_language} -> {target_language}。",
                "只处理当前 table unit。",
                "数字、百分比、括号、货币、年份和顺序必须准确。",
                "只翻译文本标签，不要改写数字，不要补充解释。",
                "不要承担版面回填职责。",
                "只输出 JSON，且只能输出 JSON。",
            ]
        )
        user_payload = {
            **common_payload,
            "current_unit": {
                "unit_id": group_record["group_id"],
                "lane": lane,
                "table_role": GROUP_STORE.get(group_record["group_id"], {}).get("table_role", "row"),
                "source_text": group_record["source_text_joined"],
                "source_line_count": len(nonempty_lines(group_record["source_text_joined"])),
            },
            "output_format": {"translations": [{"unit_id": group_record["group_id"], "translation": "<译文>"}]},
        }
        user_prompt = "\n".join(
            [
                "文档场景：上市保险公司企业年报。",
                "当前输入属于表格通道。不要把表格行改写成正文句子。",
                json.dumps(user_payload, ensure_ascii=False, indent=2),
            ]
        )
    elif lane == "caption_label":
        system_prompt = "\n".join(
            [
                "你是上市保险公司年报中的标签翻译器。",
                f"语言方向：{source_language} -> {target_language}。",
                "只处理当前 caption/label unit。",
                "保持短、稳、正式，不自由改写。",
                "只输出 JSON，且只能输出 JSON。",
            ]
        )
        user_payload = {
            **common_payload,
            "current_unit": {
                "unit_id": group_record["group_id"],
                "lane": lane,
                "source_text": group_record["source_text_joined"],
            },
            "output_format": {"translations": [{"unit_id": group_record["group_id"], "translation": "<译文>"}]},
        }
        user_prompt = "\n".join(
            [
                "文档场景：上市保险公司企业年报。",
                "当前输入属于短标签通道。优先使用标准年报表达。",
                json.dumps(user_payload, ensure_ascii=False, indent=2),
            ]
        )
    else:
        system_prompt = "\n".join(
            [
                "你是上市保险公司年报翻译器。",
                f"语言方向：{source_language} -> {target_language}。",
                "只处理当前 body semantic group。",
                "只可在当前组内恢复跨块断句，不得跨组补写、跨组删写或改写事实。",
                "必须严格满足 mapping_hits 与 fact_locks。",
                "版面回填、字体压缩、分块分配不是你的职责，不要为了适配版面而删词改义。",
                "保持正式、稳定、可出版的企业年报文风。",
                "只输出 JSON，且只能输出 JSON。",
            ]
        )
        user_payload = {
            **common_payload,
            "current_group": {
                "group_id": group_record["group_id"],
                "lane": lane,
                "group_text": group_record["source_text_joined"],
                "source_block_ids": group_record["block_ids"],
                "source_block_count": len(group_record["block_ids"]),
            },
            "output_format": {"translations": [{"unit_id": group_record["group_id"], "translation": "<译文>"}]},
        }
        user_prompt = "\n".join(
            [
                "文档场景：上市保险公司企业年报。",
                "先满足 fact_locks，再保证术语稳定、语义完整和年报文风。",
                json.dumps(user_payload, ensure_ascii=False, indent=2),
            ]
        )
    PROMPT_AUDIT.append(
        {
            "group_id": group_record["group_id"],
            "page_no": group_record["page_no"],
            "lane": lane,
            "uses_group_text": "\"group_text\"" in user_prompt,
            "uses_table_role": "\"table_role\"" in user_prompt,
            "contains_raw_blocks_array": "\"blocks\"" in user_prompt,
        }
    )
    return system_prompt, user_prompt


def build_compact_prompts(
    unit: dict[str, Any],
    source_language: str,
    target_language: str,
    context_pack: dict[str, Any],
    current_translation: str,
) -> tuple[str, str]:
    lane = context_pack.get("lane", unit.get("lane", "body"))
    if lane == "body":
        return ORIGINAL_BUILD_COMPACT_PROMPTS(unit, source_language, target_language, context_pack, current_translation)
    system_prompt = "\n".join(
        [
            "你是版面压缩器。",
            f"语言方向：{source_language} -> {target_language}。",
            "只做最小必要压缩。",
            "不得改动数字、百分比、年份、金额、专有名词。",
            "只输出 JSON，且只能输出 JSON。",
        ]
    )
    user_payload = {
        "current_unit": {
            "unit_id": unit["group_id"],
            "lane": lane,
            "source_text": unit["source_text_joined"],
            "current_translation": sp12.clean_translation(current_translation),
        },
        "output_format": {"translations": [{"unit_id": unit["group_id"], "translation": "<更紧凑译文>"}]},
    }
    user_prompt = "\n".join(["文档场景：上市保险公司企业年报。", json.dumps(user_payload, ensure_ascii=False, indent=2)])
    return system_prompt, user_prompt


def post_normalize_translation(unit: dict[str, Any], context_pack: dict[str, Any], translation: str) -> str:
    lane = unit.get("lane", context_pack.get("lane"))
    if lane in {"table", "caption_label"}:
        normalized = sp12.clean_translation(translation)
        normalized = normalized.replace("Not meaningful", "n/m")
        normalized = normalized.replace("not meaningful", "n/m")
        return normalized.strip()
    return ORIGINAL_POST_NORMALIZE(unit, context_pack, translation)


def build_render_artifacts(unit: dict[str, Any], render_result: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fragments: list[dict[str, Any]] = []
    anchor_maps: list[dict[str, Any]] = []
    rendered_by_block = render_result.get("rendered_by_block") or {}
    reconstructed_bboxes = render_result.get("reconstructed_bboxes") or {}
    fragment_type = "table_cell" if unit.get("lane") == "table" else "label" if unit.get("lane") == "caption_label" else "phrase"
    for index, (block_id, text) in enumerate(rendered_by_block.items(), start=1):
        fragment_id = f"{unit['group_id']}_f{index:02d}"
        fragments.append(
            {
                "fragment_id": fragment_id,
                "group_id": unit["group_id"],
                "page_no": unit["page_no"],
                "lane": unit.get("lane"),
                "fragment_order": index,
                "text": text,
                "fragment_type": fragment_type,
            }
        )
        anchor_maps.append(
            {
                "fragment_id": fragment_id,
                "group_id": unit["group_id"],
                "page_no": unit["page_no"],
                "target_anchor_ids": [block_id],
                "allocation_reason": "rendered_by_block",
                "used_reconstruction": len(unit.get("block_ids", [])) > 1 and unit.get("mode") == "semantic_group",
                "within_group_bbox": True,
                "reconstructed_bbox": reconstructed_bboxes.get(block_id),
            }
        )
    return fragments, anchor_maps


def render_unit(page: fitz.Page, unit: dict[str, Any], translation: str, target_language: str, commit: bool) -> dict[str, Any]:
    result = ORIGINAL_RENDER_UNIT(page=page, unit=unit, translation=translation, target_language=target_language, commit=commit)
    fragments, anchor_maps = build_render_artifacts(unit, result)
    result["render_fragments"] = fragments
    result["fragment_anchor_map"] = anchor_maps
    result["lane"] = unit.get("lane")
    result["group_bbox"] = unit.get("group_bbox")
    result["used_group_reflow"] = len(unit.get("block_ids", [])) > 1 and unit.get("mode") == "semantic_group"
    return result


def build_output_contract(unit_id: str, translation_placeholder: str) -> str:
    return json.dumps(
        {"translations": [{"unit_id": unit_id, "translation": translation_placeholder}]},
        ensure_ascii=False,
        indent=2,
    )


def join_section(title: str, lines: list[str]) -> str:
    cleaned = [line.rstrip() for line in lines if str(line).strip()]
    if not cleaned:
        return ""
    return "\n".join([title, *cleaned])


def render_page_section_lines(page_sections: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in page_sections[:3]:
        target = str(item.get("target_section") or item.get("source_section") or "").strip()
        content_type = str(item.get("content_type") or "").strip()
        page_range = item.get("page_range") or []
        range_text = ""
        if isinstance(page_range, list) and len(page_range) == 2:
            range_text = f"（页码 {page_range[0]}-{page_range[1]}）"
        if target:
            suffix = f"，类型：{content_type}" if content_type else ""
            lines.append(f"- 当前章节：{target}{suffix}{range_text}")
    return lines


def render_neighbor_lines(neighbor_context: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    prev_text = str(neighbor_context.get("previous_group_source_excerpt") or "").strip()
    next_text = str(neighbor_context.get("next_group_source_excerpt") or "").strip()
    if prev_text:
        lines.append(f"- 上一组摘要：{prev_text}")
    if next_text:
        lines.append(f"- 下一组摘要：{next_text}")
    return lines


def render_mapping_lines(mapping_hits: list[dict[str, Any]], limit: int = 8) -> list[str]:
    lines: list[str] = []
    for item in mapping_hits[:limit]:
        source = str(item.get("source") or "").strip()
        target = str(item.get("target") or "").strip()
        hit_type = str(item.get("hit_type") or "").strip()
        if source and target:
            suffix = f" [{hit_type}]" if hit_type else ""
            lines.append(f"- {source} => {target}{suffix}")
    return lines


def render_fact_lock_lines(fact_locks: list[dict[str, Any]], limit: int = 8) -> list[str]:
    lines: list[str] = []
    for item in fact_locks[:limit]:
        label = str(item.get("label") or "").strip()
        source_value = str(item.get("source_value") or "").strip()
        expected_forms = [str(value).strip() for value in item.get("expected_forms") or [] if str(value).strip()]
        if not source_value and not expected_forms:
            continue
        expected_text = " / ".join(expected_forms[:3])
        if label and source_value and expected_text:
            lines.append(f"- {label}: {source_value} -> {expected_text}")
        elif source_value and expected_text:
            lines.append(f"- {source_value} -> {expected_text}")
        elif source_value:
            lines.append(f"- {source_value}")
    return lines


def render_style_rule_lines(style_rules: list[str], limit: int = 5) -> list[str]:
    return [f"- {str(rule).strip()}" for rule in style_rules[:limit] if str(rule).strip()]


def build_body_user_prompt(
    group_record: dict[str, Any],
    source_language: str,
    target_language: str,
    group_context_record: dict[str, Any],
    profile: dict[str, Any],
) -> str:
    sections = [
        join_section(
            "任务",
            [
                f"- 语言方向：{source_language} -> {target_language}",
                "- 文档场景：上市公司企业年报",
                f"- 公司：{profile.get('company_name_target', '')}",
                f"- 行业：{profile.get('industry', '')}",
                f"- 报告类型：{profile.get('report_type', '')}",
                f"- 当前页面：{group_record['page_no']}",
                "- 当前输入单元：正文语义组（group）",
            ],
        ),
        join_section(
            "翻译要求",
            [
                "- 只翻译当前正文组，不要承担排版、压缩、分块、回填职责。",
                "- 可以在当前 group 内恢复断句和段落语义，但不得跨 group 补写或删写。",
                "- 保持上市公司年报文风：正式、稳定、可出版。",
                "- 数字、百分比、货币、年份、专有名词必须准确。",
                "- 如术语锁定与原有表达冲突，优先遵守术语锁定和事实锁定。",
            ],
        ),
        join_section(
            "页面上下文",
            [
                *render_page_section_lines(group_context_record.get("page_sections", [])),
                f"- 术语使用模式：{group_context_record.get('term_usage_mode', '')}",
                *render_neighbor_lines(group_context_record.get("neighbor_context", {})),
            ],
        ),
        join_section("文体与偏好", render_style_rule_lines(group_context_record.get("style_rules", []))),
        join_section("术语锁定", render_mapping_lines(group_context_record.get("mapping_hits", []))),
        join_section("事实锁定", render_fact_lock_lines(group_context_record.get("fact_locks", []))),
        join_section(
            "当前正文组",
            [
                f"- group_id：{group_record['group_id']}",
                f"- group_bbox：{group_record['group_bbox']}",
                "- 原文：",
                group_record["source_text_joined"],
            ],
        ),
        join_section("输出格式", [build_output_contract(group_record["group_id"], "<译文>")]),
    ]
    return "\n\n".join(section for section in sections if section)


def build_label_user_prompt(
    group_record: dict[str, Any],
    source_language: str,
    target_language: str,
    group_context_record: dict[str, Any],
    profile: dict[str, Any],
) -> str:
    sections = [
        join_section(
            "任务",
            [
                f"- 语言方向：{source_language} -> {target_language}",
                "- 文档场景：上市公司企业年报",
                f"- 公司：{profile.get('company_name_target', '')}",
                f"- 当前页面：{group_record['page_no']}",
                "- 当前输入单元：短标签 / 小标题",
            ],
        ),
        join_section(
            "翻译要求",
            [
                "- 保持短、稳、正式，不要自由改写。",
                "- 不要把短标签扩写成解释性句子。",
                "- 不负责排版和回填。",
            ],
        ),
        join_section(
            "页面上下文",
            [
                *render_page_section_lines(group_context_record.get("page_sections", [])),
                f"- 术语使用模式：{group_context_record.get('term_usage_mode', '')}",
                *render_neighbor_lines(group_context_record.get("neighbor_context", {})),
            ],
        ),
        join_section("术语锁定", render_mapping_lines(group_context_record.get("mapping_hits", []))),
        join_section(
            "当前标签",
            [
                f"- unit_id：{group_record['group_id']}",
                "- 原文：",
                group_record["source_text_joined"],
            ],
        ),
        join_section("输出格式", [build_output_contract(group_record["group_id"], "<译文>")]),
    ]
    return "\n\n".join(section for section in sections if section)


def build_table_user_prompt(
    group_record: dict[str, Any],
    source_language: str,
    target_language: str,
    group_context_record: dict[str, Any],
    profile: dict[str, Any],
) -> str:
    source_lines = nonempty_lines(group_record["source_text_joined"])
    sections = [
        join_section(
            "任务",
            [
                f"- 语言方向：{source_language} -> {target_language}",
                "- 文档场景：上市公司企业年报",
                f"- 公司：{profile.get('company_name_target', '')}",
                f"- 当前页面：{group_record['page_no']}",
                "- 当前输入单元：表格单元 / 表格行",
                f"- table_role：{GROUP_STORE.get(group_record['group_id'], {}).get('table_role', 'row')}",
            ],
        ),
        join_section(
            "翻译要求",
            [
                "- 保持表格语义，不要改写成正文句子。",
                "- 尽量保持原有行结构和顺序。",
                "- 数字、百分比、货币、缩写、括号位置必须准确。",
                "- 不负责排版和回填。",
            ],
        ),
        join_section(
            "页面上下文",
            [
                *render_page_section_lines(group_context_record.get("page_sections", [])),
                *render_neighbor_lines(group_context_record.get("neighbor_context", {})),
            ],
        ),
        join_section("术语锁定", render_mapping_lines(group_context_record.get("mapping_hits", []))),
        join_section("事实锁定", render_fact_lock_lines(group_context_record.get("fact_locks", []))),
        join_section(
            "当前表格输入",
            [
                f"- unit_id：{group_record['group_id']}",
                f"- 原文行数：{len(source_lines)}",
                "- 原文：",
                group_record["source_text_joined"],
            ],
        ),
        join_section("输出格式", [build_output_contract(group_record["group_id"], "<译文>")]),
    ]
    return "\n\n".join(section for section in sections if section)


def build_translation_prompts_v2(
    group_record: dict[str, Any],
    source_language: str,
    target_language: str,
    group_context_record: dict[str, Any],
) -> tuple[str, str]:
    profile = group_context_record.get("global_profile", {})
    lane = group_context_record.get("lane", group_record.get("lane", "body"))
    common_payload = {
        "task": {
            "scenario": "listed_company_annual_report",
            "industry": profile.get("industry", ""),
            "report_type": profile.get("report_type", ""),
            "company_name_target": profile.get("company_name_target", ""),
            "direction": f"{source_language} -> {target_language}",
        },
        "page_context": {
            "page_no": group_record["page_no"],
            "page_sections": group_context_record.get("page_sections", []),
            "term_usage_mode": group_context_record.get("term_usage_mode", ""),
            "neighbor_context": group_context_record.get("neighbor_context", {}),
        },
        "mapping_hits": [
            {"source": item["source"], "target": item["target"], "hit_type": item["hit_type"]}
            for item in group_context_record.get("mapping_hits", [])
        ],
        "fact_locks": [
            {
                "label": item["label"],
                "fact_type": item["fact_type"],
                "source_value": item["source_value"],
                "expected_forms": item["expected_forms"],
            }
            for item in group_context_record.get("fact_locks", [])
        ],
    }
    if lane == "table":
        system_prompt = "\n".join(
            [
                "你是上市公司年报中的表格翻译器。",
                f"语言方向：{source_language} -> {target_language}。",
                "只处理当前 table unit。",
                "必须逐行保持表格语义，不要把表格行改写成正文句子。",
                "优先保持源文本的行结构、顺序和数字位置；能一行对一行就一行对一行。",
                "数字、百分比、括号、货币、年份、缩写和顺序必须准确。",
                "只翻译文本标签，不要改写数字，不要补充解释。",
                "版面适配不是你的职责，不要为了适配版面删词改义。",
                "只输出 JSON，且只能输出 JSON。",
            ]
        )
        user_payload = {
            **common_payload,
            "current_unit": {
                "unit_id": group_record["group_id"],
                "lane": lane,
                "table_role": GROUP_STORE.get(group_record["group_id"], {}).get("table_role", "row"),
                "source_text": group_record["source_text_joined"],
                "source_line_count": len(nonempty_lines(group_record["source_text_joined"])),
                "source_lines": nonempty_lines(group_record["source_text_joined"]),
            },
            "output_format": {"translations": [{"unit_id": group_record["group_id"], "translation": "<译文>"}]},
        }
        user_prompt = "\n".join(
            [
                "文档场景：上市保险公司企业年报。",
                "当前输入属于表格通道。不要把表格行改写成正文句子。",
                "如果源文本本身是多行，请尽量保持译文也是多行，并与源行顺序一致。",
                json.dumps(user_payload, ensure_ascii=False, indent=2),
            ]
        )
    elif lane == "caption_label":
        system_prompt = "\n".join(
            [
                "你是上市公司年报中的标签翻译器。",
                f"语言方向：{source_language} -> {target_language}。",
                "只处理当前 caption/label unit。",
                "保持短、稳、正式，不自由改写。",
                "只输出 JSON，且只能输出 JSON。",
            ]
        )
        user_payload = {
            **common_payload,
            "current_unit": {
                "unit_id": group_record["group_id"],
                "lane": lane,
                "source_text": group_record["source_text_joined"],
            },
            "output_format": {"translations": [{"unit_id": group_record["group_id"], "translation": "<译文>"}]},
        }
        user_prompt = "\n".join(
            [
                "文档场景：上市保险公司企业年报。",
                "当前输入属于短标签通道。优先使用标准年报表达。",
                json.dumps(user_payload, ensure_ascii=False, indent=2),
            ]
        )
    else:
        system_prompt = "\n".join(
            [
                "你是上市公司年报翻译器。",
                f"语言方向：{source_language} -> {target_language}。",
                "只处理当前 body semantic group。",
                "只可在当前组内恢复跨块断句，不得跨组补写、跨组删写或改写事实。",
                "必须严格满足 mapping_hits 与 fact_locks。",
                "版面回填、字体压缩、分块分配不是你的职责，不要为了适配版面删词改义。",
                "保持正式、稳定、可出版的企业年报文风。",
                "只输出 JSON，且只能输出 JSON。",
            ]
        )
        user_payload = {
            **common_payload,
            "current_group": {
                "group_id": group_record["group_id"],
                "lane": lane,
                "group_text": group_record["source_text_joined"],
                "source_block_ids": group_record["block_ids"],
                "source_block_count": len(group_record["block_ids"]),
            },
            "output_format": {"translations": [{"unit_id": group_record["group_id"], "translation": "<译文>"}]},
        }
        user_prompt = "\n".join(
            [
                "文档场景：上市保险公司企业年报。",
                "先满足 fact_locks，再保证术语稳定、语义完整和年报文风。",
                json.dumps(user_payload, ensure_ascii=False, indent=2),
            ]
        )
    PROMPT_AUDIT.append(
        {
            "group_id": group_record["group_id"],
            "page_no": group_record["page_no"],
            "lane": lane,
            "uses_group_text": "\"group_text\"" in user_prompt,
            "uses_table_role": "\"table_role\"" in user_prompt,
            "contains_raw_blocks_array": "\"blocks\"" in user_prompt,
        }
    )
    return system_prompt, user_prompt


def build_compact_prompts_v2(
    unit: dict[str, Any],
    source_language: str,
    target_language: str,
    context_pack: dict[str, Any],
    current_translation: str,
) -> tuple[str, str]:
    lane = context_pack.get("lane", unit.get("lane", "body"))
    if lane == "body":
        return ORIGINAL_BUILD_COMPACT_PROMPTS(unit, source_language, target_language, context_pack, current_translation)
    if lane == "table":
        current_table_translation = normalize_table_translation(current_translation)
        system_prompt = "\n".join(
            [
                "你是表格译文压缩器。",
                f"语言方向：{source_language} -> {target_language}。",
                "只做最小必要压缩。",
                "必须保持表格逐行结构，不要把多行压成一句话。",
                "不要改动数字、百分比、年份、金额、专有名词、缩写和行顺序。",
                "只输出 JSON，且只能输出 JSON。",
            ]
        )
        user_payload = {
            "current_unit": {
                "unit_id": unit["group_id"],
                "lane": lane,
                "table_role": GROUP_STORE.get(unit["group_id"], {}).get("table_role", "row"),
                "source_text": unit["source_text_joined"],
                "source_line_count": len(nonempty_lines(unit["source_text_joined"])),
                "current_translation": current_table_translation,
                "current_line_count": len(nonempty_lines(current_table_translation)),
            },
            "output_format": {"translations": [{"unit_id": unit["group_id"], "translation": "<更紧凑译文>"}]},
        }
        user_prompt = "\n".join(
            [
                "文档场景：上市保险公司企业年报。",
                "当前输入属于表格通道。只允许做最小必要压缩，且必须保持逐行结构。",
                json.dumps(user_payload, ensure_ascii=False, indent=2),
            ]
        )
        return system_prompt, user_prompt
    system_prompt = "\n".join(
        [
            "你是版面压缩器。",
            f"语言方向：{source_language} -> {target_language}。",
            "只做最小必要压缩。",
            "不得改动数字、百分比、年份、金额、专有名词。",
            "只输出 JSON，且只能输出 JSON。",
        ]
    )
    user_payload = {
        "current_unit": {
            "unit_id": unit["group_id"],
            "lane": lane,
            "source_text": unit["source_text_joined"],
            "current_translation": sp12.clean_translation(current_translation),
        },
        "output_format": {"translations": [{"unit_id": unit["group_id"], "translation": "<更紧凑译文>"}]},
    }
    user_prompt = "\n".join(["文档场景：上市保险公司企业年报。", json.dumps(user_payload, ensure_ascii=False, indent=2)])
    return system_prompt, user_prompt


def post_normalize_translation_v2(unit: dict[str, Any], context_pack: dict[str, Any], translation: str) -> str:
    lane = unit.get("lane", context_pack.get("lane"))
    if lane == "table":
        return normalize_table_translation(translation)
    if lane == "caption_label":
        return sp12.clean_translation(translation).strip()
    return ORIGINAL_POST_NORMALIZE(unit, context_pack, translation)


def tokenize_for_layout(text: str, target_language: str) -> list[str]:
    normalized = clean_multiline_translation(text)
    if not normalized:
        return []
    if target_language.lower() == "english" or " " in normalized:
        return re.findall(r"\S+\s*", normalized)
    return [char for char in normalized if char.strip()]


def choose_font_specs(style: dict[str, Any]) -> list[dict[str, Any]]:
    font_specs = sp05.normalize_font_specs(
        style.get("font_specs") or [style.get("font_name") or "Helvetica", "Helvetica", "Times-Roman"]
    )
    return font_specs or [{"fontname": "Helvetica"}]


def preferred_font_spec(style: dict[str, Any]) -> dict[str, Any]:
    return choose_font_specs(style)[0]


def wrap_tokens_to_width(tokens: list[str], font_spec: dict[str, Any], font_size: float, max_width: float) -> list[str]:
    if not tokens:
        return []
    width = max(6.0, float(max_width))
    lines: list[str] = []
    current = ""
    for token in tokens:
        candidate = f"{current}{token}"
        candidate_width = sp05.measure_text_width(candidate.strip(), font_spec, fontsize=font_size)
        if current and candidate_width > width:
            lines.append(current.strip())
            current = token
            continue
        current = candidate
    if current.strip():
        lines.append(current.strip())
    return lines


def token_char_size(token: str) -> int:
    return max(1, len(token.strip()))


def token_boundary_bonus(token: str) -> float:
    stripped = token.strip()
    if not stripped:
        return 0.0
    if re.search(r"[.!?;:]$", stripped):
        return 0.45
    if re.search(r"[,)]$", stripped):
        return 0.25
    return 0.0


def split_tokens_by_block_weights(tokens: list[str], blocks: list[dict[str, Any]]) -> list[list[str]]:
    if not blocks:
        return []
    if len(blocks) == 1:
        return [tokens]

    weights = [
        max(
            1.0,
            float(block.get("char_count") or len(sp12.clean_text(block.get("source_text", ""))) or 1),
            float(block["bbox"][3] - block["bbox"][1]) * 2.2,
        )
        for block in blocks
    ]
    token_sizes = [token_char_size(token) for token in tokens]
    remaining_chars = sum(token_sizes)
    remaining_weight = sum(weights)
    cursor = 0
    chunks: list[list[str]] = []

    for index, weight in enumerate(weights):
        blocks_left_after = len(blocks) - index - 1
        if index == len(blocks) - 1:
            chunks.append(tokens[cursor:])
            break
        if cursor >= len(tokens):
            chunks.append([])
            remaining_weight -= weight
            continue
        target_chars = max(1, int(round(remaining_chars * weight / max(1.0, remaining_weight))))
        start = cursor
        consumed = 0
        best_end = min(len(tokens) - blocks_left_after, start + 1)
        best_score = float("inf")
        probe = start
        while probe < len(tokens) - blocks_left_after:
            consumed += token_sizes[probe]
            score = abs(consumed - target_chars) - token_boundary_bonus(tokens[probe])
            if consumed >= max(1, int(target_chars * 0.65)) and score < best_score:
                best_end = probe + 1
                best_score = score
            if consumed >= target_chars and probe + 1 > best_end and token_boundary_bonus(tokens[probe]) > 0:
                best_end = probe + 1
                break
            if consumed > target_chars * 1.35 and probe + 1 >= best_end:
                break
            probe += 1
        chunks.append(tokens[start:best_end])
        used_chars = sum(token_sizes[start:best_end])
        cursor = best_end
        remaining_chars -= used_chars
        remaining_weight -= weight

    while len(chunks) < len(blocks):
        chunks.append([])
    return chunks


def block_lineheight(block: dict[str, Any]) -> float:
    font_size = max(1.0, float(block["_style"]["font_size"]))
    if font_size >= 14:
        return 0.98
    if font_size <= 9:
        return 0.92
    return 0.95


def block_required_height(block: dict[str, Any], line_count: int, scale: float) -> float:
    original_height = max(4.0, float(block["bbox"][3] - block["bbox"][1]))
    if line_count <= 0:
        return max(4.0, original_height * 0.4)
    font_size = max(1.0, float(block["_style"]["font_size"]) * scale)
    lineheight = block_lineheight(block)
    padding = max(2.0, font_size * 0.35)
    return max(original_height * 0.5, font_size + max(0, line_count - 1) * font_size * lineheight + padding)


def probe_textbox_insert(
    page: fitz.Page,
    rect: fitz.Rect,
    text: str,
    block: dict[str, Any],
    scale: float,
) -> float:
    style = block["_style"]
    font_spec = preferred_font_spec(style)
    font_name = sp05.ensure_page_font(page, font_spec)
    shape = page.new_shape()
    return shape.insert_textbox(
        rect,
        text,
        fontsize=max(1.0, float(style["font_size"]) * scale),
        fontname=font_name,
        color=sp05.rgb255_to_pdf(style["color_rgb255"]),
        align=0,
        lineheight=block_lineheight(block),
    )


def commit_textbox_insert(
    page: fitz.Page,
    rect: fitz.Rect,
    text: str,
    block: dict[str, Any],
    scale: float,
) -> None:
    style = block["_style"]
    font_spec = preferred_font_spec(style)
    font_name = sp05.ensure_page_font(page, font_spec)
    shape = page.new_shape()
    shape.insert_textbox(
        rect,
        text,
        fontsize=max(1.0, float(style["font_size"]) * scale),
        fontname=font_name,
        color=sp05.rgb255_to_pdf(style["color_rgb255"]),
        align=0,
        lineheight=block_lineheight(block),
    )
    shape.commit()


def build_adaptive_group_layout(
    page: fitz.Page,
    unit: dict[str, Any],
    translation: str,
    target_language: str,
) -> dict[str, Any] | None:
    blocks = unit.get("blocks") or []
    if len(blocks) <= 1:
        return None
    tokens = tokenize_for_layout(translation, target_language)
    if not tokens:
        return None

    group_rect = fitz.Rect(unit["group_bbox"])
    original_heights = [max(4.0, float(block["bbox"][3] - block["bbox"][1])) for block in blocks]
    gaps = [
        max(0.0, min(10.0, float(curr["bbox"][1] - prev["bbox"][3])))
        for prev, curr in zip(blocks, blocks[1:])
    ]
    fixed_gap_total = sum(gaps)
    available_height = max(6.0, group_rect.height - fixed_gap_total)
    token_chunks = split_tokens_by_block_weights(tokens, blocks)

    for step in range(0, 20):
        scale = round(1.02 - step * 0.025, 3)
        wrapped_by_block: list[list[str]] = []
        required_heights: list[float] = []
        for block, chunk in zip(blocks, token_chunks):
            font_spec = preferred_font_spec(block["_style"])
            font_size = max(1.0, float(block["_style"]["font_size"]) * scale)
            max_width = max(8.0, float(block["bbox"][2] - block["bbox"][0]) - 2.0)
            wrapped_lines = wrap_tokens_to_width(chunk, font_spec, font_size, max_width)
            wrapped_by_block.append(wrapped_lines)
            required_heights.append(block_required_height(block, len(wrapped_lines), scale))
        if sum(required_heights) > available_height:
            continue

        slack = max(0.0, available_height - sum(required_heights))
        original_total = sum(original_heights) or 1.0
        expanded_heights = [
            required + slack * (original_height / original_total)
            for required, original_height in zip(required_heights, original_heights)
        ]

        y_cursor = group_rect.y0
        reconstructed: dict[str, list[float]] = {}
        block_texts: dict[str, str] = {}
        all_lines: list[str] = []
        overflow = False

        for index, (block, lines, height) in enumerate(zip(blocks, wrapped_by_block, expanded_heights)):
            rect = fitz.Rect(
                float(block["bbox"][0]),
                y_cursor,
                float(block["bbox"][2]),
                min(group_rect.y1, y_cursor + height),
            )
            text = "\n".join(lines).strip()
            reconstructed[block["block_id"]] = [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)]
            block_texts[block["block_id"]] = text
            all_lines.extend(lines)
            if text:
                unused = probe_textbox_insert(page=page, rect=rect, text=text, block=block, scale=scale)
                if unused < -0.1:
                    overflow = True
                    break
            y_cursor = rect.y1 + (gaps[index] if index < len(gaps) else 0.0)

        if overflow:
            continue

        return {
            "layout_mode": "group_adaptive_blocks",
            "fit_status": "ok" if scale >= 0.85 else "font_shrink",
            "font_ratio": round(scale, 3),
            "rendered_lines": all_lines,
            "rendered_by_block": block_texts,
            "slot_count": len(all_lines),
            "selected_scale": scale,
            "reconstructed_bboxes": reconstructed,
            "wrapped_lines_by_block": {
                block["block_id"]: lines for block, lines in zip(blocks, wrapped_by_block)
            },
            "block_heights": {block["block_id"]: round(height, 2) for block, height in zip(blocks, expanded_heights)},
        }
    return None


def render_body_group_v2(page: fitz.Page, unit: dict[str, Any], translation: str, target_language: str, commit: bool) -> dict[str, Any]:
    original_preview = ORIGINAL_RENDER_UNIT(
        page=page,
        unit=unit,
        translation=translation,
        target_language=target_language,
        commit=False,
    )
    adaptive_preview = build_adaptive_group_layout(page=page, unit=unit, translation=translation, target_language=target_language)

    use_adaptive = False
    if adaptive_preview is not None:
        original_ratio = float(original_preview.get("font_ratio") or 0.0)
        adaptive_ratio = float(adaptive_preview.get("font_ratio") or 0.0)
        original_ok = original_preview.get("fit_status") != "overflow"
        adaptive_ok = adaptive_preview.get("fit_status") != "overflow"
        if adaptive_ok and not original_ok:
            use_adaptive = True
        elif original_ratio < 0.7 and adaptive_ratio >= original_ratio:
            use_adaptive = True
        elif original_ratio < 0.85 and adaptive_ratio >= original_ratio + 0.03:
            use_adaptive = True
        elif adaptive_ratio >= 0.9 and original_ratio < 0.9:
            use_adaptive = True
        elif adaptive_ratio > original_ratio + 0.1:
            use_adaptive = True

    if not use_adaptive:
        committed = ORIGINAL_RENDER_UNIT(
            page=page,
            unit=unit,
            translation=translation,
            target_language=target_language,
            commit=commit,
        )
        committed["reconstructed_bboxes"] = {}
        return committed

    if commit:
        for block in unit["blocks"]:
            block_id = block["block_id"]
            text = adaptive_preview["rendered_by_block"].get(block_id, "")
            if not text.strip():
                continue
            rect = fitz.Rect(adaptive_preview["reconstructed_bboxes"][block_id])
            commit_textbox_insert(page=page, rect=rect, text=text, block=block, scale=float(adaptive_preview["selected_scale"]))
    return adaptive_preview


def render_table_unit_v2(page: fitz.Page, unit: dict[str, Any], translation: str, commit: bool) -> dict[str, Any]:
    block = unit["blocks"][0]
    font_size, fit_status, layout_mode = sp05.fit_translation_block(
        page=page,
        block=block,
        translation=translation,
        style=block["_style"],
        raw_segments=block["_segments"],
        commit=commit,
    )
    return {
        "layout_mode": layout_mode,
        "fit_status": fit_status,
        "font_ratio": round(font_size / max(1.0, block["_style"]["font_size"]), 3),
        "rendered_lines": nonempty_lines(translation) or [translation],
        "rendered_by_block": {block["block_id"]: translation},
        "slot_count": len(block["_segments"]) or 1,
        "selected_scale": round(font_size / max(1.0, block["_style"]["font_size"]), 3),
    }


def render_unit_v2(page: fitz.Page, unit: dict[str, Any], translation: str, target_language: str, commit: bool) -> dict[str, Any]:
    if unit.get("lane") == "table":
        result = render_table_unit_v2(page=page, unit=unit, translation=translation, commit=commit)
    elif unit.get("lane") == "body" and unit.get("mode") == "semantic_group":
        result = render_body_group_v2(
            page=page,
            unit=unit,
            translation=translation,
            target_language=target_language,
            commit=commit,
        )
    else:
        result = ORIGINAL_RENDER_UNIT(page=page, unit=unit, translation=translation, target_language=target_language, commit=commit)
    fragments, anchor_maps = build_render_artifacts(unit, result)
    result["render_fragments"] = fragments
    result["fragment_anchor_map"] = anchor_maps
    result["lane"] = unit.get("lane")
    result["group_bbox"] = unit.get("group_bbox")
    result["used_group_reflow"] = len(unit.get("block_ids", [])) > 1 and unit.get("mode") == "semantic_group"
    return result


def build_translation_prompts_v3(
    group_record: dict[str, Any],
    source_language: str,
    target_language: str,
    group_context_record: dict[str, Any],
) -> tuple[str, str]:
    profile = group_context_record.get("global_profile", {})
    lane = group_context_record.get("lane", group_record.get("lane", "body"))
    if lane == "table":
        system_prompt = "\n".join(
            [
                "你是上市公司年报表格翻译助手。",
                f"语言方向：{source_language} -> {target_language}。",
                "只负责翻译当前表格单元，不负责排版、回填、压缩。",
                "保持表格语义和顺序，不要改写成正文。",
                "输出必须是 JSON，且只能输出 JSON。",
            ]
        )
        user_prompt = build_table_user_prompt(group_record, source_language, target_language, group_context_record, profile)
    elif lane == "caption_label":
        system_prompt = "\n".join(
            [
                "你是上市公司年报标签翻译助手。",
                f"语言方向：{source_language} -> {target_language}。",
                "只负责翻译当前短标签或小标题，不负责排版、回填、压缩。",
                "保持短、稳、正式，不要扩写成解释句。",
                "输出必须是 JSON，且只能输出 JSON。",
            ]
        )
        user_prompt = build_label_user_prompt(group_record, source_language, target_language, group_context_record, profile)
    else:
        system_prompt = "\n".join(
            [
                "你是上市公司年报正文翻译助手。",
                f"语言方向：{source_language} -> {target_language}。",
                "只负责翻译当前正文语义组，不负责排版、回填、压缩、分块。",
                "允许在当前 group 内恢复断句和语义连接，但禁止跨 group 补写、删写或改写事实。",
                "必须遵守术语锁定和事实锁定。",
                "输出必须是 JSON，且只能输出 JSON。",
            ]
        )
        user_prompt = build_body_user_prompt(group_record, source_language, target_language, group_context_record, profile)
    PROMPT_AUDIT.append(
        {
            "group_id": group_record["group_id"],
            "page_no": group_record["page_no"],
            "lane": lane,
            "uses_group_text": "当前正文组" in user_prompt,
            "uses_table_role": "table_role" in user_prompt,
            "contains_raw_blocks_array": "\"blocks\"" in user_prompt,
            "json_contract_only": "\"translations\"" in user_prompt and "\"task\"" not in user_prompt,
        }
    )
    return system_prompt, user_prompt


def build_compact_prompts_v3(
    unit: dict[str, Any],
    source_language: str,
    target_language: str,
    context_pack: dict[str, Any],
    current_translation: str,
) -> tuple[str, str]:
    lane = context_pack.get("lane", unit.get("lane", "body"))
    if lane == "table":
        current_table_translation = normalize_table_translation(current_translation)
        system_prompt = "\n".join(
            [
                "你是上市公司年报表格译文压缩助手。",
                f"语言方向：{source_language} -> {target_language}。",
                "只做最小必要压缩，不改变数字、顺序、单位和表格语义。",
                "输出必须是 JSON，且只能输出 JSON。",
            ]
        )
        user_prompt = "\n".join(
            [
                "任务",
                f"- unit_id：{unit['group_id']}",
                "- 输入单元：表格单元 / 表格行",
                f"- table_role：{GROUP_STORE.get(unit['group_id'], {}).get('table_role', 'row')}",
                "",
                "压缩要求",
                "- 只做最小必要压缩。",
                "- 保持逐行表格语义。",
                "- 不改变数字、百分比、货币、括号、缩写和顺序。",
                "",
                "原文",
                unit["source_text_joined"],
                "",
                "当前译文",
                current_table_translation,
                "",
                "输出格式",
                build_output_contract(unit["group_id"], "<更紧凑译文>"),
            ]
        )
        return system_prompt, user_prompt
    if lane == "caption_label":
        system_prompt = "\n".join(
            [
                "你是上市公司年报短标签压缩助手。",
                f"语言方向：{source_language} -> {target_language}。",
                "只做最小必要压缩，不改变核心语义，不扩写。",
                "输出必须是 JSON，且只能输出 JSON。",
            ]
        )
        user_prompt = "\n".join(
            [
                "任务",
                f"- unit_id：{unit['group_id']}",
                "- 输入单元：短标签 / 小标题",
                "",
                "原文",
                unit["source_text_joined"],
                "",
                "当前译文",
                sp12.clean_translation(current_translation),
                "",
                "输出格式",
                build_output_contract(unit["group_id"], "<更紧凑译文>"),
            ]
        )
        return system_prompt, user_prompt
    system_prompt = "\n".join(
        [
            "你是上市公司年报正文译文压缩助手。",
            f"语言方向：{source_language} -> {target_language}。",
            "只做最小必要压缩，不改变事实、数字、术语和句间逻辑。",
            "不要承担排版、分块、回填职责。",
            "输出必须是 JSON，且只能输出 JSON。",
        ]
    )
    user_prompt = "\n".join(
        [
            "任务",
            f"- unit_id：{unit['group_id']}",
            "- 输入单元：正文语义组（group）",
            "",
            "压缩要求",
            "- 只删除冗余表达，不改变事实和数字。",
            "- 保持年报文风正式稳定。",
            "- 不要跨组补写，也不要为了版面改义。",
            "",
            "原文",
            unit["source_text_joined"],
            "",
            "当前译文",
            sp12.clean_translation(current_translation),
            "",
            "输出格式",
            build_output_contract(unit["group_id"], "<更紧凑译文>"),
        ]
    )
    return system_prompt, user_prompt


def parse_unit_translation_v3(response_json: dict[str, Any], unit_id: str) -> str:
    try:
        return ORIGINAL_PARSE_UNIT_TRANSLATION(response_json, unit_id)
    except Exception:
        text = sp05.extract_response_text(response_json)
        candidate = sp05.strip_code_fence(text)
        pattern = re.compile(
            rf'"unit_id"\s*:\s*"{re.escape(unit_id)}"[\s\S]*?"translation"\s*:\s*"(?P<translation>[\s\S]*?)"\s*(?=,?\s*[\r\n]+\s*[}}\]])',
            flags=re.S,
        )
        match = pattern.search(candidate)
        if match:
            return sp12.clean_translation(sp05.decode_model_string(match.group("translation")))
        for line in candidate.splitlines():
            if '"translation"' not in line:
                continue
            start = line.find(":", line.find('"translation"'))
            first_quote = line.find('"', start + 1)
            last_quote = line.rfind('"')
            if first_quote != -1 and last_quote > first_quote:
                return sp12.clean_translation(sp05.decode_model_string(line[first_quote + 1 : last_quote]))
        raise


def build_group_container_style(unit: dict[str, Any]) -> dict[str, Any]:
    blocks = unit.get("blocks") or []
    first_style = dict(blocks[0]["_style"])
    avg_font = sum(float(block["_style"]["font_size"]) for block in blocks) / max(1, len(blocks))
    first_style["font_size"] = round(avg_font, 3)
    return first_style


def build_group_container_layout(
    page: fitz.Page,
    unit: dict[str, Any],
    translation: str,
    target_language: str,
) -> dict[str, Any] | None:
    blocks = unit.get("blocks") or []
    if len(blocks) <= 1:
        return None
    normalized = clean_multiline_translation(translation)
    tokens = tokenize_for_layout(normalized, target_language)
    if not tokens:
        return None
    style = build_group_container_style(unit)
    rect = fitz.Rect(unit["group_bbox"])
    font_size, fit_status = sp05.textbox_fit(
        page=page,
        rect=rect,
        text=normalized,
        style=style,
        min_font_size=max(4.5, float(style["font_size"]) * 0.55),
        commit=False,
    )
    if fit_status == "overflow":
        return None
    block_chunks = split_tokens_by_block_weights(tokens, blocks)
    block_texts = {
        block["block_id"]: "".join(chunk).strip()
        for block, chunk in zip(blocks, block_chunks)
        if "".join(chunk).strip()
    }
    return {
        "layout_mode": "group_container",
        "fit_status": fit_status,
        "font_ratio": round(font_size / max(1.0, float(style["font_size"])), 3),
        "rendered_lines": nonempty_lines(normalized) or [normalized],
        "rendered_by_block": block_texts,
        "slot_count": len(nonempty_lines(normalized)) or 1,
        "selected_scale": round(font_size / max(1.0, float(style["font_size"])), 3),
        "reconstructed_bboxes": {},
        "container_bbox": [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)],
        "container_style": style,
    }


def candidate_mode_priority(layout_mode: str) -> int:
    if layout_mode == "group_container":
        return 3
    if layout_mode == "group_adaptive_blocks":
        return 2
    if layout_mode == "group_slots":
        return 1
    return 0


def should_prefer_body_candidate(best: dict[str, Any], challenger: dict[str, Any]) -> bool:
    status_rank = {"overflow": 0, "font_shrink": 1, "ok": 2}
    best_status = status_rank.get(str(best.get("fit_status")), 0)
    challenger_status = status_rank.get(str(challenger.get("fit_status")), 0)
    if challenger_status != best_status:
        return challenger_status > best_status
    best_ratio = float(best.get("font_ratio") or 0.0)
    challenger_ratio = float(challenger.get("font_ratio") or 0.0)
    if challenger_ratio >= best_ratio + 0.08:
        return True
    if best_ratio < 0.8 and challenger_ratio >= best_ratio + 0.02:
        return True
    if challenger_ratio >= best_ratio - 0.01 and candidate_mode_priority(str(challenger.get("layout_mode"))) > candidate_mode_priority(str(best.get("layout_mode"))) and best_ratio < 0.9:
        return True
    return False


def render_body_group_v3(page: fitz.Page, unit: dict[str, Any], translation: str, target_language: str, commit: bool) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    original_preview = ORIGINAL_RENDER_UNIT(
        page=page,
        unit=unit,
        translation=translation,
        target_language=target_language,
        commit=False,
    )
    original_preview["reconstructed_bboxes"] = {}
    candidates.append(original_preview)
    adaptive_preview = build_adaptive_group_layout(page=page, unit=unit, translation=translation, target_language=target_language)
    if adaptive_preview is not None:
        candidates.append(adaptive_preview)
    container_preview = build_group_container_layout(page=page, unit=unit, translation=translation, target_language=target_language)
    if container_preview is not None:
        candidates.append(container_preview)

    best = candidates[0]
    for challenger in candidates[1:]:
        if should_prefer_body_candidate(best, challenger):
            best = challenger

    if not commit:
        return best

    if best.get("layout_mode") == "group_container":
        style = best["container_style"]
        rect = fitz.Rect(best["container_bbox"])
        font_size, fit_status = sp05.textbox_fit(
            page=page,
            rect=rect,
            text=translation,
            style=style,
            min_font_size=max(4.5, float(style["font_size"]) * 0.55),
            commit=True,
        )
        best = {
            **best,
            "fit_status": fit_status,
            "font_ratio": round(font_size / max(1.0, float(style["font_size"])), 3),
            "selected_scale": round(font_size / max(1.0, float(style["font_size"])), 3),
        }
        return best
    if best.get("layout_mode") == "group_adaptive_blocks":
        for block in unit["blocks"]:
            block_id = block["block_id"]
            text = best["rendered_by_block"].get(block_id, "")
            if not text.strip():
                continue
            rect = fitz.Rect(best["reconstructed_bboxes"][block_id])
            commit_textbox_insert(page=page, rect=rect, text=text, block=block, scale=float(best["selected_scale"]))
        return best
    committed = ORIGINAL_RENDER_UNIT(
        page=page,
        unit=unit,
        translation=translation,
        target_language=target_language,
        commit=True,
    )
    committed["reconstructed_bboxes"] = {}
    return committed


def render_unit_v3(page: fitz.Page, unit: dict[str, Any], translation: str, target_language: str, commit: bool) -> dict[str, Any]:
    if unit.get("lane") == "table":
        result = render_table_unit_v2(page=page, unit=unit, translation=translation, commit=commit)
    elif unit.get("lane") == "body" and unit.get("mode") == "semantic_group":
        result = render_body_group_v3(
            page=page,
            unit=unit,
            translation=translation,
            target_language=target_language,
            commit=commit,
        )
    else:
        result = ORIGINAL_RENDER_UNIT(page=page, unit=unit, translation=translation, target_language=target_language, commit=commit)
    fragments, anchor_maps = build_render_artifacts(unit, result)
    result["render_fragments"] = fragments
    result["fragment_anchor_map"] = anchor_maps
    result["lane"] = unit.get("lane")
    result["group_bbox"] = unit.get("group_bbox")
    result["used_group_reflow"] = len(unit.get("block_ids", [])) > 1 and unit.get("mode") == "semantic_group"
    return result


def per_page_deltas(evaluation_payload: dict[str, Any]) -> list[dict[str, Any]]:
    baseline = {item["page_no"]: item for item in evaluation_payload.get("v11_vs_human", {}).get("per_page", [])}
    current = {item["page_no"]: item for item in evaluation_payload.get("spike12_vs_human", {}).get("per_page", [])}
    rows: list[dict[str, Any]] = []
    for page_no in sorted(current):
        base = baseline.get(page_no, {})
        now = current[page_no]
        rows.append(
            {
                "page_no": page_no,
                "token_f1_delta": round(now.get("token_f1", 0.0) - base.get("token_f1", 0.0), 4),
                "content_f1_delta": round(now.get("content_f1", 0.0) - base.get("content_f1", 0.0), 4),
                "sequence_ratio_delta": round(now.get("sequence_ratio", 0.0) - base.get("sequence_ratio", 0.0), 4),
                "number_recall_delta": round(now.get("number_recall", 0.0) - base.get("number_recall", 0.0), 4),
            }
        )
    return rows


def average_layout_from_report(report_path: Path) -> dict[int, dict[str, Any]]:
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        grouped: dict[int, list[dict[str, Any]]] = {}
        for item in payload:
            if "page_no" not in item:
                continue
            grouped.setdefault(int(item["page_no"]), []).append(item)
        return {
            page_no: {
                "avg_font_ratio": round(sum(float(unit.get("font_ratio_final", 0.0)) for unit in items) / max(1, len(items)), 4),
                "compact_used": sum(1 for unit in items if unit.get("used_compact_retry")),
                "overflow_count": sum(1 for unit in items if str(unit.get("fit_status_final")) == "overflow"),
                "unit_count": len(items),
            }
            for page_no, items in grouped.items()
        }
    return sp12.average_layout_from_report(report_path)


def build_baseline_page_texts(path: Path, page_block_order: dict[int, list[str]], pages: list[int]) -> dict[int, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    page_block_texts: dict[int, dict[str, str]] = {page_no: {} for page_no in pages}
    for item in payload:
        page_no = int(item["page_no"])
        if page_no not in page_block_texts:
            continue
        if item.get("block_outputs"):
            for block_id, block_text in item.get("block_outputs", {}).items():
                page_block_texts[page_no][str(block_id)] = str(block_text or "")
        elif item.get("block_id") and "translation" in item:
            page_block_texts[page_no][str(item["block_id"])] = str(item.get("translation") or "")
    results: dict[int, str] = {}
    for page_no in pages:
        ordered = [page_block_texts[page_no].get(block_id, "") for block_id in page_block_order[page_no]]
        results[page_no] = sp12.normalize_text_for_eval("\n".join(text for text in ordered if text.strip()))
    return results


def build_stage_markdown(stage_results: list[dict[str, Any]]) -> str:
    lines = ["# Spike 13 阶段状态", ""]
    for stage in stage_results:
        lines.append(f"## 阶段 {stage['stage']} {stage['stage_name']}")
        lines.append(f"- 状态：{'通过' if stage['passed'] else '失败'}")
        lines.append(f"- 结论：{stage['summary']}")
        lines.append(f"- 详情：`{json.dumps(stage['details'], ensure_ascii=False)}`")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_acceptance_report(stage_results: list[dict[str, Any]], evaluation_payload: dict[str, Any], focus_findings: dict[str, Any], output_dir: Path) -> str:
    overall = "通过" if all(item["passed"] for item in stage_results) else "未通过"
    avg = evaluation_payload["spike12_vs_human"]["average"]
    delta = evaluation_payload["delta_spike12_minus_v11"]
    lines = [
        "# Spike 13 验收报告",
        "",
        f"- 总体结论：{overall}",
        f"- 输出目录：`{output_dir}`",
        f"- 阶段门通过数：{sum(1 for item in stage_results if item['passed'])}/{len(stage_results)}",
        "",
        "## 机制核验",
        f"- 正文 prompt 审计：`{output_dir / 'prompt_audit.json'}`",
        f"- lane 路由证据：`{output_dir / 'lane_records.json'}`",
        f"- 组级上下文：`{output_dir / 'group_context_records.json'}`",
        f"- 回填片段：`{output_dir / 'render_fragments.json'}`",
        f"- fragment 到 anchor 映射：`{output_dir / 'fragment_anchor_maps.json'}`",
        "",
        "## 平均指标",
        f"- token_f1：{avg['token_f1']}（相对基线 {delta['token_f1']:+.4f}）",
        f"- content_f1：{avg['content_f1']}（相对基线 {delta['content_f1']:+.4f}）",
        f"- sequence_ratio：{avg['sequence_ratio']}（相对基线 {delta['sequence_ratio']:+.4f}）",
        f"- number_recall：{avg['number_recall']}（相对基线 {delta['number_recall']:+.4f}）",
        "",
        "## 页级观察",
    ]
    for row in per_page_deltas(evaluation_payload):
        verdict = "提升" if row["content_f1_delta"] >= 0 else "退化"
        lines.append(
            f"- 页 {row['page_no']}：{verdict}；token_f1 {row['token_f1_delta']:+.4f}，content_f1 {row['content_f1_delta']:+.4f}，sequence_ratio {row['sequence_ratio_delta']:+.4f}，number_recall {row['number_recall_delta']:+.4f}"
        )
    lines.extend(
        [
            "",
            "## 关键问题核验",
            f"- p19 尾句并组：{'是' if focus_findings['tail_group_merged'] else '否'}",
            f"- `US$19.97 billion` 硬错误：{focus_findings['bad_scale_count']}",
            f"- `regarding dividend payments` 残句：{focus_findings['broken_fragment_count']}",
            f"- 末期股息/全年股息串位：{focus_findings['dividend_mixup_count']}",
            f"- 侧边栏进入主链路：{focus_findings['sidebar_intrusion_count']}",
            "",
            "## 结论说明",
            "- 若正文 prompt 审计仍显示模型看到原始 blocks 文本数组，则本轮不应视为机制达标。",
            "- 若页 20 表格区指标或版面退化，应优先复盘 table lane，而不是继续调正文提示词。",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def build_summary_report(stage_results: list[dict[str, Any]], evaluation_payload: dict[str, Any], focus_findings: dict[str, Any]) -> str:
    delta = evaluation_payload["delta_spike12_minus_v11"]
    page_rows = per_page_deltas(evaluation_payload)
    improved_pages = [str(item["page_no"]) for item in page_rows if item["content_f1_delta"] >= 0]
    regressed_pages = [str(item["page_no"]) for item in page_rows if item["content_f1_delta"] < 0]
    lines = [
        "# Spike 13 总结报告",
        "",
        "## 本轮确认有效的点",
        "- 已把 lane separation 提升为独立设计约束，而不是仅靠后验观察。",
        "- 正文、表格、短标签和侧边栏已在工程侧区分处理。",
        "- `prompt_audit.json`、`lane_records.json`、`render_fragments.json`、`fragment_anchor_maps.json` 已作为证据文件补入输出。",
        "",
        "## 本轮结果",
        f"- 相对基线，token_f1 {delta['token_f1']:+.4f}，content_f1 {delta['content_f1']:+.4f}，sequence_ratio {delta['sequence_ratio']:+.4f}，number_recall {delta['number_recall']:+.4f}。",
        f"- 内容页提升页：{', '.join(improved_pages) if improved_pages else '无'}。",
        f"- 内容页退化页：{', '.join(regressed_pages) if regressed_pages else '无'}。",
        f"- 第 19 页尾句并组：{'已保持' if focus_findings['tail_group_merged'] else '失效'}。",
        "",
        "## 反思",
        "- 只看平均指标仍然不够，必须回到页级和 lane 级看退化点。",
        "- 正文 prompt 如果已经去块化，而结果仍不稳，下一步应优先复盘 context 和 render，而不是再把工程职责塞回 prompt。",
        "- 表格 lane 如果仍退化，说明单块原位回填只是过渡方案，后续需要继续走 cell/row 级 TableIR。",
        "",
        "## 后续动作",
        "- 先检查 `prompt_audit.json` 中正文 lane 是否还有原始块暴露。",
        "- 重点复盘页 20 的 `table lane` 输出和版面结果。",
        "- 在确认前 20 页没有新增硬错误后，再决定是否扩页。",
        "",
        "## 阶段状态",
    ]
    for stage in stage_results:
        lines.append(f"- 阶段 {stage['stage']} {stage['stage_name']}：{'通过' if stage['passed'] else '失败'}")
    return "\n".join(lines).strip() + "\n"


def write_json_file(path: Path, payload: Any) -> None:
    if path.name == "anchor_blocks.json":
        ORIGINAL_WRITE_JSON(path, payload)
        ORIGINAL_WRITE_JSON(
            path.with_name("lane_records.json"),
            [
                {
                    "page_no": item["page_no"],
                    "block_id": item["block_id"],
                    "lane": item.get("lane"),
                    "lane_reason": item.get("lane_reason"),
                    "source_signals": item.get("lane_signals", []),
                    "bbox": item.get("bbox"),
                }
                for item in payload
            ],
        )
        return
    if path.name == "semantic_groups.json":
        enriched = []
        body_groups = []
        table_units = []
        caption_units = []
        for item in payload:
            full = GROUP_STORE.get(item["group_id"], {})
            row = {**item, "lane": full.get("lane"), "group_bbox": full.get("group_bbox"), "group_text": full.get("source_text_joined"), "table_role": full.get("table_role")}
            enriched.append(row)
            if full.get("lane") == "body":
                body_groups.append(row)
            elif full.get("lane") == "table":
                table_units.append(row)
            elif full.get("lane") == "caption_label":
                caption_units.append(row)
        ORIGINAL_WRITE_JSON(path, enriched)
        ORIGINAL_WRITE_JSON(path.with_name("body_group_debug.json"), body_groups)
        ORIGINAL_WRITE_JSON(path.with_name("table_units.json"), table_units)
        ORIGINAL_WRITE_JSON(path.with_name("caption_units.json"), caption_units)
        return
    if path.name == "translations.json":
        ORIGINAL_WRITE_JSON(path, payload)
        render_fragments: list[dict[str, Any]] = []
        fragment_maps: list[dict[str, Any]] = []
        for item in payload:
            render_result = item.get("render_result") or {}
            render_fragments.extend(render_result.get("render_fragments") or [])
            fragment_maps.extend(render_result.get("fragment_anchor_map") or [])
        ORIGINAL_WRITE_JSON(path.with_name("render_fragments.json"), render_fragments)
        ORIGINAL_WRITE_JSON(path.with_name("fragment_anchor_maps.json"), fragment_maps)
        ORIGINAL_WRITE_JSON(path.with_name("prompt_audit.json"), PROMPT_AUDIT)
        return
    if path.name == "render_plans.json":
        ORIGINAL_WRITE_JSON(
            path,
            [
                {
                    **item,
                    "lane": GROUP_STORE.get(item["group_id"], {}).get("lane"),
                    "group_bbox": GROUP_STORE.get(item["group_id"], {}).get("group_bbox"),
                    "used_group_reflow": len(item.get("block_ids", [])) > 1
                    and item.get("layout_mode") in {"group_slots", "group_adaptive_blocks"},
                }
                for item in payload
            ],
        )
        return
    ORIGINAL_WRITE_JSON(path, payload)


sp12.parse_args = parse_args
sp12.AnthropicGatewayClient = AnthropicGatewayClientWithThinking
sp12.build_anchor_block_records = build_anchor_block_records
sp12.build_semantic_group_records = build_semantic_group_records
sp12.build_group_context_record = build_group_context_record
sp12.build_fact_lock_records = build_fact_lock_records
sp12.build_mapping_hit_records = build_mapping_hit_records
sp12.build_translation_prompts = build_translation_prompts_v3
sp12.build_compact_prompts = build_compact_prompts_v3
sp12.post_normalize_translation = post_normalize_translation_v2
sp12.parse_unit_translation = parse_unit_translation_v3
sp12.render_unit = render_unit_v3
sp12.build_baseline_page_texts = build_baseline_page_texts
sp12.average_layout_from_report = average_layout_from_report
sp12.build_stage_markdown = build_stage_markdown
sp12.build_acceptance_report = build_acceptance_report
sp12.build_summary_report = build_summary_report
sp12.write_json_file = write_json_file


if __name__ == "__main__":
    sp12.main()
