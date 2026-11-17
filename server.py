import os
import re
import time
import uuid
import shutil
import urllib.request
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import yt_dlp
import mutagen
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC

BASE_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
STATIC_DIR = BASE_DIR / "static"

DOWNLOADS_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

app = FastAPI(title="YouTube to MP3 Converter API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=3)

# In-memory storage for jobs
jobs: Dict[str, Dict[str, Any]] = {}

def clean_youtube_url(url: str) -> str:
    """Extract and normalize canonical YouTube video URL from various formats."""
    url = url.strip()
    # Supports:
    # - https://www.youtube.com/watch?v=VIDEO_ID
    # - https://youtu.be/VIDEO_ID
    # - https://www.youtube.com/shorts/VIDEO_ID
    # - https://m.youtube.com/watch?v=VIDEO_ID
    # - https://music.youtube.com/watch?v=VIDEO_ID
    # - https://www.youtube.com/embed/VIDEO_ID
    pattern = r'(?:https?:\/\/)?(?:www\.|m\.|music\.)?(?:youtube\.com\/(?:watch\?.*?v=|shorts\/|embed\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    if match:
        video_id = match.group(1)
        return f"https://www.youtube.com/watch?v={video_id}"
    return url

def sanitize_filename(name: str) -> str:
    """Sanitize string for safe filesystem usage and HTTP headers."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = re.sub(r'[\s_]+', ' ', clean).strip()
    return clean[:120] if clean else "audio"

def format_duration(seconds: Optional[int]) -> str:
    """Format duration in seconds into readable MM:SS or HH:MM:SS."""
    if not seconds or seconds < 0:
        return "Unknown"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

class InfoRequest(BaseModel):
    url: str

class ConvertRequest(BaseModel):
    url: str
    quality: str = "320" # 128, 192, 256, 320
    title: Optional[str] = None
    artist: Optional[str] = None
    embed_thumbnail: bool = True
    trim_start: Optional[float] = None
    trim_end: Optional[float] = None

@app.post("/api/info")
def get_video_info(req: InfoRequest):
    """Fetch video metadata without downloading the full audio."""
    clean_url = clean_youtube_url(req.url)
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'ios']}},
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            if not info:
                raise HTTPException(status_code=400, detail="Could not extract video metadata.")
            
            # Extract relevant fields
            title = info.get('title') or "Unknown Title"
            author = info.get('uploader') or info.get('channel') or "Unknown Artist"
            duration = info.get('duration')
            thumbnail = info.get('thumbnail') or ""
            video_id = info.get('id') or ""
            view_count = info.get('view_count') or 0
            
            return {
                "success": True,
                "data": {
                    "id": video_id,
                    "url": clean_url,
                    "title": title,
                    "author": author,
                    "duration": duration,
                    "duration_formatted": format_duration(duration),
                    "thumbnail": thumbnail,
                    "view_count": view_count
                }
            }
    except Exception as e:
        error_msg = str(e)
        if "is not a valid URL" in error_msg or "Unsupported URL" in error_msg:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL. Please provide a valid YouTube link.")
        raise HTTPException(status_code=400, detail=f"Failed to fetch video details: {error_msg}")

def run_conversion_job(job_id: str, req: ConvertRequest):
    """Worker task that downloads audio, converts to MP3, and embeds metadata."""
    job = jobs[job_id]
    job['status'] = 'downloading'
    job['progress'] = 10
    job['status_text'] = 'Connecting to YouTube...'

    clean_url = clean_youtube_url(req.url)
    out_base = str(DOWNLOADS_DIR / job_id)
    raw_output = f"{out_base}.%(ext)s"

    def progress_hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes') or 0
            if total > 0:
                pct = 15 + int((downloaded / total) * 55) # 15% to 70%
                job['progress'] = min(pct, 70)
                speed = d.get('_speed_str', '').strip()
                eta = d.get('_eta_str', '').strip()
                status_parts = [f"Downloading audio: {int((downloaded / total) * 100)}%"]
                if speed:
                    status_parts.append(f"at {speed}")
                if eta:
                    status_parts.append(f"ETA {eta}")
                job['status_text'] = " ".join(status_parts)
            else:
                job['progress'] = 30
                job['status_text'] = 'Downloading audio stream...'
        elif d['status'] == 'finished':
            job['progress'] = 75
            job['status'] = 'converting'
            job['status_text'] = f'Encoding {req.quality}kbps MP3 audio with FFmpeg...'

    quality = req.quality if req.quality in ["128", "192", "256", "320"] else "320"

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': raw_output,
        'extractor_args': {'youtube': {'player_client': ['android', 'ios']}},
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': quality,
        }],
        'progress_hooks': [progress_hook],
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            meta = ydl.extract_info(clean_url, download=True)
            if not meta:
                raise Exception("Failed to retrieve video stream.")
            
            video_title = req.title.strip() if req.title and req.title.strip() else (meta.get('title') or "Audio")
            video_artist = req.artist.strip() if req.artist and req.artist.strip() else (meta.get('uploader') or meta.get('channel') or "YouTube")
            thumbnail_url = meta.get('thumbnail') or ""
            duration = meta.get('duration')

        mp3_path = Path(f"{out_base}.mp3")
        if not mp3_path.exists():
            raise Exception("MP3 conversion failed - output file not created.")

        # Trimming support if requested
        if req.trim_start is not None or req.trim_end is not None:
            job['progress'] = 80
            job['status_text'] = 'Trimming audio segment...'
            trimmed_path = Path(f"{out_base}_trimmed.mp3")
            
            ffmpeg_cmd = ["ffmpeg", "-y", "-i", str(mp3_path)]
            if req.trim_start is not None and req.trim_start > 0:
                ffmpeg_cmd.extend(["-ss", str(req.trim_start)])
            if req.trim_end is not None and req.trim_end > 0:
                ffmpeg_cmd.extend(["-to", str(req.trim_end)])
            ffmpeg_cmd.extend(["-c:a", "libmp3lame", "-b:a", f"{quality}k", str(trimmed_path)])
            
            import subprocess
            res = subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if res.returncode == 0 and trimmed_path.exists():
                mp3_path.unlink(missing_ok=True)
                trimmed_path.rename(mp3_path)

        # ID3 Tagging & Album Art
        job['status'] = 'tagging'
        job['progress'] = 88
        job['status_text'] = 'Embedding ID3 metadata & album art...'

        try:
            audio = MP3(str(mp3_path), ID3=ID3)
            try:
                audio.add_tags()
            except Exception:
                pass

            audio.tags.add(TIT2(encoding=3, text=video_title))
            audio.tags.add(TPE1(encoding=3, text=video_artist))
            audio.tags.add(TALB(encoding=3, text="YouTube Audio"))

            if req.embed_thumbnail and thumbnail_url:
                try:
                    thumb_req = urllib.request.Request(
                        thumbnail_url,
                        headers={'User-Agent': 'Mozilla/5.0'}
                    )
                    with urllib.request.urlopen(thumb_req, timeout=8) as resp:
                        img_data = resp.read()
                        mime = 'image/jpeg' if 'jpg' in thumbnail_url or 'jpeg' in thumbnail_url else 'image/png'
                        audio.tags.add(APIC(
                            encoding=3,
                            mime=mime,
                            type=3, # front cover
                            desc='Cover',
                            data=img_data
                        ))
                except Exception as thumb_err:
                    print(f"Thumbnail embed warning: {thumb_err}")

            audio.save()
        except Exception as tag_err:
            print(f"ID3 Tagging warning: {tag_err}")

        # Finalize file details
        safe_title = sanitize_filename(video_title)
        safe_artist = sanitize_filename(video_artist)
        download_filename = f"{safe_artist} - {safe_title}.mp3" if safe_artist and safe_artist != "YouTube" else f"{safe_title}.mp3"
        file_size = mp3_path.stat().st_size

        job['progress'] = 100
        job['status'] = 'completed'
        job['status_text'] = 'Conversion complete! Your MP3 is ready.'
        job['file_path'] = str(mp3_path)
        job['filename'] = download_filename
        job['file_size'] = file_size
        job['file_size_formatted'] = f"{file_size / (1024 * 1024):.2f} MB"
        job['title'] = video_title
        job['artist'] = video_artist
        job['duration'] = duration
        job['duration_formatted'] = format_duration(duration)
        job['thumbnail'] = thumbnail_url
        job['quality'] = f"{quality} kbps"

    except Exception as e:
        job['status'] = 'error'
        job['error'] = str(e)
        job['status_text'] = f"Failed: {str(e)}"
        print(f"Error converting {clean_url}: {e}")

@app.post("/api/convert")
def start_conversion(req: ConvertRequest):
    """Start an asynchronous conversion job."""
    clean_url = clean_youtube_url(req.url)
    job_id = str(uuid.uuid4())
    
    jobs[job_id] = {
        'id': job_id,
        'url': clean_url,
        'status': 'queued',
        'progress': 0,
        'status_text': 'Preparing download request...',
        'created_at': time.time(),
        'error': None,
        'file_path': None,
        'filename': None,
        'file_size': 0,
        'file_size_formatted': '',
        'title': req.title or "Processing...",
        'artist': req.artist or "",
        'quality': req.quality
    }
    
    executor.submit(run_conversion_job, job_id, req)
    return {"success": True, "job_id": job_id}

@app.get("/api/progress/{job_id}")
def get_job_progress(job_id: str):
    """Check status and progress of a conversion job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    return {
        "id": job['id'],
        "status": job['status'],
        "progress": job['progress'],
        "status_text": job['status_text'],
        "error": job.get('error'),
        "filename": job.get('filename'),
        "file_size_formatted": job.get('file_size_formatted'),
        "title": job.get('title'),
        "artist": job.get('artist'),
        "duration_formatted": job.get('duration_formatted'),
        "thumbnail": job.get('thumbnail'),
        "quality": job.get('quality')
    }

@app.api_route("/api/stream/{job_id}", methods=["GET", "HEAD"])
def stream_audio(job_id: str):
    """Stream converted MP3 directly for in-browser playback."""
    if job_id not in jobs or jobs[job_id]['status'] != 'completed':
        raise HTTPException(status_code=404, detail="Audio file not ready or not found")
    
    file_path = jobs[job_id].get('file_path')
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File on disk not found")
    
    return FileResponse(
        path=file_path,
        media_type="audio/mpeg",
        headers={"Accept-Ranges": "bytes"}
    )

@app.api_route("/api/download/{job_id}", methods=["GET", "HEAD"])
def download_audio(job_id: str):
    """Download converted MP3 file with proper filename header."""
    if job_id not in jobs or jobs[job_id]['status'] != 'completed':
        raise HTTPException(status_code=404, detail="File not ready or job not found")
    
    job = jobs[job_id]
    file_path = job.get('file_path')
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File does not exist on disk")
    
    filename = job.get('filename') or "audio.mp3"
    
    # URL encode filename for Content-Disposition header
    from urllib.parse import quote
    encoded_filename = quote(filename)
    
    return FileResponse(
        path=file_path,
        media_type="audio/mpeg",
        filename=filename,
        headers={
            "Content-Disposition": f"attachment; filename=\"{encoded_filename}\"; filename*=UTF-8''{encoded_filename}"
        }
    )

@app.get("/api/history")
def get_conversion_history():
    """Retrieve list of completed conversion jobs."""
    completed = [
        {
            "id": j['id'],
            "title": j.get('title'),
            "artist": j.get('artist'),
            "duration_formatted": j.get('duration_formatted'),
            "thumbnail": j.get('thumbnail'),
            "file_size_formatted": j.get('file_size_formatted'),
            "quality": j.get('quality'),
            "created_at": j.get('created_at'),
            "filename": j.get('filename')
        }
        for j in jobs.values()
        if j['status'] == 'completed' and j.get('file_path') and os.path.exists(j.get('file_path'))
    ]
    # Sort newest first
    completed.sort(key=lambda x: x.get('created_at', 0), reverse=True)
    return {"success": True, "history": completed[:15]}

@app.delete("/api/history/{job_id}")
def delete_conversion(job_id: str):
    """Delete a conversion job and remove its MP3 file."""
    if job_id in jobs:
        file_path = jobs[job_id].get('file_path')
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        del jobs[job_id]
        return {"success": True, "message": "Conversion deleted"}
    raise HTTPException(status_code=404, detail="Job not found")

# Periodic cleanup task for old files (files > 2 hours)
def cleanup_old_files():
    cutoff = time.time() - (2 * 3600)
    for f in DOWNLOADS_DIR.glob("*.mp3"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)
        except Exception:
            pass

@app.on_event("startup")
async def startup_event():
    cleanup_old_files()

# Serve static frontend files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.api_route("/", methods=["GET", "HEAD"])
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")

if __name__ == "__main__":
    import uvicorn
    print("Starting YouTube to MP3 Converter server on http://localhost:8000 ...")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
