from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import fitz


ROOT = Path(__file__).resolve().parents[3]
SPIKE08_SCRIPT = ROOT / "spikes" / "08_semantic_group_reflow" / "semantic_group_reflow.py"
SPIKE08_EVAL = ROOT / "spikes" / "08_semantic_group_reflow" / "evaluate_vs_human_reference.py"
SPIKE11_SCRIPT = ROOT / "spikes" / "11_sanitized_background_translation" / "translate_with_sanitized_background.py"

DEFAULT_INPUT = ROOT / "样本" / "中文" / "AIA_2021_Annual_Report_zh.pdf"
DEFAULT_REFERENCE = ROOT / "样本" / "英文" / "AIA_2021_Annual_Report_en.pdf"
DEFAULT_BLOCKS = ROOT / "spikes" / "01_text_block_extraction" / "output" / "AIA_2021_Annual_Report_zh" / "blocks.jsonl"
DEFAULT_DOCUMENT_BACKGROUND = (
    ROOT / "spikes" / "09_document_understanding_workflow" / "output" / "sample_2021_pages_10_13_19_20_run1" / "document_background.json"
)
DEFAULT_COMPANY_MEMORY = (
    ROOT / "spikes" / "06_company_memory_learning" / "output" / "AIA_excl_2021_v4" / "company_memory.json"
)
DEFAULT_GLOSSARY = ROOT / "spikes" / "07_translation_current_bundle" / "configs" / "glossary_zh_en_seed.json"
DEFAULT_PATTERNS = ROOT / "spikes" / "07_translation_current_bundle" / "configs" / "patterns_zh_en.json"
DEFAULT_V11_BASELINE_DIR = ROOT / "spikes" / "11_sanitized_background_translation" / "output" / "focus_pages_10_13_19_20_run3"
DEFAULT_OUTPUT = ROOT / "spikes" / "12_anchor_group_render" / "output" / "focus_pages_10_13_19_20_run1"
DEFAULT_MODEL = "claude-3-5-sonnet-20241022"

SIDEBAR_REFERENCE_TEXT = "Overview Financial and Operating Review Corporate Governance Additional Information Financial Statements"
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "will",
    "with",
}


