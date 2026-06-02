"""
Status endpoints.

GET /api/v1/health      — liveness check
GET /api/v1/jobs        — list all jobs (dev only)
DELETE /api/v1/jobs     — clear all jobs + downloaded files (dev only)
"""

from fastapi import APIRouter
from app.services.downloader import _jobs
from app.config import settings
import os
import glob

router = APIRouter()


@router.get("/health")
async def health():
    """Liveness / readiness probe."""
    download_dir = os.path.abspath(settings.DOWNLOAD_DIR)
    file_count = len(os.listdir(download_dir)) if os.path.isdir(download_dir) else 0
    return {
        "status": "ok",
        "active_jobs": len(_jobs),
        "download_dir": download_dir,
        "files_on_disk": file_count,
    }


@router.get("/jobs")
async def list_jobs():
    """Return all in-memory jobs. Use for debugging only."""
    return {"count": len(_jobs), "jobs": list(_jobs.values())}


@router.delete("/jobs")
async def clear_jobs():
    """Delete all jobs and purge the downloads directory. Dev/testing only."""
    _jobs.clear()
    download_dir = os.path.abspath(settings.DOWNLOAD_DIR)
    removed = 0
    for f in glob.glob(os.path.join(download_dir, "*")):
        try:
            os.remove(f)
            removed += 1
        except OSError:
            pass
    return {"cleared": True, "files_removed": removed}
