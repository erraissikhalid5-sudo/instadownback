"""
Pydantic models for request validation and response serialization.
"""

from pydantic import BaseModel, HttpUrl, field_validator
from typing import List, Optional
from enum import Enum
import re


class MediaType(str, Enum):
    video = "video"
    photo = "photo"
    carousel = "carousel"
    unknown = "unknown"


class DownloadStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


# ── Requests ──────────────────────────────────────────────────────────────────

class DownloadRequest(BaseModel):
    url: str
    quality: Optional[str] = "best"          # "best" | "720" | "480" | "360"
    prefer_tool: Optional[str] = "auto"       # "auto" | "ytdlp" | "instaloader"

    @field_validator("url")
    @classmethod
    def validate_instagram_url(cls, v: str) -> str:
        pattern = r"https?://(www\.)?instagram\.com/(p|reel|tv)/[\w-]+"
        if not re.match(pattern, v):
            raise ValueError(
                "URL must be a valid Instagram post, reel, or TV URL. "
                "Example: https://www.instagram.com/reel/ABC123/"
            )
        return v.strip().split("?")[0]  # strip query params


# ── Responses ─────────────────────────────────────────────────────────────────

class MediaFile(BaseModel):
    filename: str
    url: str                  # public URL to download the file
    media_type: MediaType
    size_bytes: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration_secs: Optional[float] = None    # for videos


class DownloadResponse(BaseModel):
    job_id: str
    status: DownloadStatus
    url: str                  # original Instagram URL
    media_type: MediaType
    files: List[MediaFile] = []
    thumbnail: Optional[str] = None
    caption: Optional[str] = None
    author: Optional[str] = None
    tool_used: Optional[str] = None          # "ytdlp" | "instaloader"
    error: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: DownloadStatus
    progress: Optional[int] = None           # 0-100
    error: Optional[str] = None
