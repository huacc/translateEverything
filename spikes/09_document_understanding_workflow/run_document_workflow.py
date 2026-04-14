from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_07 = ROOT / "spikes" / "07_translation_current_bundle" / "scripts" / "translate_with_controls.py"
SCRIPT_08 = ROOT / "spikes" / "08_semantic_group_reflow" / "semantic_group_reflow.py"
DEFAULT_BLOCKS = ROOT / "spikes" / "01_text_block_extraction" / "output" / "AIA_2021_Annual_Report_zh" / "blocks.jsonl"
DEFAULT_OUTPUT = ROOT / "spikes" / "09_document_understanding_workflow" / "output" / "sample_2021_pages_10_13_19_20"
DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
DEFAULT_COMPANY_MEMORY = ROOT / "spikes" / "06_company_memory_learning" / "output" / "AIA_excl_2021_v4" / "company_memory.json"


def load_module(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reuse07 = load_module(SCRIPT_07, "workflow_reuse07")
reuse08 = load_module(SCRIPT_08, "workflow_reuse08")

AnthropicGatewayClient = reuse07.AnthropicGatewayClient
classify_block_type = reuse07.classify_block_type
load_page_records = reuse07.load_page_records
normalize_source_text = reuse07.normalize_source_text
parse_json_from_text = reuse07.parse_json_from_text
parse_page_numbers = reuse07.parse_page_numbers
write_json_file = reuse07.write_json_file
extract_response_text = reuse07.extract_response_text
build_semantic_units = reuse08.build_semantic_units
is_narrative_candidate = reuse08.is_narrative_candidate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Spike 09: workflow-first document understanding and group labeling experiment."
    )
    parser.add_argument("--blocks-jsonl", type=Path, default=DEFAULT_BLOCKS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pages", type=str, default="10,13,19,20")
    parser.add_argument("--front-pages", type=int, default=30)
    parser.add_argument("--company-memory", type=Path, default=DEFAULT_COMPANY_MEMORY)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-output-tokens", type=int, default=2600)
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def clean_text(text: str) -> str:
    return normalize_source_text(text).strip()


def build_front_page_records(blocks_jsonl: Path, max_pages: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with blocks_jsonl.open("r", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if int(record["page_no"]) <= max_pages:
                records.append(record)
    return records


def enrich_blocks(page_record: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for block in sorted(page_record["blocks"], key=lambda item: item["reading_order"]):
        block_type = classify_block_type(block)
        enriched = {**block, "_block_type": block_type}
        enriched["_narrative_candidate"] = is_narrative_candidate(enriched, block_type)
        blocks.append(enriched)
    return blocks


def summarize_page(page_record: dict[str, Any]) -> dict[str, Any]:
    blocks = enrich_blocks(page_record)
    headings = [clean_text(block["source_text"]) for block in blocks if block["_block_type"] == "heading"][:4]
    labels = [clean_text(block["source_text"]) for block in blocks if block["_block_type"] == "label"][:6]
    body_samples = [clean_text(block["source_text"]) for block in blocks if block["_block_type"] == "body" and int(block.get("char_count") or 0) >= 18][:2]
    type_counter = Counter(block["_block_type"] for block in blocks)
    return {
        "page_no": page_record["page_no"],
        "text_block_count": page_record["text_block_count"],
        "headings": headings,
        "labels": labels,
        "body_samples": body_samples,
        "block_type_summary": dict(type_counter),
    }


def build_document_evidence(front_page_records: list[dict[str, Any]], company_memory: dict[str, Any]) -> dict[str, Any]:
    page_summaries = [summarize_page(record) for record in front_page_records]
    heading_hits: list[dict[str, Any]] = []
    label_hits: list[dict[str, Any]] = []
    for page in page_summaries:
        for heading in page["headings"]:
            heading_hits.append({"page_no": page["page_no"], "text": heading})
        for label in page["labels"]:
            label_hits.append({"page_no": page["page_no"], "text": label})

    title_entries = []
    for item in company_memory.get("prompt_title_entries", [])[:20]:
        title_entries.append(
            {
                "source": item.get("source"),
                "target": item.get("target"),
                "source_kind": item.get("source_kind"),
            }
        )

    memory_terms = []
    term_map = company_memory.get("term_map", {})
    for source_text, target_text in list(term_map.items())[:40]:
        memory_terms.append({"source": source_text, "target": target_text})

    return {
        "front_page_count": len(front_page_records),
        "page_summaries": page_summaries,
        "headings": heading_hits[:80],
        "labels": label_hits[:120],
        "company_memory_titles": title_entries,
        "company_memory_terms": memory_terms,
    }


def build_document_understanding_prompts(evidence: dict[str, Any]) -> tuple[str, str]:
    system_prompt = "\n".join(
        [
            "你是上市公司年报文档理解器。",
            "你不是翻译器，不输出译文，不输出长解释。",
            "你的任务是基于整份年报的证据，产出后续翻译 workflow 可复用的结构化背景档案。",
            "如果不确定，可以保守输出，并显式标记 confidence。",
            "输出必须是 JSON，且只能输出 JSON。",
        ]
    )
    user_prompt = "\n".join(
        [
            "请根据以下证据，输出结构化文档背景。",
            "目标语言方向：Traditional Chinese -> English",
            "你需要输出：document_profile / section_map / role_map / termbase / style_guide / risk_policy",
            "不要输出英文译文段落，只输出结构化背景。",
            "证据如下：",
            json.dumps(evidence, ensure_ascii=False, indent=2),
            "返回格式示例：",
            json.dumps(
                {
                    "document_profile": {
                        "company_name_source": "",
                        "company_name_target": "",
                        "industry": "",
                        "report_type": "annual_report",
                        "source_language": "Traditional Chinese",
                        "target_language": "English",
                        "style_keywords": [],
                        "confidence": "medium",
                    },
                    "section_map": [],
                    "role_map": [],
                    "termbase": [],
                    "style_guide": {"global_rules": [], "title_rules": [], "table_rules": [], "body_rules": []},
                    "risk_policy": {"high_risk_flags": [], "context_escalation_rules": []},
                },
                ensure_ascii=False,
                indent=2,
            ),
        ]
    )
    return system_prompt, user_prompt


def build_group_label_prompt(
    document_background: dict[str, Any],
    unit: dict[str, Any],
) -> tuple[str, str]:
    system_prompt = "\n".join(
        [
            "你是年报组级标签器。",
            "你不是翻译器，不输出译文。",
            "你只输出当前文本单元的结构化标签，用于后续翻译前的上下文选择。",
            "标签必须保守、可复用、可工程消费。",
            "输出必须是 JSON，且只能输出 JSON。",
        ]
    )
    background_brief = {
        "document_profile": document_background.get("document_profile", {}),
        "section_map": document_background.get("section_map", [])[:12],
        "role_map": document_background.get("role_map", [])[:20],
        "termbase": document_background.get("termbase", [])[:50],
        "style_guide": document_background.get("style_guide", {}),
        "risk_policy": document_background.get("risk_policy", {}),
    }
    unit_payload = {
        "page_no": unit["page_no"],
        "unit_id": unit["unit_id"],
        "mode": unit["mode"],
        "block_ids": unit["block_ids"],
        "block_types": unit["block_types"],
        "source_text_joined": unit["source_text_joined"],
    }
    user_prompt = "\n".join(
        [
            "请只对当前 unit 做标签，不要翻译。",
            "文档背景：",
            json.dumps(background_brief, ensure_ascii=False, indent=2),
            "当前 unit：",
            json.dumps(unit_payload, ensure_ascii=False, indent=2),
            "返回字段：section_id, content_type, speaker_role, topic_tags, term_hits, needs_context, context_scope, risk_level, risk_flags, translation_constraints",
            "返回格式示例：",
            json.dumps(
                {
                    "unit_id": unit["unit_id"],
                    "page_no": unit["page_no"],
                    "section_id": "",
                    "content_type": "narrative_body",
                    "speaker_role": "management",
                    "topic_tags": [],
                    "term_hits": [],
                    "needs_context": True,
                    "context_scope": "section",
                    "risk_level": "medium",
                    "risk_flags": [],
                    "translation_constraints": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
        ]
    )
    return system_prompt, user_prompt


def export_exchange(
    client: Any,
    system_prompt: str,
    user_prompt: str,
    prompt_dir: Path,
    api_dir: Path,
    stem: str,
    meta: dict[str, Any],
) -> dict[str, Any]:
    request_payload, response_payload = client._post_messages(system_prompt, user_prompt)
    write_text(prompt_dir / f"{stem}.system.txt", system_prompt)
    write_text(prompt_dir / f"{stem}.user.txt", user_prompt)
    write_text(prompt_dir / f"{stem}.response.txt", extract_response_text(response_payload))
    write_json_file(
        api_dir / f"{stem}.json",
        {"meta": meta, "request": request_payload, "response": response_payload},
    )
    return response_payload


def parse_payload(response_payload: dict[str, Any]) -> dict[str, Any]:
    return parse_json_from_text(extract_response_text(response_payload))


def select_context_pack(document_background: dict[str, Any], label: dict[str, Any]) -> dict[str, Any]:
    section_id = str(label.get("section_id") or "")
    term_hits = {str(item) for item in label.get("term_hits", [])}
    selected_section = next(
        (item for item in document_background.get("section_map", []) if str(item.get("section_id", "")) == section_id),
        None,
    )
    matched_terms = []
    for item in document_background.get("termbase", []):
        source = str(item.get("source") or "")
        target = str(item.get("target") or "")
        if source in term_hits or target in term_hits:
            matched_terms.append(item)
    return {
        "global": document_background.get("document_profile", {}),
        "section": selected_section,
        "terms": matched_terms[:16],
        "style": document_background.get("style_guide", {}),
        "risk_policy": document_background.get("risk_policy", {}),
        "label": label,
    }


def build_units(page_records: dict[int, dict[str, Any]], page_numbers: list[int]) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    for page_no in page_numbers:
        blocks = enrich_blocks(page_records[page_no])
        for unit in build_semantic_units(page_no, blocks):
            units.append(
                {
                    "page_no": unit["page_no"],
                    "unit_id": unit["unit_id"],
                    "mode": unit["mode"],
                    "block_ids": unit["block_ids"],
                    "block_types": unit["block_types"],
                    "source_text_joined": unit["source_text_joined"],
                }
            )
    return units


def summarize_labels(labels: list[dict[str, Any]]) -> dict[str, Any]:
    risk_counter = Counter(str(item.get("risk_level") or "unknown") for item in labels)
    content_counter = Counter(str(item.get("content_type") or "unknown") for item in labels)
    section_counter = Counter(str(item.get("section_id") or "unknown") for item in labels)
    context_counter = Counter(str(item.get("context_scope") or "unknown") for item in labels)
    flag_counter: Counter[str] = Counter()
    for item in labels:
        for flag in item.get("risk_flags", []):
            flag_counter[str(flag)] += 1
    return {
        "label_count": len(labels),
        "risk_level_summary": dict(risk_counter),
        "content_type_summary": dict(content_counter),
        "section_summary": dict(section_counter),
        "context_scope_summary": dict(context_counter),
        "top_risk_flags": flag_counter.most_common(16),
    }


def main() -> None:
    args = parse_args()
    page_numbers = parse_page_numbers(args.pages)
    page_records = load_page_records(args.blocks_jsonl, set(page_numbers))
    front_page_records = build_front_page_records(args.blocks_jsonl, args.front_pages)
    company_memory = read_json(args.company_memory) if args.company_memory.exists() else {}
    client = AnthropicGatewayClient.from_env(model=args.model, max_output_tokens=args.max_output_tokens)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    prompt_dir = args.output_dir / "prompt_exports"
    api_dir = args.output_dir / "api_logs"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    api_dir.mkdir(parents=True, exist_ok=True)

    evidence = build_document_evidence(front_page_records, company_memory)
    write_json_file(args.output_dir / "document_evidence.json", evidence)

    doc_system, doc_user = build_document_understanding_prompts(evidence)
    doc_response = export_exchange(
        client=client,
        system_prompt=doc_system,
        user_prompt=doc_user,
        prompt_dir=prompt_dir,
        api_dir=api_dir,
        stem="document_understanding",
        meta={"stage": "document_understanding"},
    )
    document_background = parse_payload(doc_response)
    write_json_file(args.output_dir / "document_background.json", document_background)

    units = build_units(page_records, page_numbers)
    write_json_file(args.output_dir / "units.json", units)

    labels: list[dict[str, Any]] = []
    context_packs: list[dict[str, Any]] = []
    for unit in units:
        label_system, label_user = build_group_label_prompt(document_background, unit)
        label_response = export_exchange(
            client=client,
            system_prompt=label_system,
            user_prompt=label_user,
            prompt_dir=prompt_dir,
            api_dir=api_dir,
            stem=f"{unit['unit_id']}_label",
            meta={"stage": "group_label", "page_no": unit["page_no"], "unit_id": unit["unit_id"]},
        )
        label = parse_payload(label_response)
        labels.append(label)
        context_packs.append(
            {
                "unit_id": unit["unit_id"],
                "page_no": unit["page_no"],
                "context_pack": select_context_pack(document_background, label),
            }
        )

    write_json_file(args.output_dir / "group_labels.json", labels)
    write_json_file(args.output_dir / "selected_context_packs.json", context_packs)
    write_json_file(
        args.output_dir / "report.json",
        {
            "pages": page_numbers,
            "front_pages_used": args.front_pages,
            "document_background_summary": {
                "section_count": len(document_background.get("section_map", [])),
                "role_count": len(document_background.get("role_map", [])),
                "term_count": len(document_background.get("termbase", [])),
            },
            "group_label_summary": summarize_labels(labels),
        },
    )


if __name__ == "__main__":
    main()
