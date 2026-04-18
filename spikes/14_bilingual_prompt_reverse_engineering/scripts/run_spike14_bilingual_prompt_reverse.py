from __future__ import annotations

import argparse
import base64
import json
import os
import time
from pathlib import Path
from typing import Any

import fitz
import requests


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ZH_PDF = ROOT / "样本" / "中文" / "AIA_2021_Annual_Report_zh.pdf"
DEFAULT_EN_PDF = ROOT / "样本" / "英文" / "AIA_2021_Annual_Report_en.pdf"
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "spikes"
    / "14_bilingual_prompt_reverse_engineering"
    / "output"
    / "aia_2021_prompt_consultation_first20"
)
DEFAULT_PROMPT_EXPORTS = (
    ROOT
    / "spikes"
    / "13_lane_separated_render"
    / "output"
    / "first20_opus46_adaptive_v2_promptclean_r2"
    / "prompt_exports"
)
DEFAULT_MODEL = "claude-opus-4-6"
DEFAULT_FOCUS_PAGES = "1-20"
DEFAULT_SAMPLE_PAGES = [2, 3, 10, 14, 17, 19, 20]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Spike 14: extract bilingual PDF text and ask Claude how to redesign prompts against human reference."
    )
    parser.add_argument("--zh-pdf", type=Path, default=DEFAULT_ZH_PDF)
    parser.add_argument("--en-pdf", type=Path, default=DEFAULT_EN_PDF)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--prompt-exports-dir", type=Path, default=DEFAULT_PROMPT_EXPORTS)
    parser.add_argument("--focus-pages", default=DEFAULT_FOCUS_PAGES)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-output-tokens", type=int, default=4096)
    parser.add_argument("--thinking-mode", choices=["none", "adaptive"], default="adaptive")
    parser.add_argument("--material-mode", choices=["sampled", "full_text"], default="sampled")
    parser.add_argument("--consult-input-mode", choices=["auto", "text_only"], default="auto")
    parser.add_argument("--full-text-scope", choices=["both", "zh_only", "en_only"], default="both")
    return parser.parse_args()


def parse_pages(spec: str) -> list[int]:
    values: list[int] = []
    for part in str(spec).split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            step = 1 if end >= start else -1
            values.extend(range(start, end + step, step))
        else:
            values.append(int(token))
    deduped: list[int] = []
    seen: set[int] = set()
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped


def clean_page_text(text: str) -> str:
    lines = []
    for raw_line in str(text or "").splitlines():
        line = " ".join(raw_line.strip().split())
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def extract_pdf_text(pdf_path: Path) -> dict[str, Any]:
    document = fitz.open(pdf_path)
    pages: list[dict[str, Any]] = []
    full_parts: list[str] = []
    for page_index in range(document.page_count):
        page = document.load_page(page_index)
        text = clean_page_text(page.get_text("text", sort=True))
        record = {
            "page_no": page_index + 1,
            "char_count": len(text),
            "line_count": len([line for line in text.splitlines() if line.strip()]),
            "text": text,
        }
        pages.append(record)
        if text:
            full_parts.append(f"[Page {page_index + 1}]\n{text}")
    document.close()
    return {
        "source_pdf": str(pdf_path),
        "page_count": len(pages),
        "pages": pages,
        "full_text": "\n\n".join(full_parts).strip(),
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_subset_pdf(source_pdf: Path, pages: list[int], output_pdf: Path) -> None:
    source_doc = fitz.open(source_pdf)
    subset_doc = fitz.open()
    for page_no in pages:
        subset_doc.insert_pdf(source_doc, from_page=page_no - 1, to_page=page_no - 1)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    subset_doc.save(output_pdf)
    subset_doc.close()
    source_doc.close()


def clip_text(text: str, limit: int = 1200) -> str:
    cleaned = clean_page_text(text)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "..."


def find_prompt_examples(prompt_dir: Path) -> dict[str, dict[str, str]]:
    user_files = sorted(prompt_dir.glob("*_translation.user.txt"))
    if not user_files:
        raise FileNotFoundError(f"No translation prompt exports found in {prompt_dir}")

    def load_pair(user_file: Path) -> dict[str, str]:
        system_file = user_file.with_name(user_file.name.replace(".user.txt", ".system.txt"))
        return {
            "user_path": str(user_file),
            "system_path": str(system_file),
            "user_text": user_file.read_text(encoding="utf-8"),
            "system_text": system_file.read_text(encoding="utf-8") if system_file.exists() else "",
        }

    examples: dict[str, dict[str, str]] = {}
    for user_file in user_files:
        text = user_file.read_text(encoding="utf-8")
        if "当前输入单元：短标签 / 小标题" in text and "label" not in examples:
            examples["label"] = load_pair(user_file)
        elif "当前输入单元：正文语义组（group）" in text and "body" not in examples:
            examples["body"] = load_pair(user_file)
        elif "当前输入单元：表格单元 / 表格行" in text and "table" not in examples:
            examples["table"] = load_pair(user_file)
        if {"label", "body", "table"} <= set(examples):
            break
    return examples


def build_prompt_examples_md(examples: dict[str, dict[str, str]]) -> str:
    sections = ["# 当前提示词样例", ""]
    title_map = {"label": "标签", "body": "正文", "table": "表格"}
    for key in ["label", "body", "table"]:
        if key not in examples:
            continue
        item = examples[key]
        sections.extend(
            [
                f"## {title_map[key]} Prompt",
                "",
                f"- user: `{item['user_path']}`",
                f"- system: `{item['system_path']}`",
                "",
                "### System",
                "",
                "```text",
                item["system_text"].strip(),
                "```",
                "",
                "### User",
                "",
                "```text",
                item["user_text"].strip(),
                "```",
                "",
            ]
        )
    return "\n".join(sections).strip() + "\n"


def build_sampled_bilingual_material_md(
    zh_extract: dict[str, Any],
    en_extract: dict[str, Any],
    examples: dict[str, dict[str, str]],
    focus_pages: list[int],
) -> str:
    zh_pages = {item["page_no"]: item for item in zh_extract["pages"]}
    en_pages = {item["page_no"]: item for item in en_extract["pages"]}
    sections = [
        "# 双语 PDF 咨询材料",
        "",
        "## 任务目标",
        "",
        "- 当前系统正在做上市公司年报 PDF 的中文到英文翻译与高保真回填。",
        "- 我们已经有一版人工英文 PDF，可视为“目标风格与目标表达”的强参考。",
        "- 这次不是让模型直接翻译，而是让模型反向分析：提示词应该如何设计，才能更接近人工译文效果。",
        "",
        "## 当前已知问题",
        "",
        "- 当前很多 prompt 仍然混入了对翻译本身无贡献的信息，例如页码范围、章节类型标签、过长的邻近摘要。",
        "- 标签类 prompt 经常上下文过重，正文类 prompt 的上下文也有明显噪声。",
        "- 我们希望把“真正应由模型处理的内容”和“应由工程层处理的约束”分开。",
        "",
        "## 当前 Prompt 样例摘要",
        "",
    ]
    for key in ["label", "body", "table"]:
        if key not in examples:
            continue
        item = examples[key]
        sections.extend(
            [
                f"### {key}",
                "",
                "#### system",
                "",
                "```text",
                item["system_text"].strip(),
                "```",
                "",
                "#### user",
                "",
                "```text",
                clip_text(item["user_text"], 1600),
                "```",
                "",
            ]
        )

    sections.extend(["## 双语页样本", ""])
    for page_no in focus_pages:
        zh_text = zh_pages.get(page_no, {}).get("text", "")
        en_text = en_pages.get(page_no, {}).get("text", "")
        sections.extend(
            [
                f"### Page {page_no}",
                "",
                "#### 中文原文摘录",
                "",
                "```text",
                clip_text(zh_text, 1600),
                "```",
                "",
                "#### 人工英文摘录",
                "",
                "```text",
                clip_text(en_text, 1600),
                "```",
                "",
            ]
        )
    return "\n".join(sections).strip() + "\n"


def build_full_bilingual_material_md(
    zh_extract: dict[str, Any],
    en_extract: dict[str, Any],
    full_text_scope: str,
    focus_pages: list[int],
) -> str:
    sections = [
        "# 双语 PDF 全文咨询材料",
        "",
        "## 任务目标",
        "",
        "- 当前系统正在做上市公司年报 PDF 的中文到英文翻译与高保真回填。",
        "- 已有人工英文 PDF，可视为目标表达与目标文风。",
        "- 现在提供中英文两版全文抽取文本，请基于全文内容反向分析提示词设计。",
        "",
        "## 当前已知问题",
        "",
        "- 当前 prompt 混入了不少对翻译本身无贡献的字段。",
        "- 我们希望区分：哪些信息应放在 prompt 中，哪些应下沉到工程层。",
        "- 我们希望输出 lane 级别的最小 prompt 模板，而不是继续堆上下文。",
        "",
    ]
    if full_text_scope in {"both", "zh_only"}:
        sections.extend(
            [
                "## 中文原版全文抽取",
                "",
                "```text",
                zh_extract["full_text"].strip(),
                "```",
                "",
            ]
        )
    else:
        zh_pages = {item["page_no"]: item for item in zh_extract["pages"]}
        sections.extend(["## 中文原版关键页样本", ""])
        for page_no in [page for page in DEFAULT_SAMPLE_PAGES if page in focus_pages]:
            sections.extend(
                [
                    f"### Page {page_no}",
                    "",
                    "```text",
                    clip_text(zh_pages.get(page_no, {}).get("text", ""), 1600),
                    "```",
                    "",
                ]
            )
    if full_text_scope in {"both", "en_only"}:
        sections.extend(
            [
                "## 人工英文全文抽取",
                "",
                "```text",
                en_extract["full_text"].strip(),
                "```",
                "",
            ]
        )
    else:
        en_pages = {item["page_no"]: item for item in en_extract["pages"]}
        sections.extend(["## 人工英文关键页样本", ""])
        for page_no in [page for page in DEFAULT_SAMPLE_PAGES if page in focus_pages]:
            sections.extend(
                [
                    f"### Page {page_no}",
                    "",
                    "```text",
                    clip_text(en_pages.get(page_no, {}).get("text", ""), 1600),
                    "```",
                    "",
                ]
            )
    return "\n".join(sections).strip() + "\n"


def build_consult_system_prompt() -> str:
    return "\n".join(
        [
            "你是企业年报翻译系统的提示词架构顾问。",
            "你需要同时理解中文原版 PDF、人工英文 PDF、以及当前系统提示词样例。",
            "你的任务不是翻译当前文档，而是反向分析：怎样设计提示词，才能更接近人工英文版的表达、术语和文风。",
            "请用中文回答。",
            "请输出结构化 Markdown，避免空泛建议。",
        ]
    )


def build_consult_user_prompt(focus_pages: list[int], prompt_examples_md: str, material_md: str) -> str:
    page_list = ", ".join(str(page) for page in focus_pages)
    return "\n".join(
        [
            "# 咨询目标",
            "",
            f"- 当前重点评估页：{page_list}",
            "- 我们已经有中文原版 PDF、人工英文 PDF、以及当前系统正在使用的 prompt 样例。",
            "- 请你根据这些材料，反向分析怎样构建更有效的提示词，而不是直接翻译文档。",
            "",
            "# 请重点回答",
            "",
            "1. 当前 prompt 中，哪些字段对翻译准确性和风格控制几乎没有帮助，应该删除。",
            "2. 当前 prompt 中，哪些字段应该保留，但要缩短或改写。",
            "3. 哪些约束本质上不该放在 prompt 中，而应该由工程层处理。",
            "4. 请基于人工英文 PDF 的风格，提炼一套全局翻译风格规则。",
            "5. 请分别给出标签、正文、表格三类 lane 的最小有效 prompt 模板。",
            "6. 请明确指出：哪些信息应该是全局必带，哪些应该是 lane 必带，哪些应该是按需局部注入。",
            "7. 如果需要增加文档级预处理步骤，请给出最小可行 workflow。",
            "",
            "# 输出要求",
            "",
            "- 用中文输出。",
            "- 先给结论，再给模板。",
            "- 每个模板尽量短，不要继续堆无用上下文。",
            "- 模板输入主体请使用 Markdown 风格文本，不要把内部 JSON 结构直接塞给模型。",
            "",
            "# 当前 Prompt 样例",
            "",
            prompt_examples_md.strip(),
            "",
            "# 双语材料",
            "",
            material_md.strip(),
        ]
    )


def build_pdf_document_item(pdf_path: Path) -> dict[str, Any]:
    return {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": base64.b64encode(pdf_path.read_bytes()).decode("ascii"),
        },
    }


