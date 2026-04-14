from __future__ import annotations

import argparse
import importlib.util
import json
import re
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import fitz


ROOT = Path(__file__).resolve().parents[2]
SPIKE10_SCRIPT = ROOT / "spikes" / "10_background_context_translation" / "translate_with_background_context.py"
SPIKE09_BACKGROUND = (
    ROOT
    / "spikes"
    / "09_document_understanding_workflow"
    / "output"
    / "sample_2021_pages_10_13_19_20_run1"
    / "document_background.json"
)
SPIKE06_COMPANY_MEMORY = (
    ROOT
    / "spikes"
    / "06_company_memory_learning"
    / "output"
    / "AIA_excl_2021_v4"
    / "company_memory.json"
)
DEFAULT_BLOCKS = ROOT / "spikes" / "01_text_block_extraction" / "output" / "AIA_2021_Annual_Report_zh" / "blocks.jsonl"
DEFAULT_OUTPUT = ROOT / "spikes" / "11_sanitized_background_translation" / "output" / "focus_pages_10_13_19_20_run1"

FINANCIAL_SECTION_TYPES = {"financial_review", "cfo_review", "business_metrics", "valuation_metrics"}
GENERIC_SECTION_TYPES = {"executive_summary", "financial_review"}

STRUCTURED_EXACT_OVERRIDES = {
    "概覽\n財務及營運回顧\n企業管治\n其他資料\n財務報表": "Overview\nFinancial and Operating Review\nCorporate Governance\nAdditional Information\nFinancial Statements",
    "財務及營運回顧": "Financial and Operating Review",
    "集團首席財務總監回顧": "Group Chief Financial Officer's Review",
    "按分部劃分的新業務價值、年化新保費及利潤率": "VONB, ANP and Margin by Segment",
    "2020年\n2019年\n新業務價值變動": "2020\n2019\nVONB Change",
    "新業務\n價值\n利潤率\n年化\n新保費\n新業務\n價值": "VONB\nMargin\nANP\nVONB",
    "新業務\n價值\n利潤率\n年化\n新保費\n按年變動\n（固定匯率）\n按年變動\n（實質匯率）": "VONB\nMargin\nANP\nYoY\nCER\nYoY\nAER",
    "百萬美元，除另有說明外\n新業務\n價值": "US$ millions, unless otherwise stated\nVONB",
    "為符合合併準備金及\n資本要求所作調整": "Adjustment to reflect\nconsolidated reserving and\ncapital requirements",
    "未分配集團總部開支的\n稅後價值": "After-tax value of unallocated\nGroup Office expenses",
    "扣除非控股權益前的總計": "Total before\nnon-controlling interests",
}

STRUCTURED_LINE_OVERRIDES = {
    "概覽": "Overview",
    "主席報告": "Chairman's Statement",
    "財務及營運回顧": "Financial and Operating Review",
    "集團首席財務總監回顧": "Group Chief Financial Officer's Review",
    "新業務表現": "New Business Performance",
    "企業管治": "Corporate Governance",
    "其他資料": "Additional Information",
    "財務報表": "Financial Statements",
    "香港": "Hong Kong",
    "泰國": "Thailand",
    "新加坡": "Singapore",
    "馬來西亞": "Malaysia",
    "中國內地": "Mainland China",
    "其他市場": "Other Markets",
    "小計": "Subtotal",
    "非控股權益": "Non-controlling interests",
    "總計": "Total",
    "無意義": "n/m",
    "百萬美元，除另有說明外": "US$ millions, unless otherwise stated",
}

TARGET_SECTION_OVERRIDES = {
    "概覽": "Overview",
    "主席報告": "Chairman's Statement",
    "集團首席執行官兼總裁報告": "Group Chief Executive and President's Report",
    "財務及營運回顧": "Financial and Operating Review",
    "集團首席財務總監回顧": "Group Chief Financial Officer's Review",
    "新業務表現": "New Business Performance",
    "內涵價值權益": "EV Equity",
    "企業管治": "Corporate Governance",
    "其他資料": "Additional Information",
    "財務報表": "Financial Statements",
}

