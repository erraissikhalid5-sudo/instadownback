"""
yt-dlp based downloader for Instagram Reels, Videos, and Photos.

yt-dlp handles:
  - Reels  (/reel/...)
  - Videos (/tv/...)
  - Single photos and carousels (/p/...)
"""

import yt_dlp
import os
import uuid
import asyncio
from typing import Optional
from pathlib import Path

from app.config import settings
from app.schemas import MediaFile, MediaType


# Map yt-dlp quality labels to format selectors
QUALITY_MAP = {
    "best": "bestvideo+bestaudio/best",
    "720":  "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480":  "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360":  "bestvideo[height<=360]+bestaudio/best[height<=360]",
}


def _build_ydl_opts(job_id: str, quality: str, progress_hook=None) -> dict:
    output_dir = os.path.abspath(settings.DOWNLOAD_DIR)
    os.makedirs(output_dir, exist_ok=True)

    opts: dict = {
        "outtmpl": os.path.join(output_dir, f"{job_id}_%(autonumber)s.%(ext)s"),
        "format": QUALITY_MAP.get(quality, QUALITY_MAP["best"]),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,    # allow carousel (playlist)
        "merge_output_format": "mp4",
        "writethumbnail": False,
        "writeinfojson": False,
    }

    # Attach cookies if configured
    if settings.COOKIES_FILE and os.path.isfile(settings.COOKIES_FILE):
        opts["cookiefile"] = settings.COOKIES_FILE
    elif settings.INSTAGRAM_USERNAME and settings.INSTAGRAM_PASSWORD:
        opts["username"] = settings.INSTAGRAM_USERNAME
        opts["password"] = settings.INSTAGRAM_PASSWORD

    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

    return opts


def _detect_media_type(info: dict) -> MediaType:
    """Detect media type from yt-dlp info dict."""
    entries = info.get("entries")
    if entries and len(entries) > 1:
        return MediaType.carousel
    vcodec = info.get("vcodec", "none")
    acodec = info.get("acodec", "none")
    if vcodec and vcodec != "none":
        return MediaType.video
    if acodec == "none" and vcodec == "none":
        return MediaType.photo
    return MediaType.unknown


def _collect_files(job_id: str, info: dict, base_url: str) -> list[MediaFile]:
    """Scan download dir for files belonging to this job and build MediaFile list."""
    output_dir = Path(settings.DOWNLOAD_DIR)
    matched = sorted(output_dir.glob(f"{job_id}_*"))

    files: list[MediaFile] = []
    entries = info.get("entries") or [info]

    for idx, path in enumerate(matched):
        entry = entries[idx] if idx < len(entries) else info
        media_type = MediaType.video if path.suffix in {".mp4", ".webm", ".mov"} else MediaType.photo
        files.append(
            MediaFile(
                filename=path.name,
                url=f"{base_url}/files/{path.name}",
                media_type=media_type,
                size_bytes=path.stat().st_size,
                width=entry.get("width"),
                height=entry.get("height"),
                duration_secs=entry.get("duration"),
            )
        )
    return files


async def download_with_ytdlp(
    url: str,
    job_id: str,
    quality: str = "best",
    base_url: str = "http://localhost:8000",
    progress_callback=None,
) -> dict:
    """
    Download Instagram media using yt-dlp.

    Returns a dict with keys: files, media_type, caption, author, thumbnail, error.
    """

    result = {
        "files": [],
        "media_type": MediaType.unknown,
        "caption": None,
        "author": None,
        "thumbnail": None,
        "error": None,
    }

    progress_hook_data = {"progress": 0}

    def _hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
            downloaded = d.get("downloaded_bytes", 0)
            pct = int(downloaded / total * 100)
            progress_hook_data["progress"] = pct
            if progress_callback:
                asyncio.get_event_loop().call_soon_threadsafe(
                    progress_callback, pct
                )

    opts = _build_ydl_opts(job_id, quality, progress_hook=_hook)

    try:
        loop = asyncio.get_event_loop()

        def _run():
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return info

        info = await loop.run_in_executor(None, _run)

        if info is None:
            result["error"] = "yt-dlp returned no info — post may be private or deleted."
            return result

        result["media_type"] = _detect_media_type(info)
        result["caption"] = info.get("description") or info.get("title")
        result["author"] = info.get("uploader") or info.get("channel")
        result["thumbnail"] = info.get("thumbnail")
        result["files"] = _collect_files(job_id, info, base_url)

    except yt_dlp.utils.DownloadError as e:
        result["error"] = f"yt-dlp DownloadError: {e}"
    except Exception as e:
        result["error"] = f"yt-dlp unexpected error: {e}"

    return result
