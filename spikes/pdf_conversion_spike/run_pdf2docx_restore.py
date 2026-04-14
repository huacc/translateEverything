from __future__ import annotations

import argparse
import json
from pathlib import Path

from pdf2docx import Converter


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO_ROOT / "\u6837\u672c"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
LANG_DIR_MAP = {
    "\u4e2d\u6587": "zh",
    "\u82f1\u6587": "en",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Restore sample PDFs to DOCX with pdf2docx."
    )
    parser.add_argument("--sample", help="Convert only PDFs whose stem contains this value.")
    parser.add_argument(
        "--lang",
        choices=["all", "zh", "en"],
        default="all",
        help="Filter by sample language bucket.",
    )
    parser.add_argument("--limit", type=int, help="Stop after this many matching PDFs.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Override the output directory.",
    )
    return parser.parse_args()


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


def convert_pdf(pdf_path: Path, output_root: Path) -> dict[str, object]:
    language = detect_language(pdf_path)
    doc_dir = output_root / "pdf2docx" / language / pdf_path.stem
    doc_dir.mkdir(parents=True, exist_ok=True)

    docx_path = doc_dir / f"{pdf_path.stem}_via_pdf2docx.docx"

    converter = Converter(str(pdf_path))
    try:
        converter.convert(str(docx_path))
    finally:
        converter.close()

    return {
        "source_pdf": str(pdf_path),
        "language": language,
        "output_dir": str(doc_dir),
        "docx": str(docx_path),
        "docx_size": docx_path.stat().st_size,
        "status": "ok",
    }


def main() -> None:
    args = parse_args()
    pdf_files = discover_pdf_files(SAMPLES_DIR)
    selected_files = filter_pdf_files(pdf_files, args.sample, args.lang, args.limit)

    if not selected_files:
        raise SystemExit("No matching sample PDFs were found.")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    summary: list[dict[str, object]] = []
    for pdf_path in selected_files:
        try:
            record = convert_pdf(pdf_path, args.output_dir)
        except Exception as exc:
            record = {
                "source_pdf": str(pdf_path),
                "language": detect_language(pdf_path),
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }
        summary.append(record)
        print(json.dumps(record, ensure_ascii=False))

    summary_path = args.output_dir / "pdf2docx" / "summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"summary={summary_path}")


if __name__ == "__main__":
    main()