CONTEXTUAL_TERM_RULES = [
    {
        "sources": ["友邦保險中國業務"],
        "heading": "AIA China",
        "table": "AIA China",
        "overview_narrative": "AIA China",
        "financial_narrative": "AIA China",
    },
    {
        "sources": ["友邦保險香港業務"],
        "heading": "AIA Hong Kong",
        "table": "AIA Hong Kong",
        "overview_narrative": "AIA Hong Kong",
        "financial_narrative": "AIA Hong Kong",
    },
    {
        "sources": ["友邦保險澳門分公司"],
        "heading": "AIA Macau",
        "table": "AIA Macau",
        "overview_narrative": "AIA Macau",
        "financial_narrative": "AIA Macau",
    },
    {
        "sources": ["中國內地訪港客戶", "中國內地訪港旅客", "中國內地訪澳客戶"],
        "heading": "Mainland Chinese visitors",
        "table": "Mainland Chinese visitors",
        "overview_narrative": "Mainland Chinese visitors",
        "financial_narrative": "Mainland Chinese visitors",
    },
    {
        "sources": ["個人遊計劃"],
        "heading": "Individual Visit Scheme",
        "table": "Individual Visit Scheme",
        "overview_narrative": "Individual Visit Scheme",
        "financial_narrative": "Individual Visit Scheme",
    },
    {
        "sources": ["新業務價值利潤率"],
        "heading": "New Business Value Margin",
        "table": "VONB margin",
        "overview_narrative": "value of new business margin",
        "financial_narrative": "VONB margin",
    },
    {
        "sources": ["新業務價值"],
        "heading": "New Business Value",
        "table": "VONB",
        "overview_narrative": "value of new business (VONB)",
        "financial_narrative": "VONB",
    },
    {
        "sources": ["年化新保費"],
        "heading": "Annualized New Premium",
        "table": "ANP",
        "overview_narrative": "annualized new premiums (ANP)",
        "financial_narrative": "ANP",
    },
    {
        "sources": ["稅後營運溢利"],
        "heading": "Operating Profit After Tax",
        "table": "OPAT",
        "overview_narrative": "operating profit after tax (OPAT)",
        "financial_narrative": "OPAT",
    },
    {
        "sources": ["產生的基本自由盈餘", "基本自由盈餘"],
        "heading": "Underlying Free Surplus Generation",
        "table": "UFSG",
        "overview_narrative": "underlying free surplus generation (UFSG)",
        "financial_narrative": "UFSG",
    },
    {
        "sources": ["自由盈餘"],
        "heading": "Free Surplus",
        "table": "Free Surplus",
        "overview_narrative": "free surplus",
        "financial_narrative": "free surplus",
    },
    {
        "sources": ["內涵價值權益"],
        "heading": "EV Equity",
        "table": "EV Equity",
        "overview_narrative": "EV Equity",
        "financial_narrative": "Embedded value (EV) equity",
    },
    {
        "sources": ["內涵價值營運溢利"],
        "heading": "EV Operating Profit",
        "table": "EV operating profit",
        "overview_narrative": "EV operating profit",
        "financial_narrative": "EV operating profit",
    },
    {
        "sources": ["內涵價值"],
        "heading": "Embedded Value",
        "table": "EV",
        "overview_narrative": "embedded value (EV)",
        "financial_narrative": "EV",
    },
    {
        "sources": ["集團當地資本總和法覆蓋率"],
        "heading": "Group LCSM Cover Ratio",
        "table": "Group LCSM cover ratio",
        "overview_narrative": "Group Local Capital Summation Method (LCSM) cover ratio",
        "financial_narrative": "Group Local Capital Summation Method (LCSM) cover ratio",
    },
    {
        "sources": ["營運溢利率"],
        "heading": "Operating Margin",
        "table": "operating margin",
        "overview_narrative": "operating margin",
        "financial_narrative": "operating margin",
    },
    {
        "sources": ["有效保單組合"],
        "heading": "In-Force Portfolio",
        "table": "in-force portfolio",
        "overview_narrative": "in-force portfolio",
        "financial_narrative": "in-force portfolio",
    },
    {
        "sources": ["續保率"],
        "heading": "Renewal Rate",
        "table": "persistency",
        "overview_narrative": "renewal rate",
        "financial_narrative": "persistency",
    },
    {
        "sources": ["續保保費"],
        "heading": "Renewal Premiums",
        "table": "renewal premiums",
        "overview_narrative": "renewal premiums",
        "financial_narrative": "renewal premiums",
    },
    {
        "sources": ["2019冠狀病毒病"],
        "heading": "COVID-19",
        "table": "COVID-19",
        "overview_narrative": "COVID-19",
        "financial_narrative": "COVID-19",
    },
]


