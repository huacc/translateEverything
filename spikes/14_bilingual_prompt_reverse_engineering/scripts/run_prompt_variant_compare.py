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
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "spikes"
    / "14_bilingual_prompt_reverse_engineering"
    / "output"
    / "prompt_variant_compare_v2_promptlogs"
)
DEFAULT_MODEL = os.environ.get("PROMPT_COMPARE_MODEL") or os.environ.get("ANTHROPIC_MODEL") or "claude-opus-4-6"


@dataclass
class Sample:
    sample_id: str
    page_no: int
    section: str
    source_text: str
    human_reference: str


PROMPT_BASELINE = """你是上市保险公司年报正文翻译助手。
语言方向：中文 -> 英文。
场景：港股/国际资本市场保险公司正式年报。

要求：
1. 只做翻译，不做解释，不做总结，不做改写性发挥。
2. 忠实保留原文信息、语气和段落顺序，不增、不漏、不擅自润色。
3. 数字、货币、百分比、年份、专有名词、公司名、人名、地名必须准确。
4. 优先使用标准保险、金融、精算、治理相关术语。
5. 译文风格必须正式、稳定、可出版，符合上市公司英文年报语气。

输出规则：
- 只输出最终英文译文。
- 保持原段落结构。"""


PROMPT_A = """你现在是国际顶级上市保险公司年报中英翻译专家，拥有超过15年将中文正式财报翻译成标准英文年报的经验，翻译水平达到香港联交所上市规则和国际财务报告准则（IFRS）的专业要求。

你的翻译必须同时满足以下标准：
1. 术语高度一致、专业准确。所有金融、保险、精算、监管术语必须优先使用国际资本市场通用的标准英文表达。
2. 风格正式、严谨、专业。采用香港/国际上市公司年报的典型英文风格，客观、中性、简洁、权威。
3. 绝对忠实原文。严格忠实于中文原意，不增加、不省略、不解释、不自由改写。
4. 格式与呈现稳定。保留原文段落结构、标题语气、数据和逻辑顺序。

输出规则：
- 只输出翻译后的英文文本。
- 不要添加任何解释、前言、说明或引号。
- 直接开始输出译文。"""


PROMPT_B = """# Role: 全球顶级金融与保险行业专业翻译官

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


PROMPT_C = """你是上市保险公司年报翻译助手，负责将中文年报正文翻译成正式英文年报文本。
语言方向：中文 -> 英文。
文体场景：港股/国际上市保险公司年度报告。

请严格遵守以下要求：
1. 先保真，再表达。只做翻译，不解释，不总结，不额外润色。
2. 忠实保留原文事实、逻辑、语气和段落顺序，不增、不漏、不自由改写。
3. 金融、保险、精算、监管、公司治理相关内容优先使用国际资本市场通用术语。
4. 数字、百分比、货币、年份、公司名、人名、地名、专有名词必须准确。
5. 英文风格要正式、稳健、可出版，贴近上市公司英文年报，而不是口语化商务文案。
6. 如原文术语存在行业固定译法，优先采用固定译法；如无把握，使用保守直译，不自行发挥。

输出规则：
- 只输出最终英文译文。
- 保持原段落结构与信息顺序。
- 不输出任何说明、标题或注释。"""


USER_PROMPT_TEMPLATE = """现在，请直接翻译以下中文年报段落。

要求：
1. 只输出英文译文。
2. 不要解释，不要补充背景。
3. 保持原段落顺序。

中文原文：