def extract_response_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in payload.get("content", []):
        if item.get("type") == "text" and item.get("text"):
            parts.append(str(item["text"]))
    return "\n".join(parts).strip()


def post_messages(
    model: str,
    max_output_tokens: int,
    thinking_mode: str,
    system_prompt: str,
    user_prompt: str,
    document_items: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not base_url or not api_key:
        raise RuntimeError("Missing ANTHROPIC_BASE_URL or ANTHROPIC_AUTH_TOKEN in the environment.")

    content: list[dict[str, Any] | str]
    if document_items:
        content = [*document_items, {"type": "text", "text": user_prompt}]
    else:
        content = user_prompt

    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_output_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": content}],
    }
    if thinking_mode == "adaptive":
        payload["thinking"] = {"type": "adaptive"}
        payload["output_config"] = {"effort": "max"}
    else:
        payload["temperature"] = 0

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = requests.post(f"{base_url}/v1/messages", headers=headers, json=payload, timeout=600)
            if response.status_code >= 500 or response.status_code == 429:
                response.raise_for_status()
            response.raise_for_status()
            return payload, response.json()
        except requests.exceptions.HTTPError as exc:
            last_error = exc
            status_code = exc.response.status_code if exc.response is not None else 0
            if status_code in {429, 500, 502, 503, 504} and attempt < 3:
                time.sleep(5 * attempt)
                continue
            raise
        except requests.RequestException as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(5 * attempt)
                continue
            raise
    if last_error is not None:
        raise last_error
    raise RuntimeError("Unexpected request failure without captured exception.")