def load_module(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load_module(SPIKE10_SCRIPT, "spike11_base")

AnthropicGatewayClient = base.AnthropicGatewayClient
apply_text_redactions = base.apply_text_redactions
classify_block_type = base.classify_block_type
collect_relevant_terms = base.collect_relevant_terms
collect_unit_slots = base.collect_unit_slots
extract_raw_line_segments = base.extract_raw_line_segments
extract_response_text = base.extract_response_text
infer_block_style = base.infer_block_style
is_better_result = base.is_better_result
is_narrative_candidate = base.is_narrative_candidate
load_page_records = base.load_page_records
parse_page_numbers = base.parse_page_numbers
parse_unit_translation = base.parse_unit_translation
render_page = base.render_page
render_unit = base.render_unit
resolve_controlled_translation = base.resolve_controlled_translation
save_comparison = base.save_comparison
should_retry_compact = base.should_retry_compact
write_json_file = base.write_json_file
write_text_file = base.write_text_file
build_semantic_units = base.build_semantic_units
clean_text = base.clean_text
clean_translation = base.clean_translation


def find_first(name: str) -> Path:
    matches = sorted(ROOT.rglob(name), key=lambda item: len(str(item)))
    if not matches:
        raise FileNotFoundError(name)
    return matches[0]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Spike 11: sanitized document background with closed-form structural and terminology controls."
    )
    parser.add_argument("--input", type=Path, default=find_first("AIA_2021_Annual_Report_zh.pdf"))
    parser.add_argument("--blocks-jsonl", type=Path, default=DEFAULT_BLOCKS)
    parser.add_argument("--document-background", type=Path, default=SPIKE09_BACKGROUND)
    parser.add_argument("--company-memory", type=Path, default=SPIKE06_COMPANY_MEMORY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pages", type=str, default="10,13,19,20")
    parser.add_argument("--source-language", default="Traditional Chinese")
    parser.add_argument("--target-language", default="English")
    parser.add_argument("--model", default=base.DEFAULT_MODEL)
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


def build_company_title_map(company_memory: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in company_memory.get("prompt_title_entries", []):
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "").strip()
        target = str(item.get("target") or "").strip()
        if source and target:
            result[source] = target
    return result


def sanitize_document_background(document_background: dict[str, Any], company_memory: dict[str, Any]) -> dict[str, Any]:
    sanitized = deepcopy(document_background)
    title_map = build_company_title_map(company_memory)
    for item in sanitized.get("section_map", []):
        source = str(item.get("source_section") or "").strip()
        if source in TARGET_SECTION_OVERRIDES:
            item["target_section"] = TARGET_SECTION_OVERRIDES[source]
        elif source in title_map:
            item["target_section"] = title_map[source]

    sanitized["style_guide"] = {
        "global_rules": [
            {"rule": "Use US$ for U.S. dollar amounts."},
            {"rule": "Keep listed-company annual report disclosure tone formal and publishable."},
            {"rule": "Do not change numbers, percentages, years, named entities or financial metric values."},
        ],
        "title_rules": [
            {"rule": "Keep headings short, stable and standard."},
            {"rule": "Prefer established annual report section names over free paraphrase."},
        ],
        "table_rules": [
            {"rule": "Use established financial abbreviations for table labels when provided."},
            {"rule": "Keep row and column semantics unchanged."},
            {"rule": "Use n/m for 無意義."},
        ],
        "body_rules": [
            {"rule": "For overview narrative, use full financial metric name plus abbreviation when provided."},
            {"rule": "For financial review and business metrics narrative, use established abbreviations when provided."},
            {"rule": "Prefer AIA China / AIA Hong Kong / AIA Macau over loose paraphrases when matched."},
        ],
    }
    sanitized["translation_policy"] = {
        "scenario": "listed_company_annual_report",
        "direction": "Traditional Chinese -> English",
        "currency_notation": "US$",
    }
    return sanitized


def build_spike11_glossary(glossary: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(glossary)
    merged.setdefault("exact_map", {}).update(STRUCTURED_EXACT_OVERRIDES)
    merged.setdefault("line_map", {}).update(STRUCTURED_LINE_OVERRIDES)
    merged.setdefault("term_map", {}).update(
        {
            "友邦保險": "AIA",
            "友邦保險中國業務": "AIA China",
            "友邦保險香港業務": "AIA Hong Kong",
            "友邦保險澳門分公司": "AIA Macau",
            "中國內地": "Mainland China",
            "中國內地訪港客戶": "Mainland Chinese visitors",
            "中國內地訪港旅客": "Mainland Chinese visitors",
            "中國內地訪澳客戶": "Mainland Chinese visitors",
            "個人遊計劃": "Individual Visit Scheme",
        }
    )
    return merged


def page_range_width(section: dict[str, Any]) -> int:
    page_range = section.get("page_range") or []
    if len(page_range) == 2:
        start, end = int(page_range[0]), int(page_range[1])
        return max(1, end - start + 1)
    if len(page_range) == 1:
        return 1
    return 9999


def section_rank(item: dict[str, Any]) -> tuple[int, int, str]:
    content_type = str(item.get("content_type") or "")
    specificity_rank = 2 if content_type in GENERIC_SECTION_TYPES else 0
    parent_rank = 1 if content_type == "cfo_review" else 2
    return (page_range_width(item), specificity_rank + parent_rank, content_type)


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
    if not matches:
        return []

    matches.sort(key=section_rank)
    primary = matches[0]
    selected = [primary]
    primary_type = str(primary.get("content_type") or "")
    parent_candidates: list[dict[str, Any]] = []
    if primary_type == "business_metrics":
        parent_candidates = [item for item in matches[1:] if str(item.get("content_type") or "") in {"cfo_review", "financial_review"}]
    elif primary_type == "valuation_metrics":
        parent_candidates = [item for item in matches[1:] if str(item.get("content_type") or "") in {"financial_review"}]
    if parent_candidates:
        parent_candidates.sort(key=section_rank)
        selected.append(parent_candidates[0])
    return selected[:2]


def unit_text(unit: dict[str, Any]) -> str:
    return clean_text(unit.get("source_text_joined", ""))


def unit_is_table_like(unit: dict[str, Any], page_sections: list[dict[str, Any]]) -> bool:
    text = unit_text(unit)
    if re.search(r"\d", text) and re.search(r"[%$()]", text):
        return True
    if len(re.findall(r"\d", text)) >= 6:
        return True
    return any(str(item.get("content_type") or "") in FINANCIAL_SECTION_TYPES for item in page_sections) and re.search(r"\d", text) is not None


def unit_is_heading_like(unit: dict[str, Any]) -> bool:
    block_types = [str(item) for item in unit.get("block_types", [])]
    return len(block_types) == 1 and block_types[0] in {"heading", "label"}


def determine_term_usage_mode(unit: dict[str, Any], page_sections: list[dict[str, Any]]) -> str:
    if unit_is_heading_like(unit):
        return "heading"
    if unit_is_table_like(unit, page_sections):
        return "table"
    primary_content_type = str(page_sections[0].get("content_type") or "") if page_sections else ""
    if primary_content_type in FINANCIAL_SECTION_TYPES:
        return "financial_narrative"
    return "overview_narrative"


def select_style_rules(document_background: dict[str, Any], unit: dict[str, Any], page_sections: list[dict[str, Any]]) -> list[str]:
    style_guide = document_background.get("style_guide", {})
    rules = [str(item.get("rule") or "").strip() for item in style_guide.get("global_rules", [])]
    if unit_is_heading_like(unit):
        rules.extend(str(item.get("rule") or "").strip() for item in style_guide.get("title_rules", []))
    elif unit_is_table_like(unit, page_sections):
        rules.extend(str(item.get("rule") or "").strip() for item in style_guide.get("table_rules", []))
    else:
        rules.extend(str(item.get("rule") or "").strip() for item in style_guide.get("body_rules", []))
    seen: set[str] = set()
    deduped: list[str] = []
    for rule in rules:
        if not rule or rule in seen:
            continue
        seen.add(rule)
        deduped.append(rule)
    return deduped[:6]


def select_relevant_roles(document_background: dict[str, Any], unit: dict[str, Any], page_sections: list[dict[str, Any]]) -> list[dict[str, str]]:
    text = unit_text(unit)
    source_sections = {str(item.get("source_section") or "") for item in page_sections}
    selected: list[dict[str, str]] = []
    for item in document_background.get("role_map", []):
        source_title = str(item.get("source_title") or "").strip()
        context = str(item.get("context") or "").strip()
        if source_title and source_title in text:
            selected.append(
                {
                    "source": source_title,
                    "target": str(item.get("target_title") or "").strip(),
                    "role": str(item.get("role") or "").strip(),
                }
            )
            continue
        if context and context in source_sections:
            selected.append(
                {
                    "source": source_title,
                    "target": str(item.get("target_title") or "").strip(),
                    "role": str(item.get("role") or "").strip(),
                }
            )
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in selected:
        key = (item["source"], item["target"], item["role"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:4]


def select_context_terms(document_background: dict[str, Any], unit: dict[str, Any], page_sections: list[dict[str, Any]]) -> list[dict[str, str]]:
    text = unit_text(unit)
    usage_mode = determine_term_usage_mode(unit, page_sections)
    selected: list[dict[str, str]] = []
    covered_sources: set[str] = set()
    for rule in CONTEXTUAL_TERM_RULES:
        target = str(rule.get(usage_mode) or "").strip()
        if not target:
            continue
        for source in rule["sources"]:
            if source in text:
                covered_sources.add(source)
                selected.append({"source": source, "target": target})
                break

    for item in document_background.get("termbase", []):
        source = str(item.get("source_term") or "").strip()
        target = str(item.get("target_term") or "").strip()
        if source and target and source in text and source not in covered_sources:
            selected.append({"source": source, "target": target})

    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in selected:
        source = item["source"]
        if source in seen:
            continue
        seen.add(source)
        unique.append(item)
    return unique[:16]


def build_context_pack(document_background: dict[str, Any], unit: dict[str, Any]) -> dict[str, Any]:
    page_sections = select_page_sections(int(unit["page_no"]), document_background.get("section_map", []))
    profile = document_background.get("document_profile", {})
    usage_mode = determine_term_usage_mode(unit, page_sections)
    return {
        "global_profile": {
            "company_name_target": str(profile.get("company_name_target") or ""),
            "industry": str(profile.get("industry") or ""),
            "report_type": str(profile.get("report_type") or ""),
            "report_year": profile.get("report_year"),
        },
        "term_usage_mode": usage_mode,
        "page_sections": [
            {
                "source_section": str(item.get("source_section") or ""),
                "target_section": str(item.get("target_section") or ""),
                "content_type": str(item.get("content_type") or ""),
                "page_range": item.get("page_range", []),
            }
            for item in page_sections
        ],
        "roles": select_relevant_roles(document_background, unit, page_sections),
        "terms": select_context_terms(document_background, unit, page_sections),
        "style_rules": select_style_rules(document_background, unit, page_sections),
    }


def merge_term_hits(preferred_hits: list[dict[str, str]], glossary_hits: list[dict[str, str]]) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    seen_sources: set[str] = set()
    for group in [preferred_hits, glossary_hits]:
        for item in group:
            source = str(item.get("source") or "").strip()
            target = str(item.get("target") or "").strip()
            if not source or not target or source in seen_sources:
                continue
            seen_sources.add(source)
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
            "你是上市公司年报翻译器。",
            f"语言方向：{source_language} -> {target_language}。",
            "你只处理当前翻译单元。",
            "如果当前单元由多个连续文本块组成，只允许在当前组内恢复被换行打断的句子；不得引入组外信息。",
            "优先严格采用提供的标准术语、角色名称和章节叫法。",
            "不得增删事实，不得保留中文残片，不得输出解释。",
            "输出必须是 JSON，并且只能输出 JSON。",
        ]
    )
    blocks_payload = [
        {"block_id": block["block_id"], "source_text": clean_text(block.get("source_text", ""))}
        for block in unit["blocks"]
    ]
    user_payload = {
        "task": {
            "scenario": "listed_company_annual_report",
            "direction": f"{source_language} -> {target_language}",
        },
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
            "文档场景：上市公司企业年报。",
            "请优先复用 document_background 和 matched_terms 中提供的标准写法。",
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
    return base.build_compact_prompts(unit, source_language, target_language, context_pack, current_translation)


def export_prompt_bundle(prompt_dir: Path, stem: str, system_prompt: str, user_prompt: str, response_payload: dict[str, Any] | None = None) -> None:
    write_text_file(prompt_dir / f"{stem}.system.txt", system_prompt)
    write_text_file(prompt_dir / f"{stem}.user.txt", user_prompt)
    if response_payload is not None:
        write_text_file(prompt_dir / f"{stem}.response.txt", extract_response_text(response_payload))


def call_model_for_unit(client: Any, prompt_dir: Path, api_logs_dir: Path, stem: str, system_prompt: str, user_prompt: str, meta: dict[str, Any]) -> dict[str, Any]:
    request_payload, response_payload = client._post_messages(system_prompt, user_prompt)
    export_prompt_bundle(prompt_dir, stem, system_prompt, user_prompt, response_payload=response_payload)
    write_json_file(api_logs_dir / f"{stem}.json", {"meta": meta, "request": request_payload, "response": response_payload})
    return response_payload


def replace_first_case_insensitive(text: str, pattern: str, replacement: str) -> str:
    return re.sub(pattern, replacement, text, count=1, flags=re.IGNORECASE)


def decimal_to_text(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def normalize_hong_kong_cents_phrase(source_text: str, translation: str) -> str:
    if "港仙" not in source_text:
        return translation

    source_match = re.search(r"每股\s*(\d+(?:\.\d+)?)\s*港仙", source_text)
    if source_match:
        cents_text = source_match.group(1)
        return re.sub(
            r"\bHK\$\s*\d+(?:\.\d+)?\s+per share\b",
            f"{cents_text} Hong Kong cents per share",
            translation,
            flags=re.IGNORECASE,
        )

    def replace_amount(match: re.Match[str]) -> str:
        amount_text = match.group(1)
        try:
            cents_value = (Decimal(amount_text) * Decimal("100")).normalize()
        except InvalidOperation:
            return match.group(0)
        cents_text = format(cents_value, "f").rstrip("0").rstrip(".")
        return f"{cents_text} Hong Kong cents per share"

    return re.sub(
        r"\bHK\$\s*(\d+(?:\.\d+)?)\s+per share\b",
        replace_amount,
        translation,
        flags=re.IGNORECASE,
    )


def normalize_scaled_usd_amounts(source_text: str, translation: str) -> str:
    normalized = translation
    seen: set[tuple[str, str]] = set()
    patterns = [
        (r"(\d+(?:\.\d+)?)億美元", Decimal("0.1"), Decimal("100")),
        (r"(\d+(?:\.\d+)?)萬美元", Decimal("0.00001"), Decimal("0.01")),
    ]

    for pattern, billion_scale, million_scale in patterns:
        for match in re.finditer(pattern, source_text):
            source_number = match.group(1)
            dedupe_key = (pattern, source_number)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            try:
                source_value = Decimal(source_number)
            except InvalidOperation:
                continue

            expected_billion = source_value * billion_scale
            expected_million = source_value * million_scale
            if expected_billion >= 1:
                expected_amount = decimal_to_text(expected_billion)
                expected_unit = "billion"
            else:
                expected_amount = decimal_to_text(expected_million)
                expected_unit = "million"

            normalized = re.sub(
                rf"\bUS\$\s*{re.escape(source_number)}\s+(?:billion|million)\b",
                f"US${expected_amount} {expected_unit}",
                normalized,
                flags=re.IGNORECASE,
            )
    return normalized


def post_normalize_translation(unit: dict[str, Any], context_pack: dict[str, Any], translation: str) -> str:
    normalized = clean_translation(translation)
    usage_mode = str(context_pack.get("term_usage_mode") or "")
    source_text = unit_text(unit)

    normalized = re.sub(r"\bUSD(?=\s*\d)", "US$", normalized)
    normalized = normalize_scaled_usd_amounts(source_text, normalized)
    normalized = normalize_hong_kong_cents_phrase(source_text, normalized)
    normalized = normalized.replace("Mainland China visitors", "Mainland Chinese visitors")
    normalized = normalized.replace("Mainland China visitor", "Mainland Chinese visitor")
    normalized = normalized.replace("AIA's China business", "AIA China")
    normalized = normalized.replace("AIA's Hong Kong operations", "AIA Hong Kong")
    normalized = normalized.replace("AIA's Hong Kong business", "AIA Hong Kong")
    normalized = normalized.replace("AIA's Macau branch", "AIA Macau")
    normalized = normalized.replace("Group head office", "Group Office")
    normalized = normalized.replace("Group head office expenses", "Group Office expenses")
    normalized = normalized.replace("New Business Value margin", "VONB margin")
    normalized = normalized.replace("new business value margin", "VONB margin")
    normalized = normalized.replace("UFSG generated grew", "UFSG increased")

    if "提供無間斷的支援" in source_text:
        normalized = "Providing uninterrupted support."
    if "內涵價值權益" in source_text:
        normalized = replace_first_case_insensitive(normalized, r"\bev equity(?=\s+as at\b)", "Embedded value (EV) equity")

    if usage_mode == "financial_narrative":
        if "新業務價值" in source_text:
            normalized = re.sub(r"\b[Nn]ew [Bb]usiness [Vv]alue\b", "VONB", normalized)
        if "年化新保費" in source_text:
            normalized = re.sub(r"\b[Aa]nnuali[sz]ed [Nn]ew [Pp]remiums?\b", "ANP", normalized)
        if "稅後營運溢利" in source_text:
            normalized = re.sub(r"\b[Oo]perating [Pp]rofit [Aa]fter [Tt]ax\b", "OPAT", normalized)
        if "基本自由盈餘" in source_text:
            normalized = re.sub(r"\b(?:underlying )?[Ff]ree [Ss]urplus(?: [Gg]eneration| [Gg]enerated)?\b", "UFSG", normalized)
        if "內涵價值營運溢利" in source_text:
            normalized = re.sub(r"\b[Ee]mbedded [Vv]alue [Oo]perating [Pp]rofit\b", "EV operating profit", normalized)
        if "內涵價值權益" in source_text:
            normalized = replace_first_case_insensitive(normalized, r"\bev equity\b", "Embedded value (EV) equity")
            normalized = re.sub(r"\b[Ee]mbedded [Vv]alue(?: \(EV\))? [Ee]quity\b", "Embedded value (EV) equity", normalized)
        normalized = normalized.replace("Not meaningful", "n/m")
    elif usage_mode == "overview_narrative":
        if "新業務價值" in source_text and re.search(r"\bnew business value\b", normalized, flags=re.IGNORECASE):
            normalized = replace_first_case_insensitive(normalized, r"\bnew business value\b", "value of new business (VONB)")
            normalized = re.sub(r"\bnew business value\b", "VONB", normalized, flags=re.IGNORECASE)
        if "稅後營運溢利" in source_text:
            normalized = replace_first_case_insensitive(normalized, r"\boperating profit after tax\b", "operating profit after tax (OPAT)")
        if "基本自由盈餘" in source_text:
            normalized = replace_first_case_insensitive(
                normalized,
                r"\b(?:underlying )?free surplus(?: generated| generation)?\b",
                "underlying free surplus generation (UFSG)",
            )
        if "集團當地資本總和法覆蓋率" in source_text:
            normalized = re.sub(
                r"\b(?:the )?group(?:'s)? local capital [a-z ]+ coverage ratio\b",
                "Group Local Capital Summation Method (LCSM) cover ratio",
                normalized,
                flags=re.IGNORECASE,
            )
        if "內涵價值權益" in source_text:
            normalized = re.sub(r"\bembedded value equity\b", "EV Equity", normalized, flags=re.IGNORECASE)
    return normalized.strip()


def main() -> None:
    args = parse_args()
    base_glossary = load_json(args.glossary)
    glossary = build_spike11_glossary(base_glossary)
    patterns = load_json(args.patterns)
    document_background = sanitize_document_background(load_json(args.document_background), load_json(args.company_memory))
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

    write_json_file(args.output_dir / "document_background_sanitized.json", document_background)
    write_json_file(args.output_dir / "glossary_spike11_merged.json", glossary)

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
            enriched = {**block, "_block_type": block_type, "_style": style, "_segments": segments}
            enriched["_narrative_candidate"] = is_narrative_candidate(enriched, block_type)
            blocks.append(enriched)

        segment_map = {block["block_id"]: block["_segments"] for block in blocks}
        units = build_semantic_units(page_no=page_no, blocks=blocks)
        for unit in units:
            unit["slots"] = collect_unit_slots(unit, segment_map)

        page_unit_reports: list[dict[str, Any]] = []
        for unit in units:
            context_pack = build_context_pack(document_background, unit)
            context_packs.append({"page_no": page_no, "unit_id": unit["unit_id"], "context_pack": context_pack})

            controlled = None
            translation_source = "model_initial"
            if unit["mode"] == "single_block":
                controlled = resolve_controlled_translation(unit["blocks"][0], unit["blocks"][0]["_block_type"], glossary, patterns)

            if controlled:
                initial_translation = clean_translation(controlled["translation"])
                translation_source = str(controlled["translation_source"])
                matched_terms: list[dict[str, str]] = []
            else:
                glossary_hits = collect_relevant_terms(unit["blocks"], glossary, limit=12)
                matched_terms = merge_term_hits(context_pack.get("terms", []), glossary_hits)
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

            initial_translation = post_normalize_translation(unit, context_pack, initial_translation)
            best_translation = initial_translation
            best_result = render_unit(page=translated_page, unit=unit, translation=best_translation, target_language=args.target_language, commit=False)
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
                compact_translation = post_normalize_translation(unit, context_pack, parse_unit_translation(compact_response, unit["unit_id"]))
                compact_result = render_unit(page=translated_page, unit=unit, translation=compact_translation, target_language=args.target_language, commit=False)
                if is_better_result(compact_result, best_result):
                    best_translation = compact_translation
                    best_result = compact_result
                    compact_used = True

            committed_result = render_unit(page=translated_page, unit=unit, translation=best_translation, target_language=args.target_language, commit=True)
            block_outputs = committed_result["rendered_by_block"] or {block["block_id"]: best_translation for block in unit["blocks"]}
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
        page_reports.append({"page_no": page_no, "unit_count": len(units), "reports": page_unit_reports})

    write_json_file(args.output_dir / "selected_context_packs.json", context_packs)
    write_json_file(args.output_dir / "translations.json", translations_payload)
    write_json_file(args.output_dir / "report.json", {"pages": page_reports})
    redacted_doc.save(args.output_dir / "native_redacted.pdf")
    translated_doc.save(args.output_dir / "translated_en.pdf")


if __name__ == "__main__":
    main()
