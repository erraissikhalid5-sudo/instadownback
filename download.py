"""
Download endpoints.

POST  /api/v1/download          — start a download job (async)
GET   /api/v1/download/{job_id} — poll job result
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from app.schemas import DownloadRequest, DownloadResponse
from app.services import downloader

router = APIRouter()


@router.post("/download", response_model=DownloadResponse, status_code=202)
async def start_download(
    body: DownloadRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    """
    Kick off an async download job.

    Returns immediately with `status: pending` and a `job_id`.
    Poll `GET /api/v1/download/{job_id}` to get the final result.

    **url** — Instagram post/reel/tv URL (query params stripped automatically)  
    **quality** — `best` | `720` | `480` | `360` (only affects videos)  
    **prefer_tool** — `auto` | `ytdlp` | `instaloader`
    """
    job_id = downloader.create_job(body.url)

    # Build a base_url so returned file URLs are absolute
    base_url = str(request.base_url).rstrip("/")

    background_tasks.add_task(
        downloader.run_download,
        job_id=job_id,
        url=body.url,
        quality=body.quality or "best",
        prefer_tool=body.prefer_tool or "auto",
        base_url=base_url,
    )

    return downloader.build_response(job_id)


@router.get("/download/{job_id}", response_model=DownloadResponse)
async def get_download(job_id: str):
    """
    Retrieve the status and result of a download job.

    - `status: pending`     — queued, not yet started  
    - `status: processing`  — in progress  
    - `status: done`        — files ready in `files[]`  
    - `status: failed`      — see `error` field  
    """
    response = downloader.build_response(job_id)
    if response is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return response
