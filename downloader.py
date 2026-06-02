"""
Download orchestrator.

Strategy:
  - "auto"        → try yt-dlp first; fall back to Instaloader on failure
  - "ytdlp"       → yt-dlp only
  - "instaloader" → Instaloader only

Job state is stored in-memory (dict). For production, replace with Redis or a DB.
"""

import uuid
import asyncio
from typing import Optional
from datetime import datetime

from app.schemas import DownloadStatus, MediaType, DownloadResponse, MediaFile
from app.services.ytdlp_service import download_with_ytdlp
from app.services.instaloader_service import download_with_instaloader
from app.config import settings


# ── In-memory job store ────────────────────────────────────────────────────────
# Replace with Redis / SQLite / Postgres for production multi-process deployments.
_jobs: dict[str, dict] = {}
_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT)


def create_job(url: str) -> str:
    job_id = uuid.uuid4().hex
    _jobs[job_id] = {
        "job_id": job_id,
        "status": DownloadStatus.pending,
        "url": url,
        "media_type": MediaType.unknown,
        "files": [],
        "caption": None,
        "author": None,
        "thumbnail": None,
        "tool_used": None,
        "error": None,
        "progress": 0,
        "created_at": datetime.utcnow().isoformat(),
    }
    return job_id


def get_job(job_id: str) -> Optional[dict]:
    return _jobs.get(job_id)


def _update_job(job_id: str, **kwargs):
    if job_id in _jobs:
        _jobs[job_id].update(kwargs)


async def run_download(
    job_id: str,
    url: str,
    quality: str,
    prefer_tool: str,
    base_url: str,
):
    """
    Background task: perform the download and update job state.
    """
    async with _semaphore:
        _update_job(job_id, status=DownloadStatus.processing, progress=5)

        result = None
        tool_used = None

        # ── yt-dlp path ────────────────────────────────────────────────────────
        if prefer_tool in ("auto", "ytdlp"):
            def _progress(pct: int):
                _update_job(job_id, progress=min(pct, 95))

            result = await download_with_ytdlp(
                url=url,
                job_id=job_id,
                quality=quality,
                base_url=base_url,
                progress_callback=_progress,
            )
            if not result["error"]:
                tool_used = "ytdlp"

        # ── Instaloader fallback ───────────────────────────────────────────────
        if prefer_tool == "instaloader" or (prefer_tool == "auto" and result and result["error"]):
            ytdlp_error = result["error"] if result else None
            result = await download_with_instaloader(
                url=url,
                job_id=job_id,
                base_url=base_url,
            )
            if not result["error"]:
                tool_used = "instaloader"
            elif ytdlp_error:
                # Both failed — surface the yt-dlp error as primary
                result["error"] = f"yt-dlp: {ytdlp_error} | Instaloader: {result['error']}"

        # ── Finalise job ───────────────────────────────────────────────────────
        if result and not result["error"] and result["files"]:
            _update_job(
                job_id,
                status=DownloadStatus.done,
                progress=100,
                files=[f.model_dump() for f in result["files"]],
                media_type=result["media_type"],
                caption=result["caption"],
                author=result["author"],
                thumbnail=result["thumbnail"],
                tool_used=tool_used,
                error=None,
            )
        else:
            _update_job(
                job_id,
                status=DownloadStatus.failed,
                progress=0,
                error=result["error"] if result else "Unknown error",
                tool_used=tool_used,
            )


def build_response(job_id: str) -> Optional[DownloadResponse]:
    job = get_job(job_id)
    if job is None:
        return None
    return DownloadResponse(
        job_id=job["job_id"],
        status=job["status"],
        url=job["url"],
        media_type=job["media_type"],
        files=[MediaFile(**f) for f in job["files"]],
        caption=job["caption"],
        author=job["author"],
        thumbnail=job["thumbnail"],
        tool_used=job["tool_used"],
        error=job["error"],
    )
