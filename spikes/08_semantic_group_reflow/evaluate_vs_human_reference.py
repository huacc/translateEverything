from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import fitz


ROOT = Path(__file__).resolve().parents[2]
BLOCKS_JSONL = ROOT / "spikes" / "01_text_block_extraction" / "output" / "AIA_2021_Annual_Report_zh" / "blocks.jsonl"
REFERENCE_PDF = ROOT / "样本" / "英文" / "AIA_2021_Annual_Report_en.pdf"
V07_TRANSLATIONS = ROOT / "spikes" / "07_translation_current_bundle" / "outputs" / "first20_current" / "translations.json"
V08_TRANSLATIONS = ROOT / "spikes" / "08_semantic_group_reflow" / "output" / "focus_pages_10_13_19_20_run1" / "translations.json"
V08_REPORT = ROOT / "spikes" / "08_semantic_group_reflow" / "output" / "focus_pages_10_13_19_20_run1" / "report.json"
PAGES = [10, 13, 19, 20]

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have", "in", "is", "it",
    "its", "of", "on", "or", "that", "the", "their", "this", "to", "was", "were", "will", "with",
}


@dataclass
class PageMetrics:
    page_no: int
    token_f1: float
    content_f1: float
    sequence_ratio: float
    number_recall: float
    token_count_ref: int
    token_count_hyp: int


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_page_block_order(path: Path, pages: list[int]) -> dict[int, list[str]]:
    wanted = set(pages)
    result: dict[int, list[str]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            page_no = int(record["page_no"])
            if page_no not in wanted:
                continue
            block_ids = [block["block_id"] for block in sorted(record["blocks"], key=lambda item: item["reading_order"])]
            result[page_no] = block_ids
    return result


def load_reference_page_texts(path: Path, pages: list[int]) -> dict[int, str]:
    doc = fitz.open(path)
    result: dict[int, str] = {}
    for page_no in pages:
        words = doc[page_no - 1].get_text("words", sort=True)
        ordered = [str(item[4]) for item in words]
        result[page_no] = " ".join(ordered)
    return result


def normalize_text(text: str) -> str:
    cleaned = str(text)
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u00a0": " ",
    }
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    cleaned = cleaned.replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip().lower()


def tokenize(text: str) -> list[str]:
    normalized = normalize_text(text)
    return re.findall(r"[a-z]+(?:'[a-z]+)?|\d+(?:\.\d+)?%?|us\$|hk\$|\$", normalized)


def content_tokens(tokens: list[str]) -> list[str]:
    return [token for token in tokens if token not in STOPWORDS and not re.fullmatch(r"\d+(?:\.\d+)?%?", token)]


def number_tokens(tokens: list[str]) -> list[str]:
    return [token for token in tokens if re.fullmatch(r"\d+(?:\.\d+)?%?", token)]


def counter_f1(reference: list[str], hypothesis: list[str]) -> float:
    if not reference and not hypothesis:
        return 1.0
    if not reference or not hypothesis:
        return 0.0
    ref_counter = Counter(reference)
    hyp_counter = Counter(hypothesis)
    overlap = sum((ref_counter & hyp_counter).values())
    precision = overlap / max(1, sum(hyp_counter.values()))
    recall = overlap / max(1, sum(ref_counter.values()))
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def number_recall(reference: list[str], hypothesis: list[str]) -> float:
    ref_counter = Counter(reference)
    if not ref_counter:
        return 1.0
    hyp_counter = Counter(hypothesis)
    overlap = sum((ref_counter & hyp_counter).values())
    return overlap / max(1, sum(ref_counter.values()))


def sequence_ratio(reference: list[str], hypothesis: list[str]) -> float:
    return SequenceMatcher(a=reference, b=hypothesis).ratio()


def build_v07_page_texts(path: Path, pages: list[int], page_block_order: dict[int, list[str]]) -> dict[int, str]:
    payload = read_json(path)
    block_map: dict[str, str] = {}
    for item in payload:
        page_no = int(item["page_no"])
        if page_no not in page_block_order:
            continue
        block_map[str(item["block_id"])] = str(item.get("translation") or "")
    result: dict[int, str] = {}
    for page_no in pages:
        texts = [block_map.get(block_id, "") for block_id in page_block_order[page_no]]
        result[page_no] = "\n".join(text for text in texts if text.strip())
    return result


def build_v08_page_texts(path: Path, pages: list[int], page_block_order: dict[int, list[str]]) -> dict[int, str]:
    payload = read_json(path)
    page_block_texts: dict[int, dict[str, str]] = {page_no: {} for page_no in pages}
    for item in payload:
        page_no = int(item["page_no"])
        if page_no not in page_block_texts:
            continue
        for block_id, block_text in (item.get("block_outputs") or {}).items():
            page_block_texts[page_no][str(block_id)] = str(block_text or "")
    result: dict[int, str] = {}
    for page_no in pages:
        texts = [page_block_texts[page_no].get(block_id, "") for block_id in page_block_order[page_no]]
        result[page_no] = "\n".join(text for text in texts if text.strip())
    return result


