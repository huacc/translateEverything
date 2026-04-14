from __future__ import annotations

import re
from pathlib import Path

import pypandoc
from markitdown import MarkItDown


SRC_PDF = Path(
    "D:/\u9879\u76ee/\u5f00\u6e90\u9879\u76ee/ontology-scenario/\u6837\u672c/\u4e2d\u6587/AIA_2021_Annual_Report_zh.pdf"
)
OUT_DIR = Path(
    "D:/\u9879\u76ee/\u5f00\u6e90\u9879\u76ee/ontology-scenario/spikes/\u8f6c\u6362"
)


def clean_markdown(markdown_text: str) -> str:
    text = markdown_text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\f", "\n\n\\newpage\n\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    raw_md_path = OUT_DIR / "AIA_2021_Annual_Report_zh.raw.md"
    cleaned_md_path = OUT_DIR / "AIA_2021_Annual_Report_zh.md"
    docx_path = OUT_DIR / "AIA_2021_Annual_Report_zh_from_markdown.docx"

    converter = MarkItDown(enable_plugins=False)
    result = converter.convert(str(SRC_PDF))

    raw_markdown = result.markdown
    cleaned_markdown = clean_markdown(raw_markdown)

    raw_md_path.write_text(raw_markdown, encoding="utf-8")
    cleaned_md_path.write_text(cleaned_markdown, encoding="utf-8")

    pypandoc.convert_file(
        str(cleaned_md_path),
        "docx",
        format="markdown+hard_line_breaks",
        outputfile=str(docx_path),
        extra_args=["--wrap=none"],
    )

    print(f"raw_markdown={raw_md_path}")
    print(f"cleaned_markdown={cleaned_md_path}")
    print(f"docx_from_markdown={docx_path}")


if __name__ == "__main__":
    main()
