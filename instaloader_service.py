"""
Instaloader based downloader for Instagram Photos and Carousels.

Instaloader is better than yt-dlp for:
  - High-resolution photos
  - Carousel (sidecar) posts with multiple images
  - Metadata (captions, likes, timestamps)

It requires valid session credentials for most content after 2023.
"""

import instaloader
import os
import re
import asyncio
import shutil
from pathlib import Path
from typing import Optional

from app.config import settings
from app.schemas import MediaFile, MediaType


def _get_loader() -> instaloader.Instaloader:
    """Create and optionally authenticate an Instaloader instance."""
    L = instaloader.Instaloader(
        download_videos=True,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
        dirname_pattern=settings.DOWNLOAD_DIR,
        filename_pattern="{shortcode}_{mediaid}",
    )

    if settings.INSTAGRAM_USERNAME and settings.INSTAGRAM_PASSWORD:
        try:
            L.login(settings.INSTAGRAM_USERNAME, settings.INSTAGRAM_PASSWORD)
        except instaloader.exceptions.BadCredentialsException:
            raise ValueError("Invalid Instagram credentials in .env")
        except instaloader.exceptions.TwoFactorAuthRequiredException:
            raise ValueError(
                "2FA required — log in manually with `instaloader --login <user>` "
                "to save a session file, then set INSTAGRAM_USERNAME only."
            )

    return L


def _shortcode_from_url(url: str) -> str:
    """Extract post shortcode from an Instagram URL."""
    match = re.search(r"instagram\.com/(?:p|reel|tv)/([\w-]+)", url)
    if not match:
        raise ValueError(f"Cannot parse shortcode from URL: {url}")
    return match.group(1)


def _collect_files(shortcode: str, base_url: str) -> list[MediaFile]:
    """Find files downloaded for a given shortcode."""
    output_dir = Path(settings.DOWNLOAD_DIR)
    # Instaloader saves as: <shortcode>_<mediaid>.<ext>
    matched = sorted(output_dir.glob(f"{shortcode}_*"))

    files: list[MediaFile] = []
    for path in matched:
        if path.suffix in {".jpg", ".jpeg", ".png", ".webp"}:
            media_type = MediaType.photo
        elif path.suffix in {".mp4", ".mov", ".webm"}:
            media_type = MediaType.video
        else:
            continue  # skip .json, .txt etc.

        files.append(
            MediaFile(
                filename=path.name,
                url=f"{base_url}/files/{path.name}",
                media_type=media_type,
                size_bytes=path.stat().st_size,
            )
        )
    return files


async def download_with_instaloader(
    url: str,
    job_id: str,
    base_url: str = "http://localhost:8000",
) -> dict:
    """
    Download Instagram media using Instaloader.

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

    try:
        shortcode = _shortcode_from_url(url)
        loop = asyncio.get_event_loop()

        def _run():
            L = _get_loader()
            post = instaloader.Post.from_shortcode(L.context, shortcode)

            # Download all media for the post
            L.download_post(post, target=Path(settings.DOWNLOAD_DIR))

            return {
                "caption": post.caption,
                "author": post.owner_username,
                "is_video": post.is_video,
                "typename": post.typename,  # GraphSidecar = carousel
                "media_count": post.mediacount if hasattr(post, "mediacount") else 1,
            }

        meta = await loop.run_in_executor(None, _run)

        # Determine media type
        typename = meta.get("typename", "")
        if typename == "GraphSidecar":
            result["media_type"] = MediaType.carousel
        elif meta.get("is_video"):
            result["media_type"] = MediaType.video
        else:
            result["media_type"] = MediaType.photo

        result["caption"] = meta.get("caption")
        result["author"] = meta.get("author")
        result["files"] = _collect_files(shortcode, base_url)

    except instaloader.exceptions.LoginRequiredException:
        result["error"] = (
            "Instagram requires login for this content. "
            "Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD in .env"
        )
    except instaloader.exceptions.PrivateProfileNotFollowedException:
        result["error"] = "This account is private and you are not following it."
    except instaloader.exceptions.PostChangedException:
        result["error"] = "Post was deleted or changed during download."
    except ValueError as e:
        result["error"] = str(e)
    except Exception as e:
        result["error"] = f"Instaloader unexpected error: {e}"

    return result