def save_api_log(path: Path, meta: dict[str, Any], request_payload: dict[str, Any], response_payload: dict[str, Any]) -> None:
    write_json(
        path,
        {
            "meta": meta,
            "request": request_payload,
            "response": response_payload,
        },
    )


def save_error_log(path: Path, meta: dict[str, Any], request_payload: dict[str, Any], error_text: str) -> None:
    write_json(
        path,
        {
            "meta": meta,
            "request": request_payload,
            "error": error_text,
        },
    )


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    extracted_dir = output_dir / "extracted"
    consult_dir = output_dir / "consultation"
    api_logs_dir = consult_dir / "api_logs"
    focus_pages = parse_pages(args.focus_pages)

    zh_extract = extract_pdf_text(args.zh_pdf.resolve())
    en_extract = extract_pdf_text(args.en_pdf.resolve())
    write_json(extracted_dir / "zh_pages.json", zh_extract["pages"])
    write_json(extracted_dir / "en_pages.json", en_extract["pages"])
    write_text(extracted_dir / "zh_full.txt", zh_extract["full_text"])
    write_text(extracted_dir / "en_full.txt", en_extract["full_text"])
    write_json(
        extracted_dir / "extraction_summary.json",
        {
            "zh_pdf": str(args.zh_pdf.resolve()),
            "en_pdf": str(args.en_pdf.resolve()),
            "zh_page_count": zh_extract["page_count"],
            "en_page_count": en_extract["page_count"],
            "focus_pages": focus_pages,
        },
    )

    zh_subset_pdf = consult_dir / "zh_first20.pdf"
    en_subset_pdf = consult_dir / "en_first20.pdf"
    build_subset_pdf(args.zh_pdf.resolve(), focus_pages, zh_subset_pdf)
    build_subset_pdf(args.en_pdf.resolve(), focus_pages, en_subset_pdf)

    examples = find_prompt_examples(args.prompt_exports_dir.resolve())
    prompt_examples_md = build_prompt_examples_md(examples)
    write_text(consult_dir / "current_prompt_examples.md", prompt_examples_md)

    if args.material_mode == "full_text":
        bilingual_material_md = build_full_bilingual_material_md(
            zh_extract=zh_extract,
            en_extract=en_extract,
            full_text_scope=args.full_text_scope,
            focus_pages=focus_pages,
        )
    else:
        bilingual_material_md = build_sampled_bilingual_material_md(
            zh_extract=zh_extract,
            en_extract=en_extract,
            examples=examples,
            focus_pages=[page for page in DEFAULT_SAMPLE_PAGES if page in focus_pages],
        )
    write_text(consult_dir / "bilingual_consultation_material.md", bilingual_material_md)

    system_prompt = build_consult_system_prompt()
    user_prompt = build_consult_user_prompt(focus_pages, prompt_examples_md, bilingual_material_md)
    write_text(consult_dir / "consult_system_prompt.txt", system_prompt)
    write_text(consult_dir / "consult_user_prompt.txt", user_prompt)

    response_payload: dict[str, Any] | None = None
    used_mode = "text_only" if args.consult_input_mode == "text_only" else "pdf_documents"

    if args.consult_input_mode == "text_only":
        text_request_payload, response_payload = post_messages(
            model=args.model,
            max_output_tokens=args.max_output_tokens,
            thinking_mode=args.thinking_mode,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            document_items=None,
        )
        save_api_log(
            api_logs_dir / "consult_text_only.json",
            {
                "mode": "text_only",
                "focus_pages": focus_pages,
                "material_mode": args.material_mode,
            },
            text_request_payload,
            response_payload,
        )
    else:
        pdf_request_payload: dict[str, Any] | None = None
        try:
            pdf_request_payload, response_payload = post_messages(
                model=args.model,
                max_output_tokens=args.max_output_tokens,
                thinking_mode=args.thinking_mode,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                document_items=[build_pdf_document_item(zh_subset_pdf), build_pdf_document_item(en_subset_pdf)],
            )
            save_api_log(
                api_logs_dir / "consult_with_pdf.json",
                {
                    "mode": "pdf_documents",
                    "focus_pages": focus_pages,
                    "zh_subset_pdf": str(zh_subset_pdf),
                    "en_subset_pdf": str(en_subset_pdf),
                    "material_mode": args.material_mode,
                },
                pdf_request_payload,
                response_payload,
            )
        except Exception as exc:
            if pdf_request_payload is not None:
                save_error_log(
                    api_logs_dir / "consult_with_pdf_error.json",
                    {
                        "mode": "pdf_documents",
                        "focus_pages": focus_pages,
                        "material_mode": args.material_mode,
                    },
                    pdf_request_payload,
                    repr(exc),
                )
            used_mode = "text_fallback"
            text_request_payload, response_payload = post_messages(
                model=args.model,
                max_output_tokens=args.max_output_tokens,
                thinking_mode=args.thinking_mode,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                document_items=None,
            )
            save_api_log(
                api_logs_dir / "consult_text_fallback.json",
                {
                    "mode": "text_fallback",
                    "focus_pages": focus_pages,
                    "reason": "pdf_document_request_failed",
                    "material_mode": args.material_mode,
                },
                text_request_payload,
                response_payload,
            )

    response_text = extract_response_text(response_payload or {})
    write_text(consult_dir / "claude_prompt_advice.md", response_text)
    write_json(
        consult_dir / "consultation_summary.json",
        {
            "mode_used": used_mode,
            "model": args.model,
            "focus_pages": focus_pages,
            "material_mode": args.material_mode,
            "full_text_scope": args.full_text_scope,
            "zh_subset_pdf": str(zh_subset_pdf),
            "en_subset_pdf": str(en_subset_pdf),
            "response_text_path": str((consult_dir / "claude_prompt_advice.md").resolve()),
        },
    )


if __name__ == "__main__":
    main()
