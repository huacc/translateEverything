from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pypandoc
from markitdown import MarkItDown


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO_ROOT / "\u6837\u672c"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
LANG_DIR_MAP = {
    "\u4e2d\u6587": "zh",
    "\u82f1\u6587": "en",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run MarkItDown conversion on repo sample PDFs."
    )
    parser.add_argument(
        "--sample",
        help="Convert only PDFs whose stem contains this value.",
    )
    parser.add_argument(
        "--lang",
        choices=["all", "zh", "en"],
        default="all",
        help="Filter by sample language bucket.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Stop after this many matching PDFs.",
    )
    parser.add_argument(
        "--docx",
        action="store_true",
        help="Also build a DOCX from the cleaned Markdown via pandoc.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Override the output directory.",
    )
    return parser.parse_args()


def clean_markdown(markdown_text: str) -> str:
    text = markdown_text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\f", "\n\n\\newpage\n\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def detect_language(pdf_path: Path) -> str:
    for part in pdf_path.parts:
        if part in LANG_DIR_MAP:
            return LANG_DIR_MAP[part]
    return "unknown"


def discover_pdf_files(samples_dir: Path) -> list[Path]:
    return sorted(path for path in samples_dir.rglob("*.pdf") if path.is_file())


def filter_pdf_files(
    files: list[Path], sample_filter: str | None, lang: str, limit: int | None
) -> list[Path]:
    filtered = files

    if sample_filter:
        sample_filter_lower = sample_filter.lower()
        filtered = [
            path for path in filtered if sample_filter_lower in path.stem.lower()
        ]

    if lang != "all":
        filtered = [path for path in filtered if detect_language(path) == lang]

    if limit is not None:
        filtered = filtered[:limit]

    return filtered


def convert_pdf(
    converter: MarkItDown, pdf_path: Path, output_root: Path, emit_docx: bool
) -> dict[str, object]:
    language = detect_language(pdf_path)
    doc_dir = output_root / "markitdown" / language / pdf_path.stem
    doc_dir.mkdir(parents=True, exist_ok=True)

    raw_md_path = doc_dir / "raw.md"
    cleaned_md_path = doc_dir / "cleaned.md"
    docx_path = doc_dir / f"{pdf_path.stem}_from_markdown.docx"

    result = converter.convert(str(pdf_path))
    raw_markdown = result.markdown
    cleaned_markdown = clean_markdown(raw_markdown)

    raw_md_path.write_text(raw_markdown, encoding="utf-8")
    cleaned_md_path.write_text(cleaned_markdown, encoding="utf-8")

    generated_docx = None
    if emit_docx:
        pypandoc.convert_file(
            str(cleaned_md_path),
            "docx",
            format="markdown+hard_line_breaks",
            outputfile=str(docx_path),
            extra_args=["--wrap=none"],
        )
        generated_docx = str(docx_path)

    return {
        "source_pdf": str(pdf_path),
        "language": language,
        "output_dir": str(doc_dir),
        "raw_md": str(raw_md_path),
        "cleaned_md": str(cleaned_md_path),
        "docx": generated_docx,
        "raw_markdown_chars": len(raw_markdown),
        "cleaned_markdown_chars": len(cleaned_markdown),
        "status": "ok",
    }


def main() -> None:
    args = parse_args()

    pdf_files = discover_pdf_files(SAMPLES_DIR)
    selected_files = filter_pdf_files(pdf_files, args.sample, args.lang, args.limit)

    if not selected_files:
        raise SystemExit("No matching sample PDFs were found.")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    converter = MarkItDown(enable_plugins=False)
    summary: list[dict[str, object]] = []

    for pdf_path in selected_files:
        try:
            record = convert_pdf(converter, pdf_path, args.output_dir, args.docx)
        except Exception as exc:
            record = {
                "source_pdf": str(pdf_path),
                "language": detect_language(pdf_path),
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }
        summary.append(record)
        print(json.dumps(record, ensure_ascii=False))

    summary_path = args.output_dir / "markitdown" / "summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"summary={summary_path}")


if __name__ == "__main__":
    main()