{source_text}
"""


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9$%.,'-]+", text.lower())


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


def load_samples() -> list[Sample]:
    payload = json.loads(TRANSLATIONS_JSON.read_text(encoding="utf-8"))
    by_id = {item["unit_id"]: item for item in payload}
    return [
        Sample(
            sample_id="p10_g01",
            page_no=10,
            section="Chairman's Statement",
            source_text=by_id["p10_g01"]["source_text"],
            human_reference=(
                "Throughout AIA's long history in the region we have managed our businesses through many periods "
                "of change and uncertainty, earning our company a reputation which is synonymous with trust, "
                "resilience and doing the right thing for our stakeholders. From early 2020, the COVID-19 "
                "pandemic presented an ever-changing and complex operating environment and we witnessed "
                "unprecedented shifts in politics, macroeconomics and capital markets. AIA's financial strength "
                "and Purpose of 'helping people live Healthier, Longer, Better Lives' has never been more relevant. "
                "I am immensely grateful to all of our employees, agents and partners for their care and dedication, "
                "remaining steadfast in supporting our customers, their families, and our communities, through this "
                "most challenging time."
            ),
        ),
        Sample(
            sample_id="p11_g04",
            page_no=11,
            section="Chairman's Statement",
            source_text=by_id["p11_g04"]["source_text"],
            human_reference=(
                "The global impacts of Environmental, Social and Governance (ESG) issues continue to be of great "
                "significance. We remain committed to playing our part in the transition to a brighter future and "
                "our ESG efforts have been recognised again in 2020. The rating agency, Sustainalytics, ranked AIA "
                "second in our industry out of more than 270 peers, noting the strength and quality of our corporate "
                "governance. Additionally, our ESG Corporate Rating score from Institutional Shareholder Services "
                "Inc. (ISS) remains 'Prime', placing us among the best in our industry for our sustainability "
                "performance. AIA recognises that there is much more we can do in this area to achieve better "
                "outcomes for our communities and it remains a personal priority that I share with my Board "
                "colleagues, our senior management team and all our employees."
            ),
        ),
        Sample(
            sample_id="p19_g04",
            page_no=19,
            section="Group Chief Financial Officer's Review",
            source_text=by_id["p19_g04"]["source_text"],
            human_reference=(
                "Our high-quality, recurring earnings sources and active management of our in-force portfolio drove "
                "OPAT growth of 5 per cent to US$5,942 million, while maintaining an operating margin of 16.9 per "
                "cent. Renewal premiums received increased by 10 per cent, and total recurring premiums accounted "
                "for over 90 per cent of premiums received in 2020. OPAT growth was supported by significant "
                "positive claims experience throughout the year, which offset the effect of lower yields on new fixed "
                "income investments and lower assumed long-term returns on equity investments. As anticipated, the "
                "exceptional positive medical claims experience highlighted in the first half was not repeated in the "
                "second half, however we continued to see a positive contribution to OPAT growth from this source. "
                "Persistency improved in the second half, supported by a normalisation of lapse experience for AIA "
                "Thailand, and has remained at 95 per cent for the Group."
            ),
        ),
    ]


def call_model(model: str, system_prompt: str, user_prompt: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not base_url or not api_key:
        raise RuntimeError("Missing ANTHROPIC_BASE_URL or ANTHROPIC_AUTH_TOKEN.")

    payload = {
        "model": model,
        "max_tokens": 1800,
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


def write_prompt_logs(
    prompt_dir: Path,
    sample: Sample,
    variant_name: str,
    system_prompt: str,
    user_prompt: str,
    request_payload: dict[str, Any],
) -> None:
    base_name = f"{sample.sample_id}_{variant_name}"
    (prompt_dir / f"{base_name}.system.txt").write_text(system_prompt, encoding="utf-8")
    (prompt_dir / f"{base_name}.user.txt").write_text(user_prompt, encoding="utf-8")
    (prompt_dir / f"{base_name}.payload.json").write_text(
        json.dumps(request_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    combined = "\n".join(
        [
            f"# {base_name}",
            "",
            "## system",
            "",
            "```text",
            system_prompt,
            "```",
            "",
            "## user",
            "",
            "```text",
            user_prompt,
            "```",
            "",
        ]
    )
    (prompt_dir / f"{base_name}.combined.md").write_text(combined, encoding="utf-8")


def build_report(
    output_dir: Path,
    model: str,
    samples: list[Sample],
    variants: dict[str, str],
    results: list[dict[str, Any]],
) -> None:
    averages: list[dict[str, Any]] = []
    lines = [
        "# Prompt Variant Compare v2",
        "",
        f"- model: `{model}`",
        f"- samples: `{len(samples)}`",
        f"- variants: `{', '.join(variants.keys())}`",
        f"- prompt logs: [{(output_dir / 'prompt_exports').as_posix()}]({(output_dir / 'prompt_exports').as_posix()})",
        "",
    ]

    for sample in samples:
        lines.extend(
            [
                f"## {sample.sample_id} | page {sample.page_no} | {sample.section}",
                "",
                "### 中文原文",
                "",
                "```text",
                sample.source_text,
                "```",
                "",
                "### 人工英文参考",
                "",
                sample.human_reference,
                "",
            ]
        )
        sample_rows = [row for row in results if row["sample_id"] == sample.sample_id]
        sample_rows.sort(key=lambda row: row["variant"])
        best_token = max(sample_rows, key=lambda row: row["token_f1"])
        best_seq = max(sample_rows, key=lambda row: row["sequence_ratio"])
        lines.extend(
            [
                f"- best_token_f1: `{best_token['variant']}` = {best_token['token_f1']}",
                f"- best_sequence_ratio: `{best_seq['variant']}` = {best_seq['sequence_ratio']}",
                "",
            ]
        )
        for row in sample_rows:
            lines.extend(
                [
                    f"### {row['variant']}",
                    "",
                    f"- token_f1: {row['token_f1']}",
                    f"- sequence_ratio: {row['sequence_ratio']}",
                    f"- prompt log: [{row['prompt_log_base_name']}]({(output_dir / 'prompt_exports' / (row['prompt_log_base_name'] + '.combined.md')).as_posix()})",
                    "",
                    row["translation"],
                    "",
                ]
            )

    for variant_name in variants:
        rows = [row for row in results if row["variant"] == variant_name]
        avg_token_f1 = round(sum(row["token_f1"] for row in rows) / len(rows), 4)
        avg_sequence = round(sum(row["sequence_ratio"] for row in rows) / len(rows), 4)
        averages.append(
            {
                "variant": variant_name,
                "avg_token_f1": avg_token_f1,
                "avg_sequence_ratio": avg_sequence,
            }
        )

    averages.sort(key=lambda item: (-item["avg_token_f1"], -item["avg_sequence_ratio"]))
    (output_dir / "averages.json").write_text(
        json.dumps(averages, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines.extend(["## Averages", ""])
    for item in averages:
        lines.append(
            f"- {item['variant']}: avg_token_f1={item['avg_token_f1']}, avg_sequence_ratio={item['avg_sequence_ratio']}"
        )
    lines.append("")
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory to write comparison outputs.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Anthropic model id.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    prompt_dir = output_dir / "prompt_exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    prompt_dir.mkdir(parents=True, exist_ok=True)

    samples = load_samples()
    variants = {
        "baseline": PROMPT_BASELINE,
        "prompt_a": PROMPT_A,
        "prompt_b": PROMPT_B,
        "prompt_c": PROMPT_C,
    }

    (output_dir / "variant_prompts.json").write_text(
        json.dumps(variants, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    results: list[dict[str, Any]] = []
    for sample in samples:
        for variant_name, system_prompt in variants.items():
            user_prompt = USER_PROMPT_TEMPLATE.format(source_text=sample.source_text)
            request_payload, response_payload, translation = call_model(args.model, system_prompt, user_prompt)
            write_prompt_logs(prompt_dir, sample, variant_name, system_prompt, user_prompt, request_payload)
            record = {
                "sample_id": sample.sample_id,
                "page_no": sample.page_no,
                "section": sample.section,
                "variant": variant_name,
                "source_text": sample.source_text,
                "human_reference": sample.human_reference,
                "translation": translation,
                "sequence_ratio": round(sequence_ratio(sample.human_reference, translation), 4),
                "token_f1": round(token_f1(sample.human_reference, translation), 4),
                "prompt_log_base_name": f"{sample.sample_id}_{variant_name}",
                "request": request_payload,
                "response": response_payload,
            }
            results.append(record)
            (output_dir / f"{sample.sample_id}_{variant_name}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    (output_dir / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    build_report(output_dir, args.model, samples, variants, results)


if __name__ == "__main__":
    main()
