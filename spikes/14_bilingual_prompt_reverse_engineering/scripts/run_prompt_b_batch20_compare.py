from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[3]
TRANSLATIONS_JSON = (
    ROOT
    / "spikes"
    / "13_lane_separated_render"
    / "output"
    / "first20_opus46_adaptive_v2_promptclean_r2"
    / "translations.json"
)
EN_PAGES_JSON = (
    ROOT
    / "spikes"
    / "14_bilingual_prompt_reverse_engineering"
    / "output"
    / "aia_2021_prompt_consultation_first20"
    / "extracted"
    / "en_pages.json"
)
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "spikes"
    / "14_bilingual_prompt_reverse_engineering"
    / "output"
    / "prompt_b_batch20_compare_v1"
)
DEFAULT_MODEL = os.environ.get("PROMPT_COMPARE_MODEL") or os.environ.get("ANTHROPIC_MODEL") or "claude-opus-4-6"

DEFAULT_SYSTEM_PROMPT = """# Role: 全球顶级金融与保险行业专业翻译官

## 专家背景
你是一位拥有20年行业经验的资深金融翻译专家，深刻理解国际财务报告准则（IFRS）、保险业务、精算科学以及国际资本市场年报写作规范。

## 翻译原则
- 术语优先：识别并使用行业公认术语，如 Value of New Business、Embedded Value、Operating Profit After Tax。
- 句式重构：在不增删事实的前提下，将中文长句重组为符合英文年报习惯的正式句式。
- 语气庄重：保持上市企业年报的严谨、客观、专业感。
- 逻辑对齐：如果原文存在因果、转折、并列关系，要用清晰、正式的英文表达呈现。

## 执行要求
- 忠实原文，不增加、不删减、不解释。
- 数字、百分比、货币单位、年份必须准确。
- 只输出最终英文译文，不输出术语清单、分析过程或额外说明。"""


@dataclass
class SampleParagraph:
    sample_id: str
    page_no: int
    unit_ids: list[str]
    source_text: str
    human_reference: str


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9$%.,'\"()/-]+", text.lower())


