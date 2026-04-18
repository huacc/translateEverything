"""
AI translation system mock backend.

This mock service is intentionally product-facing:
- accepts uploaded PDFs from the frontend
- stores uploaded files and exposes stable URLs for PDF.js rendering
- returns task/config payloads compatible with the current frontend
- emits SSE events that drive the translation execution page
- maps known AIA sample PDFs to their real counterpart PDFs for review
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fitz
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pypdf import PdfReader


APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parent
SAMPLE_DIRS = {
    "zh": REPO_DIR / "样本" / "中文",
    "en": REPO_DIR / "样本" / "英文",
}
STORAGE_DIR = APP_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
ARTIFACTS_DIR = STORAGE_DIR / "artifacts"
SEED_DIR = STORAGE_DIR / "seed"
PREVIEWS_DIR = STORAGE_DIR / "previews"

for path in (STORAGE_DIR, UPLOADS_DIR, ARTIFACTS_DIR, SEED_DIR, PREVIEWS_DIR):
    path.mkdir(parents=True, exist_ok=True)


app = FastAPI(title="AI Translation System Mock API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/api/v1/files", StaticFiles(directory=str(STORAGE_DIR)), name="files")


CONFIG_PAYLOAD: dict[str, Any] = {
    "languages": [
        {"code": "zh", "name": "中文", "native_name": "中文"},
        {"code": "en", "name": "英文", "native_name": "English"},
    ],
    "glossaries": [
        {
            "id": 1,
            "name": "默认术语库",
            "description": "通用技术与产品术语",
            "term_count": 1250,
            "source_lang": "en",
            "target_lang": "zh",
        },
        {
            "id": 2,
            "name": "金融年报术语库",
            "description": "适用于年报与财务披露场景",
            "term_count": 680,
            "source_lang": "zh",
            "target_lang": "en",
        },
    ],
    "translation_styles": [
        {
            "id": "professional",
            "name": "专业技术",
            "description": "适用于技术文档、产品手册等专业内容",
        },
        {
            "id": "formal",
            "name": "正式商务",
            "description": "适用于合同、协议、商务文件等正式场景",
        },
        {
            "id": "academic",
            "name": "学术论文",
            "description": "适用于论文、研究报告等学术内容",
        },
    ],
}

jobs: dict[int, dict[str, Any]] = {}
job_id_counter = 1


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_public_url(file_path: Path | None) -> str | None:
    if file_path is None:
        return None
    relative = file_path.relative_to(STORAGE_DIR).as_posix()
    return f"/api/v1/files/{relative}"


def public_url_to_storage_path(public_url: str | None) -> Path | None:
    if not public_url:
        return None

    prefix = "/api/v1/files/"
    if not public_url.startswith(prefix):
        raise HTTPException(status_code=400, detail="Unsupported storage URL")

    return STORAGE_DIR / public_url.replace(prefix, "", 1)


def resolve_job_file_path(job: dict[str, Any], kind: str) -> Path:
    if kind not in {"source", "target"}:
        raise HTTPException(status_code=400, detail="kind must be source or target")

    public_url = job["source_file_path"] if kind == "source" else job["target_file_path"]
    if kind == "target" and not public_url:
        raise HTTPException(status_code=409, detail="Target PDF is not available yet")

    storage_path = public_url_to_storage_path(public_url)
    if storage_path is None or not storage_path.exists():
        raise HTTPException(status_code=404, detail="PDF file missing")

    return storage_path


def render_pdf_page_png(file_path: Path, page: int, dpi: int) -> bytes:
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be greater than or equal to 1")

    safe_dpi = max(72, min(dpi, 288))

    try:
        with fitz.open(file_path) as document:
            if page > document.page_count:
                raise HTTPException(status_code=404, detail="page out of range")

            pdf_page = document.load_page(page - 1)
            zoom = safe_dpi / 72
            pixmap = pdf_page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            return pixmap.tobytes("png")
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Failed to render preview: {error}") from error


def get_preview_cache_path(task_id: int, kind: str, page: int, dpi: int) -> Path:
    preview_dir = PREVIEWS_DIR / str(task_id) / kind
    preview_dir.mkdir(parents=True, exist_ok=True)
    return preview_dir / f"page_{page:04d}_{dpi}.png"


def safe_filename(name: str) -> str:
    keep = [char if char.isalnum() or char in ("-", "_", ".") else "_" for char in name]
    return "".join(keep).strip("._") or "document.pdf"


def count_pdf_pages(file_path: Path) -> int:
    try:
        return len(PdfReader(str(file_path)).pages)
    except Exception:
        return 0


def extract_page_excerpt(file_path: Path | None, page_number: int) -> str:
    if file_path is None or not file_path.exists():
        return ""

    try:
        reader = PdfReader(str(file_path))
        page = reader.pages[page_number - 1]
        text = (page.extract_text() or "").replace("\n", " ")
        text = re.sub(r"\s+", " ", text).strip()
    except Exception:
        return ""

    if not text:
        return ""

    if len(text) > 120:
        return f"{text[:120].rstrip()}..."
    return text


def copy_to_storage(source_path: Path, subdir: str, target_name: str | None = None) -> Path:
    target_dir = STORAGE_DIR / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / (target_name or safe_filename(source_path.name))
    shutil.copyfile(source_path, target_path)
    return target_path


def normalize_file_key(file_name: str, source_lang: str) -> str:
    stem = Path(file_name).stem
    suffix = f"_{source_lang}"
    if stem.endswith(suffix):
        return stem[: -len(suffix)]

    if stem.endswith("_zh") or stem.endswith("_en"):
        return stem.rsplit("_", 1)[0]

    return stem


def resolve_sample_pdf(file_name: str, lang: str) -> Path | None:
    file_key = normalize_file_key(file_name, lang)
    candidate = SAMPLE_DIRS[lang] / f"{file_key}_{lang}.pdf"
    if candidate.exists():
        return candidate
    return None


def resolve_target_sample_for_job(job: dict[str, Any]) -> Path | None:
    return resolve_sample_pdf(job["source_file_name"], job["target_lang"])


def build_job(
    *,
    job_id: int,
    source_file_name: str,
    source_file_path: Path,
    source_lang: str,
    target_lang: str,
    status: str,
    stage: str,
    target_file_path: Path | None = None,
    page_count: int = 0,
    total_segments: int = 0,
    completed_segments: int = 0,
    failed_segments: int = 0,
    progress_percent: float = 0.0,
    glossary_id: int | None = None,
    translation_style: str = "professional",
    enable_quality_check: bool = True,
    critical_issue_count: int = 0,
    warning_issue_count: int = 0,
    info_issue_count: int = 0,
    error_message: str | None = None,
    created_at: str | None = None,
    updated_at: str | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
) -> dict[str, Any]:
    created = created_at or now_iso()
    updated = updated_at or created
    return {
        "id": job_id,
        "source_file_name": source_file_name,
        "source_file_path": to_public_url(source_file_path),
        "target_file_path": to_public_url(target_file_path),
        "source_lang": source_lang,
        "target_lang": target_lang,
        "source_format": "pdf",
        "session_id": None,
        "task_run_id": None,
        "current_prompt_bundle_id": job_id,
        "status": status,
        "stage": stage,
        "page_count": page_count,
        "total_segments": total_segments,
        "completed_segments": completed_segments,
        "failed_segments": failed_segments,
        "progress_percent": progress_percent,
        "document_summary": {
            "title": Path(source_file_name).stem,
            "page_count": page_count,
        },
        "translation_notes": [],
        "task_prompt_text": None,
        "options": {
            "enable_quality_check": enable_quality_check,
            "translation_style": translation_style,
            "glossary_id": glossary_id,
        },
        "quality_issue_counts": {
            "critical": critical_issue_count,
            "warning": warning_issue_count,
            "info": info_issue_count,
        },
        "critical_issue_count": critical_issue_count,
        "warning_issue_count": warning_issue_count,
        "info_issue_count": info_issue_count,
        "export_blocked": critical_issue_count > 0,
        "export_status": "blocked" if critical_issue_count > 0 else "ready",
        "artifact_available": target_file_path is not None,
        "error_message": error_message,
        "created_at": created,
        "updated_at": updated,
        "started_at": started_at,
        "completed_at": completed_at,
    }


def create_seed_job(
    job_id: int,
    *,
    source_file_name: str,
    source_lang: str,
    target_lang: str,
    status: str,
    stage: str,
    target_ready: bool,
    translation_style: str = "professional",
    enable_quality_check: bool = True,
    completed_segments: int = 0,
    failed_segments: int = 0,
    progress_percent: float = 0.0,
    critical_issue_count: int = 0,
    warning_issue_count: int = 0,
    info_issue_count: int = 0,
    error_message: str | None = None,
) -> dict[str, Any]:
    source_sample = resolve_sample_pdf(source_file_name, source_lang)
    if source_sample is None:
        raise FileNotFoundError(f"Seed source sample missing: {source_file_name}")

    target_sample = resolve_sample_pdf(source_file_name, target_lang)
    if target_ready and target_sample is None:
        raise FileNotFoundError(f"Seed target sample missing for: {source_file_name}")

    source_storage = copy_to_storage(source_sample, "seed", source_file_name)
    target_storage = (
        copy_to_storage(
            target_sample,
            "seed",
            f"{normalize_file_key(source_file_name, source_lang)}_{target_lang}.pdf",
        )
        if target_ready and target_sample
        else None
    )

    source_pages = count_pdf_pages(source_storage)
    target_pages = count_pdf_pages(target_storage) if target_storage else 0
    page_count = max(source_pages, target_pages, 1)
    total_segments = max(page_count * 6, 12)

    started_at = now_iso() if status in {"in_progress", "completed", "failed"} else None
    completed_at = now_iso() if status == "completed" else None

    return build_job(
        job_id=job_id,
        source_file_name=source_file_name,
        source_file_path=source_storage,
        target_file_path=target_storage,
        source_lang=source_lang,
        target_lang=target_lang,
        status=status,
        stage=stage,
        page_count=page_count,
        total_segments=total_segments,
        completed_segments=completed_segments,
        failed_segments=failed_segments,
        progress_percent=progress_percent,
        translation_style=translation_style,
        enable_quality_check=enable_quality_check,
        critical_issue_count=critical_issue_count,
        warning_issue_count=warning_issue_count,
        info_issue_count=info_issue_count,
        error_message=error_message,
        started_at=started_at,
        completed_at=completed_at,
    )


def init_seed_jobs() -> None:
    global jobs, job_id_counter

    jobs = {
        1: create_seed_job(
            1,
            source_file_name="AIA_2023_Annual_Report_zh.pdf",
            source_lang="zh",
            target_lang="en",
            status="in_progress",
            stage="translating",
            target_ready=False,
            translation_style="formal",
            completed_segments=720,
            progress_percent=38.0,
        ),
        2: create_seed_job(
            2,
            source_file_name="AIA_2023_Annual_Report_zh.pdf",
            source_lang="zh",
            target_lang="en",
            status="completed",
            stage="completed",
            target_ready=True,
            translation_style="formal",
            completed_segments=max(count_pdf_pages(resolve_sample_pdf("AIA_2023_Annual_Report_zh.pdf", "zh")), 1) * 6,
            progress_percent=100.0,
            warning_issue_count=2,
            info_issue_count=3,
        ),
        3: create_seed_job(
            3,
            source_file_name="AIA_2022_Annual_Report_zh.pdf",
            source_lang="zh",
            target_lang="en",
            status="completed",
            stage="completed",
            target_ready=True,
            translation_style="professional",
            completed_segments=max(count_pdf_pages(resolve_sample_pdf("AIA_2022_Annual_Report_zh.pdf", "zh")), 1) * 6,
            progress_percent=100.0,
            info_issue_count=1,
        ),
    }
    job_id_counter = 4


def ensure_job(task_id: int) -> dict[str, Any]:
    job = jobs.get(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="Task not found")
    return job


def build_artifact_for_job(job: dict[str, Any]) -> None:
    if job["target_file_path"]:
        return

    source_url = job["source_file_path"]
    if not source_url:
        return

    artifact_name = f"task_{job['id']}_translated.pdf"
    artifact_path = ARTIFACTS_DIR / artifact_name
    target_sample = resolve_target_sample_for_job(job)

    if target_sample and target_sample.exists():
        shutil.copyfile(target_sample, artifact_path)
    else:
        source_path = STORAGE_DIR / source_url.replace("/api/v1/files/", "", 1)
        shutil.copyfile(source_path, artifact_path)

    job["target_file_path"] = to_public_url(artifact_path)
    job["artifact_available"] = True


init_seed_jobs()


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "AI Translation System Mock API", "version": "3.0.0"}


@app.get("/api/v1/config")
async def get_config() -> dict[str, Any]:
    return CONFIG_PAYLOAD


@app.get("/api/v1/translations")
async def list_translations() -> dict[str, list[dict[str, Any]]]:
    ordered = sorted(jobs.values(), key=lambda item: item["id"], reverse=True)
    return {"jobs": ordered}


@app.get("/api/v1/translations/{task_id}")
async def get_translation(task_id: int) -> dict[str, dict[str, Any]]:
    return {"job": ensure_job(task_id)}


@app.post("/api/v1/translations/upload")
async def upload_translation(
    file: UploadFile = File(...),
    source_lang: str = Form(...),
    target_lang: str = Form(...),
    glossary_id: int | None = Form(default=None),
    translation_style: str = Form(default="professional"),
    enable_quality_check: bool = Form(default=True),
) -> dict[str, dict[str, Any]]:
    global job_id_counter

    suffix = Path(file.filename or "document.pdf").suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(status_code=400, detail="当前 MVP 仅支持 PDF 上传")

    job_id = job_id_counter
    job_id_counter += 1

    filename = safe_filename(file.filename or f"task_{job_id}.pdf")
    upload_path = UPLOADS_DIR / f"{job_id}_{filename}"

    with upload_path.open("wb") as target:
        shutil.copyfileobj(file.file, target)

    page_count = count_pdf_pages(upload_path)
    total_segments = max(page_count * 6, 12)

    job = build_job(
        job_id=job_id,
        source_file_name=file.filename or filename,
        source_file_path=upload_path,
        source_lang=source_lang,
        target_lang=target_lang,
        status="pending",
        stage="queued",
        page_count=page_count,
        total_segments=total_segments,
        glossary_id=glossary_id,
        translation_style=translation_style,
        enable_quality_check=enable_quality_check,
    )
    jobs[job_id] = job
    return {"job": job}


@app.post("/api/v1/translations/{task_id}/pause")
async def pause_translation(task_id: int) -> dict[str, dict[str, Any]]:
    job = ensure_job(task_id)
    job["status"] = "paused"
    job["updated_at"] = now_iso()
    return {"job": job}


@app.post("/api/v1/translations/{task_id}/resume")
async def resume_translation(task_id: int) -> dict[str, dict[str, Any]]:
    job = ensure_job(task_id)
    if job["status"] == "completed":
        return {"job": job}

    job["status"] = "in_progress"
    if job["stage"] == "queued":
        job["stage"] = "analyzing"
    job["updated_at"] = now_iso()
    job["started_at"] = job["started_at"] or now_iso()
    return {"job": job}


@app.post("/api/v1/translations/{task_id}/cancel")
async def cancel_translation(task_id: int) -> dict[str, dict[str, Any]]:
    job = ensure_job(task_id)
    job["status"] = "cancelled"
    job["stage"] = "failed"
    job["updated_at"] = now_iso()
    job["error_message"] = "任务已被用户取消"
    return {"job": job}


@app.delete("/api/v1/translations/{task_id}")
async def delete_translation(task_id: int) -> dict[str, bool]:
    ensure_job(task_id)
    del jobs[task_id]
    return {"ok": True}


@app.get("/api/v1/translations/{task_id}/artifact")
async def download_artifact(task_id: int) -> FileResponse:
    job = ensure_job(task_id)
    if not job["target_file_path"]:
        raise HTTPException(status_code=409, detail="Artifact not available")

    artifact_path = public_url_to_storage_path(job["target_file_path"])
    if artifact_path is None:
        raise HTTPException(status_code=404, detail="Artifact file missing")
    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail="Artifact file missing")

    return FileResponse(
        path=str(artifact_path),
        media_type="application/pdf",
        filename=f"{Path(job['source_file_name']).stem}_translated.pdf",
    )


@app.get("/api/v1/translations/{task_id}/preview")
async def get_translation_preview(
    task_id: int,
    kind: str = "source",
    page: int = 1,
    dpi: int = 144,
) -> FileResponse:
    job = ensure_job(task_id)
    file_path = resolve_job_file_path(job, kind)
    cache_path = get_preview_cache_path(task_id, kind, page, dpi)

    if not cache_path.exists() or cache_path.stat().st_mtime < file_path.stat().st_mtime:
        cache_path.write_bytes(render_pdf_page_png(file_path, page=page, dpi=dpi))

    return FileResponse(
        path=str(cache_path),
        media_type="image/png",
        filename=cache_path.name,
    )


@app.get("/api/v1/translations/{task_id}/stream")
async def translation_stream(task_id: int) -> StreamingResponse:
    job = ensure_job(task_id)

    async def event_generator():
        if job["status"] == "completed":
            payload = {
                "type": "task_completed",
                "data": {
                    "taskId": str(task_id),
                    "status": "completed",
                    "message": "任务已经完成",
                },
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            return

        if job["status"] == "cancelled":
            payload = {
                "type": "error",
                "data": {
                    "taskId": str(task_id),
                    "status": "failed",
                    "message": "任务已取消",
                },
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            return

        total_pages = max(job["page_count"], 1)
        total_segments = max(job["total_segments"], total_pages * 6)
        simulated_steps = min(total_pages, 8)
        target_sample = resolve_target_sample_for_job(job)

        job["status"] = "in_progress"
        job["stage"] = "analyzing"
        job["started_at"] = job["started_at"] or now_iso()
        job["updated_at"] = now_iso()

        logs = [
            ("analyzing", "parse_document", "正在解析 PDF 页面结构"),
            ("analyzing", "collect_terms", "正在提取术语和关键上下文"),
            ("translating", "build_prompt", "正在构建逐页翻译上下文"),
        ]

        for stage, step, message in logs:
            job["stage"] = stage
            event = {
                "type": "execution_log",
                "data": {
                    "stage": stage,
                    "step": step,
                    "status": "completed",
                    "message": message,
                    "timestamp": now_iso(),
                },
            }
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.4)

        for step_index in range(1, simulated_steps + 1):
            if job["status"] == "paused":
                while job["status"] == "paused":
                    await asyncio.sleep(0.2)

            if job["status"] == "cancelled":
                break

            job["stage"] = "translating"
            current_page = min(
                total_pages,
                max(1, round((step_index / simulated_steps) * total_pages)),
            )
            completed_segments = min(
                total_segments,
                round((step_index / simulated_steps) * total_segments),
            )
            progress = round((step_index / simulated_steps) * 92, 2)

            job["completed_segments"] = completed_segments
            job["progress_percent"] = progress
            job["updated_at"] = now_iso()

            excerpt = extract_page_excerpt(target_sample, current_page)
            chunk_content = excerpt or f"第 {current_page} 页已完成模拟翻译。"

            log_event = {
                "type": "execution_log",
                "data": {
                    "stage": "translating",
                    "step": f"page_{current_page}",
                    "status": "in_progress",
                    "message": f"正在处理第 {current_page} / {total_pages} 页",
                    "timestamp": now_iso(),
                },
            }
            progress_event = {
                "type": "progress",
                "data": {
                    "currentPage": current_page,
                    "totalPages": total_pages,
                    "percentage": progress,
                },
            }
            chunk_event = {
                "type": "translation_chunk",
                "data": {
                    "pageNum": current_page,
                    "blockId": f"p{current_page}_summary",
                    "content": chunk_content,
                    "isComplete": True,
                },
            }

            for payload in (log_event, progress_event, chunk_event):
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.4)

        if job["status"] == "cancelled":
            payload = {
                "type": "error",
                "data": {
                    "taskId": str(task_id),
                    "status": "failed",
                    "message": "任务已取消",
                },
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            return

        job["stage"] = "rendering"
        render_event = {
            "type": "execution_log",
            "data": {
                "stage": "rendering",
                "step": "build_artifact",
                "status": "in_progress",
                "message": "正在生成译后 PDF",
                "timestamp": now_iso(),
            },
        }
        yield f"data: {json.dumps(render_event, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.5)

        build_artifact_for_job(job)
        job["status"] = "completed"
        job["stage"] = "completed"
        job["progress_percent"] = 100.0
        job["completed_segments"] = total_segments
        job["completed_at"] = now_iso()
        job["updated_at"] = now_iso()

        progress_event = {
            "type": "progress",
            "data": {
                "currentPage": total_pages,
                "totalPages": total_pages,
                "percentage": 100,
            },
        }
        complete_event = {
            "type": "task_completed",
            "data": {
                "taskId": str(task_id),
                "status": "completed",
                "message": "翻译完成，可以进入对比审校",
            },
        }

        yield f"data: {json.dumps(progress_event, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps(complete_event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
