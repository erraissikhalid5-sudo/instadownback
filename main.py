"""
Instagram Media Downloader — FastAPI Backend
Supports Reels/Videos and Photos/Carousels via yt-dlp + Instaloader fallback.
Run: uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from app.routers import download, status
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure downloads directory exists on startup
    os.makedirs(settings.DOWNLOAD_DIR, exist_ok=True)
    yield
    # Cleanup logic can go here (e.g., purge old files)


app = FastAPI(
    title="Instagram Media Downloader API",
    description="Download Instagram Reels, Videos, Photos, and Carousels.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — restrict origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve downloaded files statically
app.mount("/files", StaticFiles(directory=settings.DOWNLOAD_DIR), name="files")

# Routers
app.include_router(download.router, prefix="/api/v1", tags=["Download"])
app.include_router(status.router, prefix="/api/v1", tags=["Status"])


@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "message": "Instagram Downloader API is running."}