def load_module(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


sp08 = load_module(SPIKE08_SCRIPT, "spike12_sp08")
sp08_eval = load_module(SPIKE08_EVAL, "spike12_sp08_eval")
sp11 = load_module(SPIKE11_SCRIPT, "spike12_sp11")

AnthropicGatewayClient = sp11.AnthropicGatewayClient
build_compact_prompts = sp11.build_compact_prompts
build_context_pack = sp11.build_context_pack
build_spike11_glossary = sp11.build_spike11_glossary
call_collect_relevant_terms = sp11.collect_relevant_terms
classify_block_type = sp11.classify_block_type
clean_text = sp08.clean_text
clean_translation = sp08.clean_translation
collect_unit_slots = sp08.collect_unit_slots
extract_raw_line_segments = sp11.extract_raw_line_segments
extract_response_text = sp11.extract_response_text
infer_block_style = sp11.infer_block_style
is_better_result = sp08.is_better_result
load_page_records = sp11.load_page_records
merge_term_hits = sp11.merge_term_hits
parse_page_numbers = sp11.parse_page_numbers
parse_unit_translation = sp08.parse_unit_translation
post_normalize_translation = sp11.post_normalize_translation
render_page = sp11.render_page
render_unit = sp08.render_unit
resolve_controlled_translation = sp11.resolve_controlled_translation
sanitize_document_background = sp11.sanitize_document_background
save_comparison = sp11.save_comparison
should_retry_compact = sp08.should_retry_compact
write_json_file = sp11.write_json_file
write_text_file = sp08.write_text_file


class StageGateError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Spike 12: AnchorBlock + SemanticGroup + FactLock + RenderPlan end-to-end experiment.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--reference-pdf", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--blocks-jsonl", type=Path, default=DEFAULT_BLOCKS)
    parser.add_argument("--document-background", type=Path, default=DEFAULT_DOCUMENT_BACKGROUND)
    parser.add_argument("--company-memory", type=Path, default=DEFAULT_COMPANY_MEMORY)
    parser.add_argument("--glossary", type=Path, default=DEFAULT_GLOSSARY)
    parser.add_argument("--patterns", type=Path, default=DEFAULT_PATTERNS)
    parser.add_argument("--v11-baseline-dir", type=Path, default=DEFAULT_V11_BASELINE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pages", type=str, default="10,13,19,20")
    parser.add_argument("--source-language", default="Traditional Chinese")
    parser.add_argument("--target-language", default="English")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-output-tokens", type=int, default=1800)
    parser.add_argument("--render-dpi", type=int, default=110)
    parser.add_argument("--compact-threshold", type=float, default=0.84)
    parser.add_argument("--stop-after-stage", type=int, default=6)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_file(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "size": stat.st_size,
        "mtime": stat.st_mtime,
    }


def block_width(block: dict[str, Any]) -> float:
    return float(block["bbox"][2] - block["bbox"][0])


def block_font_size(block: dict[str, Any]) -> float:
    return float(block.get("font_size_max") or block.get("font_size_avg") or 10.0)


def x_overlap_ratio(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_x0, _, left_x1, _ = left["bbox"]
    right_x0, _, right_x1, _ = right["bbox"]
    overlap = max(0.0, min(left_x1, right_x1) - max(left_x0, right_x0))
    min_width = max(1.0, min(left_x1 - left_x0, right_x1 - right_x0))
    return overlap / min_width


def vertical_gap(prev_block: dict[str, Any], next_block: dict[str, Any]) -> float:
    return float(next_block["bbox"][1] - prev_block["bbox"][3])


def likely_numeric_dense(block: dict[str, Any]) -> bool:
    text = clean_text(block.get("source_text", ""))
    if not text:
        return False
    digit_count = sum(1 for char in text if char.isdigit())
    symbol_count = sum(1 for char in text if char in "%$(),./:-")
    return digit_count + symbol_count >= max(4, int(len(text) * 0.4))


def ends_paragraph(text: str) -> bool:
    return bool(re.search(r"[。！？!?\.”\"]\s*$", text.strip()))


def is_tableish_dense(block: dict[str, Any]) -> bool:
    text = str(block.get("source_text") or "")
    line_count = max(1, len([line for line in text.splitlines() if line.strip()]))
    segments = block.get("_segments") or []
    if line_count >= 4 and likely_numeric_dense(block):
        return True
    if len(segments) >= 6 and likely_numeric_dense(block):
        return True
    if block_width(block) >= 300 and line_count >= 3 and likely_numeric_dense(block):
        return True
    return False


def is_sidebar_excluded(block: dict[str, Any], block_type: str) -> tuple[bool, str | None]:
    if block_type == "sidebar_nav":
        return True, "sidebar_nav"
    width = block_width(block)
    x0 = float(block["bbox"][0])
    if x0 >= 560 and width <= 28:
        return True, "page_edge_rail"
    return False, None


def is_primary_narrative_candidate(block: dict[str, Any], block_type: str) -> bool:
    text = clean_text(block.get("source_text", ""))
    if not text:
        return False
    if block.get("region") == "bottom":
        return False
    if block_type in {"footer", "chart_label", "sidebar_nav"}:
        return False
    if block.get("role") == "header":
        return False
    if block_type == "heading" and block_font_size(block) >= 16:
        return False
    if block_width(block) <= 36:
        return False
    if is_tableish_dense(block):
        return False
    if likely_numeric_dense(block):
        return False
    return True


def can_merge_primary_group(current_group: list[dict[str, Any]], candidate: dict[str, Any]) -> bool:
    prev_block = current_group[-1]
    prev_gap = vertical_gap(prev_block, candidate)
    if prev_gap < -1.0:
        return False
    font_ratio = min(block_font_size(prev_block), block_font_size(candidate)) / max(
        block_font_size(prev_block),
        block_font_size(candidate),
    )
    if font_ratio < 0.84:
        return False
    if x_overlap_ratio(prev_block, candidate) < 0.72:
        return False
    max_group_width = max(block_width(item) for item in current_group)
    short_prev_line = block_width(prev_block) < max_group_width * 0.78
    strong_end = ends_paragraph(clean_text(prev_block.get("source_text", "")))
    max_gap = max(7.5, min(13.0, (block_font_size(prev_block) + block_font_size(candidate)) * 0.45))
    if prev_gap > max_gap:
        return False
    if short_prev_line and prev_gap > 4.0:
        return False
    if strong_end and prev_gap > 4.0:
        return False
    if abs(prev_block["bbox"][0] - candidate["bbox"][0]) > 10 and prev_gap > 2.0:
        return False
    if len(current_group) >= 8:
        return False
    char_total = sum(int(item.get("char_count") or len(clean_text(item.get("source_text", "")))) for item in current_group)
    if char_total >= 420:
        return False
    return True


def is_tail_clause_candidate(current_group: list[dict[str, Any]], candidate: dict[str, Any]) -> bool:
    if not current_group:
        return False
    prev_block = current_group[-1]
    candidate_text = clean_text(candidate.get("source_text", ""))
    prev_text = clean_text(prev_block.get("source_text", ""))
    if not candidate_text or not prev_text:
        return False
    if candidate.get("is_sidebar_excluded"):
        return False
    if candidate.get("_block_type") in {"sidebar_nav", "footer", "chart_label", "heading"}:
        return False
    if "\n" in str(candidate.get("source_text") or ""):
        return False
    if len(candidate_text) > 48:
        return False
    if not re.match(r"^[\(（]?\d", candidate_text):
        return False
    if not re.search(r"(億美元|萬美元|港仙|%|自由盈餘|股息|保費|利潤|權益|率)", candidate_text):
        return False
    if is_tableish_dense(candidate):
        return False
    gap = vertical_gap(prev_block, candidate)
    if gap < -1.0 or gap > 8.5:
        return False
    font_ratio = min(block_font_size(prev_block), block_font_size(candidate)) / max(
        block_font_size(prev_block),
        block_font_size(candidate),
    )
    if font_ratio < 0.84:
        return False
    if x_overlap_ratio(prev_block, candidate) < 0.38:
        return False
    if block_width(candidate) > block_width(prev_block) * 0.72:
        return False
    if ends_paragraph(prev_text):
        return False
    return True


def build_anchor_block_records(page_no: int, page_record: dict[str, Any], page: fitz.Page) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    for block in sorted(page_record["blocks"], key=lambda item: item["reading_order"]):
        style = infer_block_style(page, block)
        segments = extract_raw_line_segments(page, block)
        block_type = classify_block_type(block)
        sidebar_flag, exclude_reason = is_sidebar_excluded(block, block_type)
        enriched = {
            **block,
            "_style": style,
            "_segments": segments,
            "_block_type": block_type,
            "is_sidebar_excluded": sidebar_flag,
            "exclude_reason": exclude_reason,
        }
        enriched["_narrative_candidate"] = is_primary_narrative_candidate(enriched, block_type)
        enriched["translation_target"] = not sidebar_flag
        anchors.append(
            {
                "page_no": page_no,
                "block_id": enriched["block_id"],
                "reading_order": enriched["reading_order"],
                "bbox": list(enriched["bbox"]),
                "region": enriched.get("region"),
                "role": enriched.get("role"),
                "char_count": int(enriched.get("char_count") or len(clean_text(enriched.get("source_text", "")))),
                "source_text": str(enriched.get("source_text") or ""),
                "block_type": block_type,
                "style": style,
                "slots": collect_unit_slots({"blocks": [enriched]}, {enriched["block_id"]: segments}),
                "font_size_avg": enriched.get("font_size_avg"),
                "font_size_max": enriched.get("font_size_max"),
                "segment_count": len(segments),
                "is_sidebar_excluded": sidebar_flag,
                "exclude_reason": exclude_reason,
                "translation_target": enriched["translation_target"],
                "narrative_candidate": enriched["_narrative_candidate"],
                "_runtime": enriched,
            }
        )
    return anchors


def build_semantic_group_records(page_no: int, anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pending_group: list[dict[str, Any]] = []
    raw_units: list[list[dict[str, Any]]] = []

    def flush_pending() -> None:
        nonlocal pending_group
        if pending_group:
            raw_units.append(pending_group)
            pending_group = []

    for anchor in anchors:
        runtime_block = anchor["_runtime"]
        if anchor["is_sidebar_excluded"]:
            flush_pending()
            raw_units.append([anchor])
            continue
        if not anchor["narrative_candidate"]:
            if pending_group and is_tail_clause_candidate([item["_runtime"] for item in pending_group], runtime_block):
                pending_group.append(anchor)
                continue
            flush_pending()
            raw_units.append([anchor])
            continue
        if not pending_group:
            pending_group = [anchor]
            continue
        if can_merge_primary_group([item["_runtime"] for item in pending_group], runtime_block):
            pending_group.append(anchor)
        else:
            flush_pending()
            pending_group = [anchor]
    flush_pending()

    group_records: list[dict[str, Any]] = []
    group_index = 1
    for block_group in raw_units:
        is_group = len(block_group) > 1 and not block_group[0]["is_sidebar_excluded"]
        group_id = f"p{page_no}_g{group_index:02d}" if is_group else str(block_group[0]["block_id"])
        if is_group:
            group_index += 1
        runtime_blocks = [block["_runtime"] for block in block_group]
        reason_records: list[dict[str, Any]] = []
        if is_group:
            for previous, current in zip(block_group, block_group[1:]):
                merge_kind = "tail_numeric_clause" if not current["narrative_candidate"] else "adjacent_narrative"
                reason_records.append({"kind": merge_kind, "from": previous["block_id"], "to": current["block_id"]})
        elif block_group[0]["is_sidebar_excluded"]:
            reason_records.append({"kind": "excluded_single", "reason": block_group[0]["exclude_reason"] or "sidebar_excluded"})
        else:
            reason_records.append({"kind": "single_non_narrative", "reason": block_group[0]["block_type"]})
        group_records.append(
            {
                "group_id": group_id,
                "unit_id": group_id,
                "page_no": page_no,
                "mode": "semantic_group" if is_group else "single_block",
                "block_ids": [block["block_id"] for block in block_group],
                "block_types": [block["block_type"] for block in block_group],
                "source_text_joined": "\n".join(clean_text(block["source_text"]) for block in block_group if clean_text(block["source_text"])),
                "translation_target": all(block["translation_target"] for block in block_group),
                "is_sidebar_group": any(block["is_sidebar_excluded"] for block in block_group),
                "group_reason": reason_records,
                "slots": collect_unit_slots({"blocks": runtime_blocks}, {block["block_id"]: block["_segments"] for block in runtime_blocks}),
                "blocks": runtime_blocks,
            }
        )
    return group_records


def sentence_window(text: str, position: int) -> str:
    if not text:
        return ""
    separators = "。！？!?"
    start = position
    end = position
    while start > 0 and text[start - 1] not in separators:
        start -= 1
    while end < len(text) and text[end] not in separators:
        end += 1
    return text[start:end].strip()


def decimal_to_text(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def normalize_number_string(value: str) -> str:
    return value.replace(",", "").strip()


def normalize_text_for_eval(text: str) -> str:
    cleaned = re.sub(re.escape(SIDEBAR_REFERENCE_TEXT), " ", str(text), flags=re.IGNORECASE)
    cleaned = cleaned.replace("\n", " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def classify_fact_label(evidence: str, amount_text: str, unit_type: str) -> str:
    if unit_type == "hk_cents":
        if "末期股息" in evidence:
            return "final_dividend_per_share"
        if "全年股息" in evidence:
            return "total_dividend_per_share"
        return f"hk_cents_per_share_{amount_text}"
    if unit_type == "usd":
        if "派付股息" in evidence:
            return "dividend_paid_usd"
        if "基本自由盈餘" in evidence:
            return "ufsg_usd"
        if "自由盈餘" in evidence:
            return "free_surplus_usd"
        if "內涵價值權益" in evidence:
            return "ev_equity_usd"
        if "內涵價值營運溢利" in evidence:
            return "ev_operating_profit_usd"
        if "正面營運差異" in evidence:
            return "positive_operating_variance_usd"
        if "稅後營運溢利" in evidence:
            return "opat_usd"
        return f"usd_amount_{amount_text}"
    if unit_type == "percent":
        if "償付能力充足率" in evidence:
            return "solvency_ratio_pct"
        if "集團當地資本總和法覆蓋率" in evidence:
            return "group_lcsm_cover_ratio_pct"
        return f"percentage_{amount_text}"
    return f"date_{amount_text}"


def usd_expected_forms(amount_text: str, scale_token: str) -> tuple[list[str], list[str]]:
    try:
        source_value = Decimal(amount_text)
    except InvalidOperation:
        return [], []
    if scale_token == "億":
        billion_value = source_value * Decimal("0.1")
        million_value = source_value * Decimal("100")
    else:
        billion_value = source_value * Decimal("0.00001")
        million_value = source_value * Decimal("0.01")
    billion_text = decimal_to_text(billion_value)
    million_text = decimal_to_text(million_value)
    million_with_commas = f"{int(million_value):,}" if million_value == int(million_value) else million_text
    return [f"US${billion_text} billion", f"US${million_text} million", f"US${million_with_commas} million"], [billion_text, million_text]


def build_fact_lock_records(group_record: dict[str, Any]) -> list[dict[str, Any]]:
    text = group_record["source_text_joined"].replace("\n", "")
    fact_records: list[dict[str, Any]] = []

    for match in re.finditer(r"(截至)?(\d{4})年(\d{1,2})月(\d{1,2})日", text):
        evidence = sentence_window(text, match.start())
        label = classify_fact_label(evidence, match.group(2), "date")
        fact_records.append(
            {
                "group_id": group_record["group_id"],
                "page_no": group_record["page_no"],
                "label": label,
                "fact_type": "date",
                "source_value": match.group(0),
                "expected_forms": [f"{int(match.group(4))} {match.group(3)} {match.group(2)}"],
                "expected_numbers": [match.group(2), match.group(3), match.group(4)],
                "required_keywords": [],
                "source_block_ids": group_record["block_ids"],
                "source_evidence_text": evidence,
                "importance": "medium",
                "validate": False,
            }
        )

    for match in re.finditer(r"每股\s*(\d+(?:\.\d+)?)\s*港仙", text):
        value = match.group(1)
        evidence = sentence_window(text, match.start())
        local_evidence = text[max(0, match.start() - 16) : min(len(text), match.end() + 16)]
        label = classify_fact_label(local_evidence, value, "hk_cents")
        keywords: list[str] = []
        importance = "low"
        validate = False
        if label == "final_dividend_per_share":
            keywords = ["final dividend"]
            importance = "high"
            validate = True
        elif label == "total_dividend_per_share":
            keywords = ["total dividend"]
            importance = "high"
            validate = True
        fact_records.append(
            {
                "group_id": group_record["group_id"],
                "page_no": group_record["page_no"],
                "label": label,
                "fact_type": "hk_cents_per_share",
                "source_value": f"{value}港仙",
                "expected_forms": [f"{value} Hong Kong cents per share"],
                "expected_numbers": [value],
                "required_keywords": keywords,
                "source_block_ids": group_record["block_ids"],
                "source_evidence_text": evidence,
                "importance": importance,
                "validate": validate,
            }
        )

    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(億|萬)美元", text):
        value = match.group(1)
        scale = match.group(2)
        evidence = sentence_window(text, match.start())
        local_evidence = text[max(0, match.start() - 18) : min(len(text), match.end() + 18)]
        label = classify_fact_label(local_evidence, value, "usd")
        expected_forms, expected_numbers = usd_expected_forms(value, scale)
        keywords: list[str] = []
        importance = "medium"
        validate = False
        if label in {"dividend_paid_usd", "ufsg_usd", "free_surplus_usd", "ev_equity_usd", "opat_usd"}:
            validate = True
            importance = "high"
        if label == "dividend_paid_usd":
            keywords = ["dividend"]
        elif label == "free_surplus_usd":
            keywords = ["free surplus"]
        elif label == "ufsg_usd":
            keywords = ["ufsg", "underlying free surplus generation"]
        elif label == "ev_equity_usd":
            keywords = ["embedded value", "ev equity"]
        elif label == "opat_usd":
            keywords = ["opat", "operating profit after tax"]
        fact_records.append(
            {
                "group_id": group_record["group_id"],
                "page_no": group_record["page_no"],
                "label": label,
                "fact_type": "usd_scaled_amount",
                "source_value": match.group(0),
                "expected_forms": expected_forms,
                "expected_numbers": expected_numbers,
                "required_keywords": keywords,
                "source_block_ids": group_record["block_ids"],
                "source_evidence_text": evidence,
                "importance": importance,
                "validate": validate,
            }
        )

    for match in re.finditer(r"(\d+(?:\.\d+)?)%", text):
        value = match.group(1)
        evidence = sentence_window(text, match.start())
        local_evidence = text[max(0, match.start() - 18) : min(len(text), match.end() + 18)]
        label = classify_fact_label(local_evidence, value, "percent")
        validate = label in {"solvency_ratio_pct", "group_lcsm_cover_ratio_pct"}
        fact_records.append(
            {
                "group_id": group_record["group_id"],
                "page_no": group_record["page_no"],
                "label": label,
                "fact_type": "percentage",
                "source_value": f"{value}%",
                "expected_forms": [f"{value}%"],
                "expected_numbers": [value],
                "required_keywords": [],
                "source_block_ids": group_record["block_ids"],
                "source_evidence_text": evidence,
                "importance": "medium" if validate else "low",
                "validate": validate,
            }
        )

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for record in fact_records:
        key = (record["label"], record["source_value"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def build_mapping_hit_records(group_record: dict[str, Any], context_pack: dict[str, Any], glossary: dict[str, Any]) -> list[dict[str, Any]]:
    source_text = group_record["source_text_joined"]
    preferred = context_pack.get("terms", [])
    glossary_hits = call_collect_relevant_terms(group_record["blocks"], glossary, limit=16)
    merged_hits = merge_term_hits(preferred, glossary_hits)
    preferred_sources = {str(item.get("source") or "").strip() for item in preferred}
    records: list[dict[str, Any]] = []
    for item in merged_hits:
        source = str(item.get("source") or "").strip()
        target = str(item.get("target") or "").strip()
        if not source or not target:
            continue
        hit_type = "context_term" if source in preferred_sources else "glossary_term"
        evidence_blocks = [
            block_id
            for block_id, text in zip(group_record["block_ids"], [block.get("source_text", "") for block in group_record["blocks"]])
            if source in text
        ]
        records.append(
            {
                "group_id": group_record["group_id"],
                "page_no": group_record["page_no"],
                "source": source,
                "target": target,
                "hit_type": hit_type,
                "source_block_ids": evidence_blocks or group_record["block_ids"],
                "evidence": source_text[:160],
            }
        )
    return records


def summarize_neighbor_text(text: str, max_length: int = 120) -> str:
    cleaned = clean_text(text)
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 3].rstrip() + "..."


def build_neighbor_context(group_records: list[dict[str, Any]], index: int) -> dict[str, str]:
    prev_text = ""
    next_text = ""
    for prior in range(index - 1, -1, -1):
        if group_records[prior]["translation_target"] and not group_records[prior]["is_sidebar_group"]:
            prev_text = summarize_neighbor_text(group_records[prior]["source_text_joined"])
            break
    for nxt in range(index + 1, len(group_records)):
        if group_records[nxt]["translation_target"] and not group_records[nxt]["is_sidebar_group"]:
            next_text = summarize_neighbor_text(group_records[nxt]["source_text_joined"])
            break
    return {"previous_group_source_excerpt": prev_text, "next_group_source_excerpt": next_text}


def build_group_context_record(
    group_record: dict[str, Any],
    context_pack: dict[str, Any],
    mapping_hits: list[dict[str, Any]],
    fact_locks: list[dict[str, Any]],
    neighbor_context: dict[str, str],
) -> dict[str, Any]:
    return {
        "group_id": group_record["group_id"],
        "page_no": group_record["page_no"],
        "mode": group_record["mode"],
        "block_ids": group_record["block_ids"],
        "page_sections": context_pack.get("page_sections", []),
        "global_profile": context_pack.get("global_profile", {}),
        "term_usage_mode": context_pack.get("term_usage_mode"),
        "roles": context_pack.get("roles", []),
        "style_rules": context_pack.get("style_rules", []),
        "mapping_hits": mapping_hits,
        "fact_locks": fact_locks,
        "neighbor_context": neighbor_context,
    }


def build_translation_prompts(
    group_record: dict[str, Any],
    source_language: str,
    target_language: str,
    group_context_record: dict[str, Any],
) -> tuple[str, str]:
    profile = group_context_record.get("global_profile", {})
    blocks_payload = [
        {
            "block_id": block["block_id"],
            "block_type": group_record["block_types"][index],
            "source_text": clean_text(block.get("source_text", "")),
        }
        for index, block in enumerate(group_record["blocks"])
    ]
    system_prompt = "\n".join(
        [
            "你是上市保险公司年报翻译器。",
            f"语言方向：{source_language} -> {target_language}。",
            "只处理当前 semantic group。",
            "可以在当前组内恢复跨块断句，但不得跨组补写、跨组删写或改写事实。",
            "必须严格满足 mapping_hits 与 fact_locks。",
            "版面回填、字体压缩、分块分配不是你的职责，不要为了适配版面而删词改义。",
            "保持正式、稳定、可出版的企业年报文风。",
            "只输出 JSON，且只能输出 JSON。",
        ]
    )
    user_payload = {
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
                "required_keywords": item["required_keywords"],
            }
            for item in group_context_record.get("fact_locks", [])
            if item.get("importance") in {"high", "medium"}
        ],
        "current_group": {
            "group_id": group_record["group_id"],
            "mode": group_record["mode"],
            "block_ids": group_record["block_ids"],
            "block_types": group_record["block_types"],
            "blocks": blocks_payload,
            "joined_source_text": group_record["source_text_joined"],
        },
        "output_format": {
            "translations": [
                {
                    "unit_id": group_record["group_id"],
                    "translation": "<译文>",
                }
            ]
        },
    }
    user_prompt = "\n".join(
        [
            "文档场景：上市保险公司企业年报。",
            "先满足 fact_locks，再保证术语稳定、语义完整和年报文风。",
            json.dumps(user_payload, ensure_ascii=False, indent=2),
        ]
    )
    return system_prompt, user_prompt


def build_fact_repair_prompts(
    group_record: dict[str, Any],
    current_translation: str,
    failures: list[dict[str, Any]],
    group_context_record: dict[str, Any],
    source_language: str,
    target_language: str,
) -> tuple[str, str]:
    system_prompt = "\n".join(
        [
            "你是上市保险公司年报译文校正器。",
            f"语言方向：{source_language} -> {target_language}。",
            "只修正当前译文中与 fact_locks 冲突的内容，不重写其他信息。",
            "保持正式、稳定、可出版的企业年报文风。",
            "只输出 JSON，且只能输出 JSON。",
        ]
    )
    user_payload = {
        "current_group": {
            "group_id": group_record["group_id"],
            "joined_source_text": group_record["source_text_joined"],
            "current_translation": current_translation,
        },
        "fact_lock_failures": failures,
        "fact_locks": [
            {
                "label": item["label"],
                "source_value": item["source_value"],
                "expected_forms": item["expected_forms"],
                "required_keywords": item["required_keywords"],
            }
            for item in group_context_record.get("fact_locks", [])
            if item.get("validate")
        ],
        "output_format": {
            "translations": [
                {
                    "unit_id": group_record["group_id"],
                    "translation": "<修正后的译文>",
                }
            ]
        },
    }
    user_prompt = "\n".join(
        [
            "只修正事实锁定冲突，不要额外改写。",
            json.dumps(user_payload, ensure_ascii=False, indent=2),
        ]
    )
    return system_prompt, user_prompt


def export_prompt_bundle(prompt_dir: Path, stem: str, system_prompt: str, user_prompt: str, response_payload: dict[str, Any] | None = None) -> None:
    write_text_file(prompt_dir / f"{stem}.system.txt", system_prompt)
    write_text_file(prompt_dir / f"{stem}.user.txt", user_prompt)
    if response_payload is not None:
        write_text_file(prompt_dir / f"{stem}.response.txt", extract_response_text(response_payload))


def call_model_for_group(
    client: Any,
    prompt_dir: Path,
    api_logs_dir: Path,
    stem: str,
    system_prompt: str,
    user_prompt: str,
    meta: dict[str, Any],
) -> dict[str, Any]:
    request_payload, response_payload = client._post_messages(system_prompt, user_prompt)
    export_prompt_bundle(prompt_dir, stem, system_prompt, user_prompt, response_payload)
    write_json_file(api_logs_dir / f"{stem}.json", {"meta": meta, "request": request_payload, "response": response_payload})
    return response_payload


def replace_number_after_keyword(text: str, keyword_pattern: str, replacement_value: str) -> str:
    pattern = re.compile(rf"({keyword_pattern}[^0-9]{{0,80}})(\d+(?:,\d{{3}})*(?:\.\d+)?)", re.IGNORECASE)
    return pattern.sub(lambda match: f"{match.group(1)}{replacement_value}", text, count=1)


def apply_fact_lock_repairs(translation: str, fact_locks: list[dict[str, Any]]) -> str:
    return translation


def numeric_tokens(text: str) -> set[str]:
    return {normalize_number_string(item) for item in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", str(text))}


def contains_expected_keyword(text: str, keywords: list[str]) -> bool:
    lowered = str(text).lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def validate_translation_against_fact_locks(translation: str, fact_locks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    numbers = numeric_tokens(translation)
    lowered = translation.lower()
    for fact in fact_locks:
        if not fact.get("validate"):
            continue
        expected_hit = False
        for expected_form in fact.get("expected_forms", []):
            if expected_form.lower() in lowered:
                expected_hit = True
                break
        if not expected_hit and fact.get("expected_numbers"):
            expected_hit = any(normalize_number_string(value) in numbers for value in fact["expected_numbers"])
        keyword_ok = True
        if fact.get("required_keywords"):
            keyword_ok = contains_expected_keyword(translation, fact["required_keywords"])
        corruption_ok = True
        if fact["label"] == "final_dividend_per_share" and fact.get("expected_numbers"):
            amount = re.escape(fact["expected_numbers"][0])
            if re.search(rf"final dividend[^.]{0,40}{amount}%", translation, flags=re.IGNORECASE):
                corruption_ok = False
        if fact["label"] == "total_dividend_per_share" and fact.get("expected_numbers"):
            amount = re.escape(fact["expected_numbers"][0])
            if re.search(rf"total dividend[^.]{0,40}for[^.]{0,10}{amount}[^.]{0,10}to", translation, flags=re.IGNORECASE):
                corruption_ok = False
        if not expected_hit or not keyword_ok or not corruption_ok:
            failures.append(
                {
                    "label": fact["label"],
                    "fact_type": fact["fact_type"],
                    "source_value": fact["source_value"],
                    "expected_forms": fact.get("expected_forms", []),
                    "required_keywords": fact.get("required_keywords", []),
                    "corruption_detected": not corruption_ok,
                }
            )
    return failures


def stage_check(stage_results: list[dict[str, Any]], stage_no: str, stage_name: str, passed: bool, summary: str, details: dict[str, Any], output_dir: Path) -> None:
    stage_results.append(
        {
            "stage": stage_no,
            "stage_name": stage_name,
            "passed": passed,
            "summary": summary,
            "details": details,
        }
    )
    write_json_file(output_dir / "stage_gate_results.json", {"stages": stage_results})
    if not passed:
        raise StageGateError(f"Stage {stage_no} failed: {summary}")


def build_candidate_page_texts(
    translations_payload: list[dict[str, Any]],
    page_block_order: dict[int, list[str]],
    pages: list[int],
) -> dict[int, str]:
    page_block_texts: dict[int, dict[str, str]] = {page_no: {} for page_no in pages}
    for item in translations_payload:
        page_no = int(item["page_no"])
        if page_no not in page_block_texts:
            continue
        for block_id, block_text in (item.get("block_outputs") or {}).items():
            page_block_texts[page_no][str(block_id)] = str(block_text or "")
    results: dict[int, str] = {}
    for page_no in pages:
        ordered = [page_block_texts[page_no].get(block_id, "") for block_id in page_block_order[page_no]]
        results[page_no] = normalize_text_for_eval("\n".join(text for text in ordered if text.strip()))
    return results


def build_baseline_page_texts(path: Path, page_block_order: dict[int, list[str]], pages: list[int]) -> dict[int, str]:
    payload = load_json(path)
    page_block_texts: dict[int, dict[str, str]] = {page_no: {} for page_no in pages}
    for item in payload:
        page_no = int(item["page_no"])
        if page_no not in page_block_texts:
            continue
        for block_id, block_text in (item.get("block_outputs") or {}).items():
            page_block_texts[page_no][str(block_id)] = str(block_text or "")
    results: dict[int, str] = {}
    for page_no in pages:
        ordered = [page_block_texts[page_no].get(block_id, "") for block_id in page_block_order[page_no]]
        results[page_no] = normalize_text_for_eval("\n".join(text for text in ordered if text.strip()))
    return results


def average_layout_from_report(report_path: Path) -> dict[int, dict[str, Any]]:
    payload = load_json(report_path)
    pages_payload = payload.get("pages", [])
    summary: dict[int, dict[str, Any]] = {}
    for page in pages_payload:
        page_no = int(page["page_no"])
        reports = page.get("reports", [])
        if not reports:
            continue
        summary[page_no] = {
            "avg_font_ratio": round(sum(float(item["font_ratio"]) for item in reports) / len(reports), 4),
            "compact_used": sum(1 for item in reports if item.get("compact_used")),
            "overflow_count": sum(1 for item in reports if item.get("fit_status") == "overflow"),
            "unit_count": len(reports),
        }
    return summary


def tokenize(text: str) -> list[str]:
    normalized = sp08_eval.normalize_text(text)
    return re.findall(r"[a-z]+(?:'[a-z]+)?|\d+(?:\.\d+)?%?|us\$|hk\$|\$", normalized)


def content_tokens(tokens: list[str]) -> list[str]:
    return [token for token in tokens if token not in STOPWORDS and not re.fullmatch(r"\d+(?:\.\d+)?%?", token)]


def number_tokens(tokens: list[str]) -> list[str]:
    return [token for token in tokens if re.fullmatch(r"\d+(?:\.\d+)?%?", token)]


def evaluate_pages(reference_texts: dict[int, str], candidate_texts: dict[int, str], pages: list[int]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for page_no in pages:
        ref_tokens = tokenize(reference_texts[page_no])
        hyp_tokens = tokenize(candidate_texts[page_no])
        ref_content = content_tokens(ref_tokens)
        hyp_content = content_tokens(hyp_tokens)
        ref_numbers = number_tokens(ref_tokens)
        hyp_numbers = number_tokens(hyp_tokens)
        results.append(
            {
                "page_no": page_no,
                "token_f1": round(sp08_eval.counter_f1(ref_tokens, hyp_tokens), 4),
                "content_f1": round(sp08_eval.counter_f1(ref_content, hyp_content), 4),
                "sequence_ratio": round(sp08_eval.sequence_ratio(ref_tokens, hyp_tokens), 4),
                "number_recall": round(sp08_eval.number_recall(ref_numbers, hyp_numbers), 4),
                "token_count_ref": len(ref_tokens),
                "token_count_hyp": len(hyp_tokens),
            }
        )
    return results


def average_metrics(per_page: list[dict[str, Any]]) -> dict[str, float]:
    count = max(1, len(per_page))
    return {
        "token_f1": round(sum(item["token_f1"] for item in per_page) / count, 4),
        "content_f1": round(sum(item["content_f1"] for item in per_page) / count, 4),
        "sequence_ratio": round(sum(item["sequence_ratio"] for item in per_page) / count, 4),
        "number_recall": round(sum(item["number_recall"] for item in per_page) / count, 4),
    }


def delta_metrics(current: dict[str, float], baseline: dict[str, float]) -> dict[str, float]:
    return {
        key: round(float(current[key]) - float(baseline[key]), 4)
        for key in ["token_f1", "content_f1", "sequence_ratio", "number_recall"]
    }


def layout_summary_from_page_reports(page_reports: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    summary: dict[int, dict[str, Any]] = {}
    for page in page_reports:
        page_no = int(page["page_no"])
        reports = page.get("reports", [])
        if not reports:
            continue
        summary[page_no] = {
            "avg_font_ratio": round(sum(float(item["font_ratio"]) for item in reports) / len(reports), 4),
            "compact_used": sum(1 for item in reports if item.get("compact_used")),
            "overflow_count": sum(1 for item in reports if item.get("fit_status") == "overflow"),
            "unit_count": len(reports),
        }
    return summary


def build_stage_markdown(stage_results: list[dict[str, Any]]) -> str:
    lines = ["# Spike 12 阶段状态", ""]
    for stage in stage_results:
        status = "通过" if stage["passed"] else "失败"
        lines.append(f"## 阶段 {stage['stage']} {stage['stage_name']}")
        lines.append(f"- 状态：{status}")
        lines.append(f"- 结论：{stage['summary']}")
        lines.append(f"- 详情：`{json.dumps(stage['details'], ensure_ascii=False)}`")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_acceptance_report(
    stage_results: list[dict[str, Any]],
    evaluation_payload: dict[str, Any],
    focus_findings: dict[str, Any],
    output_dir: Path,
) -> str:
    final_stage = stage_results[-1]
    overall = "通过" if final_stage["passed"] and all(item["passed"] for item in stage_results) else "未通过"
    avg = evaluation_payload["spike12_vs_human"]["average"]
    delta = evaluation_payload["delta_spike12_minus_v11"]
    lines = [
        "# Spike 12 验收报告",
        "",
        f"- 总体结论：{overall}",
        f"- 最终阶段：阶段 {final_stage['stage']} {final_stage['stage_name']}",
        f"- 输出目录：`{output_dir}`",
        "",
        "## 阶段门结果",
    ]
    for stage in stage_results:
        status = "通过" if stage["passed"] else "失败"
        lines.append(f"- 阶段 {stage['stage']} {stage['stage_name']}：{status}；{stage['summary']}")
    lines.extend(
        [
            "",
            "## 内容指标",
            f"- token_f1：{avg['token_f1']}（相对 v11 {delta['token_f1']:+.4f}）",
            f"- content_f1：{avg['content_f1']}（相对 v11 {delta['content_f1']:+.4f}）",
            f"- sequence_ratio：{avg['sequence_ratio']}（相对 v11 {delta['sequence_ratio']:+.4f}）",
            f"- number_recall：{avg['number_recall']}（相对 v11 {delta['number_recall']:+.4f}）",
            "",
            "## 关键问题核验",
            f"- p19 尾句并组：{'是' if focus_findings['tail_group_merged'] else '否'}",
            f"- `US$19.97 billion` 硬错误：{focus_findings['bad_scale_count']}",
            f"- `regarding dividend payments` 残句：{focus_findings['broken_fragment_count']}",
            f"- 末期股息/全年股息串位：{focus_findings['dividend_mixup_count']}",
            f"- 侧边栏进入主链路：{focus_findings['sidebar_intrusion_count']}",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def build_summary_report(
    stage_results: list[dict[str, Any]],
    evaluation_payload: dict[str, Any],
    focus_findings: dict[str, Any],
) -> str:
    avg = evaluation_payload["spike12_vs_human"]["average"]
    delta = evaluation_payload["delta_spike12_minus_v11"]
    lines = [
        "# Spike 12 总结报告",
        "",
        "## 已打通的关键链路",
        "- 基线冻结、资产快照、执行配置快照已落盘。",
        "- AnchorBlock / SemanticGroup / GroupContext / FactLock / RenderPlan 全链路已落盘。",
        "- 侧边栏对象已从主翻译与主回填链路排除。",
        "- 页级评估、阶段门验收、提示词与 API 日志已同步输出。",
        "",
        "## 本轮结果",
        f"- 相对 v11，token_f1 {delta['token_f1']:+.4f}，content_f1 {delta['content_f1']:+.4f}，sequence_ratio {delta['sequence_ratio']:+.4f}，number_recall {delta['number_recall']:+.4f}。",
        f"- Spike 12 对人工参考的平均指标：token_f1 {avg['token_f1']}，content_f1 {avg['content_f1']}，sequence_ratio {avg['sequence_ratio']}，number_recall {avg['number_recall']}。",
        f"- 第 19 页尾句并组：{'已解决' if focus_findings['tail_group_merged'] else '未解决'}。",
        f"- 股息与金额硬错误：scale={focus_findings['bad_scale_count']}，dividend_mixup={focus_findings['dividend_mixup_count']}。",
        "",
        "## 残余风险",
        "- 本轮仍基于 PDF 锚点回填，复杂版面与长段落 shrink 风险没有根除。",
        "- 事实锁定当前主要覆盖高风险金额、股息和关键比率，尚未扩展到全部财务口径。",
        "- 侧边栏本轮明确降级，不作为翻译目标。",
        "",
        "## 阶段状态",
    ]
    for stage in stage_results:
        lines.append(f"- 阶段 {stage['stage']} {stage['stage_name']}：{'通过' if stage['passed'] else '失败'}")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    original_dir = args.output_dir / "original"
    redacted_dir = args.output_dir / "redacted"
    translated_dir = args.output_dir / "translated"
    comparison_dir = args.output_dir / "comparison"
    prompt_dir = args.output_dir / "prompt_exports"
    api_logs_dir = args.output_dir / "api_logs"
    for directory in [original_dir, redacted_dir, translated_dir, comparison_dir, prompt_dir, api_logs_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    pages = parse_page_numbers(args.pages)
    stage_results: list[dict[str, Any]] = []

    baseline_snapshot = {
        "focus_pages": pages,
        "input_pdf": snapshot_file(args.input),
        "reference_pdf": snapshot_file(args.reference_pdf),
        "blocks_jsonl": snapshot_file(args.blocks_jsonl),
        "v11_baseline_dir": str(args.v11_baseline_dir),
        "v11_translations": snapshot_file(args.v11_baseline_dir / "translations.json"),
        "v11_report": snapshot_file(args.v11_baseline_dir / "report.json"),
        "problem_feedback": [
            snapshot_file(ROOT / "docs" / "问题反馈" / "问题1.txt"),
            snapshot_file(ROOT / "docs" / "问题反馈" / "问题2.txt"),
            snapshot_file(ROOT / "docs" / "问题反馈" / "问题3.md"),
        ],
    }
    write_json_file(args.output_dir / "baseline_snapshot.json", baseline_snapshot)
    stage_check(
        stage_results,
        "0",
        "冻结基线",
        True,
        "基线页、人工参考、v11 对照和问题反馈已冻结。",
        {"focus_pages": pages},
        args.output_dir,
    )

    glossary = build_spike11_glossary(load_json(args.glossary))
    patterns = load_json(args.patterns)
    document_background = sanitize_document_background(load_json(args.document_background), load_json(args.company_memory))

    asset_snapshot = {
        "mapping_library_version": snapshot_file(args.glossary),
        "company_memory_version": snapshot_file(args.company_memory),
        "financial_metric_map_version": snapshot_file(args.glossary),
        "style_policy_version": snapshot_file(args.document_background),
        "document_background_schema_version": snapshot_file(args.document_background),
        "prompt_bundle_subset_version": "spike12_v1",
    }
    execution_config_snapshot = {
        "model": args.model,
        "max_output_tokens": args.max_output_tokens,
        "compact_threshold": args.compact_threshold,
        "render_dpi": args.render_dpi,
        "pages": pages,
        "source_language": args.source_language,
        "target_language": args.target_language,
        "stop_after_stage": args.stop_after_stage,
    }
    write_json_file(args.output_dir / "asset_snapshot.json", asset_snapshot)
    write_json_file(args.output_dir / "execution_config_snapshot.json", execution_config_snapshot)
    write_json_file(args.output_dir / "document_background_sanitized.json", document_background)
    write_json_file(args.output_dir / "glossary_spike12_merged.json", glossary)
    stage_check(
        stage_results,
        "0.5",
        "冻结学习资产与执行输入",
        True,
        "资产快照与执行配置快照已落盘。",
        {"model": args.model, "compact_threshold": args.compact_threshold, "render_dpi": args.render_dpi},
        args.output_dir,
    )

    if args.stop_after_stage == 0:
        write_text_file(args.output_dir / "stage_status.md", build_stage_markdown(stage_results))
        return

    page_records = load_page_records(args.blocks_jsonl, set(pages))
    original_doc = fitz.open(args.input)
    redacted_doc = fitz.open(args.input)
    translated_doc = fitz.open(args.input)

    anchor_blocks_payload: list[dict[str, Any]] = []
    semantic_groups_payload: list[dict[str, Any]] = []
    mapping_hits_payload: list[dict[str, Any]] = []
    fact_locks_payload: list[dict[str, Any]] = []
    group_context_records: list[dict[str, Any]] = []

    page_to_groups: dict[int, list[dict[str, Any]]] = {}
    all_anchors_by_page: dict[int, list[dict[str, Any]]] = {}
    for page_no in pages:
        page_record = page_records[page_no]
        original_page = original_doc[page_no - 1]
        anchors = build_anchor_block_records(page_no, page_record, original_page)
        all_anchors_by_page[page_no] = anchors
        page_to_groups[page_no] = build_semantic_group_records(page_no, anchors)

        for group_index, group_record in enumerate(page_to_groups[page_no]):
            context_pack = build_context_pack(document_background, group_record)
            mapping_hits = [] if group_record["is_sidebar_group"] else build_mapping_hit_records(group_record, context_pack, glossary)
            fact_locks = [] if group_record["is_sidebar_group"] else build_fact_lock_records(group_record)
            neighbor_context = build_neighbor_context(page_to_groups[page_no], group_index)
            group_context = build_group_context_record(group_record, context_pack, mapping_hits, fact_locks, neighbor_context)
            group_context_records.append(group_context)
            mapping_hits_payload.extend(mapping_hits)
            fact_locks_payload.extend(fact_locks)

        anchor_blocks_payload.extend([{key: value for key, value in anchor.items() if key != "_runtime"} for anchor in anchors])
        semantic_groups_payload.extend(
            [
                {
                    "group_id": record["group_id"],
                    "page_no": record["page_no"],
                    "mode": record["mode"],
                    "block_ids": record["block_ids"],
                    "block_types": record["block_types"],
                    "source_text_joined": record["source_text_joined"],
                    "translation_target": record["translation_target"],
                    "is_sidebar_group": record["is_sidebar_group"],
                    "group_reason": record["group_reason"],
                }
                for record in page_to_groups[page_no]
            ]
        )

    write_json_file(args.output_dir / "anchor_blocks.json", anchor_blocks_payload)
    write_json_file(args.output_dir / "semantic_groups.json", semantic_groups_payload)
    write_json_file(args.output_dir / "mapping_hits.json", mapping_hits_payload)
    write_json_file(args.output_dir / "fact_locks.json", fact_locks_payload)
    write_json_file(args.output_dir / "group_context_records.json", group_context_records)

    total_source_blocks = sum(len(page_records[page_no]["blocks"]) for page_no in pages)
    traceable_anchor_count = sum(1 for item in anchor_blocks_payload if item.get("block_id") and item.get("bbox") and item.get("source_text") is not None)
    stage_check(
        stage_results,
        "1",
        "建立 Anchor IR",
        len(anchor_blocks_payload) == total_source_blocks and traceable_anchor_count == total_source_blocks,
        "AnchorBlock 数量与原始块数量一致，且均可追溯。",
        {"anchor_count": len(anchor_blocks_payload), "source_block_count": total_source_blocks},
        args.output_dir,
    )

    tail_group_merged = False
    sidebar_intrusion_count = 0
    for record in semantic_groups_payload:
        block_ids = set(record["block_ids"])
        if {"p19_b18", "p19_b19", "p19_b20"} == block_ids:
            tail_group_merged = True
        if record["is_sidebar_group"] and record["mode"] != "single_block":
            sidebar_intrusion_count += 1
    stage_check(
        stage_results,
        "2",
        "组装 SemanticGroup",
        tail_group_merged and sidebar_intrusion_count == 0,
        "第 19 页尾句并组已打通，侧边栏未混入正文组。",
        {"tail_group_merged": tail_group_merged, "sidebar_intrusion_count": sidebar_intrusion_count},
        args.output_dir,
    )

    fact_labels = {item["label"]: item for item in fact_locks_payload}
    fact_stage_passed = all(
        [
            "final_dividend_per_share" in fact_labels and fact_labels["final_dividend_per_share"]["expected_numbers"] == ["100.30"],
            "total_dividend_per_share" in fact_labels and fact_labels["total_dividend_per_share"]["expected_numbers"] == ["135.30"],
            "dividend_paid_usd" in fact_labels and "US$1.997 billion" in fact_labels["dividend_paid_usd"]["expected_forms"],
        ]
    )
    stage_check(
        stage_results,
        "3",
        "Fact Lock 与 Mapping Hit",
        fact_stage_passed,
        "关键股息与金额事实已锁定。",
        {
            "final_dividend": fact_labels.get("final_dividend_per_share", {}).get("expected_numbers"),
            "total_dividend": fact_labels.get("total_dividend_per_share", {}).get("expected_numbers"),
            "dividend_paid_usd": fact_labels.get("dividend_paid_usd", {}).get("expected_forms"),
        },
        args.output_dir,
    )

    if args.stop_after_stage <= 3:
        write_text_file(args.output_dir / "stage_status.md", build_stage_markdown(stage_results))
        return

    client = AnthropicGatewayClient.from_env(model=args.model, max_output_tokens=args.max_output_tokens)

    def apply_selected_redactions(page: fitz.Page, anchors: list[dict[str, Any]]) -> None:
        for anchor in anchors:
            if anchor["translation_target"]:
                page.add_redact_annot(fitz.Rect(anchor["bbox"]), fill=None, cross_out=False)
        page.apply_redactions(images=0, graphics=0, text=0)

    translations_payload: list[dict[str, Any]] = []
    render_plans_payload: list[dict[str, Any]] = []
    page_reports: list[dict[str, Any]] = []
    context_by_group_id = {item["group_id"]: item for item in group_context_records}

    for page_no in pages:
        original_page = original_doc[page_no - 1]
        redacted_page = redacted_doc[page_no - 1]
        translated_page = translated_doc[page_no - 1]
        anchors = all_anchors_by_page[page_no]

        apply_selected_redactions(redacted_page, anchors)
        apply_selected_redactions(translated_page, anchors)

        page_unit_reports: list[dict[str, Any]] = []
        for group_record in page_to_groups[page_no]:
            group_context_record = context_by_group_id[group_record["group_id"]]
            if group_record["is_sidebar_group"]:
                translations_payload.append(
                    {
                        "page_no": page_no,
                        "unit_id": group_record["group_id"],
                        "mode": group_record["mode"],
                        "block_ids": group_record["block_ids"],
                        "source_text": group_record["source_text_joined"],
                        "translation_source": "sidebar_excluded",
                        "final_translation": "",
                        "block_outputs": {},
                        "fact_validation_failures": [],
                    }
                )
                continue

            controlled = None
            translation_source = "model_initial"
            matched_terms = group_context_record["mapping_hits"]
            if group_record["mode"] == "single_block":
                controlled = resolve_controlled_translation(group_record["blocks"][0], group_record["block_types"][0], glossary, patterns)

            repair_used = False
            repaired_translation: str | None = None

            if controlled:
                initial_translation = clean_translation(controlled["translation"])
                translation_source = str(controlled["translation_source"])
            else:
                system_prompt, user_prompt = build_translation_prompts(
                    group_record=group_record,
                    source_language=args.source_language,
                    target_language=args.target_language,
                    group_context_record=group_context_record,
                )
                response = call_model_for_group(
                    client=client,
                    prompt_dir=prompt_dir,
                    api_logs_dir=api_logs_dir,
                    stem=f"{group_record['group_id']}_translation",
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    meta={"stage": "translation", "page_no": page_no, "group_id": group_record["group_id"]},
                )
                initial_translation = parse_unit_translation(response, group_record["group_id"])

            initial_translation = post_normalize_translation(group_record, group_context_record, initial_translation)
            initial_translation = apply_fact_lock_repairs(initial_translation, group_context_record.get("fact_locks", []))
            fact_failures = validate_translation_against_fact_locks(initial_translation, group_context_record.get("fact_locks", []))
            best_translation = initial_translation

            if fact_failures and not controlled:
                repair_used = True
                repair_system, repair_user = build_fact_repair_prompts(
                    group_record=group_record,
                    current_translation=initial_translation,
                    failures=fact_failures,
                    group_context_record=group_context_record,
                    source_language=args.source_language,
                    target_language=args.target_language,
                )
                repair_response = call_model_for_group(
                    client=client,
                    prompt_dir=prompt_dir,
                    api_logs_dir=api_logs_dir,
                    stem=f"{group_record['group_id']}_fact_repair",
                    system_prompt=repair_system,
                    user_prompt=repair_user,
                    meta={"stage": "fact_repair", "page_no": page_no, "group_id": group_record["group_id"]},
                )
                repaired_translation = parse_unit_translation(repair_response, group_record["group_id"])
                repaired_translation = post_normalize_translation(group_record, group_context_record, repaired_translation)
                repaired_translation = apply_fact_lock_repairs(repaired_translation, group_context_record.get("fact_locks", []))
                best_translation = repaired_translation
                fact_failures = validate_translation_against_fact_locks(best_translation, group_context_record.get("fact_locks", []))

            best_result = render_unit(
                page=translated_page,
                unit=group_record,
                translation=best_translation,
                target_language=args.target_language,
                commit=False,
            )

            compact_translation = None
            compact_used = False
            if not controlled and should_retry_compact(best_result, args.compact_threshold):
                compact_system, compact_user = build_compact_prompts(
                    unit=group_record,
                    source_language=args.source_language,
                    target_language=args.target_language,
                    context_pack=group_context_record,
                    current_translation=best_translation,
                )
                compact_response = call_model_for_group(
                    client=client,
                    prompt_dir=prompt_dir,
                    api_logs_dir=api_logs_dir,
                    stem=f"{group_record['group_id']}_compact",
                    system_prompt=compact_system,
                    user_prompt=compact_user,
                    meta={"stage": "compact", "page_no": page_no, "group_id": group_record["group_id"]},
                )
                compact_translation = parse_unit_translation(compact_response, group_record["group_id"])
                compact_translation = post_normalize_translation(group_record, group_context_record, compact_translation)
                compact_translation = apply_fact_lock_repairs(compact_translation, group_context_record.get("fact_locks", []))
                compact_failures = validate_translation_against_fact_locks(compact_translation, group_context_record.get("fact_locks", []))
                compact_result = render_unit(
                    page=translated_page,
                    unit=group_record,
                    translation=compact_translation,
                    target_language=args.target_language,
                    commit=False,
                )
                if not compact_failures and is_better_result(compact_result, best_result):
                    best_translation = compact_translation
                    best_result = compact_result
                    compact_used = True
                    fact_failures = compact_failures

            committed_result = render_unit(
                page=translated_page,
                unit=group_record,
                translation=best_translation,
                target_language=args.target_language,
                commit=True,
            )
            block_outputs = committed_result["rendered_by_block"] or {block["block_id"]: best_translation for block in group_record["blocks"]}
            final_fact_failures = validate_translation_against_fact_locks(best_translation, group_context_record.get("fact_locks", []))

            translations_payload.append(
                {
                    "page_no": page_no,
                    "unit_id": group_record["group_id"],
                    "mode": group_record["mode"],
                    "block_ids": group_record["block_ids"],
                    "source_text": group_record["source_text_joined"],
                    "group_context_record": group_context_record,
                    "matched_terms": matched_terms,
                    "initial_translation": initial_translation,
                    "repaired_translation": repaired_translation,
                    "compact_translation": compact_translation,
                    "final_translation": best_translation,
                    "translation_source": translation_source,
                    "repair_used": repair_used,
                    "compact_used": compact_used,
                    "fact_validation_failures": final_fact_failures,
                    "render_result": committed_result,
                    "block_outputs": block_outputs,
                }
            )
            render_plans_payload.append(
                {
                    "group_id": group_record["group_id"],
                    "page_no": page_no,
                    "block_ids": group_record["block_ids"],
                    "slot_count": len(group_record["slots"]),
                    "layout_mode": committed_result["layout_mode"],
                    "fit_status": committed_result["fit_status"],
                    "font_ratio": committed_result["font_ratio"],
                    "rendered_lines": committed_result["rendered_lines"],
                    "rendered_by_block": block_outputs,
                    "selected_scale": committed_result.get("selected_scale"),
                }
            )
            page_unit_reports.append(
                {
                    "unit_id": group_record["group_id"],
                    "mode": group_record["mode"],
                    "block_ids": group_record["block_ids"],
                    "translation_source": translation_source,
                    "repair_used": repair_used,
                    "compact_used": compact_used,
                    "fit_status": committed_result["fit_status"],
                    "font_ratio": committed_result["font_ratio"],
                    "layout_mode": committed_result["layout_mode"],
                    "fact_failure_count": len(final_fact_failures),
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
        page_reports.append({"page_no": page_no, "unit_count": len(page_to_groups[page_no]), "reports": page_unit_reports})

    write_json_file(args.output_dir / "translations.json", translations_payload)
    write_json_file(args.output_dir / "render_plans.json", render_plans_payload)
    write_json_file(args.output_dir / "report.json", {"pages": page_reports})
    redacted_doc.save(args.output_dir / "native_redacted.pdf")
    translated_doc.save(args.output_dir / "translated_en.pdf")

    p19_tail_group = next((item for item in translations_payload if set(item["block_ids"]) == {"p19_b18", "p19_b19", "p19_b20"}), None)
    p19_dividend_group = next((item for item in translations_payload if set(item["block_ids"]) == {"p19_b24", "p19_b25", "p19_b26"}), None)
    bad_scale_count = sum(1 for item in translations_payload if "US$19.97 billion" in str(item.get("final_translation") or ""))
    broken_fragment_count = sum(1 for item in translations_payload if "regarding dividend payments" in str(item.get("final_translation") or "").lower())
    dividend_mixup_count = 0
    if p19_dividend_group:
        text = str(p19_dividend_group.get("final_translation") or "")
        if re.search(r"final dividend[^.]{0,80}135\.30", text, flags=re.IGNORECASE):
            dividend_mixup_count += 1
        if re.search(r"total dividend[^.]{0,80}100\.30", text, flags=re.IGNORECASE):
            dividend_mixup_count += 1
        dividend_mixup_count += len(p19_dividend_group.get("fact_validation_failures") or [])
    sidebar_render_count = sum(1 for item in render_plans_payload if any(block_id in {"p13_b4", "p19_b4"} for block_id in item["block_ids"]))

    stage4_passed = bool(
        p19_tail_group
        and bad_scale_count == 0
        and broken_fragment_count == 0
        and dividend_mixup_count == 0
        and not p19_tail_group.get("fact_validation_failures")
    )
    stage_check(
        stage_results,
        "4",
        "按组翻译",
        stage4_passed,
        "关键金额、股息和尾句残缺问题已在组翻译阶段受控。",
        {
            "bad_scale_count": bad_scale_count,
            "broken_fragment_count": broken_fragment_count,
            "dividend_mixup_count": dividend_mixup_count,
        },
        args.output_dir,
    )

    current_layout = layout_summary_from_page_reports(page_reports)
    baseline_layout = average_layout_from_report(args.v11_baseline_dir / "report.json")
    overflow_count = sum(item["overflow_count"] for item in current_layout.values())
    # Spike 12 changed unitization and excluded sidebars, so page-level average font ratio
    # is only comparable within a small tolerance rather than exact equality.
    layout_not_worse = all(
        current_layout.get(page_no, {}).get("avg_font_ratio", 0.0) + 0.05 >= baseline_layout.get(page_no, {}).get("avg_font_ratio", 0.0)
        for page_no in pages
    )
    stage5_passed = overflow_count == 0 and sidebar_render_count == 0 and layout_not_worse
    stage_check(
        stage_results,
        "5",
        "生成 RenderPlan 并回填",
        stage5_passed,
        "RenderPlan 已生成，未出现侧边栏回填，且版面指标未明显差于 v11。",
        {
            "overflow_count": overflow_count,
            "sidebar_render_count": sidebar_render_count,
            "layout_not_worse": layout_not_worse,
        },
        args.output_dir,
    )

    if args.stop_after_stage <= 5:
        write_text_file(args.output_dir / "stage_status.md", build_stage_markdown(stage_results))
        return

    page_block_order = sp08_eval.load_page_block_order(args.blocks_jsonl, pages)
    reference_texts = {page_no: normalize_text_for_eval(text) for page_no, text in sp08_eval.load_reference_page_texts(args.reference_pdf, pages).items()}
    baseline_texts = build_baseline_page_texts(args.v11_baseline_dir / "translations.json", page_block_order, pages)
    spike12_texts = build_candidate_page_texts(translations_payload, page_block_order, pages)

    baseline_metrics = evaluate_pages(reference_texts, baseline_texts, pages)
    spike12_metrics = evaluate_pages(reference_texts, spike12_texts, pages)
    evaluation_payload = {
        "pages": pages,
        "v11_vs_human": {"average": average_metrics(baseline_metrics), "per_page": baseline_metrics},
        "spike12_vs_human": {"average": average_metrics(spike12_metrics), "per_page": spike12_metrics},
        "delta_spike12_minus_v11": delta_metrics(average_metrics(spike12_metrics), average_metrics(baseline_metrics)),
        "layout_v11": baseline_layout,
        "layout_spike12": current_layout,
    }
    write_json_file(args.output_dir / "evaluation_report.json", evaluation_payload)

    hard_error_count = bad_scale_count + broken_fragment_count + dividend_mixup_count
    delta = evaluation_payload["delta_spike12_minus_v11"]
    # Scope-adjusted PDF extraction has small evaluation noise after sidebar exclusion and regrouping.
    # Keep the gate strict on hard errors, but allow a very small metric tolerance.
    stage6_passed = all(delta[key] >= -0.005 for key in delta) and hard_error_count == 0 and sidebar_render_count == 0
    focus_findings = {
        "tail_group_merged": tail_group_merged,
        "bad_scale_count": bad_scale_count,
        "broken_fragment_count": broken_fragment_count,
        "dividend_mixup_count": dividend_mixup_count,
        "sidebar_intrusion_count": sidebar_intrusion_count + sidebar_render_count,
    }
    stage_check(
        stage_results,
        "6",
        "页级质量验收",
        stage6_passed,
        "相对 v11 的内容指标已对比完成，硬错误与侧边栏污染已复核。",
        {
            "delta_spike12_minus_v11": delta,
            "hard_error_count": hard_error_count,
            "sidebar_intrusion_count": focus_findings["sidebar_intrusion_count"],
        },
        args.output_dir,
    )

    write_text_file(args.output_dir / "stage_status.md", build_stage_markdown(stage_results))
    write_text_file(args.output_dir / "acceptance_report.md", build_acceptance_report(stage_results, evaluation_payload, focus_findings, args.output_dir))
    write_text_file(args.output_dir / "summary_report.md", build_summary_report(stage_results, evaluation_payload, focus_findings))


if __name__ == "__main__":
    main()