def token_f1(reference: str, hypothesis: str) -> float:
    ref_tokens = tokenize(reference)
    hyp_tokens = tokenize(hypothesis)
    if not ref_tokens or not hyp_tokens:
        return 0.0
    ref_counts: dict[str, int] = {}
    hyp_counts: dict[str, int] = {}
    for token in ref_tokens:
        ref_counts[token] = ref_counts.get(token, 0) + 1
    for token in hyp_tokens:
        hyp_counts[token] = hyp_counts.get(token, 0) + 1
    overlap = 0
    for token, ref_count in ref_counts.items():
        overlap += min(ref_count, hyp_counts.get(token, 0))
    precision = overlap / len(hyp_tokens)
    recall = overlap / len(ref_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def sequence_ratio(reference: str, hypothesis: str) -> float:
    return SequenceMatcher(None, normalize_whitespace(reference), normalize_whitespace(hypothesis)).ratio()


def load_translation_map() -> dict[str, dict[str, Any]]:
    payload = json.loads(TRANSLATIONS_JSON.read_text(encoding="utf-8"))
    return {item["unit_id"]: item for item in payload}


def join_source_units(translation_map: dict[str, dict[str, Any]], unit_ids: list[str]) -> str:
    text = "".join((translation_map[unit_id]["source_text"] or "").replace("\n", "") for unit_id in unit_ids)
    return normalize_whitespace(text)


def clean_extraction_artifacts(text: str) -> str:
    cleaned = normalize_whitespace(text)
    replacements = {
        "ServicesInc.": "Services Inc.",
        "possiblewithout": "possible without",
        "companyin": "company in",
        "successionplanning": "succession planning",
        "needsevolve": "needs evolve",
        "GOVERNANCEpolicy": "policy",
        "GOVERNANCEfor": "for",
        "STATEMENTShas": "has",
        "thecomplexity": "the complexity",
    }
    for src, dst in replacements.items():
        cleaned = cleaned.replace(src, dst)
    return normalize_whitespace(cleaned)


def raw_extract_en_page_paragraphs(page_no: int, page_text: str) -> list[str]:
    drop_exact = {
        "OVERVIEW",
        "REVIEW",
        "OPERATING",
        "AND",
        "FINANCIAL",
        "GOVERNANCE",
        "CORPORATE",
        "ADDITIONAL",
        "INFORMATION",
        "CHAIRMAN’S STATEMENT",
        "GROUP CHIEF EXECUTIVE AND",
        "PRESIDENT’S REPORT",
        "2020 PERFORMANCE HIGHLIGHTS",
        "ENGAGEMENT WITH PEOPLE",
    }
    edge_noise_tokens = (
        "OVERVIEW",
        "REVIEW",
        "OPERATING",
        "FINANCIAL",
        "GOVERNANCE",
        "CORPORATE",
        "ADDITIONAL",
        "INFORMATION",
        "STATEMENTS",
    )

    lines: list[str] = []
    for raw_line in page_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^\d{3}\s+AIA GROUP LIMITED$", line):
            continue
        if line in drop_exact:
            continue
        if line.isupper() and len(line) < 40:
            continue
        line = re.sub(r"\s+", " ", line)
        for token in edge_noise_tokens:
            line = re.sub(rf"^{re.escape(token)}\s+", "", line)
            line = re.sub(rf"\s+{re.escape(token)}$", "", line)
        line = line.strip()
        if line:
            lines.append(line)

    paras: list[str] = []
    buffer: list[str] = []
    for line in lines:
        if not buffer and (
            line.startswith("AIA is proud of its reputation")
            or line.startswith("Our colleagues have responded")
            or line.startswith("AIA has delivered another very strong performance")
            or line.startswith("Mr. Lee Yuan Siong")
        ):
            continue
        buffer.append(line)
        if re.search(r"[.\"]$", line):
            paras.append(clean_extraction_artifacts(" ".join(buffer)))
            buffer = []
    if buffer:
        paras.append(clean_extraction_artifacts(" ".join(buffer)))

    if page_no == 10:
        return paras[2:6]
    if page_no == 11:
        esg = clean_extraction_artifacts(paras[3] + " " + paras[4])
        growth_block = paras[5]
        if "Finally," not in growth_block and len(paras) > 6:
            growth_block = clean_extraction_artifacts(growth_block + " " + paras[6])
        parts = re.split(r"\bFinally,\s+", growth_block, maxsplit=1)
        if len(parts) != 2:
            raise ValueError("Failed to split page 11 growth/closing paragraph.")
        growth, closing_tail = parts
        growth = clean_extraction_artifacts(growth)
        closing = clean_extraction_artifacts("Finally, " + closing_tail)
        return [paras[0], paras[1], paras[2], esg, growth, closing]
    if page_no == 13:
        dividend = clean_extraction_artifacts(paras[3])
        distribution = clean_extraction_artifacts(paras[5])
        technology = clean_extraction_artifacts(paras[6] + " " + paras[7])
        closing = clean_extraction_artifacts(paras[8])
        return [paras[0], paras[1], paras[2], dividend, paras[4], distribution, technology, closing]
    if page_no == 14:
        first = paras[0]
        first = re.sub(r"^GROUP CHIEF EXECUTIVE.*?REPORT\s+", "", first)
        return [clean_extraction_artifacts(first), clean_extraction_artifacts(paras[1])]
    raise ValueError(f"Unexpected page for reference extraction: {page_no}")


def build_reference_bank() -> dict[int, list[str]]:
    page_payload = json.loads(EN_PAGES_JSON.read_text(encoding="utf-8"))
    page_texts = {item["page_no"]: item["text"] for item in page_payload}
    return {
        10: raw_extract_en_page_paragraphs(10, page_texts[10]),
        11: raw_extract_en_page_paragraphs(11, page_texts[11]),
        13: raw_extract_en_page_paragraphs(13, page_texts[13]),
        14: raw_extract_en_page_paragraphs(14, page_texts[14]),
    }


def build_samples() -> list[SampleParagraph]:
    translation_map = load_translation_map()
    reference_bank = build_reference_bank()
    definitions: list[tuple[str, int, list[str], int]] = [
        ("S01", 10, ["p10_g01", "p10_b18"], 0),
        ("S02", 10, ["p10_g02", "p10_b21"], 1),
        ("S03", 10, ["p10_g03"], 2),
        ("S04", 10, ["p10_g04", "p10_b27"], 3),
        ("S05", 11, ["p11_g01"], 0),
        ("S06", 11, ["p11_g02", "p11_b7"], 1),
        ("S07", 11, ["p11_g03", "p11_b11"], 2),
        ("S08", 11, ["p11_g04", "p11_b17"], 3),
        ("S09", 11, ["p11_g05"], 4),
        ("S10", 11, ["p11_b22", "p11_b23"], 5),
        ("S11", 13, ["p13_g01", "p13_b3"], 0),
        ("S12", 13, ["p13_g02", "p13_b8"], 1),
        ("S13", 13, ["p13_g03", "p13_b13"], 2),
        ("S14", 13, ["p13_b14", "p13_b15"], 3),
        ("S15", 13, ["p13_g04", "p13_b19"], 4),
        ("S16", 13, ["p13_g05"], 5),
        ("S17", 13, ["p13_g06", "p13_b25"], 6),
        ("S18", 13, ["p13_g07"], 7),
        ("S19", 14, ["p14_g01", "p14_b7"], 0),
        ("S20", 14, ["p14_g02"], 1),
    ]

    samples: list[SampleParagraph] = []
    for sample_id, page_no, unit_ids, ref_index in definitions:
        samples.append(
            SampleParagraph(
                sample_id=sample_id,
                page_no=page_no,
                unit_ids=unit_ids,
                source_text=join_source_units(translation_map, unit_ids),
                human_reference=reference_bank[page_no][ref_index],
            )
        )
    return samples


def build_user_prompt(samples: list[SampleParagraph], include_tail_notes: bool) -> str:
    lines = [
        "现在请直接翻译以下20个中文年报正文段落。",
        "",
        "输出要求：",
        "1. 必须逐段翻译，不合并，不拆分，不省略。",
        "2. 保持编号顺序。",
        "3. 每段必须按原编号输出。",
    "4. 输出格式必须严格如下：",
        "### S01",
        "<英文译文>",
        "",
        "### S02",
        "<英文译文>",
        "",
        "其余段落依此类推，直到 ### S20。",
        "",
    ]
    if include_tail_notes:
        lines.extend(
            [
                "5. 在全部译文之后，单独追加：",
                "### Narrative Notes",
                "<两处关键改进的简要说明>",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "5. 只输出译文，不要解释。",
                "",
            ]
        )
    lines.extend(
        [
        "待翻译段落：",
        "",
        ]
    )
    for sample in samples:
        lines.extend(
            [
                f"### {sample.sample_id} | page {sample.page_no}",
                sample.source_text,
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def call_model(model: str, system_prompt: str, user_prompt: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not base_url or not api_key:
        raise RuntimeError("Missing ANTHROPIC_BASE_URL or ANTHROPIC_AUTH_TOKEN.")

    payload = {
        "model": model,
        "max_tokens": 7000,
        "temperature": 0,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    url = base_url.rstrip("/") + "/v1/messages"

    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=300)
            response.raise_for_status()
            data = response.json()
            text = "\n".join(
                item.get("text", "")
                for item in data.get("content", [])
                if item.get("type") == "text"
            ).strip()
            return payload, data, text
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < 3:
                time.sleep(5 * attempt)
                continue
            raise RuntimeError(str(last_error)) from exc
    raise RuntimeError(str(last_error))


def parse_response_sections(response_text: str) -> tuple[dict[str, str], str]:
    header_pattern = re.compile(r"^###\s*(.+?)\s*$", re.MULTILINE)
    matches = list(header_pattern.finditer(response_text))
    sections: dict[str, str] = {}
    tail_chunks: list[str] = []
    for idx, match in enumerate(matches):
        header = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(response_text)
        body = response_text[start:end].strip()
        body = re.sub(r"\n[-*]{3,}\s*$", "", body).strip()
        sample_match = re.fullmatch(r"(S\d{2})(?:\s*\|.*)?", header)
        if sample_match:
            sections[sample_match.group(1)] = body
        else:
            chunk = f"### {header}\n{body}".strip()
            if chunk:
                tail_chunks.append(chunk)
    return sections, "\n\n".join(tail_chunks).strip()


def build_human_reference_markdown(samples: list[SampleParagraph]) -> str:
    lines = ["# Human Reference", ""]
    for sample in samples:
        lines.extend([f"### {sample.sample_id}", sample.human_reference, ""])
    return "\n".join(lines).strip() + "\n"


def build_comparison_markdown(
    model: str,
    system_prompt: str,
    user_prompt: str,
    response_text: str,
    samples: list[SampleParagraph],
    parsed_translations: dict[str, str],
    response_tail_notes: str,
    metrics_rows: list[dict[str, Any]],
) -> str:
    avg_token = round(sum(row["token_f1"] for row in metrics_rows) / len(metrics_rows), 4) if metrics_rows else 0.0
    avg_sequence = (
        round(sum(row["sequence_ratio"] for row in metrics_rows) / len(metrics_rows), 4) if metrics_rows else 0.0
    )
    lines = [
        "# Prompt B Batch 20 Comparison",
        "",
        f"- model: `{model}`",
        f"- paragraph_count: `{len(samples)}`",
        f"- parsed_paragraph_count: `{len(parsed_translations)}`",
        f"- avg_token_f1: `{avg_token}`",
        f"- avg_sequence_ratio: `{avg_sequence}`",
        "",
        "## System Prompt",
        "",
        "```text",
        system_prompt,
        "```",
        "",
        "## User Prompt",
        "",
        "```text",
        user_prompt.strip(),
        "```",
        "",
        "## Claude Raw Response",
        "",
        "```text",
        response_text.strip(),
        "```",
        "",
    ]
    if response_tail_notes:
        lines.extend(
            [
                "## Claude Tail Notes",
                "",
                "```text",
                response_tail_notes,
                "```",
                "",
            ]
        )
    lines.extend(
        [
        "## Human Reference Combined",
        "",
        ]
    )
    for sample in samples:
        lines.extend([f"### {sample.sample_id}", sample.human_reference, ""])

    lines.extend(["## Per Paragraph Comparison", ""])
    metrics_by_id = {row["sample_id"]: row for row in metrics_rows}
    for sample in samples:
        row = metrics_by_id.get(sample.sample_id, {})
        claude_text = parsed_translations.get(sample.sample_id, "")
        lines.extend(
            [
                f"### {sample.sample_id} | page {sample.page_no}",
                "",
                f"- unit_ids: `{', '.join(sample.unit_ids)}`",
                f"- token_f1: `{row.get('token_f1', 0.0)}`",
                f"- sequence_ratio: `{row.get('sequence_ratio', 0.0)}`",
                "",
                "#### Source ZH",
                "",
                "```text",
                sample.source_text,
                "```",
                "",
                "#### Claude",
                "",
                "```text",
                claude_text,
                "```",
                "",
                "#### Human Reference",
                "",
                "```text",
                sample.human_reference,
                "```",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to write outputs.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Anthropic model id.")
    parser.add_argument("--system-prompt-file", help="Path to a UTF-8 text file containing the system prompt.")
    parser.add_argument("--output-prefix", default="prompt_b_batch20", help="Prefix for output filenames.")
    parser.add_argument(
        "--include-tail-notes",
        action="store_true",
        help="Ask the model to append a separate narrative-notes section after all translations.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    samples = build_samples()
    system_prompt = (
        Path(args.system_prompt_file).read_text(encoding="utf-8")
        if args.system_prompt_file
        else DEFAULT_SYSTEM_PROMPT
    )
    user_prompt = build_user_prompt(samples, include_tail_notes=args.include_tail_notes)
    request_payload, response_payload, response_text = call_model(args.model, system_prompt, user_prompt)
    parsed, tail_notes = parse_response_sections(response_text)

    metrics_rows: list[dict[str, Any]] = []
    for sample in samples:
        claude_text = parsed.get(sample.sample_id, "")
        metrics_rows.append(
            {
                "sample_id": sample.sample_id,
                "page_no": sample.page_no,
                "unit_ids": sample.unit_ids,
                "token_f1": round(token_f1(sample.human_reference, claude_text), 4),
                "sequence_ratio": round(sequence_ratio(sample.human_reference, claude_text), 4),
                "claude_translation": claude_text,
                "human_reference": sample.human_reference,
                "source_text": sample.source_text,
            }
        )

    (output_dir / "samples.json").write_text(
        json.dumps([sample.__dict__ for sample in samples], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "request_payload.json").write_text(
        json.dumps(request_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "response_payload.json").write_text(
        json.dumps(response_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "parsed_response.json").write_text(
        json.dumps(parsed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "tail_notes.txt").write_text(tail_notes, encoding="utf-8")
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / f"{args.output_prefix}.system.txt").write_text(system_prompt, encoding="utf-8")
    (output_dir / f"{args.output_prefix}.user.txt").write_text(user_prompt, encoding="utf-8")
    (output_dir / f"{args.output_prefix}.response.txt").write_text(response_text, encoding="utf-8")
    (output_dir / f"{args.output_prefix}.human_reference.md").write_text(
        build_human_reference_markdown(samples),
        encoding="utf-8",
    )
    (output_dir / f"{args.output_prefix}_full_compare.md").write_text(
        build_comparison_markdown(
            model=args.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_text=response_text,
            samples=samples,
            parsed_translations=parsed,
            response_tail_notes=tail_notes,
            metrics_rows=metrics_rows,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
