from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate glossary candidates from repeated PDF blocks.")
    parser.add_argument("--blocks-jsonl", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-text-length", type=int, default=40)
    parser.add_argument("--min-count", type=int, default=3)
    parser.add_argument("--top-k", type=int, default=200)
    return parser.parse_args()


def normalize_text(text: str) -> str:
    lines = [" ".join(line.split()) for line in str(text).splitlines()]
    return "\n".join(line for line in lines if line).strip()


def main() -> None:
    args = parse_args()
    block_counter: Counter[str] = Counter()
    line_counter: Counter[str] = Counter()
    block_pages: dict[str, list[int]] = defaultdict(list)
    line_pages: dict[str, list[int]] = defaultdict(list)

    with args.blocks_jsonl.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            record = json.loads(raw_line)
            page_no = int(record["page_no"])
            for block in record["blocks"]:
                text = normalize_text(block.get("source_text", ""))
                if not text:
                    continue
                if len(text) <= args.max_text_length:
                    block_counter[text] += 1
                    if page_no not in block_pages[text]:
                        block_pages[text].append(page_no)
                for line in text.splitlines():
                    line = normalize_text(line)
                    if not line or len(line) > args.max_text_length:
                        continue
                    line_counter[line] += 1
                    if page_no not in line_pages[line]:
                        line_pages[line].append(page_no)

    exact_candidates = [
        {
            "source_text": text,
            "count": count,
            "page_samples": block_pages[text][:10],
        }
        for text, count in block_counter.most_common(args.top_k)
        if count >= args.min_count
    ]
    line_candidates = [
        {
            "source_text": text,
            "count": count,
            "page_samples": line_pages[text][:10],
        }
        for text, count in line_counter.most_common(args.top_k)
        if count >= args.min_count
    ]

    payload = {
        "schema_id": "glossary_candidates_v1",
        "source": str(args.blocks_jsonl),
        "max_text_length": args.max_text_length,
        "min_count": args.min_count,
        "exact_candidates": exact_candidates,
        "line_candidates": line_candidates,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"candidates={args.output}")
    print(f"exact_candidates={len(exact_candidates)}")
    print(f"line_candidates={len(line_candidates)}")


if __name__ == "__main__":
    main()
