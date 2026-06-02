# Instagram Media Downloader — FastAPI Backend

Download Instagram **Reels/Videos** and **Photos/Carousels** via a clean REST API.  
Uses **yt-dlp** as primary engine with **Instaloader** as automatic fallback.

---

## Project Structure

```
instagram_backend/
├── main.py                          # FastAPI app entry point
├── requirements.txt
├── .env.example                     # Copy to .env and fill in values
├── downloads/                       # Media files saved here (auto-created)
└── app/
    ├── config.py                    # Settings from .env
    ├── schemas.py                   # Pydantic request/response models
    ├── routers/
    │   ├── download.py              # POST /download, GET /download/{job_id}
    │   └── status.py                # GET /health, /jobs, DELETE /jobs
    └── services/
        ├── downloader.py            # Job orchestrator (picks tool, tracks state)
        ├── ytdlp_service.py         # yt-dlp implementation
        └── instaloader_service.py   # Instaloader implementation
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — add Instagram credentials for best results
```

### 3. Run the server

```bash
uvicorn main:app --reload --port 8000
```

### 4. Open interactive docs

```
http://localhost:8000/docs
```

---

## API Reference

### POST `/api/v1/download`
Start a download job. Returns immediately with `status: pending`.

**Request body:**
```json
{
  "url": "https://www.instagram.com/reel/ABC123xyz/",
  "quality": "best",
  "prefer_tool": "auto"
}
```

| Field | Values | Default | Notes |
|-------|--------|---------|-------|
| `url` | Instagram post/reel/tv URL | required | Query params stripped automatically |
| `quality` | `best` `720` `480` `360` | `best` | Only affects videos |
| `prefer_tool` | `auto` `ytdlp` `instaloader` | `auto` | `auto` = yt-dlp → Instaloader fallback |

**Response `202 Accepted`:**
```json
{
  "job_id": "a1b2c3d4...",
  "status": "pending",
  "url": "https://www.instagram.com/reel/ABC123xyz/",
  "media_type": "unknown",
  "files": []
}
```

---

### GET `/api/v1/download/{job_id}`
Poll for job result.

**Response when done:**
```json
{
  "job_id": "a1b2c3d4...",
  "status": "done",
  "url": "https://www.instagram.com/reel/ABC123xyz/",
  "media_type": "video",
  "files": [
    {
      "filename": "a1b2c3d4_000001.mp4",
      "url": "http://localhost:8000/files/a1b2c3d4_000001.mp4",
      "media_type": "video",
      "size_bytes": 8423910,
      "width": 1080,
      "height": 1920,
      "duration_secs": 30.0
    }
  ],
  "caption": "Check this out 🔥 #reels",
  "author": "someuser",
  "thumbnail": "https://...",
  "tool_used": "ytdlp"
}
```

**Status values:** `pending` → `processing` → `done` | `failed`

---

### GET `/api/v1/health`
Liveness check.

### GET `/api/v1/jobs`
List all in-memory jobs (dev/debug).

### DELETE `/api/v1/jobs`
Clear all jobs and purge downloaded files (dev/debug).

---

## Tool Selection Logic

```
prefer_tool = "auto"  →  yt-dlp  ──(fails)──▶  Instaloader  ──(fails)──▶  error
prefer_tool = "ytdlp"  →  yt-dlp only
prefer_tool = "instaloader"  →  Instaloader only
```

**yt-dlp** is better for:
- Reels / video content
- No login required for public posts (use cookies for reliability)

**Instaloader** is better for:
- High-res photos
- Carousels (multi-image posts)
- Rich metadata

---

## Authentication

Instagram heavily restricts unauthenticated access. For reliable downloads:

### Option A — Username + Password (`.env`)
```
INSTAGRAM_USERNAME=your_username
INSTAGRAM_PASSWORD=your_password
```

### Option B — Cookies (yt-dlp only)
```bash
yt-dlp --cookies-from-browser chrome --cookies cookies.txt https://www.instagram.com/
```
Then set `COOKIES_FILE=./cookies.txt` in `.env`.

---

## Production Notes

- **Job storage**: the in-memory dict in `downloader.py` is reset on restart.  
  Replace with Redis (`aioredis`) or a database for multi-worker deployments.
- **File cleanup**: implement a background scheduler (e.g. `APScheduler`) to  
  delete files older than `FILE_TTL_SECONDS`.
- **Rate limiting**: add `slowapi` middleware to prevent abuse.
- **Auth**: protect endpoints with an API key header or OAuth.
- **Storage**: for scale, stream files to S3/R2 instead of local disk.