def evaluate_pages(reference_texts: dict[int, str], candidate_texts: dict[int, str], pages: list[int]) -> list[PageMetrics]:
    results: list[PageMetrics] = []
    for page_no in pages:
        ref_tokens = tokenize(reference_texts[page_no])
        hyp_tokens = tokenize(candidate_texts[page_no])
        ref_content = content_tokens(ref_tokens)
        hyp_content = content_tokens(hyp_tokens)
        ref_numbers = number_tokens(ref_tokens)
        hyp_numbers = number_tokens(hyp_tokens)
        results.append(
            PageMetrics(
                page_no=page_no,
                token_f1=counter_f1(ref_tokens, hyp_tokens),
                content_f1=counter_f1(ref_content, hyp_content),
                sequence_ratio=sequence_ratio(ref_tokens, hyp_tokens),
                number_recall=number_recall(ref_numbers, hyp_numbers),
                token_count_ref=len(ref_tokens),
                token_count_hyp=len(hyp_tokens),
            )
        )
    return results


def round_metrics(metrics: PageMetrics) -> dict[str, Any]:
    return {
        "page_no": metrics.page_no,
        "token_f1": round(metrics.token_f1, 4),
        "content_f1": round(metrics.content_f1, 4),
        "sequence_ratio": round(metrics.sequence_ratio, 4),
        "number_recall": round(metrics.number_recall, 4),
        "token_count_ref": metrics.token_count_ref,
        "token_count_hyp": metrics.token_count_hyp,
    }


def average_metrics(metrics: list[PageMetrics]) -> dict[str, float]:
    count = max(1, len(metrics))
    return {
        "token_f1": round(sum(item.token_f1 for item in metrics) / count, 4),
        "content_f1": round(sum(item.content_f1 for item in metrics) / count, 4),
        "sequence_ratio": round(sum(item.sequence_ratio for item in metrics) / count, 4),
        "number_recall": round(sum(item.number_recall for item in metrics) / count, 4),
    }


def load_v08_layout_summary(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    pages = payload.get("pages", [])
    summary: dict[int, dict[str, Any]] = {}
    for page in pages:
        page_no = int(page["page_no"])
        reports = page.get("reports", [])
        if not reports:
            continue
        summary[page_no] = {
            "avg_font_ratio": round(sum(float(item["font_ratio"]) for item in reports) / len(reports), 4),
            "ok_or_shrink": len(reports),
            "unit_count": len(reports),
            "compact_used": sum(1 for item in reports if item.get("compact_used")),
        }
    return summary


def main() -> None:
    page_block_order = load_page_block_order(BLOCKS_JSONL, PAGES)
    reference_texts = load_reference_page_texts(REFERENCE_PDF, PAGES)
    v07_texts = build_v07_page_texts(V07_TRANSLATIONS, PAGES, page_block_order)
    v08_texts = build_v08_page_texts(V08_TRANSLATIONS, PAGES, page_block_order)

    v07_metrics = evaluate_pages(reference_texts, v07_texts, PAGES)
    v08_metrics = evaluate_pages(reference_texts, v08_texts, PAGES)
    v08_layout = load_v08_layout_summary(V08_REPORT)

    output = {
        "pages": PAGES,
        "v07_vs_human": {
            "average": average_metrics(v07_metrics),
            "per_page": [round_metrics(item) for item in v07_metrics],
        },
        "v08_vs_human": {
            "average": average_metrics(v08_metrics),
            "per_page": [round_metrics(item) for item in v08_metrics],
        },
        "delta_v08_minus_v07": {
            "token_f1": round(sum(item.token_f1 for item in v08_metrics) / len(v08_metrics) - sum(item.token_f1 for item in v07_metrics) / len(v07_metrics), 4),
            "content_f1": round(sum(item.content_f1 for item in v08_metrics) / len(v08_metrics) - sum(item.content_f1 for item in v07_metrics) / len(v07_metrics), 4),
            "sequence_ratio": round(sum(item.sequence_ratio for item in v08_metrics) / len(v08_metrics) - sum(item.sequence_ratio for item in v07_metrics) / len(v07_metrics), 4),
            "number_recall": round(sum(item.number_recall for item in v08_metrics) / len(v08_metrics) - sum(item.number_recall for item in v07_metrics) / len(v07_metrics), 4),
        },
        "v08_layout_proxy": v08_layout,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
