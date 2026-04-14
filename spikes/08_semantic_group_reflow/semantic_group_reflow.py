from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import fitz


ROOT = Path(__file__).resolve().parents[2]
REUSE_SCRIPT = ROOT / "spikes" / "07_translation_current_bundle" / "scripts" / "translate_with_controls.py"
CONFIG_DIR = ROOT / "spikes" / "07_translation_current_bundle" / "configs"
DEFAULT_INPUT = ROOT / "样本" / "中文" / "AIA_2021_Annual_Report_zh.pdf"
DEFAULT_BLOCKS = ROOT / "spikes" / "01_text_block_extraction" / "output" / "AIA_2021_Annual_Report_zh" / "blocks.jsonl"
DEFAULT_OUTPUT = ROOT / "spikes" / "08_semantic_group_reflow" / "output" / "focus_pages_10_13_19_20"
DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
STATUS_RANK = {"overflow": 0, "font_shrink": 1, "ok": 2}


def load_reuse_module() -> Any:
    spec = importlib.util.spec_from_file_location("translation_reuse", REUSE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load reuse module: {REUSE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reuse = load_reuse_module()

AnthropicGatewayClient = reuse.AnthropicGatewayClient
apply_text_redactions = reuse.apply_text_redactions
classify_block_type = reuse.classify_block_type
collect_relevant_terms = reuse.collect_relevant_terms
extract_raw_line_segments = reuse.extract_raw_line_segments
extract_response_text = reuse.extract_response_text
fit_translation_block = reuse.fit_translation_block
infer_block_style = reuse.infer_block_style
insert_single_line_best_fit = reuse.insert_single_line_best_fit
load_page_records = reuse.load_page_records
measure_text_width = reuse.measure_text_width
normalize_source_text = reuse.normalize_source_text
parse_json_from_text = reuse.parse_json_from_text
parse_page_numbers = reuse.parse_page_numbers
render_page = reuse.render_page
resolve_controlled_translation = reuse.resolve_controlled_translation
save_comparison = reuse.save_comparison
write_json_file = reuse.write_json_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Spike 08: semantic grouping for cross-block translation and slot-based reflow."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--blocks-jsonl", type=Path, default=DEFAULT_BLOCKS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pages", type=str, default="10,13,19,20")
    parser.add_argument("--source-language", default="Traditional Chinese")
    parser.add_argument("--target-language", default="English")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-output-tokens", type=int, default=1800)
    parser.add_argument("--render-dpi", type=int, default=110)
    parser.add_argument("--compact-threshold", type=float, default=0.84)
    parser.add_argument("--glossary", type=Path, default=CONFIG_DIR / "glossary_zh_en_seed.json")
    parser.add_argument("--patterns", type=Path, default=CONFIG_DIR / "patterns_zh_en.json")
    return parser.parse_args()


def load_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def clean_text(text: str) -> str:
    return normalize_source_text(text).strip()


def clean_translation(text: str) -> str:
    lines = [" ".join(line.split()) for line in str(text).splitlines()]
    return " ".join(line for line in lines if line).strip()


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
    return bool(re.search(r"[。！？!?；;：:.”\"]\s*$", text.strip()))


def is_narrative_candidate(block: dict[str, Any], block_type: str) -> bool:
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
    if likely_numeric_dense(block):
        return False
    if block_width(block) <= 36:
        return False
    return True


def can_merge_into_group(
    current_group: list[dict[str, Any]],
    candidate: dict[str, Any],
) -> bool:
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


def build_semantic_units(page_no: int, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered_blocks = sorted(blocks, key=lambda item: item["reading_order"])
    pending_group: list[dict[str, Any]] = []
    raw_units: list[list[dict[str, Any]]] = []

    def flush_group() -> None:
        nonlocal pending_group
        if pending_group:
            raw_units.append(pending_group)
            pending_group = []

    for block in ordered_blocks:
        if not block["_narrative_candidate"]:
            flush_group()
            raw_units.append([block])
            continue
        if not pending_group:
            pending_group = [block]
            continue
        if can_merge_into_group(pending_group, block):
            pending_group.append(block)
        else:
            flush_group()
            pending_group = [block]
    flush_group()

    units: list[dict[str, Any]] = []
    group_index = 1
    for block_group in raw_units:
        is_group = len(block_group) > 1
        unit_id = f"p{page_no}_g{group_index:02d}" if is_group else str(block_group[0]["block_id"])
        if is_group:
            group_index += 1
        units.append(
            {
                "unit_id": unit_id,
                "page_no": page_no,
                "mode": "semantic_group" if is_group else "single_block",
                "block_ids": [block["block_id"] for block in block_group],
                "blocks": block_group,
                "block_types": [block["_block_type"] for block in block_group],
                "source_text_joined": "\n".join(
                    clean_text(block.get("source_text", ""))
                    for block in block_group
                    if clean_text(block.get("source_text", ""))
                ),
            }
        )
    return units


def collect_unit_slots(unit: dict[str, Any], segment_map: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for block in unit["blocks"]:
        segments = segment_map.get(block["block_id"]) or []
        if segments:
            for segment_index, segment in enumerate(segments, start=1):
                slots.append(
                    {
                        "slot_id": f"{block['block_id']}_s{segment_index:02d}",
                        "block_id": block["block_id"],
                        "bbox": list(segment["bbox"]),
                        "font_size": float(segment.get("font_size") or block.get("font_size_avg") or 10),
                        "font_specs": segment.get("font_specs") or [],
                        "color_rgb255": tuple(segment.get("color_rgb255") or (0, 0, 0)),
                    }
                )
        else:
            slots.append(
                {
                    "slot_id": f"{block['block_id']}_s01",
                    "block_id": block["block_id"],
                    "bbox": list(block["bbox"]),
                    "font_size": block_font_size(block),
                    "font_specs": [],
                    "color_rgb255": tuple(block.get("_style", {}).get("color_rgb255") or (0, 0, 0)),
                }
            )
    slots.sort(key=lambda item: (round(item["bbox"][1], 2), round(item["bbox"][0], 2)))
    return slots


def tokenize_for_target(text: str, target_language: str) -> list[str]:
    normalized = clean_translation(text)
    if not normalized:
        return []
    if target_language.lower() == "english":
        return re.findall(r"\S+\s*", normalized)
    if " " in normalized:
        return re.findall(r"\S+\s*", normalized)
    return [char for char in normalized if char.strip()]


def measure_line(line: str, slot: dict[str, Any], scale: float) -> float:
    if not line.strip():
        return 0.0
    font_specs = slot.get("font_specs") or [{"fontname": "Helvetica"}]
    font_spec = font_specs[0]
    fontsize = max(1.0, float(slot["font_size"]) * scale)
    return float(measure_text_width(line, font_spec, fontsize=fontsize))


def assign_tokens_to_slots(
    tokens: list[str],
    slots: list[dict[str, Any]],
    scale: float,
) -> list[str] | None:
    if not slots:
        return None
    lines: list[str] = []
    token_index = 0
    for slot_index, slot in enumerate(slots):
        if token_index >= len(tokens):
            lines.append("")
            continue
        remaining_slots = len(slots) - slot_index
        reserve_for_rest = max(0, remaining_slots - 1)
        max_width = max(1.0, float(slot["bbox"][2] - slot["bbox"][0]) - 1.0)
        current = ""
        while token_index < len(tokens):
            candidate = f"{current}{tokens[token_index]}"
            candidate_width = measure_line(candidate.strip(), slot, scale)
            tokens_left_after = len(tokens) - (token_index + 1)
            if candidate_width <= max_width and tokens_left_after >= reserve_for_rest:
                current = candidate
                token_index += 1
                continue
            if not current:
                current = candidate
                token_index += 1
            break
        if slot_index == len(slots) - 1 and token_index < len(tokens):
            current = f"{current}{''.join(tokens[token_index:])}"
            token_index = len(tokens)
        lines.append(current.strip())
    if token_index < len(tokens):
        return None
    return lines


def collapse_slot_lines_by_block(slots: list[dict[str, Any]], lines: list[str]) -> dict[str, str]:
    by_block: dict[str, list[str]] = {}
    for slot, line in zip(slots, lines):
        if not line.strip():
            continue
        by_block.setdefault(slot["block_id"], []).append(line.strip())
    return {block_id: "\n".join(block_lines) for block_id, block_lines in by_block.items()}


def evaluate_slot_lines(
    page: fitz.Page,
    slots: list[dict[str, Any]],
    lines: list[str],
    scale: float,
    commit: bool,
) -> tuple[float, str]:
    min_ratio = 1.0
    status = "ok"
    for slot, line in zip(slots, lines):
        if not line.strip():
            continue
        rect = fitz.Rect(slot["bbox"])
        rect.x0 = max(0.0, rect.x0 - 0.5)
        rect.x1 += 0.5
        fitted_size, fitted_status = insert_single_line_best_fit(
            page=page,
            rect=rect,
            text=line,
            color_rgb255=slot["color_rgb255"],
            preferred_font_size=float(slot["font_size"]) * scale,
            preferred_fonts=slot.get("font_specs") or ["Helvetica", "Times-Roman"],
            min_font_size=max(3.0, float(slot["font_size"]) * 0.55),
            commit=commit,
        )
        min_ratio = min(min_ratio, fitted_size / max(1.0, float(slot["font_size"])))
        if fitted_status == "overflow":
            return min_ratio, "overflow"
        if fitted_status == "font_shrink":
            status = "font_shrink"
    return min_ratio, status


def render_group_into_slots(
    page: fitz.Page,
    slots: list[dict[str, Any]],
    translation: str,
    target_language: str,
    commit: bool,
) -> dict[str, Any]:
    tokens = tokenize_for_target(translation, target_language)
    if not tokens:
        return {
            "layout_mode": "group_slots",
            "fit_status": "overflow",
            "font_ratio": 0.0,
            "rendered_lines": [],
            "rendered_by_block": {},
            "slot_count": len(slots),
            "selected_scale": 0.0,
        }
    for step in range(0, 20):
        scale = round(1.02 - step * 0.025, 3)
        lines = assign_tokens_to_slots(tokens, slots, scale)
        if lines is None:
            continue
        font_ratio, fit_status = evaluate_slot_lines(page, slots, lines, scale=scale, commit=False)
        if fit_status == "overflow":
            continue
        if commit:
            font_ratio, fit_status = evaluate_slot_lines(page, slots, lines, scale=scale, commit=True)
        return {
            "layout_mode": "group_slots",
            "fit_status": fit_status,
            "font_ratio": round(font_ratio, 3),
            "rendered_lines": lines,
            "rendered_by_block": collapse_slot_lines_by_block(slots, lines),
            "slot_count": len(slots),
            "selected_scale": scale,
        }
    return {
        "layout_mode": "group_slots",
        "fit_status": "overflow",
        "font_ratio": 0.0,
        "rendered_lines": [],
        "rendered_by_block": {},
        "slot_count": len(slots),
        "selected_scale": 0.0,
    }


def render_single_block(
    page: fitz.Page,
    block: dict[str, Any],
    translation: str,
    commit: bool,
) -> dict[str, Any]:
    font_size, fit_status, layout_mode = fit_translation_block(
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
        "rendered_lines": [translation],
        "rendered_by_block": {block["block_id"]: translation},
        "slot_count": len(block["_segments"]) or 1,
        "selected_scale": round(font_size / max(1.0, block["_style"]["font_size"]), 3),
    }


def render_unit(
    page: fitz.Page,
    unit: dict[str, Any],
    translation: str,
    target_language: str,
    commit: bool,
) -> dict[str, Any]:
    if unit["mode"] == "semantic_group":
        return render_group_into_slots(
            page=page,
            slots=unit["slots"],
            translation=translation,
            target_language=target_language,
            commit=commit,
        )
    return render_single_block(page=page, block=unit["blocks"][0], translation=translation, commit=commit)


def build_translation_prompts(
    unit: dict[str, Any],
    source_language: str,
    target_language: str,
    glossary_hits: list[dict[str, str]],
) -> tuple[str, str]:
    system_prompt = "\n".join(
        [
            "你是上市公司年报翻译器。",
            f"语言方向：{source_language} -> {target_language}。",
            "只翻译当前输入，不补充、不解释、不总结。",
            "如果当前输入由多个连续块组成，只允许在当前组内做跨块理解；不得引入组外内容。",
            "数字、百分比、货币、年份、专有名词、公司名、人名、地名必须准确。",
            "输出必须是 JSON，且只能输出 JSON。",
        ]
    )
    blocks_payload = [
        {"block_id": block["block_id"], "source_text": clean_text(block.get("source_text", ""))}
        for block in unit["blocks"]
    ]
    user_lines = [
        "文档场景：上市公司企业年报",
        f"page_no: {unit['page_no']}",
        f"unit_id: {unit['unit_id']}",
        f"unit_mode: {unit['mode']}",
    ]
    if glossary_hits:
        user_lines.append("命中术语约束:")
        user_lines.append(json.dumps(glossary_hits, ensure_ascii=False, indent=2))
    user_lines.append("blocks:")
    user_lines.append(json.dumps(blocks_payload, ensure_ascii=False, indent=2))
    user_lines.append("joined_source_text:")
    user_lines.append(unit["source_text_joined"])
    user_lines.append("返回格式:")
    user_lines.append(
        json.dumps(
            {"translations": [{"unit_id": unit["unit_id"], "translation": "<译文>"}]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return system_prompt, "\n".join(user_lines)


def build_compact_prompts(
    unit: dict[str, Any],
    source_language: str,
    target_language: str,
    current_translation: str,
) -> tuple[str, str]:
    system_prompt = "\n".join(
        [
            "你是版面回填压缩器。",
            f"语言方向：{source_language} -> {target_language}。",
            "在不改变事实、数字、专有名词和正式语气的前提下，对当前译文做最小必要压缩。",
            "不得补充新信息，不得删除关键事实，不得改动数字和单位。",
            "输出必须是 JSON，且只能输出 JSON。",
        ]
    )
    user_lines = [
        "文档场景：上市公司企业年报",
        f"page_no: {unit['page_no']}",
        f"unit_id: {unit['unit_id']}",
        f"unit_mode: {unit['mode']}",
        f"slot_count: {len(unit['slots'])}",
        "source_text:",
        unit["source_text_joined"],
        "current_translation:",
        clean_translation(current_translation),
        "返回格式:",
        json.dumps(
            {"translations": [{"unit_id": unit["unit_id"], "translation": "<更紧凑译文>"}]},
            ensure_ascii=False,
            indent=2,
        ),
    ]
    return system_prompt, "\n".join(user_lines)


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


def parse_unit_translation(response_json: dict[str, Any], unit_id: str) -> str:
    payload = parse_json_from_text(extract_response_text(response_json))
    translations = payload.get("translations")
    if isinstance(translations, list):
        for item in translations:
            if item.get("unit_id") == unit_id and isinstance(item.get("translation"), str):
                return clean_translation(item["translation"])
    if payload.get("unit_id") == unit_id and isinstance(payload.get("translation"), str):
        return clean_translation(payload["translation"])
    raise ValueError(f"Missing translation for unit_id={unit_id}")


def should_retry_compact(result: dict[str, Any], compact_threshold: float) -> bool:
    return result["fit_status"] == "overflow" or float(result["font_ratio"]) < compact_threshold


def is_better_result(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if STATUS_RANK[left["fit_status"]] != STATUS_RANK[right["fit_status"]]:
        return STATUS_RANK[left["fit_status"]] > STATUS_RANK[right["fit_status"]]
    return float(left["font_ratio"]) > float(right["font_ratio"])


def main() -> None:
    args = parse_args()
    glossary = load_json_file(args.glossary)
    patterns = load_json_file(args.patterns)
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

    semantic_groups_payload: list[dict[str, Any]] = []
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
            enriched_block = {
                **block,
                "_block_type": classify_block_type(block),
                "_style": style,
                "_segments": segments,
            }
            enriched_block["_narrative_candidate"] = is_narrative_candidate(enriched_block, enriched_block["_block_type"])
            blocks.append(enriched_block)

        segment_map = {block["block_id"]: block["_segments"] for block in blocks}
        units = build_semantic_units(page_no=page_no, blocks=blocks)
        for unit in units:
            unit["slots"] = collect_unit_slots(unit, segment_map)

        semantic_groups_payload.append(
            {
                "page_no": page_no,
                "units": [
                    {
                        "unit_id": unit["unit_id"],
                        "mode": unit["mode"],
                        "block_ids": unit["block_ids"],
                        "block_types": unit["block_types"],
                        "slot_count": len(unit["slots"]),
                    }
                    for unit in units
                ],
            }
        )

        page_unit_reports: list[dict[str, Any]] = []
        for unit in units:
            controlled = None
            translation_source = "model_initial"
            if unit["mode"] == "single_block":
                block = unit["blocks"][0]
                controlled = resolve_controlled_translation(block, block["_block_type"], glossary, patterns)
            if controlled:
                initial_translation = clean_translation(controlled["translation"])
                translation_source = str(controlled["translation_source"])
            else:
                glossary_hits = collect_relevant_terms(unit["blocks"], glossary, limit=12)
                system_prompt, user_prompt = build_translation_prompts(
                    unit=unit,
                    source_language=args.source_language,
                    target_language=args.target_language,
                    glossary_hits=glossary_hits,
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
                "group_count": sum(1 for unit in units if unit["mode"] == "semantic_group"),
                "reports": page_unit_reports,
            }
        )

    redacted_doc.save(args.output_dir / "native_redacted.pdf")
    translated_doc.save(args.output_dir / "translated_grouped.pdf")
    write_json_file(args.output_dir / "semantic_groups.json", semantic_groups_payload)
    write_json_file(args.output_dir / "translations.json", translations_payload)
    write_json_file(args.output_dir / "report.json", {"pages": page_reports})


if __name__ == "__main__":
    main()
