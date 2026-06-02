"""
Configuration and environment settings.
Copy .env.example to .env and fill in your values.
"""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Download storage
    DOWNLOAD_DIR: str = os.path.join(os.path.dirname(__file__), "..", "downloads")

    # Instagram credentials (optional — needed for private content / Stories)
    INSTAGRAM_USERNAME: str = ""
    INSTAGRAM_PASSWORD: str = ""

    # Session cookie string (alternative to username/password for yt-dlp)
    # Export via: yt-dlp --cookies-from-browser chrome --cookies cookies.txt
    COOKIES_FILE: str = ""

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # File retention (seconds). 0 = keep forever.
    FILE_TTL_SECONDS: int = 3600

    # Max concurrent downloads
    MAX_CONCURRENT: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
